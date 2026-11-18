# 术语智能提取告知 Toast（「术语提取中...」）弹出次数 / 人均次数 / 「以后不再显示」点击次数

- **需求编号**: T121
- **规范大类**: query
- **状态**: ✅ 已验收（2026-11-16；wf `audit T121` 通过；13:04 用户明确回复「已验收」确认）
- **日期**: 2026-11-16
- **定稿 SQL**: `sql/reports/query_article_terminology_prep_toast_metrics_20261116.sql`

## 初始需求

「还有一个类似的术语智能提取会有个告知，这个事件也拉一下」。承接 T118（同语种提示）/ T120（运行时压力提示）的**同指标**：① 弹出次数 ② 人均次数 ③ 点「永不显示」次数；口径沿用前两单，便于三弹窗对比。

## 插件代码核对（2026-11-16，F:\extension commit 208d3a82f）

| 项 | 结论 | 代码位置 |
|----|------|----------|
| 弹窗定位 | 「术语智能提取」准备阶段告知 toast，文案 `articleTerminology.preparing` = 中文「术语提取中...」/ 英文 "Extracting terms..." | `locales/zh-CN.json:2230`、`locales/en.json:1751` |
| 载体与 id | toast（`showToast`），`id='article-terminology-preparing'`，`autoClose: false`（由 `finish()` 后 3 秒定时关闭） | `src/article-terminology/preparation-notice.ts:89-113` |
| ⚠️ 按钮 action_id | **`never-show-future`**（连字符），不是 T118/T120 的 `disable_future`；点击写本地 `articleTerminologyPreparationNoticeDismissed=true`，之后永久不再弹 | `src/article-terminology/preparation-notice.ts:6, 95-109` |
| 触发条件 | `shouldShowArticleTerminologyPreparationNotice`：智能提取开启 + AI 批量模式 = `recommended`（增强模式）+ 正文长度达阈值；**每个文档最多弹一次**（`hasShownInDocument`），且 dismissed 后不再弹 | `src/article-terminology/preparation-notice.ts:16-25, 72-73, 85-87` |
| 埋点 | 走同一 `showToast` → `toast_show` / `toast_action_click` / `toast_close`；`toast_id → ex_char_arg1`、`action_id/close_trigger → ex_char_arg2`、`ex_char_arg10`=cn/com；**本 toast 调用未传 `trigger`** | `src/dialogs/toast.tsx:211,259,396`、`src/analytics/format_self_report.ts:32-36` |
| 上线时间 | 文件历史 2026-09-08 ~ 09-18（术语提取功能开发期）；统一 toast 埋点 2026-08-28 `d7dfec574` 已存在 → 本弹窗全程有埋点，但**功能本身是实验性、站点受限**（设置项文案：「智能提取术语当前为实验性功能，目前已支持 AO3 站点」`locales/zh-CN.json:1399`） | `git log -- src/article-terminology/preparation-notice.ts` |
| 其它术语 toast（排除） | `articleTerminologyTranslationUpdated`（译文已更新）/ `articleTerminologySyncPending`（保存同步中）/ `articleTerminologySaveFailed` / `articleTerminologyUndoFailed` 均为操作结果提示，**不是智能提取告知**，且没有「永不显示」按钮 | `src/article-terminology/controller.ts:3422-3464` |

**库内识别口径**：

- 弹出：`event_name='toast_show' AND ex_char_arg1='article-terminology-preparing'`
- 点击永不显示：`event_name='toast_action_click' AND ex_char_arg1='article-terminology-preparing' AND ex_char_arg2='never-show-future'`
- 关闭（辅助）：`event_name='toast_close' AND ex_char_arg1='article-terminology-preparing'`

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | **主口径**：近 30 个完整北京日 2026-10-17 ~ 2026-11-15（UTC `2026-10-16 16:00:00` ≤ `created_ts` < `2026-11-15 16:00:00`），与 T118/T120 主口径逐日对齐。**辅口径**：全窗北京日 2026-08-28 ~ 2026-11-15（80 天，UTC `2026-08-27 16:00:00` 起）；Q0 实测**功能自 2026-09-07 才有数据**，8-28~9-06 为空窗。北京日 D = `(D-1)16:00 ~ D16:00 UTC`；只做粗 UTC 预过滤保分区裁剪，禁止对 `created_ts` 套 `to_date()` |
| 弹出次数 | `toast_show` + 该 id 的事件行数（1 行 = 1 次实际展示） |
| 人均次数 | 弹出次数 ÷ 去重「人」数；**人 = 有账号 `ex_int_arg1`(userid>0)，否则 `device_id`**（P018，与 T118/T120 一致）；另给 `device_id` 设备口径 |
| 点击次数 | `toast_action_click` + 该 id + **`ex_char_arg2='never-show-future'`** 的事件行数；另给点击人数、点击数/弹出数比率 |
| 范围 | 国内版 cn + 国际版 com 合计，另按 `ex_char_arg10` 拆分；不筛版本（版本分布单独看） |
| 排除 | 其它 toast_id（特别是其它 4 个术语相关 toast）；`ex_char_arg1` 为 NULL 或别的值 |
| 只读 | 仅 `immdata.user_behaviour`，`SELECT`；不对时间列套函数；大表先按 `event_name` + 时间收窄 |

