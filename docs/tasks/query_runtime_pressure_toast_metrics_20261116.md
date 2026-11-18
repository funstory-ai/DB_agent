# 「页面任务较多、译文可能稍慢」Toast 弹出次数 / 人均次数 / 「以后不再显示」点击次数

- **需求编号**: T120
- **规范大类**: query
- **状态**: ✅ 已验收（2026-11-16；wf `audit T120` 通过；13:04 用户对弹窗批次回复「已验收」，含本单复核结论）
- **日期**: 2026-11-16
- **定稿 SQL**: `sql/reports/query_runtime_pressure_toast_metrics_20261116.sql`

## 初始需求

「之前有一个弹窗的数据，现在同指标，需另一个弹窗，大意是『页面内容较多，翻译的可能会比较慢』的数据」。
对齐 T118（同语种提示 Toast）的三项指标：① 弹窗弹出次数 ② 人均次数 ③ 用户点击「永不显示」的次数；口径（时间窗、主体、cn/com）沿用 T118，便于两弹窗直接对比。

## 插件代码核对（2026-11-16，F:\extension commit 208d3a82f）

| 项 | 结论 | 代码位置 |
|----|------|----------|
| 文案定位 | 中文 `runtimePressureToast.render` = 「当前页面任务较多，译文显示可能会稍慢。」；英文 "This page has a lot going on, so translations may appear a bit slower." —— 与用户描述一致 | `locales/zh-CN.json:1820`、`locales/en.json:897` |
| 弹窗载体 | toast（`showModal` 的 toast 皮肤），`id='runtimePressure'`，`type='runtimePressure'` | `messages/content_dialog_listeners.ts:216-227`、`src/dialogs/toast.tsx:185` |
| ⚠️ 同一 id 三种文案 | `render`（页面任务多）/ `network`（网络或服务响应慢）/ `renderAndNetwork`（两者都有）共用一个 `toast_id='runtimePressure'`；msg 由 `i18nFormat(messageKey)` 生成，**messageKey / axis 不进埋点 params** | `src/runtime_pressure_toast_state.ts:112-124, 293-299`；`src/analytics/format_self_report.ts:32-36` |
| 埋点字段 | `toast_show`：`toast_id → ex_char_arg1`；`toast_action_click` 另带 `action_id → ex_char_arg2`；`toast_close` 另带 `close_trigger → ex_char_arg2`；`trigger` 独立列；`ex_char_arg10` = cn/com | `src/toast-tracking.ts:5-38`、`src/analytics/format_self_report.ts` |
| trigger | runtimePressure 分支调用 `showToast` 时**未传 `trigger`**（data 只有 type/msg/duration/diagnostics），故库内 `trigger` 预计为空，不能用来区分文案变体 | `src/runtime_pressure_toast_state.ts:293-299`、`messages/content_dialog_listeners.ts:216-227` |
| 「永不显示」按钮 | `action.id='disable_future'`（`createDisableToastAction` → `disableRuntimePressureToast`），与 T118 同名同槽位 | `messages/content_dialog_listeners.ts:111-135, 221-226` |
| 上线时间 | 压力提示本体 2026-06-07 `d19c473e4`；远程策略/不再提示 2026-07-25 `017e40024`；**统一 toast 埋点 2026-08-28 `d7dfec574`**（与 T118 同源）→ 本次与 T118 一样是「有埋点版本」的下限 | `git log -- src/runtime_pressure_toast_state.ts src/toast-tracking.ts` |
| 频控 | `hasShownRuntimePressureToast` / `deliverRuntimePressureToast` 对展示去重，`TOAST_RETRY_COOLDOWN_MS` 冷却 → 人均次数预计远低于 sameLang，不是埋点漏报 | `messages/content_dialog_listeners.ts:272, 398-409`、`src/runtime_pressure_toast_state.ts:271` |

**库内识别口径**：

