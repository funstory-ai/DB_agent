# 移动端访问 TOP 网页：可行性探查 + 正式 TOP100 交付

- **需求编号**: T117
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-11-13
- **定稿 SQL**: `sql/reports/query_mobile_top_pages_20261113.sql`
- **定稿脚本**: `scripts/export_mobile_top_pages.py`（canonical，`--end/--days/--top` 可刷新；交付须带 `WF_TASK=T117`）
- **交付**: `output/mobile_top_pages_20261113.xlsx`（7 sheet：摘要 / PV 总榜 TOP100 / 按 UV 参考榜 / 分 OS / 分版本 / 按天 TOP20 / 口径与抽样）
- **验收**: 2026-11-16 用户确认已验收；`wf status T117 = audited`（六阶段全通过），`wf_audit.py` 对 T117 零违规。本档与交付物数字未因验收改动。

## 初始需求

> 能拉到移动端访问 TOP 的网页吗

判断 `immdata` 是否留存「移动端设备访问的网页」明细，可到什么粒度（完整 URL / host / 仅翻译事件），能否出 TOP 排行；并列出可用性限制。正式口径（时间窗、PV vs UV、URL vs host、访问 vs 翻译、国内/国际版、TOP N、交付形态）待用户确认后再出数。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **正式：北京日 2026-10-14 ~ 2026-11-12（30 个完整自然日）** = UTC `2026-10-13 16:00:00` ~ `2026-11-12 16:00:00`（北京日 D = UTC (D-1)16:00 ~ D16:00）。可行性探查另用 11-12 单日 / 1 小时短窗（P021） |
| 事件 / 数据源 | `immdata.user_behaviour` 的 `event_name='webview_visit'`（App 内置浏览器访问）；域名 = `get(try_parse_json(ex_char_arg1),'domain')`。用户 11-13 确认走「App 内置浏览器」路径 |
| PV | 1 条 `webview_visit` = 1 次访问；只计归一后有效、且非自家域名的事件 |
| UV | 该域名的去重埋点 `device_id`（排除空值与全零占位 UUID）；同一设备访问多个域名各计 1，不可跨域名相加 |
| 排名 / TOP N | **按 PV 降序 TOP 100，每行同时给 PV + 设备 UV**（用户确认「pv+UV TOP100」）；另出按 UV 降序的参考榜 |
| 主体 | 埋点 `device_id`（P037：移动端 device_id 大部分不在 `imt_deviceinfo`，全程不 JOIN 设备表） |
| 移动端判据 | `lower(os_name) IN ('android','ios','ipados')`；实测 `webview_visit` 无桌面混入，未按 `platform_type` 过滤 |
| 域名归一 | 去引号 / 反转义 `\/` → 去协议 → 去路径、query、fragment、端口 → 小写 → 循环合并 `www.`/`m.`/`cn.`/`en.`/`amp.`/`mobile.` 前缀 → host 格式校验；简单前缀合并，非完整 eTLD+1 解析 |
| 剔自家 | host 含 `immersivetranslate` 的全部子域与 .com/.cn 剔除；`translify.ai` 不在剔除规则内，保留并注明 |
| 无效值 | `about:blank` / `about:srcdoc` / `127.0.0.1` / UUID 形态脏值 / `unknown` 等不计入排行 |
| 分版本 / 分 OS | `ex_char_arg10`（com 国际版 / cn 国内版）、`os_name` 三平台；附表只给 PV 拆分 |
| 交付 | `output/mobile_top_pages_20261113.xlsx`：`0_摘要` / `1_总榜_TOP100` / `1b_按UV排名TOP100`(参考) / `2_分OS` / `3_分版本` / `4_按天TOP20` / `5_口径与抽样` |
| 排除 | `user_access_log`（停更 2025-09-05）、`translate_page_performance`（无 device_id）、`official_page_view`（自家域名）、收藏/历史点击、`user_domain_tag_day`；详见「探查结果」 |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 是否存在移动端网页 URL / host 明细 | 下方「探查结果」A/B/C | ✅ 有域名级，无具体页面 URL |
| 覆盖度、量级、能否排序出 TOP | 下方「探查结果」单日 TOP 预览 | ✅ 可出 PV + 设备 UV 的 TOP 榜 |
| 数据限制（隐私 / 上报偏差 / 事件语义） | 下方「限制」 | ✅ 已列 5 条 |
| 正式口径确认（路径/指标/时间窗/归一/形态） | 用户 11-13 选择：App 内置浏览器 / PV+UV TOP100 / 近 30 天 / Excel+合并子域+剔自家 | ✅ |
| 主榜 TOP100（PV + 设备 UV） | `output/mobile_top_pages_20261113.xlsx` 的 `1_总榜_TOP100`；定稿 SQL @Q_MAIN；canonical 脚本 | ✅ |
| 分 OS / 分版本 / 按天拆分 | `2_分OS` / `3_分版本` / `4_按天TOP20` | ✅ |
| 归一/剔除口径说明与异常提示 | `0_摘要` / `5_口径与抽样`（含 TOP1 时间断点、按 UV 参考榜） | ✅ |
| 具体页面 URL 级 TOP | 库内无此粒度（唯一带完整 url 的表已停更） | 不做 + 原因 |