## 结果

### 主口径：北京日 2026-10-17 ~ 2026-11-15（30 个完整日，与 T118/T120 逐日对齐）

| 指标 | 数值 | 说明 |
|------|------|------|
| **弹出次数** | **5,681** | 日均 189 次 |
| **人均次数** | **17.37 次/人** | 5,681 ÷ 327 去重人；设备口径 16.28 次/台（349 台） |
| **点击「以后不再显示」次数** | **42** | 39 人点击；点击率 0.74%（点击数/弹出数），点击人数占被弹人数 11.93% |
| 分版 | com 5,676 次弹出 / 42 次点击（99.91% / 100%）；cn 5 / 0 | 该告知几乎只在国际版出现 |

### 辅口径：全窗（北京日 2026-08-28 ~ 2026-11-15，80 天；**实际有数据自 9-07 起**）

| 指标 | 数值 |
|------|------|
| 弹出次数 | **11,378** |
| 人均次数 | **18.78 次/人**（606 去重人；设备口径 16.63 次/台、684 台） |
| 点击「永不显示」次数 | **106**（98 人，点击率 0.93%） |

按月（北京月）弹出：9 月 1,301（9-07 起）、10 月 8,629、11 月 1–15 日 1,448；相加 = 11,378，与全窗一次聚合完全一致。8-28~9-06 无数据（功能 9 月才上线），不是漏数。

### 三个弹窗对比（同口径、同 30 日窗）

| 指标 | T118 `sameLang` | T120 `runtimePressure` | T121 术语提取告知 |
|------|-----------------|------------------------|-------------------|
| 弹出次数 | 12,435,775 | 17,086,579 | **5,681**（约为前两者的 0.046% / 0.033%） |
| 人均次数 | 7.78 | 8.90 | **17.37** |
| 点「永不显示」 | 125,805 | 82,055 | **42** |
| 点击率 | 1.01% | 0.48% | 0.74% |
| 按钮 `action_id` | `disable_future` | `disable_future` | **`never-show-future`** |

⚠️ **人均 17.37 不是「用户被打扰更多」**：分母只有 327 人（前两单是 160 万 / 192 万人），是极少数重度主体反复触发；且点过「以后不再显示」后永久不再弹，分母会被截断。三个弹窗的人均/点击率**不可直接横向解读为体验好坏**（P043）。

### 逐日形态与一处待解释台阶

10 月上中旬约 170~530 次/天，**10-30 起降到 20~80 次/天**，**11-15 单日又跳到 437 次**（前一日 22 次，约 20 倍）。Q3 显示 11-15 的 437 次只来自 **59 个设备**、版本仍为 1.34.2~1.34.4、`ex_char_arg10` 全 com、`site_host` 该事件全 NULL（字段未填）；Q6 显示单日单个主体最多 77 次、P50=4、P90=11。**没有证据判断是回归测试、内部设备还是功能放量**，本档只披露不归因（P043）。若该日属测试流量，主口径 5,681 会相应高估，但前两单同窗未做剔除，为保持同口径可比，本次也不擅自剔除（P025）。

### 解读注意（P043）

