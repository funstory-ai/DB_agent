# 直播助手桌面端埋点是否接入 Databend 的核查

- **需求编号**: T122
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-11-16
- **定稿 SQL**: `sql/reports/query_live_assistant_desktop_ingest_check_20261116.sql`

## 结论（先给答案）

**已接入，落在 `immdata.user_behaviour`（行为明细表），没有专用表也没有日汇总层。**
2026-09-01 ~ 11-16 全窗共 **3,256 条事件 / 105 台设备**，首见
**2026-10-28 08:49:17 UTC**（北京 10-28 16:49，与埋点说明同日）；
9-01 ~ 10-27 为零。近 7 天（11-09 ~ 11-16 14:00 UTC）**2,202 条 / 75 台设备 / 14 个事件名**。
量级只有几十台设备，属**灰度/内测**，不是全量上线；11-16 为不完整日。

**但实现与设计稿 13 个事件不是一一对应（3 处偏差）：**

| 设计稿 | 库内实况 | 影响 |
|--------|----------|------|
| 12 个事件 | 名称完全一致，近 7 天 1,970 条 | 可直接用 |
| `live_assistant_subtitle_manual_close` | **零命中**；实际是 `live_assistant_subtitle_close`（229 条） | 按设计稿事件名查会得到假零 |
| （未列） | 新增 `live_assistant_subtitle_interrupted`（3 条） | 对应设计稿留待确认的「运行中断是否计入失败」 |

**口径缺口（会影响后续分析，须先补）：**

1. **直播平台维度没落库**：`user_behaviour` 无 `video_platform` 列，10 个 `ex_char_arg*`
   槽位及 `site_host` / `page_type` / `translation_service` 等列全空，全窗未见
   YouTube / Twitch / Kick / TikTok / Facebook / X Spaces 等平台值 ⇒ 六平台拆分做不了。
2. **账号 ID 没填**：`ex_int_arg1`、`user_type` 全窗 0 填充（设计稿说「只有来源及映射明确时才填」），
   ⇒ 只能按 `device_id` 看，**无法按 userid 关联订单/会员**（P018 的人粒度转化暂时做不了）。
3. **`subtitle_close` ≠ 手动关闭**：`ex_char_arg2` 含 `page_navigation` 163 / `tab_closed` 29 /
   `quick_menu` 21 / `other` 16，含页面切换与标签关闭；设计稿明确手动关闭不含这些
   ⇒ 该事件不能当「手动关闭次数」。
4. **桌面端标识缺失**：`platform_type` / `browser_name` 全 NULL，只有 `os_name`=Windows/Mac OS、
   `version`=0.1.1-1→0.1.9 可识别；`ex_char_arg10` 全为 `com`（**未见 cn**）。
   桌面直报与插件透传在库内无法从字段区分，只能按 `event_name` 归类。
5. 全库 371 张表按名称盘点，唯一相关表 `immdata.imm_ai_subtitle_event` 是 AI 字幕日汇总
   （`dates/total_user/vip_count/vip_user`，418 天），**不是**直播助手数据。

**桌面端整体**：库里本来就有插件桌面端数据（近 1 天 Chrome/Edge/Safari/Electron +
`platform_type='desktop'` 数千万条/日）；本次核查的是**新的直播助手桌面 App**，
它走独立上报（`browser_name` 为 NULL），与插件桌面端是两批数据，不要混。

**不下的结论（P043）**：为什么只有 `com`、为什么账号 ID 与平台维度没填、是否还会全量放开——
本仓碰不到 `/collect` 服务端与客户端代码，均属未证实，需业务/客户端侧确认。

## 初始需求

用户：「看下桌面端的数据现在有没有接入 databend」，埋点说明文件
`C:\Users\86933\Downloads\live-assistant-analytics-summary.md`（《直播助手首批埋点说明》2026-10-28）。

该文件写明：共 13 个事件，**当时尚未实现**；仅走自建 `/collect`，
`subject: "user_behaviour"`，`logs` 中每条事件为 JSON 字符串；不新增数据库字段；
桌面端直报 8 个事件，插件透传 5 个直播字幕事件（由桌面公共接口统一上报）。

需回答：这 13 个事件现在是否已真实落进 Databend（哪几张表、哪些事件、什么时候开始、
量级与字段填充状况），以及桌面端整体数据是否另有入口。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **探测窗**：`created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'`（近 7 天，UTC 常量界）；**追溯窗**：`created_ts >= '2026-10-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'`（埋点设计日 10-28 前后，用于首见日/逐日量级）；**确认窗**：`created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'`（仅当探测窗零命中时做一次兜底）。全程不对 `created_ts` 套函数。 |
| 「接入」判定 | 事件名在 `immdata.user_behaviour` 中窗内有 ≥1 行真实事件行；零命中只能说「该窗内未查到」，须叠加元数据盘点（表名含 live/subtitle/desktop 的表）与近似事件名排查后才能下「未接入」结论。 |
| 分母 / 分子 | 不适用（存在性/完备性核查，非转化率）。计数为 `COUNT(*)` 事件行，另给 `COUNT(DISTINCT device_id)` 作量级参考。 |
| 主体 | 事件行；不按 userid 归并，不做 P018 转化主体（本题不涉及转化）。 |
| 事件清单 | 桌面 8 个：`live_assistant_app_start` / `live_assistant_login_click` / `live_assistant_login_success` / `live_assistant_login_failed` / `live_assistant_onboarding_step_show` / `live_assistant_onboarding_complete` / `live_assistant_install_plugin_click` / `live_assistant_browser_open`；插件透传 5 个：`live_assistant_subtitle_start` / `live_assistant_subtitle_success` / `live_assistant_subtitle_failed` / `live_assistant_subtitle_retry` / `live_assistant_subtitle_manual_close`。 |
| 字段核查 | 埋点说明列出 `video_platform`、`trigger`、`ex_char_arg2/3/9`、`ex_int_arg2`、`ex_char_arg10(cn/com)`、`version`、`os_name`、`device_id`；⚠️ `immdata.user_behaviour` 表结构中**没有 `video_platform` 列**（设计稿称「不新增数据库字段」），需实测直播平台落到哪个扩展槽位或是否根本没落。 |
| 范围边界 | 默认只查 `immdata`。若需查其它 schema 须用户明确要求；本次元数据盘点只读表名。碰不到 `/collect` 服务端、源库与客户端代码，不对「为什么没接入」下结论（P043）。 |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 13 个事件是否入库、命中哪些 | 定稿 SQL @Q1 精确 13 事件 + @Q2 模糊事件名：12 命中 / 1 改名 / 1 新增 | ✅ |
| 是否有专用表 / 其它承载表 | @Q0 `information_schema.tables` 371 张全库盘点；仅 `imm_ai_subtitle_event`（无关）；确认数据只在 `user_behaviour` | ✅ |
| 首见时间、逐日量级 | @Q3 逐北京日 + @Q4 全窗 min/max + @Q4b 10-28 前为零 + @Q5 版本节奏 | ✅ |
| 字段填充状况（含 `video_platform` 缺口） | @Q6 非空率 + @Q7 槽位取值盘点 + 原始行抽样；结论段 5 条缺口 | ✅ |
| 桌面端整体是否另有数据入口 | @Q10 近 1 天 `browser_name` × `platform_type` TOP（Electron/desktop 对照） | ✅ |
| 实现与设计稿的口径偏差 | @Q8 `subtitle_close` 的 `ex_char_arg2` 分布 + @Q9 trigger 枚举 | ✅ |
| 明确「已接入 / 未接入 / 未查到」的结论边界 | 本文档「结论」段 + 对话汇总；未证实项按 P043 标注 | ✅ |

