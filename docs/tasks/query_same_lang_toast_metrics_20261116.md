# 同语种提示 Toast 弹出次数 / 人均次数 / 「以后不再显示」点击次数

- **需求编号**: T118
- **规范大类**: query
- **状态**: ✅ 已验收（2026-11-16 用户确认；wf `audit T118` 通过）
- **日期**: 2026-11-16
- **定稿 SQL**: `sql/reports/query_same_lang_toast_metrics_20261116.sql`

## 初始需求

用户给出截图（推文吐槽「一进入网址就自动弹出来这个提示窗口」）：弹窗文案
"The detected source language, Simplified Chinese, matches the current target language,
Simplified Chinese. This page may have nothing to translate." + 按钮 "Don't show this again"。
要求：**看下插件代码**，然后给出 ① 弹窗的弹出次数 ② 人均次数 ③ 用户点击「永不显示」的次数。

## 插件代码核对（2026-11-16，F:\extension 已 git pull 至 208d3a82f / 2026-11-13）

| 项 | 结论 | 代码位置 |
|----|------|----------|
| 文案 | `sameLangNoTranslate` | `locales/en.json:895` |
| 按钮文案 | `neverShowFuture`（中文「以后不再显示」） | `locales/en.json:900` |
| 弹窗载体 | 是 **toast**（`showModal` 的 toast 皮肤），不是 modal 弹窗；`id='sameLang'`，默认 `trigger='same_language_check'` | `messages/content_dialog_listeners.ts:170-205`、`src/dialogs/toast.tsx:185` |
| 触发条件 | `sameLangCheck===true`（默认 true）且 `disableSameLang!==true` 且 页面语言≠auto 且 源/目标语言相同；翻译段落累计有效字符 <100 才弹（≥100 直接 reject） | `src/html-engine/mod.ts:591-610`、`src/same_language_check_state.ts` |
| 「永不显示」按钮 | `action.id='disable_future'`，点击把 `sameLangCheck` 置 false | `messages/content_dialog_listeners.ts:111-135, 203` |
| 埋点 | `reportToastEvent(id, event, trigger, params)` → `reportSingle({key:'toast_show' / 'toast_action_click' / 'toast_close'})` | `src/toast-tracking.ts:5-38` |
| 字段映射 | `toast_id → ex_char_arg1`；`action_id → ex_char_arg2`；`close_trigger → ex_char_arg2`；`trigger` 保留独立列；`ex_char_arg10` = cn/com | `src/analytics/format_self_report.ts` |
| 埋点上线 | `git log -S` / 文件历史：`src/toast-tracking.ts` 由 2026-08-28 `d7dfec574 feat: 统一 showToast 事件上报` 引入；**更早版本的同语种 toast 无这三个事件**，故计数是有埋点版本的下限 | `git log -- src/toast-tracking.ts` |

**库内识别口径**：

- 弹出：`event_name='toast_show' AND ex_char_arg1='sameLang'`
- 点击永不显示：`event_name='toast_action_click' AND ex_char_arg1='sameLang' AND ex_char_arg2='disable_future'`
- 关闭（辅助）：`event_name='toast_close' AND ex_char_arg1='sameLang'`，关闭原因在 `ex_char_arg2`

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **主口径**：近 30 个完整北京日 2026-10-17 ~ 2026-11-15（UTC `2026-10-16 16:00:00` ≤ `created_ts` < `2026-11-15 16:00:00`）。**辅口径**：埋点上线以来全窗（起点由 Q0 实测确定）。北京日 D = `(D-1)16:00 ~ D16:00 UTC`；只做粗 UTC 预过滤保分区裁剪，逐日切分在 Python 完成，禁止对 `created_ts` 套 `to_date()` |
| 弹出次数 | `toast_show` + `sameLang` 的事件行数（1 行 = 1 次实际展示） |
| 人均次数 | 弹出次数 ÷ 去重「人」数；**人 = 有账号 `ex_int_arg1`(userid>0)，否则 `device_id`**（P018）；另给 `device_id` 设备口径作对照 |
| 点击次数 | `toast_action_click` + `sameLang` + `disable_future` 的事件行数；另给点击人数、点击数/弹出数比率 |
| 范围 | 国内版 cn + 国际版 com 合计，另按 `ex_char_arg10` 拆分；不筛版本（版本分布单独看，用于解释埋点覆盖） |
| 排除 | 其它 `toast_id`（aiTranslated / runtimePressure / embedded_document_translate 等）；`toast_show` 里 `ex_char_arg1` 为 NULL 或别的值 |
| 只读 | 仅 `immdata.user_behaviour`，`SELECT`；不对时间列套函数；大表先按 `event_name` + 时间收窄 |

## 结果

### 主口径：北京日 2026-10-17 ~ 2026-11-15（30 个完整日）

| 指标 | 数值 | 说明 |
|------|------|------|
| **弹出次数** | **12,435,775** | 日均 414,526 次 |
| **人均次数** | **7.78 次/人** | 12,435,775 ÷ 1,599,100 去重人；设备口径 8.04 次/台（1,547,359 台） |
| **点击「以后不再显示」次数** | **125,805** | 109,863 人点击；点击率 1.01%（点击数/弹出数），点击人数占被弹人数 6.87% |
| 分版 | com 12,175,323 次弹出 / 123,384 次点击（占 97.91% / 98.08%）；cn 260,452 / 2,421 | 两版 person_uv 相加 1,605,119 比整窗去重 1,599,100 多 6,019，是同一主体跨 cn/com 上报，整窗已去重，不可相加 |