1. **⚠️ 按钮 id 与 T118/T120 不同**：本弹窗是 `never-show-future`，Q1 的 `all_action_click_cnt=42` 与 `never-show-click_cnt=42` 相等 → 该 toast 的 action_click 全部来自「以后不再显示」，没有别的按钮；Q3 单日也只出现这一个 action_id。若沿用 `disable_future` 会得到 0 次。
2. **主体方向相反**：本弹窗 `person_uv(327) < device_uv(349)`，而 T118/T120 相反。Q3 抽样 11-15 的 437 行 `with_userid_rows=437`（**全部带 userid**）→ 主体几乎都归到账号，同账号多设备合并占主导；这是数据特性，不是 SQL 错，也不能据此推断「该功能仅登录用户可用」（无权限侧证据）。
3. **覆盖与量级**：统一 toast 埋点 8-28 已有，但功能文件 9-08~09-18 才落地、库内首条 9-07（1 次）；Q0 的 9 月每天几十~百余次属灰度/实验性功能（设置文案：智能提取术语为实验性、目前支持 AO3 站点）。**8 月底~9 月初不可与 10–11 月比趋势**。
4. **触发条件很窄**（代码事实）：智能提取开启 + AI 批量模式 `recommended`（增强模式）+ 正文长度达阈值 + 每个文档最多弹一次 + dismissed 后永久不弹。这解释了为什么总量只有前两个弹窗的约两千~三千分之一。
5. **跨日关闭**：Q2 中 11-05 close=168 > show=159、11-06 close=174 > show=157，是 toast 跨北京日边界展示后关闭（`autoClose:false`、`finish()` 后 3 秒 `programmatic` 关闭，Q3 单日 programmatic 404 次），不是重复计数；11-15 关闭分项 404+11+1=416 与 Q2 close_cnt 416 逐格一致。
6. 关闭原因 11-15：`programmatic` 404（自动收起）、`close_button` 11（用户点 ×）、`replaced` 1；主动点 × 约 2.6%，远低于 T118/T120 的 4~6%，因本弹窗主要靠程序收起。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 定位弹窗与埋点（看插件代码） | 「插件代码核对」表 + Q5 事件识别 | ✅ |
| 弹出次数 | Q1 / 主口径 5,681；辅口径 11,378 | ✅ |
| 人均次数 | Q1 / 17.37 次/人（设备 16.28）；辅口径 18.78 | ✅ |
| 点击「永不显示」次数 | Q1 / 42（39 人）；辅口径 106；按钮 id 已核对 | ✅ |
| 与 T118/T120 同口径可比 + 不可横向解读说明 | 口径表 + 三弹窗对比表 + 解读注意 | ✅ |
| 11-15 台阶异常披露 | 「逐日形态」+ 抽样复核 7 | ✅ |
| 交付形态 | 用户只问「也拉一下」→ 对话汇总，沿用前两单不出 Excel | ✅ |

## 抽样复核（正式交付）

**P019 PASS**，七条独立核对（结果不落文件）：

1. **按钮 id / 字段槽位**：Q3（11-15）`toast_action_click` 的 `ex_char_arg2` 只有 `never-show-future` 一种，Q1 `all_action_click_cnt = never_show_click_cnt = 42` 互相印证；`trigger`、`ex_char_arg3` 全 NULL，`device_id` 无 NULL，版本 1.34.2~1.34.4。
2. **事件识别/排除**：Q5 主窗内所有含 `termin` 的 toast_id 只有 4 类，目标是唯一带「永不显示」的告知（5,681 show / 5,145 close / 42 action_click）；其余 `articleTerminologyTranslationUpdated`(355 show)、`SaveFailed`(25)、`UndoFailed`(2) 均为操作结果提示，已排除。
3. **整窗自洽**：Q1 5,681 / 42 与 Q4 分版加总（5,676+5、42+0）逐格相等。
4. **全窗与逐日/逐月自洽**：Q0 逐日加总 11,378 = Q1B；按月 1,301 + 8,629 + 1,448 = 11,378；Q0 主窗逐日加总 5,681 = Q1。
5. **逐日加总与整窗**：Q2 的 30 天 × cn/com 共 32 行相加 = 5,681 / 42，与 Q1 逐格相等（无漏日、无串组）。
6. **窗口与量级**：Q1 `first_show_ts=2026-10-16 16:04:05` / `last_show_ts=2026-11-15 15:59:11`，正好落在 30 个北京日内；点击数 ≪ 弹出数，无假零（9-07 起每天≥1）。
7. **合理性异常已披露未掩盖**：Q6 单日 59 主体 / 437 次，P50=4、P90=11、max=77；11-15 单日 437 次相对前一日 22 次约 20 倍台阶，已在结论中列为**待解释但不归因**；`person_uv < device_uv`、close > show 跨日现象均已给出机制解释。

## 定稿 SQL

`sql/reports/query_article_terminology_prep_toast_metrics_20261116.sql`（Q0~Q6；`@Qn` 标记同行带中文说明，程序分段执行时须从 `SELECT` 起截取）。