## 抽样复核（正式交付）

P019 **通过**，均为窄路径，未重跑全量聚合：

1. **加总自洽**：近 7 天 @Q1 精确 12 事件合计 **1,970** + @Q2 的 `subtitle_close` **229**
   + `subtitle_interrupted` **3** = **2,202**，与 @Q11③ `count(*)`=2,202 / 14 事件 / 75 台一致；
   @Q3 逐北京日 19 个有数日加总 **3,256** 与 @Q4 全窗 `count(*)`=3,256 / 105 台一致。
2. **假零复验**：设计稿的 `subtitle_manual_close` 用另一条路径
   `event_name ILIKE '%manual%'` 在 10-01~11-16 全窗复查仍为 **0 行**；
   同时 `ILIKE '%close%'` 确认库内有 `live_assistant_subtitle_close` 229 条，
   排除「SQL 写错/大小写」导致的假零，判断为**改名**而非「未接入」。
3. **原始行抽样**：6 个事件各抽 2~3 行，核对 `trigger`（login / quick_menu /
   progress_retry / onboarding_detection）、`ex_char_arg9`（尝试 ID）、
   `ex_char_arg2/3`（阶段/错误码）、`ex_int_arg2`（耗时 ms）、`ex_char_arg10`='com' 落位正确。
4. **单设备序列**：`device_id=28f70b1b...` 11-16 的 4 条序列
   `app_start → login_click → browser_open → login_success`，
   两次登录事件共用同一 `ex_char_arg9`、耗时 37,482 ms，时间戳单调递增，事件链合理。
5. **合理性判断**：105 台设备 / 3,256 条属灰度而非全量；`11-01` 无数据、11-16 为不完整日
   已在结论标注；`platform_type`/`browser_name` 全 NULL 不是 SQL 漏取（@Q10 同表其它行有值）。

异常列：无。抽样结果未另存文件。

## 同事分析清单对照（11-16 14:30 追问）

用户提供同事飞书文档截图 `live-assistant-analytics-dat...st.md`，问「是不是和数据库现状一致」。
**该文档是「第一步：数据确认（先行）+ 第二步：核心分析需求」的提问/计划清单，未给任何数字结果**，
故可对照的是它预设的**表/事件/字段/口径假设**，不是结果数字。本次为 T122 追问核查，
**未另起 T###、未改上面已交付的任何数字**（P044）；补查均为只读窄查询。

| 同事的项 | 库内现状（本次 + 13:46 已查） | 一致？ |
|---|---|---|
| 入库：`user_behaviour` / 哪张表 / 更新频率 | `immdata.user_behaviour`，持续近实时写入；14:30 查到 `max(created_ts)=2026-11-16 06:29:44 UTC`（北京 14:29:44，距查询仅 28 秒），今日 171 条/10 台 | ✅ 一致（无专用表、无日汇总层） |
| 事件覆盖：13 个 `live_assistant_*` 均已出现 | 实际 **14 个**事件名，设计稿 13 个里只有 12 个同名；`manual_close` 零命中 → 实际 `subtitle_close`；新增 `subtitle_interrupted` | ❌ 不一致，按原名查得假零 |
| 各事件日均量级 | 全窗 3,256 条/105 台、近 7 天 2,202 条/75 台，属灰度；`app_start` 76 台 / `subtitle_start` 39 台 / `install_plugin_click` 36 台 | ⚠️ 量级远小于可分平台分版本分析的规模 |
| 字段解析：`ex_char_arg9` / `ex_int_arg2` / `ex_char_arg2` / `ex_char_arg3` / `trigger` | 全部**已解析成独立列**，不是原始 JSON；`ex_char_arg9` 尝试 ID 可关联同一次操作；`ex_int_arg2` 耗时 ms | ✅ 一致 |
| 字段解析：`video_platform` | **表无此列**，10 个 `ex_char_arg*` 槽位及 site_host/page_type/translation_service 全空，全窗无 YouTube/Twitch/Kick/TikTok/Facebook/X Spaces 值 ⇒ 既不是原始 JSON 也不是列，**根本没落库** | ❌ 不一致，且直接卡死 P0 |
| 字段质量：`device_id`/`version` 填充率 | 100% | ✅ 一致 |
| 字段质量：`user_type`/`ex_int_arg1`「预期填充率低」 | 实测 **0%（全空）**，不是「低」⇒ 不能按 userid 归因 | ⚠️ 比预期更绝对 |
| `ex_char_arg2`＝「失败阶段/引导步骤」 | 一列多义，按事件复用：`subtitle_failed`=session_start(150)/host_connect(5)/readiness(4)；`onboarding_step_show`=checking/missing_plugin/ready/platforms；`login_failed`=callback/prepare/login/token_exchange；`subtitle_close`=page_navigation(167)/tab_closed(30)/quick_menu(22)/other(16)；`interrupted`=runtime ⇒ 不限定 `event_name` 直接聚合会串组 | ⚠️ 漏了 3 类语义 |
| P0 字幕启动成功率「按 `video_platform` × `version` 拆」 | `video_platform` 不存在 ⇒ **做不了平台拆分**；只能按 `version`（7 个版本）拆；且须用 `ex_char_arg9` 按尝试去重，不能拿事件数直接相除（设计稿：retry 会用新尝试 ID 再触发 start，两类事件不能相加作启动总量） | ❌ 维度不可行 |
| P0 失败原因分布：失败阶段 × 错误码 Top10 | 可做但样本薄：`subtitle_failed` 159 条、失败阶段仅 3 个值、错误码 8 个值（session_start_failed 146 等），所谓 Top10 实际只有个位数 | ⚠️ 可做但别期待丰富分布 |
| P1 全链路漏斗 `…→ install_plugin_click → subtitle_start →…` | **断链**：装插件 36 台、字幕启动 39 台，**交集仅 15 台** ⇒ 把装插件当必经前一步会丢掉约 6 成字幕启动设备；设计稿也明确「安装插件点击与打开浏览器分别统计意图与执行操作，不能相加作为安装次数」 | ❌ 链路不成立 |
| P1 登录耗时 P50/P90 | 可算：本次时点 `login_success` n=75，P50 18,303ms / P90 48,538ms；`login_failed` n=16，P50≈300,008ms（≈5 分钟超时固定值，不可当真实耗时分布）；`subtitle_success` n=95 P50 33,722ms。样本量小，分版本后基本无统计意义 | ⚠️ 可做但须注明 |
| P2 重试率 / 手动关闭率 `manual_close / success` | `manual_close` 库内 **0 条**；实际 `subtitle_close` 含大量 `page_navigation`/`tab_closed` 非手动关闭，不能当手动关闭率分子 | ❌ 口径不成立 |
| P2 按 `install_week` 分桶新老用户首日漏斗 | 近 7 天 76 台里 **66 台集中在 202646**，202644/202645/202647 各 2/4/4 台 ⇒ 几乎只有一桶有样本，做不出新老对比；且 `install_week` 是设备本地首次初始化周，非账号新装（P034） | ⚠️ 样本不足 |