## 抽样复核（正式交付）

**P019 通过**（2026-11-13；主交付取数 30 天共 1,954,172 条明细）。全部用独立窄 SQL 或另一条取数路径对拍，**未为抽样重跑主交付全量**：

1. **独立路径重算**（@Q_SAMPLE_REBUILD：SQL 先按原始 domain 预聚合 63,572 个值 → 本地按同一归一规则重算）vs 脚本逐行流式聚合：归一后 host **49,111**、入榜 PV **1,827,417**、剔自家 **111,313**、无效 **15,442** —— 四项**完全一致**；TOP10 域名与 PV 逐一相同（archiveofourown.org 345,055 / youtube.com 247,607 / x.com 186,961…）。验证流式聚合未丢行、未串组。
2. **末日窄窗**（@Q_SAMPLE_DAY，北京日 11-12）：独立 SQL **50,758 PV / 8,525 设备 / 4,555 原始 domain**，与脚本 `last_day_pv=50,758` 及探查阶段单日数字一致。
3. **youtube 域名族**（@Q_SAMPLE_YOUTUBE，原始 JSON 串 LIKE）：252,937 PV / 44,053 UV / 26 个原始值；其中 **5,330 PV** 属 `accounts.`/`consent.`/`studio.`/`music.` 等功能子域（归一后仍是独立 host，未并入主域），扣除后 **247,607 = 脚本 youtube.com PV** ✅。
4. **x.com 域名族**（@Q_SAMPLE_X 修正版，用 `get()` 精确值/前缀）：**186,961 PV / 36,793 UV** vs 脚本 **186,961 / 36,791**（UV 差 2 = 0.005%，脚本排除 5 条空 device_id 与 60 条全零占位 UUID，独立 SQL 的 `count(distinct)` 口径略宽）。⚠️ **本单抓到一处真实抽样坑**：首版 `ex_char_arg1 LIKE '%x.com/%'` 因原始 JSON 斜杠被转义成 `\/`，**漏掉 89,480 PV**（只命中 `"x.com"` 的 97,298），已改用 `get()` 精确匹配并写入定稿 SQL 注释；不要复用首版条件。
5. **合理性判断**：
   - 无假零：30 天每日 PV 首日 68,347、末日 50,758，按天合计 1,954,172 = 总量，无空窗日；各域名 UV ≤ PV ≤ 总量，无串组/负值。
   - 剔自家 111,313 PV（5.7%）、无效值 15,442 PV（0.8%）均有清单口径，不是「跑不出来」造成的缺失。
   - 设备数两个口径别混：全量 `count(DISTINCT device_id)` = **112,697**（@Q_OVERVIEW，含只访问自家/无效域名的设备）；Excel 摘要的 **103,267** 是「访问过入榜域名的去重设备」，差 9,430 全为只访问自家或无效域名的设备，非漏算。各域名 UV 也只能在这个口径内读。
   - **量级异常已标注而非掩盖**：PV TOP1 `archiveofourown.org` 345,055（占入榜 18.9%）但按 UV 仅 8,849 台；10-14~10-29 日 PV 1.9~2.5 万 / 1.4~1.6 千设备，**10-30 起骤降至 0.05~0.26 万 PV**（@Q_SAMPLE_AO3 逐日实测），单设备 30 天最高 3,740 次访问。成因（埋点/上报/客户端变更/自动化）**未证实，P043 不作因果判断**；交付加「⚠️ 数据质量提示」+ 按 UV 参考榜 + 按天矩阵，禁止读作「最受欢迎网站」。
6. **门禁**：正式导出脚本带 `WF_TASK=T117`，启动即由 `wf.require(T117,'sampled')` 拦截；`--dry-run` 用于抽样阶段，不写文件。

**结论**：数字可用于交付，但 PV TOP1 的时间断点必须随榜一同阅读；若业务要「当前最热站点」，应看近 7 天或按 UV 榜。

## 探查结果（均为只读实测，北京日 2026-11-12 = UTC 11-11 16:00 ~ 11-12 16:00）

### A. 可用主路径：App 内置浏览器访问 `webview_visit`

