# 网页访问事件与流量来源上下文

> **非任务大类**。查询 / 看板 / 异常排查涉及官网、网站浏览量、WebApp 访问、campaign、UTM、referrer、网站下载或 Onboarding 时，先读本文件。**网站页面访问与插件网页翻译是不同业务**：前者主要是 `official_page_view`，后者是 `translate_page`。
>
> 整理日期：2026-11-10。依据两个本地仓库的历史文档与 SQL；**本次未连接数据库、未核验现网埋点或 TASK 状态**。下面的字段映射有事件和时间范围；查数前须短窗核对。本文保留必要定义，DB_agent 单独克隆后也可阅读，不依赖另一个仓库才能理解口径。

## 1. 开查先定什么

先用一两句话写明：时间窗与时区、网站/域名/路径、PV 还是 UV、访客标识、是否限某 campaign，以及来源是「访问行携带」还是「首次/末次触达归因」。

- 「网站浏览量」若指 PV，按页面浏览事件次数；「访问人数」若指 UV，按已声明的网页访客标识去重。**不能默认用有插件的设备数代表全站访客**。
- 官网首页、整个网站、WebApp 功能页是不同范围。首页历史过滤为 `site_host IN ('immersivetranslate.com', 'www.immersivetranslate.com') AND trigger='/'`；不能直接套到全部域名和历史版本。
- 默认北京自然日（UTC+8），按任务确认。`created_ts` 用 UTC 常量半开区间过滤，日分组才用 `DATE(DATE_ADD(HOUR,8,created_ts))`；例如北京 2026-05-18 对应 UTC `[2026-05-17 16:00:00, 2026-05-18 16:00:00)`。禁止在 WHERE 对时间列套函数。
- **默认仍只查 `immdata`**。网页事件本身在 `immdata.user_behaviour`；本文介绍 `webdata.*` 是为了交代已有加工口径，**不自动授权查询其它 schema**。只有用户明确要求该范围及用途后，才可只读核验和使用 `webdata`。

## 2. 事件范围与名称差异

| 事件 | 历史文档中的含义 | 使用前注意 |
|------|------------------|------------|
| `official_page_view` | 官网及 WebApp 的页面访问 | 用 `site_host` + `trigger` / URL 区分页面，不等于实际执行翻译 |
| `official_download_click` | `webapp.md` 中的下载按钮点击 | 该文档的清洗 SQL 只收此名与 `official_page_view` |
| `official_download_extension_click` | 首页 AB 文档与 T063 中的插件下载点击 | 与上一名称存在文档差异；未确认是否改名、并存及各自生效时间，不能直接视为别名相加 |
| `onboarding_page_view` | 新手引导页面访问 | 有独立字段映射和 2026-06-05～06-10 格式异常，见第 8 节 |
| `pricing_purchase_btn_click` | 购买按钮点击；Onboarding 用 trigger 指定路径 | 点击不等于订单或成功付费；其它页面也可能使用该事件 |

下载率分析先按目标短窗核对两种下载事件的出现范围、字段样本和数量，再确定事件集合与去重规则。分子是点击次数还是点击访客数，必须与 PV/UV 分母配套；不把点击数称为安装成功数。

## 3. 官网访问字段字典

以下映射来自 `official_page_view` 的历史说明；**不能套到其它事件**。旧下载事件多数沿用访问字段，但下载专用字段另见下表。

| 原始字段（`immdata.user_behaviour`） | 网页含义 / 清洗别名 | 边界 |
|----------------------------------------|----------------------|------|
| `created_ts` | 上报时间 | 日粒度按 UTC+8 转换；先过滤裸列 |
| `site_host` | 当前页面域名 | 不等于来源域名 |
| `trigger` | 访问页面路径 | 如 `/`、`/document`；须核对语言前缀、尾斜杠等实际值 |
| `ex_char_arg1` | 完整页面 URL → `page_url` | 可核对 UTM、路径和语言，不应直接假设 URL 参数与落表字段完全一致 |
| `ex_char_arg2` | `document.referrer` 完整 URL → `referrer_url` | 与 UTM 来源不同 |
| `install_from` | referrer 域名 → `referrer_host` | 在网页事件里不是插件安装渠道；清洗规则也识别历史渠道标记，见第 5 节 |
| `campaign` | 活动标记，对应历史文档中的 `utm_campaign` | 是当前事件携带值，不自动代表访客首次获客或订单归因 |
| `ex_char_arg4` | `utm_source` → `traffic_source` / 归因表 `source` | 例如 `extension`；不是 `source_language` |
| `ex_char_arg5` | `utm_medium` → `traffic_medium` / 归因表 `medium` | 例如 `onboarding` |
| `ex_char_arg3` | 浏览器指纹 → 旧清洗表 `web_user_id` | 旧清洗 SQL 过滤空指纹；该值不等于账号或插件设备 |
| `device_id` | 安装插件且可注入时上报插件设备 ID | 无插件访客可为空；过滤空值会改变全站流量分母 |
| `ex_int_arg1` | 登录用户的 `user_id` → `login_user_id` | 匿名可为空；不要要求登录才计页面访问 |
| `ex_char_arg6` | 历史定义：登录用户注册时间 | 不等于网页首访时间 |
| `ex_int_arg2` | 历史定义：试用用户标志（1） | 不是试用订单，更不是付费凭据 |
| `install_day` / `is_new_user_today` | 历史网页定义：首次访问日 / 是否同日 | 不能套插件「新装」解释，也不等于新注册账号 |
| `ab_group` | 网站 AB 分组 | 网站实验按上线日期与网页分组核对；不自动套插件 `ab_tag` 或插件版本限制 |
| `ab_tag` / `version` | 可能来自已安装插件 | 空值不能作为剔除匿名网页流量的理由 |
| `interface_language` | 页面界面语言 | 不是设备母语或 IP 国家；按界面语言拆分时须明确命名 |
| `user_type` | 历史定义：默认 free，登录时传会员类型 | 单靠此值不能证明账号已注册或已付费 |
| `browser_name` / `os_name` / `platform_type` | 访问环境 | 按网页事件样本核验大小写与异常值；机器人过滤需单独定义 |
| `real_geo` | 访问时 IP 地区 | 不是母语/国籍 |