**时点说明（P044）**：`user_behaviour` 近实时追加，14:30 重跑比 13:46 多十几条
（如 `subtitle_success` 89→95、`subtitle_failed` 154→159），属正常写入，非口径矛盾；
上表「本次时点」数字只用于可行性判断，不替换本任务 13:46 已交付的格子。

**建议**：同事「第一步数据确认先行」的次序是对的；但第二步有 3 项（P0 平台拆分、
P2 手动关闭率、P2 新老分桶）在当前数据下无法按原口径交付，P1 全链路漏斗需拆成
「设备级各环节独立覆盖率」而非单链串联。需要先向客户端确认能否补 `video_platform`
与账号 ID、并确认 `subtitle_close` 的关闭原因枚举。

## 漏斗可行性专项（11-16 14:37 追问，F1~F12）

用户追问三点：① 是否入库 ② 入库多少 / 少什么字段 ③ 能否完成漏斗需求 / 少什么。
本节为 T122 第二次追问核查，**未另起 T###、未改 13:46 已交付数字（P044）**；
时点为 14:37 快照，`user_behaviour` 近实时写入，近 7 天已由 2,202 增至 **2,255 条 / 76 台**，
全窗由 3,256 增至 **3,309 条**（F1 逐事件加总），差异属正常追加，不替换已交付格子。
可复现 SQL 见 `sql/reports/query_live_assistant_desktop_ingest_check_20261116.sql` @Q12~@Q16。

### ① 已入库（结论不变）
`immdata.user_behaviour`，首见 **2026-10-28 08:49:17 UTC**（北京 16:49，与埋点说明同日），
9-01~10-27 为 0；符合设计稿「仅走 `/collect`、`subject: user_behaviour`、不新增表」。
全库 371 张表无 live_assistant 专用表/日汇总层。近实时（14:30 最新事件距查询 28 秒）。
105 台 / 3,309 条属**灰度内测**，不是全量。

### ② 入库量级与字段缺口（F12，近 7 天 2,255 条为分母）
| 状态 | 字段 |
|---|---|
| 100% 填充 | `device_id`、`version`、`os_name`、`interface_language`、`install_day`、`install_week`、`trigger`、`ex_char_arg10`、`real_geo` |
| 部分填充 | `ex_char_arg9` 尝试 ID 仅**登录 3 + 字幕 6 事件** 100%（桌面 5 事件 0%）；`ex_char_arg2` 一列多义（阶段/步骤/关闭原因）；`ex_char_arg3` 错误码仅失败事件；`ex_int_arg2` 耗时 348/2,255（仅结果事件） |
| 0% 全空 | `os_version`、`user_type`、`ex_int_arg1`(账号 ID)、`platform_type`、`browser_name`、`browser_version`、`site_host`、`page_type`、`translation_service`、`campaign`、`ab_tag`、`source_language`、`target_language`、`engine_name`、`install_from`、`is_new_user_today`、`ex_char_arg1`、`ex_char_arg4`~`arg8`、`ex_int_arg3` |
| **列不存在** | `video_platform`（设计稿「不新增数据库字段」，但也没放进现有槽位）⇒ 六平台拆分做不了 |
| 单值退化 | `ex_char_arg10` 全 `com`、无 `cn` ⇒ 国内/国际版不可分；`real_geo` 全填充但只是国家/地区，不能替代直播平台 |

事件名口径偏差不变：设计 13 个里 12 个同名，`subtitle_manual_close` 零命中 → 实际
`subtitle_close`，另新增 `subtitle_interrupted`，共 **14 个**事件名。

### ③ 漏斗结论：**设备级覆盖率可做，单链串联做不了**
**能做的两段（尝试级，`ex_char_arg9` 100% 覆盖）**：登录 `click→success/failed`、
字幕 `start→success/failed/retry/close`，可按尝试 ID 去重，不算事件数直接相除。

**不能做单链的 5 条硬证据**：
1. **无贯穿会话 ID**（F4/F8）：桌面 5 个事件（`app_start`/`browser_open`/
   `onboarding_step_show`/`onboarding_complete`/`install_plugin_click`）`ex_char_arg9` 全空，
   `ex_char_arg1`/`arg4`~`arg8` 全 0 ⇒ 全链路只能按 `device_id` 拼，跨会话必然串错。
2. **同设备多会话**（F11/F7 序列）：76 台里 **40 台 `app_start` ≥2 次**，最多 33 次；
   抽样设备 35 分钟内重启 7 次。F3 用 `min(created_ts)` 做有序相邻转化，
   `install_plugin_click→browser_open` **有序 0 / 同时命中 36**，原因是 `browser_open`
   最早一次来自登录而非装插件 ⇒ 设备级 min 取法不可靠。