- 表 `immdata.user_behaviour`，`event_name='webview_visit'`，域名在 `ex_char_arg1` 的 JSON `domain` 键（`get(try_parse_json(ex_char_arg1),'domain')`，值需 `.strip('"')` 与反转义 `\\/`）。
- 单日 **50,758 次访问 / 8,525 台去重设备 / 4,555 个原始 domain 值 / 归一化后 4,199 个 host**；`domain` 100% 有值、`device_id` 100% 有值 → **PV 与设备 UV 都能算**。
- 平台纯移动：android 23,792 / iOS 20,975 / iPadOS 5,991 事件；无桌面混入。版本 `ex_char_arg10`：com 41,739（82.2%）/ cn 9,019（17.8%）。
- 域名值格式混杂：`https://x.com/`、`x.com`、`m.youtube.com`、`www.bing.com` 并存，必须归一化到 host；是否合并子域会改变第一名（不合并：x.com 6,421 > youtube.com 3,925；合并 `m./www./cn.` 后：youtube.com 7,325 > x.com 6,421）。
- 单日 TOP 预览（严格 host，PV / 去重设备 UV）：x.com 6,421 / 2,134；youtube.com 3,925 / 1,561；m.youtube.com 3,024 / 1,507；app.immersivetranslate.com 1,445 / 514；immersivetranslate.com 1,253 / 495；accounts.google.com 1,105 / 522；pixiv.net 1,030 / 147；www.pixiv.net 705 / 278；cn.bing.com 668 / 184；fanfiction.net 663 / 21。
- 剔除自家域名且合并常见子域后 TOP5：youtube.com 7,325 / 3,129；x.com 6,421 / 2,134；bing.com 1,883 / 635；pixiv.net 1,735 / 425；accounts.google.com 1,105 / 522。

### B. 次路径：移动浏览器插件翻译站点 `translate_page_performance.site_host`

- 单日移动端（os_name ∈ android/ios/ipados）**439,681 事件 / 23,900 个 host**；TOP：x.com 51,943、immersivetranslate.com 32,495、unknown 32,349、ipsosinteractive.com 24,048、youtube.com 13,383、pixiv.net 11,559…
- **致命限制**：该类事件 `device_id` 100% 为 NULL、`ex_int_arg1`(userid) 100% 为 NULL → **只能按 PV 排，不能算 UV / 去重设备**。且语义是「网页翻译性能上报所在站点」，不等于「访问」；主翻译事件 `translate_page` 有 device_id 但 `site_host` 全空，两者无法直接按设备关联。
- TOP 里 `unknown` 占 7.4%，`ipsosinteractive.com` / `nielseniq.com` / `decipherinc.com` 等调研站高位（是否为非自然人流量**未证实**，P043）。

### C. 不能用的路径

- `immdata.user_access_log`（唯一有完整 `url` / `site` 字段，18.2 亿行）：`max(created_ts) = 2025-09-05 02:59:06`，2026-11-01 之后 0 行 → **已停更 14 个月，不能用于当前**。
- `official_page_view`：`ex_char_arg1` 有完整 URL、约 65% 有 device_id，但 host 全是自家站（immersivetranslate.com / app. / onboarding. / .cn 等），不是外部网站排行。
- `webview_favourite_item_tap` / `webview_history_tap` / `webview_from_share_extension` 也带 `domain`，但语义是收藏 / 历史 / 分享入口点击，不是「访问」。
- `user_domain_tag_day` 只有域名标签汇总（上报率 ~1.76%），无 host 明细。

## 限制

1. **只有域名级，没有具体页面 URL**：`webview_visit` 的 4,555 个 domain 值中仅 16 个带真实路径（20 次事件，占 0.04%），带完整 URL 的表已停更。所以「TOP 网页」只能理解为「TOP 站点/域名」。
2. **口径是 App 内置浏览器**：`webview_visit` 来自沉浸式翻译 App（package_name 见 `com.immersivetranslate.*` / `transtify` / `browser`），不代表用户在系统浏览器里的全部网页访问；B 路径才是移动浏览器插件，但无 UV。
3. **域名归一规则未定**：协议前缀、尾部斜杠、`www./m./cn.` 子域、自家域名是否剔除，都会改变排名，须用户拍板（本次预览用简单前缀合并，非完整 eTLD+1 解析）。
4. **P037**：移动端埋点 `device_id` 大部分不在 `imt_deviceinfo`，本任务只用埋点 `device_id`，**禁止 JOIN 设备表**当全集；UV 是「访问该域名的去重设备数」，同一设备访问多个域名会各计 1。
5. **非正式交付**：以上为 1 天 / 1 小时短窗探查（P021），仅证明字段可用与量级；正式出数须另定时间窗、按 P019 抽样复核，并注明 `unknown` / 自家域名 / 疑似调研站流量的处理。