- 弹出：`event_name='toast_show' AND ex_char_arg1='runtimePressure'`
- 点击永不显示：`event_name='toast_action_click' AND ex_char_arg1='runtimePressure' AND ex_char_arg2='disable_future'`
- 关闭（辅助）：`event_name='toast_close' AND ex_char_arg1='runtimePressure'`

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **主口径**：近 30 个完整北京日 2026-10-17 ~ 2026-11-15（UTC `2026-10-16 16:00:00` ≤ `created_ts` < `2026-11-15 16:00:00`），与 T118 主口径逐日对齐。**辅口径**：埋点上线以来全窗（北京日 2026-08-28 ~ 2026-11-15，起点由 Q0 实测确认）。北京日 D = `(D-1)16:00 ~ D16:00 UTC`；只做粗 UTC 预过滤保分区裁剪，逐日切分在 Python 完成，禁止对 `created_ts` 套 `to_date()` |
| 弹出次数 | `toast_show` + `runtimePressure` 的事件行数（1 行 = 1 次实际展示） |
| 人均次数 | 弹出次数 ÷ 去重「人」数；**人 = 有账号 `ex_int_arg1`(userid>0)，否则 `device_id`**（P018，与 T118 一致）；另给 `device_id` 设备口径作对照 |
| 点击次数 | `toast_action_click` + `runtimePressure` + `disable_future` 的事件行数；另给点击人数、点击数/弹出数比率 |
| 范围 | 国内版 cn + 国际版 com 合计，另按 `ex_char_arg10` 拆分；不筛版本（版本分布单独看，用于解释埋点覆盖） |
| ⚠️ 覆盖范围 | 本数字是**整个 runtimePressure 弹窗**，含 render / network / renderAndNetwork 三种文案；库内埋点不带文案键或 axis，**无法只筛「页面任务较多」那一版**。这是本次与需求的唯一偏差，须在结论中披露，不得当作 render 单版数字使用 |
| 排除 | 其它 `toast_id`（sameLang / aiTranslated / embedded_document_translate 等）；`ex_char_arg1` 为 NULL 或别的值 |
| 只读 | 仅 `immdata.user_behaviour`，`SELECT`；不对时间列套函数；大表先按 `event_name` + 时间收窄 |

## 结果

### 主口径：北京日 2026-10-17 ~ 2026-11-15（30 个完整日，与 T118 主口径逐日对齐）

| 指标 | 数值 | 说明 |
|------|------|------|
| **弹出次数** | **17,086,579** | 日均 569,553 次 |
| **人均次数** | **8.90 次/人** | 17,086,579 ÷ 1,920,747 去重人；设备口径 9.29 次/台（1,838,766 台） |
| **点击「以后不再显示」次数** | **82,055** | 80,068 人点击；点击率 0.48%（点击数/弹出数），点击人数占被弹人数 4.17% |
| 分版 | com 16,917,845 次弹出 / 79,784 次点击（99.01% / 97.23%）；cn 168,734 / 2,271 | 两版 person_uv 不可相加（同一主体跨 cn/com 上报），整窗已去重 |

### 辅口径：埋点上线以来全窗（北京日 2026-08-28 ~ 2026-11-15，80 天）

| 指标 | 数值 |
|------|------|
| 弹出次数 | **37,961,474** |
| 人均次数 | **12.40 次/人**（3,061,599 去重人；设备口径 13.13 次/台、2,891,848 台） |
| 点击「永不显示」次数 | **191,824**（185,480 人，点击率 0.51%） |

按月（北京月）弹出：8 月 408（8-28 起）、9 月 12,849,097、10 月 16,572,570、11 月 1–15 日 8,539,399；四段相加 = 37,961,474，与全窗一次聚合**完全一致**。

### 与 T118（同语种提示 Toast）对比，同口径同时间窗

| 指标 | T118 `sameLang` | T120 `runtimePressure` | 差异 |
|------|-----------------|------------------------|------|
| 弹出次数（30 日） | 12,435,775 | 17,086,579 | **+37.4%** |
| 人均次数（30 日） | 7.78 | 8.90 | +1.12 次 |
| 点击「永不显示」（30 日） | 125,805 | 82,055 | **−34.8%** |
| 点击率（30 日） | 1.01% | 0.48% | 约为一半 |
| 全窗弹出（80 日） | 27,870,423 | 37,961,474 | +36.2% |
| 全窗人均 / 点击 | 10.14 / 298,561 | 12.40 / 191,824 | — |

⚠️ 只陈述数字差异，**不推断原因**（P043）：两弹窗触发条件、频控、文案完全不同，点击率高低不能读作「用户更/更不能接受」。

### 逐日形态

工作日约 60~68 万次/天，周末约 39~47 万次/天（10-25/26、11-1/2、11-8/9 可见周末低谷与周一回升）；点击数稳定在 1,979~3,144 次/天，无假零、无暴涨暴跌。

### 解读注意（P043）