3. **事件顺序与假设不符**（F3）：`onboarding_complete→install_plugin_click` 同时命中 28 台，
   仅 **8 台**「完成在前」，20 台是先点装插件再完成引导；全 9 节点都命中的仅 **9/76 台**，
   且是跨会话拼出的伪完整链路。装插件 ∩ 字幕启动设备交集仅 15 台（14:30 快照）。
4. **尝试级断链严重**（F9/F10）：登录 244 次 click 中 **153 次（62.7%）无终态**
   （75 成功 + 16 失败）；字幕 408 个启动尝试中 **155 个（38.0%）无终态**
   （94 成功 + 159 失败），其中 235 个只有 `close`（多为 page_navigation/tab_closed）。
   设计稿明确「不承诺完整采集或绝对不重复」⇒ 属设计边界，但**成功率分母口径必须先对齐**。
5. **retry 关联断开**（F7 序列）：设计稿要求「重试产生 retry + 新尝试的 start，使用新尝试 ID」，
   实测 `subtitle_retry` 与新 `subtitle_start` 共享**同一** `ex_char_arg9`，
   旧尝试 ID 未在任何 retry 事件中保留 ⇒ 算不出「第几次重试 / 重试后成功率」。
   另 `manual_close` 不存在，`subtitle_close.ex_char_arg2` 含非手动原因 ⇒ 关闭率口径不成立。

**做单链漏斗还缺（需客户端/插件补）**：
① 全程 `session_id`（App 启动生成，插件透传事件同样带上，落任一空闲 `ex_char_arg*` 槽）；
② `video_platform` 落到槽位；③ 账号 ID 映射（`ex_int_arg1`/`user_type`）；
④ `subtitle_close` 关闭原因枚举对齐（手动关闭与 page_navigation/tab_closed/异常结束分开）；
⑤ retry 携带旧尝试 ID；⑥ 明确「无终态尝试」是取消/丢包/中途退出的归因规则；
⑦ 按 `version` × 平台分析需先放量（当前 76 台、失败 159 条、错误码 8 值、阶段 3 值）。

**建议交付口径**：改为「各环节设备级独立覆盖率」+「登录/字幕两个尝试级子漏斗」，
每个环节独立给 UV 与分母，不做串联除法；样本薄、灰度期，结论只作方向性参考。

## 去掉单链后，其余 5 项可行性（11-16 14:47 追问，S1~S5 + V1~V3）

用户给出「第二步：核心分析需求」截图并明确 **「不需要单链」**（口径变更，P025 留痕），
问去掉 P1 全链路漏斗后其余 5 项能否完成。按同事**原口径**逐项实算（只读，14:47 快照
2,258 条明细一次性拉回 Python，同批数据算全部指标 ⇒ 分子分母同粒度，P044）；
**未另起 T###、未改 13:46 已交付数字**。可复现 SQL 见定稿文件 @Q17~@Q21。

| 优先级 / 分析 | 判定 | 实测结果与条件 |
|---|---|---|
| **P0 字幕启动成功率**：`video_platform` × `version`，成功/(成功+明确失败) | ⚠️ **削掉平台维度后能做** | 按 `ex_char_arg9` 去重：**96 / (96+159) = 37.65%**（V3 独立路径复算一致）。按版本：`0.1.6` 1/4=25.0%、`0.1.7` 31/124=25.0%、`0.1.9` 64/127=50.4%。⚠️ 0.1.7→0.1.9 的观测差异**不能读成版本升级导致提升**（灰度人群/时间混杂，P043）。`video_platform` **列不存在**（V2：`information_schema.columns` 中 platform 类列只有全 NULL 的 `platform_type`），空闲槽位 a1/a4~a8 全 0 ⇒ **平台 × 版本交叉做不了**。`subtitle_interrupted` 3 条是否并入「明确失败」按设计稿「另行确认」，本次未并入 |
| **P0 失败原因分布**：`ex_char_arg2` × `ex_char_arg3` Top10 | ✅ **能做** | 限定 `event_name='live_assistant_subtitle_failed'` 后 159 条 / 159 个尝试 ID，阶段 3 值 × 错误码 3 值，**组合只有 3 种 ⇒ Top10 实为 3 行**：`session_start × session_start_failed` **150（94.3%）**、`host_connect × desktop_unavailable` 5、`readiness × readiness_timeout` 4。⚠️ 不限定 `event_name` 会串组：全事件 a3 共 **9 值**（5 个 login_failed 错误码 + 3 个 subtitle_failed + 1 个 interrupted 的 session_interrupted）；上一节旁注写「8 个值」为不限定事件/早时点的粗数，正式口径须限定事件 |
| **P1 登录成功率与耗时**：成功率 + `ex_int_arg2` P50/P90 | ⚠️ **能做，但成功率分母必须先问**（P025） | 尝试级 click=244 / success=75 / failed=16 / **无终态 153（62.7%）**。口径 A `success/(success+failed)` = **82.4%**，口径 B `success/click` = **30.7%**，差 2.7 倍；同事只写「成功率」未给分母，不可替其选定。耗时：`login_success` n=75，P50 **18,303ms** / P90 **48,913ms** / max 171,615ms；`login_failed` n=16 中 **11 条 ≈300,008ms 是 5 分钟超时固定值**（P50 300,008ms）⇒ 失败耗时**不能当真实分布**，建议只报成功耗时或把超时单列 |
| **P2 用户重试率**：`retry / 去重后 start` | ✅ **能做** | 141 / 409 = **34.47%**（`start` 410 条 → 409 个尝试 ID）。但要说明语义：141 条 retry **全部**与「新 start」共享同一尝试 ID，即分母已包含重试产生的那次启动，这是「带 retry 标记的启动尝试占比」，不是「重试过的用户占比」；旧尝试 ID 未保留，算不出第几次重试 / 重试后成功率 |
| **P2 手动关闭率**：`manual_close / success` | ❌ **做不了** | `live_assistant_subtitle_manual_close` **0 条**（ILIKE '%manual%' 全窗复验亦为 0）；实际 `subtitle_close` 237 条，`ex_char_arg2` 关闭原因 = `page_navigation` 168 / `tab_closed` 30 / `quick_menu` 22 / `other` 17，其中设计稿明确手动关闭**不含页面切换、旧会话清理、异常结束** ⇒ 无一个可确认为「手动关闭」的干净枚举；且 `quick_menu` 同时是 `trigger` 值（215 条），语义未澄清。分母用 `success` 也需确认。**替代可交付**：关闭原因分布（237 条 4 类），先让客户端确认枚举 |
| **P2 新老用户漏斗对比**：按 `install_week` 分桶的首日漏斗 | ⚠️ **单桶能画，跨桶对比做不了** | 76 台按 `install_week` 分桶：202644 **2 台** / 202645 **4 台** / 202646 **66 台（86.8%）** / 202647 **4 台**。按「首次 `app_start` 的北京日」定首日，202646 桶可画设备级覆盖：app_start 66 → login_success 56 → onboarding_complete 46 → install_plugin_click 32 → subtitle_start 29 → subtitle_success 14；其余三桶最大 4 台，比率只会在 0/25/50/100% 跳变，**无对比价值**。另 `install_week` 是设备本地首次初始化周、非账号新装（P034），「首日」定义（首次 app_start 北京日 vs `install_day`）也须先对齐 |