下载事件历史专用字段：`ex_char_arg7` = 按钮类型（如 zip/chrome/edge），`ex_char_arg8` = 下载目标 URL，`ex_int_arg3` = 是否由 URL 参数直接下载（1）。

**同名扩展字段存在事件/时间差异**：T063（2026-10-10）记录 `official_page_view.ex_char_arg8` 为身份类型（`fingerprint` / `device_id` / `first_party`），`ex_char_arg9` 为对应身份值；这与旧下载事件的 arg8 含义不同。不得把 arg8 在所有网页事件中固定解读为下载 URL，也不得在未核验的历史时段默认使用 arg8/arg9。T063 不是完整的字段变更记录，不能据此推断精确上线日期或全量覆盖率。

## 4. PV、UV 与身份覆盖

- **PV**：限定目标页面浏览事件、域名/路径和时间后，按同一去重口径计事件行数。原始上报行数与清洗后事件数应分别标明；有重复上报证据才制定去重，不能把 UV 当 PV。
- **旧网页 UV**：历史实现为 `COUNT(DISTINCT NULLIF(ex_char_arg3,''))`（清洗层为 `web_user_id`）。空指纹行不进入 UV，但仍需报告其行数/占比；这个指标应叫「指纹口径 UV」，不是精确自然人数。
- **身份类型 UV**：若目标时段验证 arg8/arg9 可用，可单独使用 `(身份类型, 身份值)`，但必须说明与旧指纹 UV 的差异。同一访客可能有多种身份，不能未经桥接就称为跨身份去重人数；禁止随意 `COALESCE(userid, device_id, fingerprint)` 后当作统一用户。
- **设备 / 登录 UV**：分别是非空 `device_id`、非空登录 ID 的子集指标；不能过滤后仍称「网站全部 UV」。不要 INNER JOIN `imt_deviceinfo` 或账号表来决定谁算网页访客。
- 日 UV 不能直接相加得到周/月 UV；同一访客可以访问多个 campaign/来源，分组 UV 之和也不一定等于整体 UV。
- 网站 PV / UV 是访问描述指标。涉及订单转化时另按 P018 确定账号/设备主体与可关联范围；不要为了套通用转化规则而丢掉匿名页面访问，也不要把无法关联的匿名访客算作「未转化」。

T063 的既有观察：官网指纹无法直接连到插件新装，因其抽查的 `init_page_daily` 不带官网指纹字段；纯指纹访客缺少共同关联键。后续分析须验证目标时段的桥接能力，明确可关联覆盖率。不能根据一次历史任务断言永远无法关联，也不能默认已经打通。

## 5. campaign 与来源归因

### 5.1 三种不同的问题

| 问题 | 取数对象 | 解释 |
|------|----------|------|
| 某 campaign 带来多少网站访问 | 网页事件行上的 `campaign`、`ex_char_arg4/5`，必要时核对 URL | 得到「携带该标记的访问 PV / UV」，不是全部实际触达 |
| 新访客最初从哪里来 | 网页首访历史 + 已声明的首次触达规则 | 不能只取窗口内最早一行就称历史首次获客 |
| 哪个渠道带来付费 | 可关联的访客/设备/账号 + 订单，或已验证的订单来源快照 | 须明确身份覆盖、归因窗与首次/末次触达；不是网页来源字段直接求和 |