### 辅口径：埋点上线以来全窗（北京日 2026-08-28 ~ 2026-11-15，80 天）

| 指标 | 数值 |
|------|------|
| 弹出次数 | **27,870,423** |
| 人均次数 | **10.14 次/人**（2,749,659 去重人） |
| 点击「永不显示」次数 | **298,561**（259,053 人，点击率 1.07%） |

按月（北京月）弹出：8 月 902（8-28 起）、9 月 9,633,493、10 月 12,099,235、11 月 1–15 日 6,136,793；四段相加 = 27,870,423，与全窗一次聚合**完全一致**。

### 逐日形态

工作日约 43~50 万次/天，周末约 31~35 万次/天（10-18/19、10-25/26、11-1/2、11-8/9 可见周末低谷与周一回升），无明显暴涨暴跌；点击数稳定在 3,500~4,700 次/天。

### 解读注意（P043）

1. **计数是下限**：`toast_show` / `toast_action_click` 由 2026-08-28 `d7dfec574` 引入，8-28 之前版本弹了但无埋点；抽样中 `toast_show` 版本 1.32.10~1.35.2，而 `toast_action_click` 仅 1.33.1~1.35.2，老版本点击也漏报。所以「弹出次数」是**有埋点版本的实际展示次数**，不是全部历史。
2. **人均被头部拉高**：单北京日 11-15 有 98,153 个主体共 328,550 次，均值 3.35 次但**中位数仅 1 次**，P90=6、P99=29、P99.9=108、最大 2,871；TOP 1% 主体贡献 22.23% 的弹出、TOP 0.1% 贡献 9.39%。即「多数人一天只被弹 1 次，少数设备/账号被反复弹」（是否机器人/测试流量未证实，P043）。30 天人均 7.78 次是**跨 30 天累计**，不等于每天 7.78 次。
3. 触发条件为「页面语言 = 目标语言 + 翻译出的有效字符 <100」，即**几乎没译出内容时才提示**，不是每次进网页都弹；开关 `sameLangCheck` 默认 true（截图用户遇到的是默认开）。
4. 人 = 有账号用 `ex_int_arg1`(userid)，否则 `device_id`（P018）；person_uv > device_uv 是同一设备多账号拆分与同账号多设备合并的净效应，非 SQL 错误。
5. 关闭原因（`toast_close.ex_char_arg2`）11-15：auto 259,246、replaced 21,207、close_button 19,966 —— 绝大多数是 2.5s 自动消失，用户主动点 × 约 6%。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 看插件代码定位弹窗与埋点 | 「插件代码核对」表 + `F:\extension` commit 208d3a82f | ✅ |
| 弹出次数 | Q1 / 主口径 12,435,775；辅口径 27,870,423 | ✅ |
| 人均次数 | Q1 / 7.78 次/人（设备 8.04）；辅口径 10.14 | ✅ |
| 点击「永不显示」次数 | Q1 / 125,805；辅口径 298,561 | ✅ |
| 时间窗与埋点覆盖说明 | Q0/按月覆盖 + 结果「解读注意」1 | ✅ |
| 交付形态 | 用户只问 3 个数字 → 对话汇总，未出 Excel | ✅ |

## 抽样复核（正式交付）

**P019 PASS**，五条独立核对：

1. **字段槽位/事件名**：11-15 北京日 Q3 → `toast_show/sameLang` 328,550（com 319,692 + cn 8,858）、`toast_action_click/sameLang/disable_future` 3,657（3,577 + 80），`trigger` 全部 `same_language_check`，`device_id` 无 NULL；与第一次独立探测（全 toast 事件 GROUP BY）逐格一致。
2. **整窗自洽**：Q1 整窗 12,435,775 / 125,805 与「分版 GROUP BY ex_char_arg10」加总（12,175,323+260,452、123,384+2,421）**完全相等**。
3. **全窗与逐月自洽**：按月 902 + 9,633,493 + 12,099,235 + 6,136,793 = 27,870,423，与全窗一次聚合 27,870,423 相等。
4. **逐日加总与整窗**：Q2 的 30 天 × cn/com 共 60 行按日相加 = 弹出 12,435,775、点击 125,805，与 Q1 整窗聚合**逐格完全相等**（无漏日、无重复日、无 cn/com 串组）。
5. **量级与合理性**：点击数 ≪ 弹出数、点击人数 ≪ 被弹人数；逐日 30 天在 31~51 万区间、无假零；按主体分布检查出极端值（max 2,871/日）并已在结论中披露，未掩盖。

## 定稿 SQL

`sql/reports/query_same_lang_toast_metrics_20261116.sql`（Q0~Q4；`@Qn` 标记同行带中文说明，程序分段执行时须从 `SELECT` 起截取）。全窗/分版/主体分布为对话补充查询，口径与 Q1 一致。