**结论**：去掉单链后，**5 项里 2 项能直接做**（失败原因分布、重试率），**2 项需改口径或削维度**（成功率：去掉 `video_platform`、确认 interrupted；登录：先定成功率分母 + 超时耗时单列），**1 项半做不了**（手动关闭率完全不可做；新老用户对比样本不足）。全部指标都受灰度样本约束（76 台 / 7 天），只能作方向性参考，不宜按版本/周做统计推断。

**P019 抽样**：① V3 用独立 SQL 路径复算成功率 96/159=37.65%，与明细算法一致；
② V1 按事件拆 a3，解释「8 值 vs 3 值」差异不是数据变化而是口径混用；
③ V2 用 `information_schema.columns` 复核 `video_platform` 确实不存在，排除 SQL 漏查；
④ 全批 2,258 行同一时点、同一 `created_ts` 窗，分子分母同粒度。

## `video_platform` 深度排查（11-16 14:54 追问，A~G）

用户要求「看看会不会塞在某一个字段里，多检查一下」。结论：**没有，平台维度确实没落库**，
且此前「列不存在」的判断在扩大到全库元数据 + 全窗全字段 + 整数槽位 + 早期版本后仍成立。
本节为 T122 第四次核查，未另起 T###、未改已交付数字。可复现 SQL 见定稿文件 @Q22~@Q26。

### 排查范围（比 13:46 版更宽）
1. **全库元数据**：`information_schema.columns` 精确查 `%video_platform%` → **0 行**。
   `immdata` 里含 platform/video 的列共 18 个，全是 `platform_type`（设备端类型）或
   `imm_view_dau` 的 `translate_video_subtitle*` 计数列；`imt_deviceinfo.platform` /
   `imt_campaigninfo.platform` 抽样为 `Windows 10` / `Android OS` / `Mac OS` / `Chrome OS`
   ⇒ 是 **OS 平台**，不是直播平台。表名含 live/subtitle/platform 的仍只有
   `immdata.imm_ai_subtitle_event`（418 行日汇总：dates/total_user/vip_count/vip_user，与本功能无关）。
2. **全窗全字段扫描**：`SELECT *` 拉 9-01~11-16 全部 `live_assistant%` 事件 **3,312 行 × 63 列**，
   逐列做 distinct + 关键词（六平台名 / 别名 / 中文名 / URL 片段 / `video_platform` /
   `live_platform` / `platform=` / `platform:` / JSON 特征）→ **命中 0 列**，
   **含 JSON 或键值结构的单元格 0 个**，排除「塞进 JSON 串」。
3. **整数槽位**：`ex_int_arg1`、`arg3`~`arg10` **全为 0 个非 NULL**；只有
   `ex_int_arg2` 有 566 行 / 551 distinct（24ms~300,049ms 耗时）⇒ **不存在 1~6 数字编码**。
4. **字符槽位**：a1/a4~a8 全空；a2 = 16 个阶段/步骤/关闭原因；a3 = 9 个错误码；
   a9 = 尝试 ID；a10 = 唯一值 `com`。其它列 `version` 7 个 0.1.x、`os_name` 2 值、
   `interface_language` 3 值、`real_geo` 14 个国家/地区码、`real_city` 54 城市、
   `trigger` 7 入口、`device_id` 106 个 32 位 hex、`real_ip` 184 个 —— 均非平台。
5. **早期版本**：全窗 7 个版本（0.1.1 / 0.1.1-1 / 0.1.2 / 0.1.5 / 0.1.6 / 0.1.7 / 0.1.9）
   逐版本检查过，不是「早期上报过后来停了」。

### 两个「看起来像」的线索，均已排除
| 线索 | 实测 | 判定 |
|---|---|---|
| `ex_char_arg2 = 'platforms'`（58 条） | 只出现在 `live_assistant_onboarding_step_show`，与 `onboarding_complete` 同一毫秒；是**引导步骤名**（展示平台列表页）。抽样两台设备完整序列，该步骤前后所有槽位全空 | 只记「展示过这一步」，**没记用户选了哪个平台** |
| `ex_char_arg9` 里 32 个 `generic-live-<UUID>` | 982 个尝试 ID 中非标准前缀**只有 `generic-live-` 一种**（其余 950 个纯 UUID/32位hex）；对应 97 行 / 15 台 / 2026-10-30~11-15 / 版本 0.1.1~0.1.9，**全部 `trigger='progress_retry'`**，事件为 retry 32 + start 32 + close 22 + failed 10 + success 1 | 是**重试会话 ID 前缀**，不是平台枚举；且只有一个值 `generic`，**分不出六平台** |

### 平台名确实在库里出现过，但属于另一批数据
全窗 `event_name` 含六平台关键词的只有 3 个：
`facebook_live_quality_intent` 16 / `facebook_live_quality_requested` 5 /
`youtube_live_quality_intent` 2，共 **23 条 / 2 台设备 / 11-11~11-13**。

它们是**插件 1.34.4 / Chrome desktop 的画质设置埋点**：`ex_char_arg1` =
`fixed_720`/`fixed_240`/`fixed_144`（画质档位）、`ex_char_arg3` = `native_menu`，
`platform_type='desktop'`、`user_type='anonymous'` 等公共字段全填满。
而直播助手是 `0.1.x`、公共字段大量为空、`device_id` **32 位 hex**；
平台事件的 `device_id` 是 **64 位 base64**。**两批设备精确交集 = 0**（2 台 vs 106 台）
⇒ **无法通过设备关联把平台补回直播助手**。注意 facebook/youtube 只出现在**事件名**里，
字段值中仍无 `video_platform`。