例：`source=extension`、`medium=onboarding`、`campaign=onboarding_not_upgrade` 的历史网页过滤，对应 `ex_char_arg4='extension' AND ex_char_arg5='onboarding' AND campaign='onboarding_not_upgrade'`。只按 `campaign` 过滤与同时限定三个字段，是不同人群。

`imt_campaigninfo` 是设备侧归因记录，`imt_deviceinfo` 上的 UTM 是设备档案，`imt_subscriptionordersource` 是下单来源快照；**都不是全站访问日志**。查网页 campaign 流量先看行为事件，不能先用这些表圈设备再统计流量。T063 两条校园活动链上曾出现业务归因表漏记、事件 campaign 未延续到后续插件行为的情况；这是该任务的证据，不能外推成所有 campaign 都失效或都完整。

### 5.2 历史 WebApp 来源分组

`webapp.md` 的 `traffic_group` 按以下 CASE 顺序命中，属于**历史加工规则**：

1. referrer 域名匹配沉浸式翻译 `.com` / `.cn` → `immersivetranslate`（站内/自有站点来源）。
2. source 或 medium 为 `extension`，或 referrer 标记为 `chrome_store`、`firefox_store`、`safari`、`edge_store`、`chrome_zip`、`dev`、`official_userscript` → `extension`。
3. `accounts.google.com`、`open.weixin.qq.com`、`checkout.stripe.com` → `system`（登录/支付回跳）。
4. referrer 匹配 Google / Bing / Baidu / DuckDuckGo / Yahoo / Sogou / SM / Yandex / SO → `search_engine`，另记 `search_engine_name`。
5. referrer URL 为空 → `direct`；其余 → `other`。

优先级会影响分类；不能打乱后仍称同一口径。旧 SQL 用域名字符串模糊匹配，并非可靠的域名解析器；新增规则需标明版本，核验误分类。`direct` 在这里仅表示 referrer 为空，不证明用户手动输入网址；`search_engine` 也不能单凭 referrer 区分付费/自然搜索。UTM 与 referrer 是两组证据，需保留交叉对照，不要互相覆盖后丢失原值。

### 5.3 历史新用户归因

旧实现的 `dim_web_user_first_seen` 是从已入库、非空指纹的 `dwd_webappdata` 求 `MIN(dt)`；源文档记载 2026-03-05 上线、03-06 起较完整，**最早可见访问不保证是真实首次访问**。

新用户来源表 / 营销归因表将 `dws_webapp_user_day` 限到首访日，再按 `web_user_id, dt` 排序取最早一行。该 DWS 只保留功能页，因此应解释为「可见首访日中最早的已收录功能页触达」，不自动等于全网站落地页首次触达或末次点击归因。旧 SQL 仅 `ORDER BY created_ts`；同一时间多条不同来源可能无唯一决胜键，复现时需核验并说明。

## 6. 选表与现有加工链路

| 表 / 层 | 历史用途 | 使用边界 |
|---------|----------|----------|
| `immdata.user_behaviour` | 网页原始事件与 campaign/source/medium/referrer | 本仓默认范围；必须限时间+事件。适合核对与小窗查询，大窗/看板遵守 P022 |
| `immdata.imm_official_pv_click_by_utf8_day` | 已记录结构含 `dt`、`abtest`、`browser_name`、`os_name`、`uv`、`click` | 当前表文档来源/口径待补；未记录 campaign/source/medium 字段，不能直接回答 campaign 流量 |
| `webdata.dwd_webappdata` | 原始网页字段清洗别名，保留页面/来源/身份/下载信息 | 旧 SQL 只收 `official_page_view`、`official_download_click`，且排除空 arg3；不能当作所有网页流量的完整镜像 |
| `webdata.dim_web_user_first_seen` | 已入库指纹的最早可见访问日 | 受历史起点、事件集合、空指纹过滤影响 |
| `webdata.dws_webapp_user_day` | 访问行增加功能/版本/语言/来源分组 | 名字含 day 但旧 SQL `SELECT * FROM base` 未按用户日去重；且只保留 file/text/video/image 功能页，不能覆盖首页或全站 |
| `webdata.ads_webapp_active` | WebApp 功能页 DAU / 滚动 7 日 WAU / 滚动 30 日 MAU | 去重主体是旧 `web_user_id`；不是 PV，也不是自然周/月 UV |
| `webdata.ads_webapp_new_user` | 可见首访日的新访客，滚动 1/7/30 日指标 | 不等于插件新装或账号新注册 |
| `webdata.ads_webapp_new_user_source` | 上述新访客的历史首次触达来源分组 | 不能当所有访问流量的来源分布 |
| `webdata.ads_webapp_new_user_attribution` | 上述新访客的 campaign/source/medium 归因 | 不是所有访问、订单或收入归因 |
| `webdata.ads_webapp_feature_dau` | T012 使用的 document 功能 DAU | 本仓只存有使用片段，不能据此推断完整上游定义 |
| `webdata.dwd_onboarding_event` | Onboarding 访问与购买点击清洗 | 有单独字段与历史格式处理，见第 8 节 |