1. **⚠️ 本次数字是整个 `runtimePressure` 弹窗，不是「页面任务较多」单版**。`render`（页面任务较多）/ `network`（网络或服务响应慢）/ `renderAndNetwork`（两者都有）三种文案共用同一 `toast_id`；`showToast` 调用未传 `trigger`（Q3 实测 `trigger` 全 NULL），`ex_char_arg3` 亦全 NULL，埋点没有 messageKey/axis → **库内无法拆分**。用户描述的文案对应 `render`（中英两版均含「页面任务较多」，`renderAndNetwork` 也含）。若只要单版数字，需业务侧在 toast 埋点里补报文案键/axis，或另建可对齐的诊断口径（当前 toast 埋点里没有）。
2. **计数是下限，且全窗含放量爬坡**：统一 toast 埋点由 2026-08-28 `d7dfec574` 引入，而弹窗本体 6-07 已上线、7-25 才加「不再提示」；Q0 显示 8-28 仅 4 次、8-31 397 次、9-01~9-04 数千、9-05 起 9.6 万、9-07 起 50 万+ → 9 月上旬是灰度/远程策略放量，**8 月与 9 月初不可与 10–11 月直接比趋势**。抽样版本 1.32.10~1.35.2。
3. **人均被头部拉高**：单北京日 11-15 有 170,779 个主体共 446,338 次，均值 2.61 次但**中位数仅 1 次**，P90=5、P99=20、P99.9=57、最大 1,153；TOP 1% 主体贡献 14.49% 的弹出、TOP 0.1% 贡献 4.35%（比 T118 的 22.23% / 9.39% 更平缓）。30 天人均 8.90 次是**跨 30 天累计**，不等于每天 8.90 次。极端主体是否机器人/测试流量未证实（P043）。
4. 触发由运行时压力远程策略 + `hasShownRuntimePressureToast` 每会话去重 + 冷却窗控制；**埋点有「每页一次」的频控不等于人均应该低**，一个设备一天打开大量页面仍会多次弹。
5. 关闭原因（`toast_close.ex_char_arg2`）11-15：auto 413,544、close_button 18,254、escape_key 507、replaced 449，合计 432,754 与 Q6 的 `toast_close` 行数一致；绝大多数（95.6%）是自动消失，用户主动点 × 约 4.2%。
6. 主体按 P018：有账号用 `ex_int_arg1`(userid)，否则 `device_id`；person_uv > device_uv 是「同账号多设备合并」与「同设备多账号拆分」的净效应，非 SQL 错误。移动端设备表缺口（P037）本题不触及（不 join `imt_deviceinfo`）。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 定位弹窗与埋点（看插件代码） | 「插件代码核对」表 + `F:\extension` commit 208d3a82f | ✅ |
| 弹出次数 | Q1 / 主口径 17,086,579；辅口径 37,961,474 | ✅ |
| 人均次数 | Q1 / 8.90 次/人（设备 9.29）；辅口径 12.40 | ✅ |
| 点击「永不显示」次数 | Q1 / 82,055（80,068 人）；辅口径 191,824 | ✅ |
| 与 T118 同指标同口径可比 | 口径表 + 「与 T118 对比」表 + Q6 交叉对账 | ✅ |
| ⚠️ 三文案共 id、无法只筛 render 版 | 口径表 + 解读注意 1（**本次唯一偏差，已披露**） | ✅ |
| 时间窗与埋点覆盖说明 | Q0 + 解读注意 2 | ✅ |
| 交付形态 | 用户只问同指标 3 个数字 → 对话汇总，沿用 T118 不出 Excel | ✅ |

## 抽样复核（正式交付）

**P019 PASS**，七条独立核对（结果不落文件）：

1. **字段槽位 / 事件名**：Q3（11-15 北京日）`toast_show` 446,338（com 440,078 + cn 6,260）、`toast_action_click/disable_future` 2,564（2,455 + 109）、`trigger` 与 `ex_char_arg3` 全 NULL、`device_id` 无 NULL；与 Q6 全 toast_id 分布逐格一致，也与第一次独立探测（P0/P1）一致。
2. **跨任务交叉对账**：Q6 同一北京日 `sameLang` 的 show 328,550 / click 3,657，与 T118 任务档抽样记录**逐格完全一致** → 同一份数据、同一 UTC 切分，两个弹窗可比（P044）。
3. **整窗自洽**：Q1 17,086,579 / 82,055 与 Q5 分版加总（16,917,845+168,734、79,784+2,271）**完全相等**。
4. **全窗与逐日/逐月自洽**：Q0 逐日加总 37,961,474 = Q1B；按月 408 + 12,849,097 + 16,572,570 + 8,539,399 = 37,961,474。
5. **逐日加总与整窗**：Q2 的 30 天 × cn/com 共 60 行相加 = 弹出 17,086,579、点击 82,055，与 Q1 逐格相等（无漏日、无重复日、无 cn/com 串组）。
6. **量级与合理性**：点击数 ≪ 弹出数、点击人数 ≪ 被弹人数；逐日 30 天在 39~68 万区间、无假零；11-15 `toast_close` 432,754 ≤ `toast_show` 446,338，关闭原因分项加总 432,754 自洽；Q0 的 9-05 放量是埋点/策略灰度爬坡，已在结论中披露而非抹平。
7. **主体分布**：Q7 单日 170,779 主体 / 446,338 次，P50=1、P90=5、P99=20、max=1,153，TOP1% 贡献 14.49%，与 Q4 TOP20 最大值一致；未掩盖极端值，已在「解读注意 3」披露人均代表性限制。

## 复核（11-16 用户质疑「字数/数字有点高了，确定事件和 SQL 没问题吗」）