### 结论（不变，但证据更硬）
**P0「按 `video_platform` × `version` 拆分」仍做不了**，按 `version` 单维可做。
若必须按平台拆，只能让客户端：① 把平台值写进空闲槽位（`ex_char_arg1` / `arg4`~`arg8` 全空，可用），
或 ② 按平台拆事件名（现有 `*_live_quality_*` 是另一套埋点，不可复用）。
⚠️ **猜测（P043，未证实）**：`generic-live-` 前缀暗示客户端可能把直播会话统一当「generic live」处理、
未做平台细分；本仓碰不到 `/collect` 服务端与客户端代码，须向客户端确认，
不能据此断言平台信息在别处存在。

## 文档逐字复核：「仅直播事件填写」（11-16 15:24 追问，H1~H4）

用户指出文档里 `video_platform` 注明「直播平台，仅直播事件填写」，要求再确认文档。
**本节为 T122 第五次核查，未另起 T###、未改已交付数字。可复现 SQL 见 @Q27。**

### 文档层：字段**确实写了**，但要区分三层
| 层 | 事实 | 依据 |
|---|---|---|
| ① 埋点文档 | **有**。`## 上报字段` 表第 57 行：`video_platform` \| 直播平台，仅直播事件填写 | 文档原文 |
| ② 上报协议 | 文档第 9 行「仅使用自建 `/collect`，不接 GA，**不新增数据库字段**」、第 45 行「**仅使用现有字段**，无法准确获取的值省略」、第 68 行「`logs` 中每条事件为 JSON 字符串」⇒ 这是**上报 payload 字段**，落库需服务端映射到现有列。本仓碰不到 `/collect` 服务端/客户端代码，**无法验证是否真的上报过**（P043 边界） | 文档原文 |
| ③ 数据库 | **确认没有**：无同名列、无任何槽位承载平台值、无原始 payload 表可查 | @Q22~@Q27 实测 |

⚠️ 文档第 5 行原文「事件范围已确认，共 13 个；**尚未实现**。以下事件名、字段分配及统计细则供**实施前对齐**」
⇒ 这份是**实施前设计稿**，不是已实现接口说明。「文档写了」≠「已落库」。
另：第 78 行引用的 `live-assistant-analytics-design.md`（「完整实现边界」）在
`C:\Users\86933\Downloads`、项目目录、Desktop **均不存在** ⇒ 无法核对是否有更细的字段映射约定。

### 「仅直播事件」的准确范围与专项复核
文档第 29~31 行：`## 插件透传的直播字幕事件`，适用平台 **YouTube / Twitch / Kick / TikTok / Facebook / X Spaces**，
共 **5 个事件**（start / success / failed / retry / manual_close）；桌面端 8 个事件不填该字段。
因此本次**只查这批字幕事件**，不再混全量 `live_assistant%`：

- **H1 量级**（9-01~11-16 14:00 UTC）：库内落地为 6 个实际事件名，`manual_close` 仍 0，
  改名 `subtitle_close` 360 / `subtitle_start` 606 / `subtitle_failed` 221 / `subtitle_retry` 177 /
  `subtitle_success` 171 / 新增 `subtitle_interrupted` 8，**合计 1,543 条**（H2b `count(*)`=1,543，自洽），
  首见 2026-10-28 08:50:39 UTC。
- **H2a 33 个字符列 DISTINCT 组合 1,542 行逐列枚举**：平台关键词（六平台名/别名/中文/URL/
  `video_platform`/`live_platform`/`platform=`/`platform:`）**命中 0 列**。
  a1/a4~a8 全空；`trigger` 仅 `progress_retry`/`quick_menu`；a2 8 值（阶段/关闭原因）；
  a3 4 值（错误码）；a9 606 个尝试 ID；a10 唯一 `com`；`version` 7 个 0.1.x；
  `real_geo` 12 个国家码；`user_type`/`platform_type`/`browser_name`/`site_host` 等 0 填充。
- **H2b 整数槽位**：`ex_int_arg1`、`arg3`~`arg10` **全部 0 个非 NULL**；仅 `ex_int_arg2` 400 行 /
  388 distinct（耗时）⇒ **不存在 1~6 的数字平台编码**。
- **H2c JSON 残留**：含 `{` / 引号 / `video_platform` 字样的单元格 **0 个** ⇒ 没有把 payload 原串塞进某列。
- **H3 元数据**：全库 `%video_platform%` 列 **0 行**；`user_behaviour` 含 video/live/platform 的列
  **只有 `platform_type`**（且本批 0 填充）；全库表名含 collect/raw_log/payload 的只有
  `babel_novel.readit__collection*` 两张无关表 ⇒ **没有原始上报日志表可反查**。

### 结论
**文档里有 `video_platform`，数据库里确认没有。** 之前说的「没有」指的是**库内列/值**，
不是「文档没写」；这次按文档「仅直播事件填写」的限定把范围收窄到 5 类字幕事件后重查，
结论不变。P0「按 `video_platform` × `version` 拆分」仍做不了，按 `version` 单维可做。
要补齐须由客户端把平台值写进空闲槽位（`ex_char_arg1` / `arg4`~`arg8`），
并由 `/collect` 服务端完成映射到 `user_behaviour` 现有列；两者都需向客户端/数据服务团队确认。

### 15:47 语义澄清：「没有」到底指什么

用户追问「你的没有，是直播事件有的、但这个直播事件的这个字段没有吗」。**方向对，但「字段没有」不是「列在、值为空」**：

| 层 | 事实 |
|---|---|
| 直播事件本身 | ✅ **有**：全窗落地 6 个 `live_assistant_subtitle_*` 事件名 / **1,543 条**（H1），设备、版本、尝试 ID、耗时都在 |
| ① schema | ❌ `user_behaviour` **没有名为 `video_platform` 的列**（全库精确查 0 行）；含 video/live/platform 的列只有 `platform_type`，且本批 0 填充 |
| ② 值 | ❌ **没有任何其它列/槽位承载等价的平台值**：全窗 63 列逐列扫（A~G）+ 收窄到字幕事件的 33 字符列 / 10 整数列（H2a/H2b）均命中 0；a1/a4~a8 全空、整数槽位除耗时外全 0、JSON 残留 0 ⇒ **不是「有列但全是 NULL」，是连列带值都没有** |
| ③ 追溯 | ❌ 全库无 collect/raw/payload 原始上报日志表，无法反查 `/collect` 的 JSON payload |

⚠️ **不能断言「客户端没上报」**：payload 里可能真的带了 `video_platform` key，只是服务端解析时没映射到现有列而丢弃。
本仓碰不到 `/collect` 服务端与客户端代码，这一层无法验证（P043）。
区分的意义：若只是「值空」，找客户端补值即可；现在是**列/映射都不存在**，须先找数据服务团队确认映射。
最小验证办法：抓一条线上 `/collect` 请求或看接收端原始日志，检查 payload 是否含 `video_platform` ——
有 ⇒ 服务端映射漏了；无 ⇒ 客户端未实现该字段。