使用 `webdata` 前须已获范围授权，再只读核验表存在、字段、粒度、事件范围、覆盖率与数据水位。历史脚本中的建表/TASK 定义不证明已部署或仍在运行。旧增量清洗脚本按时间、事件名、指纹、URL、trigger 形成业务键去重，并用 2 小时回看窗口；复现 PV 时应核对实际去重和迟到数据覆盖，不能默认等同原始行数。

ADS 中可同时存在具体维度和 `all` 汇总行；选择一个明确切片，不要把所有行加总。单日 UV 可用于单日指标；周/月 UV 应直接读对应去重窗口或从访客明细去重。

## 7. WebApp 功能页边界（历史实现）

| 域名 | 路径 | 历史功能归类 |
|------|------|--------------|
| `app.immersivetranslate.com` | `/`、`/file*`、`/pdf*`、`/subtitle*`、`/word*` | `file`（旧版） |
| `immersivetranslate.com` | `/document*` | `file`（新版） |
| 旧 SQL 未另限域名 | `/translate*`、`/text*`；`/video*`；`/image*` | 分别 `text`、`video`、`image` |

历史 `version_type` 由域名划分：`app.immersivetranslate.com` 为 `previous`，`immersivetranslate.com` 为 `new`；不是插件 `version`。其它域名/路径及语言前缀须核验，不能自动套入。旧文档的说明列表还提及 `/babel-doc`，但该 DWS CASE 没有单独纳入，不能只凭说明列表补计。

这些指标反映功能页访问，不证明用户实际上传文档、翻译成功或消耗额度。要回答功能使用/完成率，须另核相应操作事件或业务记录。

## 8. Onboarding 的独立字段与历史口径

- 访问 `onboarding_page_view`；点击 `pricing_purchase_btn_click`。历史点击 trigger：`onboarding_pricing` → tutorial；`onboarding_pricing_quickstart` → quickstart。
- **2026-06-04 及以前、06-11 起的历史说明**：路径从 `trigger` 识别 tutorial/quickstart（兼容拼写 `turorial`），step 从 `ex_char_arg3`，语言从 `ex_char_arg2`，测试组从 `ab_tag`。这里 arg3 是 step，**不是官网指纹**。
- **2026-06-05～06-10**：说明记录字段错位，访问事件需从 `ex_char_arg1` 完整 URL 解析路径、step、语言，不能使用 trigger、arg2、arg3 或 `interface_language` 直接归组；购买点击逻辑不变。该历史说明不保证后续永无变更。
- 历史漏斗按非空 `device_id` 去重；以首次进入该路径 step-1 为起点，只计此后的事件，语言/AB 取起点；到达型漏斗允许跳步，不保证逐步转化率≤100%。这与指纹网站 UV 是不同主体。
- tutorial 与 quickstart 的 step 数不同；quickstart 到达 step-2 与 tutorial 到达 step-3 才是旧文档的「关键任务完成」对齐点。
- 原方案还含按设备表映射注册/试用的查询；不得直接提升为本仓通用转化口径。正式转化须遵守 P018 / P013 / P037，并验证映射覆盖与订单定义；旧设备漏斗与账号转化分别命名。

## 9. 来源与维护

以下为本次核对的历史来源路径；核心映射已收录在本文中，后续改动应更新本文件并记录证据时段：

- `imm_data_dashboard/base_info/table.md`：「现有的 officia_page_view 事件对应的字段」（原文拼写如此，事件名另以样本核验）。
- `imm_data_dashboard/webdata/webapp.md`：「基础信息」「提取数据」「建表 dws_web_user_day」「webapp 新用户来源」「营销归因表」「定时刷新任务」。
- `imm_data_dashboard/webdata/网站首页ab测试数据.md`：「基础提示词」及 `official_download_extension_click` 查询。
- `imm_data_dashboard/webdata/official_homepage_onboarding_not_upgrade_devices.md`：「口径」。
- `imm_data_dashboard/webdata/onboarding_pageview_funnel.md`：「口径」。
- 本仓 [T063 官网身份与 campaign 关联观察](../tasks/query_school_campaign_convert_20261010.md)、[T012 WebApp DAU](../tasks/anomaly_webapp_document_dau_aug2026.md)及[对应 SQL](../../sql/reports/anomaly_webapp_document_dau_aug2026.sql)。
- 本次补全留档：[T096](../tasks/query_web_events_context_20261110.md)。

当新样本或埋点代码与历史定义不符，先记录目标事件、时间窗、字段样本及差异，再修正文档；不要将一个事件/时段的字段解释直接覆盖其它事件/时段。