结论：**事件没取错、SQL 没算重、数字不修订**；但「看起来偏高」有明确口径原因，见第 6 条。复核查询 V1~V5（`scripts/_tmp_t120_recheck.py`，用完已删；均为只读 SELECT）。

| # | 复核项 | 实测证据 | 判定 |
|---|--------|----------|------|
| 1 | 事件/文案是否唯一 | 全仓 `locales/zh-CN.json` 中「内容/任务较多 + 翻译慢」文案只有 `runtimePressureToast.render` / `.renderAndNetwork`（1820/1822 行）；`render/network/renderAndNetwork` 由 `getRuntimePressureToastKey()` 生成后 `i18nFormat(messageKey)` 塞进 `showTopContentDialog("showToast", {type:'runtimePressure', msg})`；Q6 全 toast_id 分布里 11-15 只有 `runtimePressure` 一个相关 id（446,338），无同义变体、无大小写/空格变体 | ✅ 事件取对 |
| 2 | SQL 独立重算 | 不用 `SUM(CASE)`，两条纯 `COUNT(*)`（只按 `event_name` 前置过滤）重算主窗：`toast_show` **17,086,579**（device_uv 1,838,766）、`toast_action_click+disable_future` **82,055** —— 与 Q1 逐格完全一致；Q0 逐日加总、Q2 逐日×版加总、Q5 分版加总、按月加总此前已全部自洽；Q1 的 `first_show_ts=2026-10-16 16:00:00.003177` / `last_show_ts=2026-11-15 15:59:59.499240` 正好 30 个北京日，非窗口写错 | ✅ 无算重/串组/窗口错 |
| 3 | 重复行 | 11-15 单日 446,338 行，按 `(device_id, created_ts 微秒, toast_id, edition)` 去重复得 445,173 → 同键重复 1,165 行（**0.26%**）；同一设备同一秒 >1 次的仅 1,787 个「设备×秒」组合、涉及 3,921 行（**0.88%**），最大 11 次/秒 | ✅ 重复计数影响 <1%，不是量级来源 |
| 4 | iframe 重复上报 / 测试流量 | 11-15 `toast_show` 的 `main_frame` 全部为 **1**（TOP22 组合无一为 0）；`ex_char_arg10` 仅 cn/com；`site_host` 该事件全为 NULL（字段未填，无法据此排测试域名，但不构成集中证据）；版本 1.34.4 占单日 94.8%、主窗 66.1%，其余为 1.33.3/1.34.2/1.34.3 等同期主力版，非单一异常版本刷量 | ✅ 无 iframe/单版本刷量证据 |
| 5 | 量级锚点（同北京日 11-15） | `translate_page` 3,877,150 次 / 538,571 设备；`translate_page_leave` 2,839,444 / 439,099；**全部** `toast_show` 920,977 / 261,250 → runtimePressure 446,338（占全部 toast 48.5%）、170,800 设备 ≈ **每 8.7 次翻译事件弹 1 次**、约 **31.7% 当日翻译设备**被弹；单日人均 2.61 次、中位数 1 次、TOP1% 主体仅贡献 14.49% | ✅ 有基数支撑，不是「每页都弹」或头部刷量 |
| 6 | 为什么仍比直觉高（口径原因） | ① **本次是三种文案合并**，不是「页面任务较多」单版；② 代码策略 `resolveRuntimePressureToastPolicy()` 默认 `enabled: true`（`config?.enabled !== false`），`handleRuntimePressureToast` 挂在 `translation_callback` / `request_error` / `request_exception`（`core.ts:3807,3844,4601`），冷却仅 `TOAST_RETRY_COOLDOWN_MS=3000`、`TOAST_DURATION_MS=2500`，`cleanEngineCtx` 会 `resetRuntimePressureToastState()` 并通知 top frame 重置 `hasShownRuntimePressureToast`（`mod.ts:780`）→ 一个设备连续浏览/翻译可多次触发；③ 主力版本 1.34.4 覆盖 66.1%。⚠️ 线上**远程策略实际取值读不到**，这里只是代码默认值与调用链，不等于线上配置实测（P043） | 事实 + 标注推测边界 |

**对用户问题的直接回答**：可以确认 `ex_char_arg1='runtimePressure'` 就是目标弹窗、SQL 口径与 T118 一致且经多种独立算法复算一致、数字不用改；如果用户心里预期的是「只弹『页面内容较多』那一句」，那 17,086,579 必然偏高，因为库内拆不出单版（解读注意 1），需业务侧补埋点。

## 定稿 SQL

`sql/reports/query_runtime_pressure_toast_metrics_20261116.sql`（Q0~Q7；`@Qn` 标记同行带中文说明，程序分段执行时须从 `SELECT` 起截取）。全窗/分版/主体分布为对话补充查询，口径与 Q1 一致。