本轮为纯语义澄清，**未重跑库、未改任何已交付数字**。

## 漏斗口径三分（15:56 追问，L1~L5）

用户质疑「为什么不能按 `device_id` 算？按时间算应该也可以？严格/宽松两种漏斗，宽松只要事件数一层层、不考虑顺序，能不能做」。
**承认修正**：此前「单链漏斗做不了」措辞过宽，指的只是**严格漏斗**；**宽松漏斗（设备集合、不考虑顺序）完全能做**，
且按 `device_id` + 时间做「有序近似」技术上也能算，只是有环节严重失真。本节为 T122 第六次核查，
沿用同一锚点（11-09~11-16 14:00 UTC，2,258 行 / 76 台，与 14:47 快照一致），未改已交付数字。可复现 SQL 见 @Q28。

### 三种口径定案
| 口径 | 定义 | 判定 |
|---|---|---|
| 严格漏斗 | 同一次会话内、按真实发生顺序串 9 节点 | ❌ 做不了：无 `session_id`，桌面 5 事件 `ex_char_arg9`=0、a1/a4~a8 全 0 |
| **宽松漏斗** | 按 `device_id` 去重取集合，**不考虑顺序、不要求同一会话** | ✅ **能做**，见 L1/L2/L3 |
| 有序近似 | 按 `device_id` + 各节点 `min(created_ts)` 要求上一层 ≤ 本层 | ⚠️ 技术上能算，但 2 处严重失真，不能当真实转化读（L4） |

### L1 各节点设备集（宽松漏斗基础）/ 总活跃 76 台
| 节点 | PV | UV | /76 覆盖率 |
|---|---|---|---|
| app_start | 218 | 76 | 100.0% |
| login_click | 244 | 70 | 92.1% |
| login_success | 75 | 65 | 85.5% |
| onboarding_step_show | 159 | 63 | 82.9% |
| onboarding_complete | 54 | 54 | 71.1% |
| install_plugin_click | 108 | 36 | 47.4% |
| browser_open | 338 | 71 | 93.4% |
| subtitle_start | 410 | 39 | 51.3% |
| subtitle_success | 96 | 24 | 31.6% |

### L2 相邻两层：分子必须取「与上层交集」
| 相邻层 | 上层UV | 本层UV | 交集 | **交集/上层（正确）** | 本层/上层（错） |
|---|---|---|---|---|---|
| app_start→login_click | 76 | 70 | 70 | 92.1% | 92.1% |
| login_click→login_success | 70 | 65 | 65 | 92.9% | 92.9% |
| login_success→onboarding_step_show | 65 | 63 | 62 | 95.4% | 96.9% |
| onboarding_step_show→onboarding_complete | 63 | 54 | 54 | 85.7% | 85.7% |
| onboarding_complete→install_plugin_click | 54 | 36 | 28 | 51.9% | 66.7% |
| install_plugin_click→browser_open | 36 | 71 | 36 | 100.0% | **197.2%（倒挂）** |
| browser_open→subtitle_start | 71 | 39 | 37 | 52.1% | 54.9% |
| subtitle_start→subtitle_success | 39 | 24 | 24 | 61.5% | 61.5% |

⚠️ **「事件数一层层」不成立**：L5 按 PV 逐层比有 5 处 >100%
（app_start→login_click 111.9%、login_success→onboarding_step_show 212.0%、
onboarding_complete→install_plugin_click 200.0%、install_plugin_click→browser_open 313.0%、
browser_open→subtitle_start 121.3%）。原因是同一步会重复触发（218 条 app_start 只来自 76 台、
338 条 browser_open 来自 71 台）。**漏斗主体必须去重设备 UV，不能用 PV**；且分子取交集，
不能拿本层 UV 直接除上层 UV。

### L3 累积集合嵌套（从 app_start 起每步都做过，仍不考虑顺序）
76 → 70 → 65 → 62 → 53 → 27 → 27 → 13 → 9 台（终点占 app_start **11.8%**）。
可做，但它是「这 7 天里全部步骤都出现过」的设备，**不是一次旅程走到底**，且窗口拉长会变大，不是转化率。

### L4 按时间有序近似：8 个相邻对里 6 个有序率 ≥97.3%，2 处失真
app_start→login_click 69/70=98.6%；login_click→login_success 65/65=100%；
login_success→onboarding_step_show 62/62=100%；onboarding_step_show→onboarding_complete 54/54=100%；
**onboarding_complete→install_plugin_click 8/28=28.6%**；**install_plugin_click→browser_open 0/36=0.0%**；
browser_open→subtitle_start 36/37=97.3%；subtitle_start→subtitle_success 24/24=100%。
失真原因：40/76 台 `app_start` ≥2 次（最多 33 次），整窗 `min(ts)` 把不同会话拼在一起；
`browser_open` 的最早一次普遍来自登录而非装插件 ⇒ 0% 不是「没人转化」，是取错了那一次。

### 结论与建议交付
- ✅ **宽松漏斗能做**：建议用「各环节独立覆盖率（统一分母 76 台）+ 相邻层交集转化率」两版，
  明确写「设备级、窗口内是否出现过、不考虑顺序与会话」。
- ⚠️ 有序近似可作为敏感性对照，但须标注 2 处失真、不能当真实转化。
- ❌ 严格漏斗仍需客户端补全程 `session_id`（P043：本仓碰不到客户端代码，不判断其内部实现）。
- 三种主体不可混：PV（条数）/ UV（去重设备）/ 尝试 ID `ex_char_arg9`（仅登录 3 + 字幕 6 事件）。

## 对照外部报告 `live-assistant-data-review.html`（16:26，M~P 核查）

用户提供的同事完整分析报告，窗口 **UTC 2026-10-28 00:00 ~ 11-16 00:00**（与本题定稿窗
11-09~11-16 14:00 不同，数字不可直接比；本轮未替换任何已交付格子）。核查方式：按报告窗口重跑
只读 SQL（M1~M3 / N1~N3 / O1~O4 / P1~P4），逐项对表。

### 一致且复算无误（原始计数层与结构性判断）
- 同窗全量 **3,137 行 / 14 事件名 / 102 台**（P4；09-01~11-16 14:00 全窗为 3,325 行 / 107 台，
  差值来自近实时追加，非口径冲突）。
- 报告核心计数逐项命中：start 573/57 台、app_start 289/102 台、failed 210、success 153/36 台、
  login_success 141/92 台、login_failed 15（M1）；失败原因 session_start×session_start_failed 186 /
  readiness×readiness_timeout 18 / host_connect×desktop_unavailable 6（M2）；
  session_start 失败里 quick_menu 131 次均值 **25.8s**、progress_retry 55 次均值 **3.8s**（P1）。
- 成功率 42.2% = 153/(153+210) 与本题口径一致（本题近 7 天 37.65% 是另一窗口，不冲突）。
- `video_platform` 拿不到、平台拆分做不了 ✅（本题 A~G / H1~H4 已用全窗 63 列复核，
  报告只扫 1,225 行子集，证据范围较窄但结论相同）。
- 严格全链路漏斗作废、装插件不是必经前一步 ✅（本题 L1~L5 同结论）。
- 「11-12~15 服务端共性问题」标注为假设、需服务端日志验证 ✅ 符合 P043。
- 补埋点建议（平台落独立列/`ex_char_arg1`、补 `browser_name`、公共字段填充率 >95%）✅ 一致。

### 有问题（3 处改变结论 + 3 处推断越界）
1. 🔴 **「1,225 行直播事件」是筛选子集，且漏掉 `subtitle_close`，导致「无结果」归因错**。
   1,225 = start 573 + app_start 289 + failed 210 + success 153，仅 4 个事件名；同窗实际 14 个 /
   3,137 行，漏 close 342、browser_open 466、login_click 362、onboarding_step_show 211、
   retry 164、install_plugin_click 131、onboarding_complete 73、login_failed 15、interrupted 7。
   且 `app_start` 是桌面端事件，按文档「仅直播事件填写」不该计入直播事件，故「完全闭合」说法不成立。
   **实测（N1/O1）**：573 条 start 对应 572 个尝试 ID，无终态 **210 个**，其中 **205 个有
   `subtitle_close`**（同一 `ex_char_arg9`）、36 个有 retry，真正无任何终态事件的只有 **3 个**。
   close 的 a2 分布：page_navigation 221 / quick_menu 52 / tab_closed 47 / other 22。
   ⇒ 「210 次无结果＝埋点闭环缺失」证据不足，主体是会话以 close 结束，不是静默丢结果事件；
   报告把「30 台首次无结果设备埋点链路排查」列为最高价值待办、以及「计入分母成功率掉到
   26.7%」的警示，都需按此改写。
2. 🔴 **登录 90.4% 是闭环口径，与字幕「210 次无结果」双标**（正是本题 Q19 的口径分歧）。
   全窗 login_click **362** / success 141 / failed 15 / **无终态 206（56.9%）**（O2）。
   90.4% = 141/156，按 click 则 **39.0%**，差 2.3 倍。报告字幕侧专门开节强调无结果，登录侧
   206 次无终态只字不提，且写「登录：成功率没问题」「口径已对齐」。另「92/102=90.2%」是
   「成功过」的设备覆盖率，不是成功率，与尝试级 90.4% 并列易混。
3. 🔴 **四阶段「完整链路」不是漏斗**：573→363→177→159→153 是用 186/18/6 三类失败倒扣出来的。
   `ex_char_arg2` 的 `session_start`/`readiness`/`host_connect` 是**失败发生在哪个阶段**的枚举，
   不是阶段完成埋点，库里无阶段到达事件 ⇒ 「建立会话通过 48.8%」「通过 89.8%/96.2%」
   「会话一旦建立后面基本都能过去」均推不出；第二步「拿到结果 573→363 流失 210」把丢/无结果
   当成一个漏斗阶段。本题 L1~L5 已定案：严格单链做不了、宽松设备级能做、PV 逐层比会倒挂。
4. 🟠 **`generic-live-*`「多为」是事实错误**：935 个尝试 ID 中仅 **32 个（3.42%）** 带该前缀，
   其余 903 个是标准 UUID/hex，唯一非标准前缀就是 `generic`（N2）。报告据此写「说明代码走通用
   直播分支、没按平台区分」「趋势指向插件没取到」＝事实错 + 把猜测写成倾向结论（违 P043）。
   本题 A~G 已定案：32 个全部 `trigger='progress_retry'`，是重试会话 ID 前缀，分不出六平台。
   报告「还缺什么」把「arg9 前缀分布」列最高价值待办 —— 该项已查完，无需再做。
5. 🟠 **「重试是恶化操作」是选择偏差**：93 次重试无需推算（`subtitle_start` 里
   `trigger='progress_retry'` 直接 93，P3），但 `subtitle_retry` 共 **164 条**
   （progress_retry 93 + quick_menu 71），报告只覆盖 56.7%。会重试的尝试本就来自刚失败的会话，
   66.7% vs 30.8% 是人群选择差异，不能推出因果上的「恶化」。
6. 🟠 **「排除用户网络差／问题在字幕链路自身」是因果断言**：两条链路口径不同（各自排除了
   206 / 210 个无终态），观测差异不足以排除混杂；应比照报告时间线那节标为「待验证假设」。

### 小问题（不改结论）
- 「点过安装插件只有 22 台」：同窗实测 **42 台**，与 subtitle_start 交集 **19 台**（P2）；方向对、数字错。
- 「闭环 363」按尝试 ID 去重实际 **362**，有 1 个孤儿结果 ID 不在 start 中；报告写「匹配率 100%」
  实为事件条数而非去重 ID。
- 「210」在文中兼指失败事件数 / 无结果数 / 流失份额，虽数学自洽（573 = 153+210+210）但极易误读。
- 留存分母混乱（17.3%=9/52、活跃天数 73.5%=25/34、总设备 57），且窗口截止 11-16 00:00 UTC，
  11-15 设备无次日观察窗 ⇒ 次日回访被系统性低估。
- 耗时：报告 P50 34s / P90 82.6s / max 151s 基于 305 条配对样本；本题 `ex_int_arg2` 全量 370 条
  为 P50 28.3s / P90 83.4s，接近但不等；`subtitle_interrupted` 有 9,317s 极端值被排除未交代（N3）。

**P019 抽样**：① 用两个候选窗口（UTC / 北京日）复算，确认报告窗是 UTC 口径且核心计数全部命中，
排除「窗口不同导致数字打架」；② 用独立集合路径按 `ex_char_arg9` 复算闭环 362 / 无终态 210，
与事件条数口径对上差异 1；③ P1 限定 `session_start` 后复算 25.8s / 3.8s 与报告完全一致，
排除「耗时口径不同」；④ 全批同窗同时点，分子分母同粒度。异常列：无。
