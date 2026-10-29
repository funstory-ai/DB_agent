# 看板：各真实模型翻译时长与报错率（网页）

- **需求编号**: T080
- **规范大类**: `dashboard`
- **状态**: ✅ **中间表已落库并通过写仓验收**（2026-10-21）；Superset 尚未挂板
- **日期**: 2026-10-21
- **模型维度决策**: 用户确认「就要 gpt-6-luna 这种真实模型名」→ 采用 **dim 映射表**（非服务名裸当维度、也非 CASE 裸写 ETL）
- **定稿 SQL（仅此 2 个）**：
  1. 写仓 ETL：`sql/reports/t080_translate_model_perf_etl.sql` — dim 表 + 日表 + 90 天回填 + 日更 TASK + 验收
  2. Superset 挂板：`sql/reports/t080_translate_model_perf_board.sql` — `ds_*` 数据集

## 初始需求

看板观测**各模型**的：① 翻译时长 ② 报错率。

| 问 | 答 |
|----|-----|
| 「各模型」指什么 | **真实模型**（gpt-6-luna / DeepSeek-V4.1-Flash 这类）；2026-10-21 追加确认 |
| 业务范围 | **只要网页**；漫画（`track_translate_manga_data`）不纳入 |
| 是否加拆分维度 | 不用 |
| 流程 | 先占号实测，再定中间表 |
| 模型维度做法 | **dim 表**（可维护；改名只改 dim + 回填，不必改 ETL 正文） |

## 事件与字段

来源 `F:\extension`（commit `5ba7d8c` / 2026-10-20；**`git pull` 失败 502，未拉最新**）：

- 事件定义 `src/analytics/first_visible_translation.ts`
- 槽位映射 `src/analytics/format_self_report.ts`
- 说明文档 `docs/translation-performance-tracking.md`
- 服务→模型映射 `default_config.json` 的 `translationServices[*].model`

主事件：`event_name = 'track_translate_page_data'`（网页）

| 字段 | 含义 |
|------|------|
| **顶层 `translation_service`** | **归一化翻译服务**（近 2 周 82 个取值）← **维度源** |
| `ex_char_arg1` | 同上但未归一（22,268 个随机后缀值），**不要直接用** |
| `ex_char_arg2` | `success` / `failure` ← 报错率依据 |
| `ex_char_arg8` | free-model 真实 provider —— **实测全空（0/2,824,221），不可用** |
| `ex_int_arg2` | `first_visible_total_ms` 端到端总时长（含页面侧开销，作副指标） |
| `ex_int_arg3` | `first_visible_request_ms` **模型侧请求耗时 → 时长主指标** |

## 三个踩过的坑（改口径前必读）

### 坑 1 · 报错率不能用「有时长」的子集算

| result | 事件数 | 缺 `request_ms` | 缺失率 |
|--------|--------|------------------|--------|
| success | 2,744,596 | 3,965 | **0.14%** |
| failure | 79,625 | 4,262 | **5.35%** |

失败行更容易没有耗时字段。一旦 `WHERE ex_int_arg3 > 0` 筛行，
**系统性漏失败样本、报错率被算低**（免费档实测 0.61% → 0.46%）。

→ ETL 取**全量行**，耗时指标用条件聚合只在 `request_ms > 0` 时计入，报错率取全量行。

### 坑 2 · 分位数不可跨日再聚合

日表存当日 `p50`/`p95`，**只能给按日折线逐点读**。近窗汇总若要做「整体耗时」，
只能用 `SUM(req_ms_sum)/SUM(req_ms_cnt)` 加权均值；**禁止** `AVG(req_ms_p50)`。
board 里 `worst_day_p95_30d` 已注明是「近 30 天最差的单日 p95」，不是 30 天整体 p95。

### 坑 3 · `model_group` 不能进 grain（实测踩到）

同一模型可能被不同档位服务共用：`gpt-6-luna` 同时来自 `openai`(builtin) 与 `openai-pro`(pro)。
把 `model_group` 放进 `GROUP BY` → 同一模型裂成 2 行，**14 日窗口 858 行 vs 854 distinct**。

→ grain 定为 `dt_bj × model_label`；`model_group` 按 `max>pro>trial>free>custom>builtin` 优先级取一个，
全部档位另存 `groups_all` 备查。修正后 14 日 854 = 854 ✅。

### 覆盖偏差（必须写进看板说明）

事件需 `enableSelfServiceReport` + `enablePerformanceReport` 同时开启且 telemetry 同意；
`skip`（缓存命中）不上报。→ **报错率 = 已上报会话内的失败率，不是全量翻译失败率。**

## 中间表

| 表 | 角色 | 粒度 | 用途 | TASK（上海） |
|----|------|------|------|--------------|
| `immdata.imm_translate_model_map` | dim | `translation_service` 唯一 | 服务→真实模型，**手工维护** | 无（人工 UPDATE） |
| `immdata.imm_translate_model_daily_perf` | kpi + 挂板主读 | `dt_bj` × `model_label` | 按日规模/报错率/耗时；近窗汇总 | `update_imm_translate_model_daily_perf` **每天 07:30** |

日表主要列：`events` / `failure_events` / `error_rate` / `req_ms_cnt` / `req_ms_sum` /
`req_ms_avg` / `req_ms_p50` / `req_ms_p95` / `svc_cnt` / `src_service` / `failure_missing_ms`。

### dim 表的来历与维护

- 种子 77 行来自插件 `default_config.json`（25 个服务能取到 model，其余为 NULL）
- 用户自建 `-custom` 服务模型未知 → NULL；免费混池无模型名 → NULL → 展示为 `[未映射] <服务名>`
- ⚠️ **这是「当前配置快照」**：今天 `openai-pro=gpt-6-luna`，历史日可能已换。
  模型改名后：① `UPDATE dim` ② 按 ETL §5.4 重算受影响区间（勿跑全文）

## 需求覆盖对照

| 需求# | 初始原文 | 字段 | 数据集 | 状态 |
|-------|----------|------|--------|------|
| 1 | 翻译时长 | `req_ms_p50` / `req_ms_p95`（`ex_int_arg3` 条件聚合） | `ds_translate_model_perf_day` | ✅ |
| 2 | 报错率 | `SUM(failure_events)/SUM(events)`（`ex_char_arg2='failure'`） | `ds_translate_model_perf_day` | ✅ |
| — | 「各模型」维度的真实模型名 | `model_label`（dim 映射） | 同上 | ✅ |

## 数据集一览

| 数据集 | 读什么 | 挂板性质 |
|--------|--------|----------|
| **`ds_translate_model_perf_day`** | `imm_translate_model_daily_perf` 滚动 90 天，**已收窄为主流通道** | 【可挂 Superset】图 1–2 |
| **`ds_translate_model_perf_window`** | 同上，近 30 天 `GROUP BY model_label`，**同套收窄规则** | 【可挂 Superset】图 3–5（无 `dt_bj`，禁按日折线） |
| `ds_translate_model_perf_recon` | 日表 SUM vs `user_behaviour` 直查 | 【仅探查·勿挂板】抽日对账 |

> 收窄只发生在**这两个 Dataset 的展示层**；底层 `imm_translate_model_daily_perf` 仍是全量，
> 所以对账必须用未过滤的直查表（见 §「抽日对账」）。详见 §「口径收窄：只看主流通道」。

### ⚠️ 两个 Dataset 的字段对照（建图前先看，最容易选错）

`model_label` / `model_group` **两边同名**，所以选错 Dataset 时这两个不会报错，
要等到用到 `events`/`failure_events` 才炸。对照如下：

| 字段 | `ds_…_day` | `ds_…_window` |
|------|-----------|---------------|
| 日期 | `dt_bj` | **无**（只有 `last_day` 表示该模型最后有数据的日子，**不是时间轴**） |
| 事件量 | `events` | `events_30d` |
| 失败数 | `failure_events` | `failure_30d` |
| 耗时分子/分母 | `req_ms_sum` / `req_ms_cnt` | `req_ms_sum_30d` / `req_ms_cnt_30d` |
| 分位数 | `req_ms_p50` / `req_ms_p95` | 只有 `worst_day_p95_30d`（近窗最差**单日** p95） |
| 用在哪 | **图 1a / 1b / 2**（按日折线） | **图 3 / 4 / 5**（Big Number / Table） |

**典型报错**（2026-10-21 实挂踩到）：

```
column failure_events doesn't exist
SELECT to_start_of_day(TO_DATETIME("last_day")) AS __timestamp, SUM(failure_events)/SUM(events)
```

→ 报错 SQL 里出现 `last_day` 就说明**这张图选了 window Dataset**，改成 `ds_…_day` 即可。
（Superset 新建图会默认继承上一次选的 Dataset，很容易忘记切。）

同时建议：**把 window Dataset 里 `last_day` 的 Temporal 勾去掉**——它不是时间轴，
勾了会让 Superset 误以为这个 Dataset 可以按时间画折线。

## Superset 挂板对照表（唯一挂板依据）

| 图# | 需求来源 | 指标 | 数据集 | 图表 | X | Metrics（Y） | Series | Dashboard Filter | 备注 |
|-----|----------|------|--------|------|---|--------------|--------|------------------|------|
| 1a | **需求#1** | 翻译时长 p50 | `ds_translate_model_perf_day` | Line | `dt_bj` | `AVG(req_ms_p50)/1000`（秒） | **`model_label`** | `model_label` + `model_group` + 时间 | **必须设 Series**；SERIES LIMIT=10 只显示最慢 10 个，其余走 Filter |
| 1b | **需求#1** | 翻译时长 p95 | `ds_translate_model_perf_day` | Line | `dt_bj` | `AVG(req_ms_p95)/1000`（秒） | **`model_label`** | 同上 | 同上 |
| 2 | **需求#2** | 报错率 | `ds_translate_model_perf_day` | Line | `dt_bj` | **`SUM(failure_events)/SUM(events)`** | **`model_label`** | 同上 | **禁止 `AVG(error_rate)`**；SERIES LIMIT=10 |
| 3 | **加项·近窗卡片** | 近 30 日报错率 | `ds_translate_model_perf_window` | Big Number | `-` | `SUM(failure_30d)/SUM(events_30d)` | `-` | `model_label` + `model_group` | 加项：需求原文未要近窗卡片 |
| 4 | **加项·近窗卡片** | 近 30 日平均请求耗时 | `ds_translate_model_perf_window` | Big Number | `-` | **`SUM(req_ms_sum_30d)/SUM(req_ms_cnt_30d)`** | `-` | 同上 | 加项；**禁止 `AVG(avg_req_ms_30d)`**（对不同模型再平均） |
| 5 | **加项·模型排行** | 模型错误率/耗时排行 | `ds_translate_model_perf_window` | Table | `-` | `error_rate_30d` / `avg_req_ms_30d` | `-` | 同上 | 加项：便于直接看 Top N 差模型；**必须带 `SUM(events_30d)` 样本量列** |
| 6 | **加项·按日明细表** | 每个模型**每天**的条数 + 报错率 | `ds_translate_model_perf_day` | Table | `-` | `SUM(events)` / `SUM(failure_events)` / `SUM(failure_events)/SUM(events)` | `-` | 同上 | 加项：折线 tooltip 只能显示 Metric、塞不下条数（再塞就多 24 条线），**条数必须走表格**；近 14 天 |
| 7 | **加项·报错原因构成** | 失败按原因拆分（网络/限流/5xx/解析/鉴权） | `ds_translate_model_perf_day` | Line | `dt_bj` | `SUM(fail_network)` / `SUM(fail_quota)` / `SUM(fail_provider)` / `SUM(fail_invalid_resp)` / `SUM(fail_auth)` | **`-`（不设 Series，原因已是多条 Metric）** | 同上 | 加项：用于区分「网络差」还是「服务挂」；**须先跑原因补丁**才有这几列 |

> **图 1 为什么拆成 1a/1b**：24 个模型 × p50+p95 两个指标 = 48 条线挤一张图，完全不可读
> （2026-10-21 用户实挂后确认）。同属需求#1，不算加新需求，只是按可读性拆图。
> **Metric 一律除以 1000 换成秒**，Y 轴格式 `,.1f`——否则 Superset 默认用 K/M 缩写（2K 会被误读成"2000 秒"）。
> **SERIES LIMIT=10 + Sort by metric Desc**：默认只显示最慢/最差的 10 个模型，其余用 Dashboard Filter 看。

> 图 4 的 Big Number 口径：`ds_translate_model_perf_window` 已按模型聚合好，
> 直接用 **`AVG(avg_req_ms_30d)`** 会误导（对不同模型再平均）。
> 若要「全模型整体」近窗耗时，请在 board 里对 `ds_translate_model_perf_day` 用
> **`SUM(req_ms_sum)/SUM(req_ms_cnt)`**；本文档按保险起见把图 4 标为加项，由你方决定是否要。

### Dashboard 全局

| 项 | 设置 |
|----|------|
| 名称 | 网页翻译 · 各模型耗时与报错率（自定） |
| 时间 Filter | `dt_bj` · Temporal · 默认近 90 天 |
| `model_label` Filter | 多选，默认空 = 全量**已收窄的**模型（约 24 个） |
| `model_group` Filter | 多选（free/trial/pro/max/builtin），默认空 = 全档位；`custom`/`unknown` 已被 Dataset 层剔除，勾不到 |
| Scoping | 两个 Filter 勾全部 8 张图 |

**禁止**做 `dim_type` 下拉切换维度长表；这里只有一个维度轴（模型），直接 Filter + Series。

**Filter 全空 = 全量**（不看某个模型时不选即可），Big Number 上 `SUM/SUM` 自动覆盖全盘。

### Superset 操作步骤

1. 数据集：纯 SQL 粘贴对应 `ds_*` 段 → **SAVE**；`dt_bj` 标 Temporal
2. Chart：按上表建 8 张（图 1 拆 1a/1b，另加图 6 按日明细表、图 7 报错原因构成）；做完挂 Dashboard
3. Dashboard Filters：`model_label` / `model_group` / 时间，各 Scoping 全选
4. 改过 SQL 后必须回来 **Edit SQL → SAVE → COLUMNS 标签 → SYNC COLUMNS FROM SOURCE → 再 SAVE**（列才会更新）

### Superset 建图逐步操作

两个 Dataset 已建。以下按「先配字段 → 再建 8 张图（图 1 拆 1a/1b；图 6 按日明细表；图 7 报错原因构成） → 最后拼 Dashboard + Filter」的顺序。

> ⚠️ **图 7 依赖原因列**：须先跑 `sql/reports/t080_translate_model_perf_reason_patch.sql`（见 §「变更记录」），
> 并回 Dataset **Edit SQL → SAVE → COLUMNS → SYNC COLUMNS FROM SOURCE → 再 SAVE**，否则 `fail_*` 列不存在会报错。
> ⚠️ 「Refresh」指的不是浏览器刷新，是 COLUMNS 页顶部的 **SYNC COLUMNS FROM SOURCE**；不改列只改 WHERE 时列数不变，可只 SAVE。

#### 步骤 0 · 两个 Dataset 的字段配置（先做，否则后面全是坑）

进入 **Data → Datasets**，逐个打开：

**`ds_translate_model_perf_day`**

| Tab | 操作 |
|-----|------|
| Columns | `dt_bj` → 勾 **Temporal**（Superset 里叫 *Is temporal*）；其余不用动 |
| Metrics | 新建 `报错率`＝`SUM(failure_events) / SUM(events)`<br>新建 `平均请求耗时`＝`SUM(req_ms_sum) / NULLIF(SUM(req_ms_cnt), 0)` |

**`ds_translate_model_perf_window`**

| Tab | 操作 |
|-----|------|
| Metrics | 新建 `近30日报错率`＝`SUM(failure_30d) / SUM(events_30d)`<br>新建 `近30日平均耗时`＝`SUM(req_ms_sum_30d) / NULLIF(SUM(req_ms_cnt_30d), 0)` |

> `window` 数据集**没有 `dt_bj`**，Columns 里不要勾 Temporal。
> 用 `NULLIF(…,0)` 是给 Big Number 兜底：万一筛出来某个模型整窗一条耗时样本都没有，
> 早些报销 Divide by zero（本任务已在 SQL 层加过 CASE 保护，这里是双保险，返回空而不是报错）。

**说明：步骤 0 是省事项，不是必做。** 预建命名 Metric 只是让各张图复用同一条定义；
完全可以在建图界面的 **METRICS 框 → Custom SQL 标签**里现场写同一条表达式，效果一样。
左栏 Metrics 只有 `COUNT(*)` 不影响建图。若现场写，表达式照搬上表即可。

#### 步骤 1 · 图1a/1b 翻译时长（按日折线，p50 / p95 各一张）

Data → Charts → **+ CHART**，两张都按下表，只有 Metric 不同：

| 项 | 填什么 |
|----|--------|
| Dataset | `ds_translate_model_perf_day` |
| Viz | **Time-series Line Chart** |
| Time Range | `Last 90 days`（Dataset 自身已是滚动 90 天，这里再取 90 天不会多也不会少） |
| **Time Grain** | **⚠️ 必须是 `Day`** —— 默认是 Week/Month 会把多天压成一个点，p50 被再平均，图看着平滑其实是错的 |
| Time Column / X 轴 | `dt_bj` |
| Metrics | 图 1a：`AVG(req_ms_p50)/1000`（Label `p50`）；图 1b：`AVG(req_ms_p95)/1000`（Label `p95`） |
| **Series（DIMENSIONS）** | **`model_label`** ← 必填 |
| **SERIES LIMIT** | **10**（SORT BY 选该 Metric Desc → 默认只显示最慢 10 个模型，其余用 Filter 看） |
| CUSTOMIZE → Y Axis Format | `,.1f` |
| CUSTOMIZE → Y Axis Label | `请求耗时 (秒)` |

三个要点：

1. **拆成两张、每张只放一个指标**。24 模型 × 2 指标 = 48 条线一张图，不可读（已实挂踩过）。
2. **Metric 除以 1000 换成秒** + Y 轴格式 `,.1f`。不除的话 Superset 默认把毫秒缩写成千
   （`2K` = 2000 ms = 2 秒，极易被误读成"2000 秒"）。
3. 为什么这里能用 `AVG(...)`：**日表 grain = dt_bj × model_label 每行唯一**，
   按「天 + 模型」分组后每组只有 1 行，AVG 就等于那一行的值。
   ⚠️ 但**一旦取消 Series**，AVG 就变成「24 个模型的分位数再平均」，数值毫无意义——所以 Series 不能省。

#### 步骤 2 · 图2 报错率（按日折线）

同上新建一张，除下列外与图 1a 完全一致：

| 项 | 填什么 |
|----|--------|
| Metrics | **步骤 0 建的 `报错率`**（即 `SUM(failure_events)/SUM(events)`） |
| Series（DIMENSIONS） | `model_label` |
| SERIES LIMIT | **10**（SORT BY 选该 Metric Desc → 默认只显示最差 10 个模型） |
| Y Axis Format | `.2%`（在 Customize → Y Axis Format 里填 d3 格式，把 0.0394 显示成 3.94%） |

> **禁止**用 `AVG(error_rate)`——那是「日率再平均」，没按样本量加权。

#### 步骤 3 · 图3 近 30 日报错率（Big Number）

| 项 | 填什么 |
|----|--------|
| Dataset | `ds_translate_model_perf_window` |
| Viz | **Big Number** |
| Metric | 步骤 0 建的 `近30日报错率` |
| Number Format | `.2%` |
| **不要** Time Column | 本 Dataset 无 `dt_bj`，选了会报错 |

#### 步骤 4 · 图4 近 30 日平均请求耗时（Big Number）

同图 3，Metric 换成 `近30日平均耗时`，Number Format 填 `,.0f`，
Subheader/后缀写 `ms`（`2184` 而不是 `2.18`）。

#### 步骤 5 · 图5 模型排行（Table）

| 项 | 填什么 |
|----|--------|
| Dataset | `ds_translate_model_perf_window` |
| Viz | **Table** |
| Group by | `model_label`、`model_group` |
| Metrics | `SUM(events_30d)`（样本量）、`近30日报错率`、`近30日平均耗时`、`MAX(worst_day_p95_30d)` |
| Sort | 按 `近30日报错率` Desc |
| Row Limit | 24（正好是全量） |

> 图 5：一定要把 **`SUM(events_30d)` 样本量**放进表里。
> 图 6：把 **`SUM(events)` 当天条数**放进表里。
> 理由（2026-10-21 实挂后补）：只显示百分比时，`glm-5.2` 当天 5/15=33%、`kimi-k2.6` 27/45=60%
> 看着很吓人，其实只是分母太小；有条数列才不会被人误读成大盘故障（P043）。
> 读表顺序应为：**先看条数 → 再看比率**。条数 < 几百的当作噪声。

#### 步骤 5b · 图6 按日明细表（Table，看每天条数）

图 1a/1b/2 是折线，tooltip **只能显示 Metric 本身**——再塞一个「条数」指标会多出 24 条线，
所以「当天有多少条」必须用表格单独看。这张表就是干这个的。

| 项 | 填什么 |
|----|--------|
| Dataset | `ds_translate_model_perf_day` |
| Viz | **Table** |
| Time Range | `Last 14 days`（太长了行数爆炸：24 模型 × 90 天 ≈ 2000 行） |
| Time Grain | `Day` |
| Time Column | `dt_bj` |
| Group by | **`dt_bj`**、`model_label` |
| Metrics | **3 个独立 Metric**：① `SUM(events)` 当天条数 ② `SUM(failure_events)` 失败条数 ③ `SUM(failure_events)/SUM(events)` 报错率（③是一个除法表达式，必须走 Custom SQL，不是两个指标） |
| Sort | 按 `SUM(events)` Desc（先看量大的，噪声自然沉底） |
| Row Limit | 200 |

用法：折线上看到某个模型某天报错率很吓人 → 来这张表按 `model_label` 一筛，
看它当天到底有几条。几十条的就是噪声，几千条还高才是真问题。
可再加 `SUM(fail_network)` / `SUM(fail_quota)` 等原因列，连"为什么失败"一起看。

#### 步骤 5c · 图7 报错原因构成（Line，需先跑原因补丁）

| 项 | 填什么 |
|----|--------|
| Dataset | `ds_translate_model_perf_day` |
| Viz | **Time-series Line Chart** |
| Time Range | `Last 90 days`；**Time Grain = Day**；Time Column = `dt_bj` |
| Metrics（**5 个**） | `SUM(fail_network)` 网络、`SUM(fail_quota)` 限流、`SUM(fail_provider)` 5xx、`SUM(fail_invalid_resp)` 解析失败、`SUM(fail_auth)` 鉴权 |
| **Series** | **空**（原因本身就是多条 Metric，再加 model_label 会变成 5×N 条线） |
| Y Axis Label | `失败条数` |

怎么看：这张图回答"报错率高到底是哪种失败撑起来的"。典型读法——

| 主导原因 | 说明 | 该找谁 |
|----------|------|--------|
| `fail_network` 高 | 客户端连不上（failed to fetch / ERR_* / 断网） | 网络/链路侧，非模型故障 |
| `fail_quota` 高 | 429 限流 | 配额/并发闸门 |
| `fail_provider` 高 | 5xx | 模型服务端 |
| `fail_invalid_resp` 高 | 响应解析不了 | 接口返回格式/模型行为变化 |
| `fail_auth` 高 | 401/403 | 上游 key/鉴权（如 `glm-4.5-air` 天天 100% 即此类） |

想看构成**占比**就把 Metric 换成 `SUM(fail_x)/SUM(events)`，Y 轴格式 `.2%`。

#### 步骤 6 · 拼 Dashboard 与挂 Filter

Dashboards → **+ DASHBOARD**，加进上面 8 张图，然后加筛选器：

| Filter | 类型 | 列 | Scoping | 默认 |
|--------|------|-----|---------|------|
| 时间 | Native 「Time range」 | `dt_bj` | **只勾图 1a、1b、2、6、7** | Last 90 days |
| 模型 | Native 「Value」 | `model_label` | **8 张全勾** | 空 = 全部 24 个模型 |
| 档位 | Native 「Value」 | `model_group` | **8 张全勾** | 空 = 全部档位 |

几个要点：

- **`model_label` 这个 Filter 要同时作用于两个 Dataset 的图**——列名相同即可跨 Dataset 生效，不用建两个。
- 图 3/4/5 来自没有时间列的 Dataset，**不受时间 Filter 影响**，Superset 可能给提示，属正常。
- 图 6 有 `dt_bj`，会受时间 Filter 影响；它 Time Range 固定 14 天，Dashboard 时间筛若选更长也不会多出数据。
- Filter 全空 = 全量。想只看付费档就勾 `model_group = pro`；想只看某个模型就勾它的 `model_label`。
- **每加一个 Filter 记得设定 Scoping**，忘了 Scoping 会出现「选了筛选器但图不动」。

#### 步骤 7 · 用这组数校验挂对了没有

| 图 | 条件 | 应显示 |
|----|------|--------|
| 图 1a | X 近 3 天 + Series `gpt-6-luna` | p50 ≈ **1.9 / 2.1 / 2.1 秒**（10-18/19/20；= 1929/2077/2149 ms） |
| 图 1b | 同上 | p95 ≈ **4.1 / 4.3 / 4.6 秒**（= 4100/4265/4565 ms） |
| 图 2 | Series `gpt-6-luna` | 报错率 ≈ **3.75% / 3.87% / 4.33%** |
| 图 2 | Series `[未映射] free-model` | ≈ **0.66% / 0.62% / 0.57%** |
| 图 2 | Series `[未映射] babelfast-pro` | ≈ **18.18% / 22.36% / 21.09%** |
| 图 3 | Filter 全空 | **2.36%**（587,700 / 24,921,402） |
| 图 3 | Filter 只选 `gpt-6-luna` | **3.94%**（15,849 / 402,114） |
| 图 4 | Filter 全空 | **2184 ms**（≈ 2.2 秒） |
| 图 4 | Filter 只选 `gpt-6-luna` | **3419 ms**（≈ 3.4 秒） |
| 图 5 | 排序 Desc，第一行 | 应为 `glm-4.5-air` ≈ **99.82%**，样本量 5,520 |

数字对不上时的二分排查：

| 现象 | 先看 |
|------|------|
| 图 1/2 日期只有几个点、或值比上表大很多 | **Time Grain 不是 Day**（最常见） |
| 图 1/2 一根线且数值是小数的平均值 | 漏了 Series `model_label` |
| 图 1/2 几十条线缠成一团、图例溢出 | 没拆 1a/1b，或没设 SERIES LIMIT=10 |
| Y 轴显示 `2.1K` 这类带 K 的数 | Metric 忘了 `/1000`，或 Y Axis Format 不是 `,.1f`；K = 千 |
| 图 3/4 报错 Divide by zero | Metric 没用 `NULLIF` 兜底，或 SQL 段不是最新版 |
| 所有图日期停在旧的一天 | 先看中间表 `MAX(dt_bj)`（数据层），再回 Dataset 点 **Refresh**（挂板层） |
| Filter 选了没反应 | 没设 Scoping |

## 写仓执行清单

| 步 | 谁 | 做什么 |
|----|----|--------|
| 1 | 写仓 | 跑 `t080_translate_model_perf_etl.sql`（§0→§4 一次跑完；重复跑全文幂等） |
| 2 | 本仓 | 按 ETL §5 复检：新鲜度 / grain 唯一 / 抽日 ratio ≈ 1.000 / TASK definition 含 INSERT |
| 3 | 双方 | 跑 `python scripts/sync_table_catalog.py` 刷新表目录，并在 `docs/tables/immdata/` 补两张表的「来源与用途」 |

依赖：无上游中间表（直读 `user_behaviour` 原始埋点），**无上下游调度冲突**。

## ETL 只读等价校验（本仓已跑，2026-10-21）

写仓前不可能真跑 INSERT，故用「dim 转 UNION ALL CTE + 同一套聚合」在只读账号上等价验证：

| 检查 | 结果 |
|------|------|
| 2026-10-19 日表 SUM(events) vs 直查 | 1,041,617 vs 1,041,617 → **ratio 1.0000** ✅ |
| 2026-10-19 日表 SUM(failure) vs 直查 | 29,640 vs 29,640 → **ratio 1.0000** ✅ |
| 2026-10-20 events / failure vs 直查 | 1,022,487 / 27,728 → **ratio 1.0000** ✅ |
| grain 唯一（2 日） | 122 = 122 ✅ |
| grain 唯一（14 日） | 854 = 854 ✅（修正 `model_group` 入 grain 前为 858 vs 854） |
| 单行查询耗时 | 1 日约 1.5–1.7s；14 日 10.4s → **90 天回填约 60–70s** |
| 日行数 | 约 61 行/日（模型级） |

### 等价结果样例（2026-10-19，真实模型名）

| model_label | group | events | 报错率 | req_p50 | req_p95 |
|-------------|-------|--------|--------|---------|---------|
| `[未映射] free-model` | free | 355,109 | 0.62% | 1177 | 4348 |
| `[未映射] bing-free` | free | 288,030 | 1.59% | 395 | 1999 |
| `[未映射] google-free` | free | 225,708 | 3.73% | 369 | 3604 |
| `[未映射] trial-pro` | trial | 71,335 | 9.86% | 852 | 3448 |
| `[未映射] deepseek-custom` | custom | 22,542 | 1.76% | 1020 | 3572 |
| **DeepSeek-V4.1-Flash** | pro | 14,130 | **9.36%** | 1758 | 4914 |
| **gpt-6-luna** | pro | 13,618 | 3.87% | 2077 | 4265 |
| `[未映射] openai-custom` | custom | 10,581 | 7.89% | 2487 | 11146 |
| **gemini-3-flash-preview** | pro | 7,395 | 4.22% | 1636 | 3730 |
| `[未映射] babelfast-pro` | pro | 4,240 | **22.36%** | 685 | 3396 |

**读数（事实）**：`babelfast-pro` 22.36%、`trial-pro` 9.86%、`DeepSeek-V4.1-Flash` 9.36% 明显高于大盘 0.6–1.6%。
**勿推断**（P043）：`DeepSeek-V4.1-Flash` 是会员付费档、样本 1.4 万/天，是否真不稳定需按日趋势复核。

## 抽日对账（写仓后必做）

见 ETL §5.3 与 board 的 `ds_translate_model_perf_recon`：

- 抽 2 日（建议 `2026-10-19`、`2026-10-20`）
- `SUM(events)` / `SUM(failure_events)` 与 `user_behaviour` 直查对照，**ratio 必须 ≈ 1.000**（出现 2.000 即叠层）
- 同时看 `MAX(dt_bj)` ≥ 昨日北京日

## 交付验收清单

| 项 | 标准 | 状态 |
|----|------|------|
| 挂板对照表含「需求来源」列 | 每行都标 需求#n / 加项· | ✅ |
| 需求#1 有图 | 图 1 | ✅ | 
| 需求#2 有图 | 图 2 | ✅ |
| 加项已标前缀 | 图 3–5 标 `加项·近窗卡片` / `加项·模型排行` | ✅ |
| 每段都标注                              | 生产段标【可挂 Superset】；对账段标【仅探查·勿挂板】 | ✅ |
| 写死日期                                | 无；用滚动窗 + `now()` | ✅ |
| 抽日对账 ratio | **3 日全部 1.0000**（events 与 failure 各自对齐） | ✅ 2026-10-21 |
| `MAX(dt_bj)` 新鲜度 | **2026-10-20**（= 昨日北京日） | ✅ 2026-10-21 |
| grain 唯一 | 4,900 = 4,900 | ✅ 2026-10-21 |
| TASK definition 含 DELETE + INSERT | Started；`CRON 0 30 7 * * *` Asia/Shanghai；definition 两者俱全 | ✅ 2026-10-21（P028/P035） |
| 表目录补「来源与用途」 | 待跑 `python scripts/sync_table_catalog.py` | ⏳ |

## 写仓验收结果（2026-10-21，表已落库）

| 检查 | 结果 |
|------|------|
| `imm_translate_model_map` | 77 行 ✅ |
| `imm_translate_model_daily_perf` | 4,900 行；`MIN(dt_bj)=2026-07-28`、`MAX(dt_bj)=2026-10-20`，85 个北京日 |
| grain 唯一 | `COUNT(*) = COUNT(DISTINCT dt_bj│model_label)` = **4,900 = 4,900** ✅ |
| 抽日对账 | 10-19 / 10-20 / 08-01 三日，`SUM(events)` 与 `SUM(failure_events)` 对 `user_behaviour` 直查 **ratio 均 1.0000** ✅ |
| TASK | `update_imm_translate_model_daily_perf` · Started · `CRON 0 30 7 * * * TIMEZONE Asia/Shanghai` · definition **同时含 DELETE 与 INSERT** ✅ |

**为何最早是 07-28 而非回填窗起点 07-23**：直查源流量 7-28 仅 2 条 → 7-29 2,010 → 7-30 9,417 → 7-31 141,152，
说明该事件是 **7-28 起灰度放量**，之前源侧本来就没有；不是 ETL 缺日。

## 缺陷修复：window 数据集除零（2026-10-21）

Superset 首挂报 `[1006] divided by zero … in expr sum(req_ms_sum) * 1.0 / sum(req_ms_cnt)`。

**根因**：近 30 天窗口里有 3 个模型整窗 `SUM(req_ms_cnt)=0`，全是**只有 1 条事件且失败**的模型（缺 `request_ms`）——与本任务「坑 1」同源，只是跑到 window 层才炸：

| model_label | events_30d | req_ms_cnt | failure_30d |
|-------------|-----------|-----------|-------------|
| `[未映射] siliconcloud-5EKcUfLh` | 1 | 0 | 1 |
| `[未映射] deepseek-vnEmD6Nq` | 1 | 0 | 1 |
| `[未映射] deeplx` | 1 | 0 | 1 |

**修法**：`avg_req_ms_30d` 与 `error_rate_30d` 都加分母保护，无样本时返回 **NULL**（Superset 显示空），
**不返回 0**——0 会被误读成「耗时 0ms」。

**已验证**：修好的两段在真实中间表上重跑均 OK（`ds_…_day` 0.5s / 4,900 行，`ds_…_window` 0.4s / 90 行），
`avg_req_ms_30d` 为 NULL 的正好是这 3 行。→ 在 Superset **Edit SQL → SAVE → COLUMNS → SYNC COLUMNS FROM SOURCE → 再 SAVE** 重新取段。

> ~~若嫌这 3 行干扰看图，可在 Dashboard Filter 上默认排除 `model_group = unknown`~~
> → 已被下一节的 Dataset 层收窄取代，且范围更大（连同全部 `custom` 一起剔除）。

## 口径收窄：只看主流通道（2026-10-21）

**起因**（用户反馈）：看板上出现大量 `[未映射] xxx-5EKcUfLh` 之类的条目，「数量很少，这些是用户的个人 API，不想看到」。

**定性**：`-custom` 后缀与随机后缀服务（`deepseek-custom` / `custom-ai-nUAyJ8Ws` / `siliconcloud-5EKcUfLh` …）
都是**用户自建服务**——用户自己填 API key 与模型名，插件不上报、服务端也无从归因。
它们不是「模型」，只能是一堆无法归因的私域桶，混在模型维度里纯属噪声。

**规则一（性质过滤）**：`model_group NOT IN ('custom', 'unknown')`

| model_group | 近 30 日行数 | 事件量 | 占全量 | 性质 |
|-------------|------------|--------|--------|------|
| custom | 945 | 1,317,945 | 5.02% | 用户自建/个人 API（含 `deepseek-custom` 67 万等高量项） |
| unknown | 36 | 59 | 0.00% | dim 未收录的新服务，同样多为个人自建 |

剔除后保留 **94.98%** 的事件量。这条**自动生效**：新出现的个人 API 默认不可见，
直到有人把它写进 `imm_translate_model_map` 并给出明确的 `model_group`。

**规则二（量级门槛）**：近 30 日 `events >= 500`
用于清掉官方通道的历史残留（`imtq-chatgpt` 1 条、`deepl` 4 条、`llama3.3` 33 条 …）。
⚠️ 副作用：低于门槛的新模型在上量之前不会出现在本 Dataset（冷启动延迟）。
要跟踪新模型放量过程就把 500 调小或删掉该行。

**day 为什么要用 `mainstream` CTE 而不是 row-level 条件**：
日表单行只有当天量，若按「当日 events>=500」过滤，小模型会被间歇性滤掉、折线断续。
统一用「近 30 日总量」判定是否主流，再回捞这些 label 的全部日期，折线连续。

**效果**：近 30 日 label 数 **90 → 24**（`ds_…_day` 1,955 行 / `ds_…_window` 24 行，均 0.3–0.6s）。
两个 Dataset 用同一套规则，保证同源两图口径一致。

**回滚**：把 board SQL 里那一行 `AND model_group NOT IN ('custom','unknown')`
和 `HAVING sum(events) >= 500` 删掉即可看到全量；中间表从未丢数据。

> 后续若要做「人工策展清单」（比如只想看公司主推的 10 个模型），正确做法是在
> `imm_translate_model_map` 加一列 `is_mainstream`、由 ETL 带进日表，
> 而不是在 board SQL 里写死一长串白名单。本次为免 ETL 重跑，先用可推导的 group 规则实现。

## 已知数据观察（首次挂板后核对，2026-10-21）

用户看到图 2 报错率「异常的高」，已核对：**图上数值与日表完全一致，图没画错**。性质分三类：

| 现象 | 结论 | 证据 |
|------|------|------|
| `glm-4.5-air` 天天 100% | **真实且持续的服务故障**，非图错、非个别用户 | 10-10 失败明细：220/224 为 `http_401 / auth_error`（认证失败），涉及 **120 个不同设备**；近 7 天逐日 182/182、200/200、139/139、150/150、166/165、179/178、157/157，**天天接近全败**。`http_401` 指向上游鉴权失效（key 过期/配额），建议查该服务（`zhipu-air-pro`）的服务端配置 |
| `kimi-k2.6` 60% / `glm-5.2` 33% / `google` 43% 等单日高值 | **小样本波动**，不是趋势 | 分母极小：glm-5.2 仅 15 条/天（5/15=33%）、kimi-k2.6 45 条/天（27/45=60%）、google 91 条/天。一天变 20~30 个点属正常抖动，**先看样本量再下结论**（P043） |
| 2026-10-10 是否全局事故 | **不是** | 当日大盘报错率 2.93%，前后日 2.49% / 3.23%，在正常波动带；`free-model` 当日 0.79% 也正常 |
| `gemini-3.1-pro-preview` 10-10 抬到 43.10% | 当日有真实抬升，但样本仅 ~200 条/天，**需拉趋势再定性** | 21.82% → 43.10% → 30.43% |

## 口径深挖：DeepSeek 8% 报错率的构成（2026-10-21，代码+数据双证）

**背景**：用户质疑 `DeepSeek-V4.1-Flash`（deepseek-pro）近 30 日 8.54% 报错率过高。

### 代码侧：失败是怎么判定的（`F:\extension` commit 5ba7d8c）

| 环节 | 代码位置 | 行为 |
|------|----------|------|
| 请求重试 | `browser/request.ts:1033` | 默认 `retry=2`（指数退避 ×2），**重试 2 次后仍失败才抛错** → 瞬时抖动不会计入 |
| 失败触发 | `services/translation.ts:1617` | 一个句子组请求抛错 → 组内每句都回调 error → 生命周期会话**立即关成 failure** |
| 成功触发 | `translate_page_lifecycle.ts:177` | 第一个非缓存段落插入页面 → success |
| 会话关闭 | 同上 | **以先到者为准**：首个可见段落出来之前，任一组请求失败即记 failure |
| 失败分类 | `html-engine/performance.ts:1400` | `failed to fetch`/`ERR_*`/断网 → network_error；401/403 → auth；429 → quota；5xx/超时 → provider_slow→translation |
| 页级口径 | — | **一页翻译有多组请求，任一组失败即计 1 次页失败** → 页级失败率天然高于请求级 |

### 数据侧：近 30 天（10-01~10-20）失败构成

| svc | 失败数 | network% | invalid% | 429% | 5xx% | 设备数 |
|-----|-------|----------|----------|------|------|--------|
| deepseek-pro | 23,043 | **82.8** | 11.7 | 4.7 | 0.7 | 9,480 |
| babelfast-pro | 14,286 | 90.3 | 7.2 | 0.6 | 1.8 | 3,464 |
| openai-pro | 10,632 | 31.9 | 11.3 | **55.9** | 0.7 | 3,774 |
| gemini-pro | 5,974 | 17.1 | 25.8 | **55.7** | 1.3 | 1,999 |
| qwen-pro | 1,685 | 15.8 | 14.1 | **68.8** | 1.2 | 637 |

**结论（有证据部分）**：
1. 8% 是**真实数据**，且是「重试 2 次后仍失败的页级会话」比例，不含瞬时抖动
2. DeepSeek 失败的 **82.8% 是客户端网络错误**（failed to fetch / ERR_*），5xx 只有 0.7%
3. 失败分散在 9,480 台设备上，**不是少数用户的问题**
4. 8-13 尖峰是 `invalid_response` 单日 45→1,412→216 的真实事件，次日回落
5. 横向看各家失败主导类型不同：deepseek/babelfast/deepl 以网络错误为主，openai/gemini/qwen 以 429 限流为主

**不能断言（P043）**：network_error 具体是用户本地网络、跨境链路、还是沉浸代理层的问题，
客户端埋点看不到网络路径，需要代理侧日志才能区分。

**可选加项（待用户确认）**：按失败原因拆图需要在 ETL 日表加 `fail_network`/`fail_429`/`fail_invalid_response` 列
（现日表只有 `failure_events` 总数），改动量小但需重跑回填。

## 变更记录

### 2026-10-21 · 日表增加「失败原因」8 列（开发中补丁）

| 项 | 内容 |
|----|------|
| 触发 | 用户质疑 DeepSeek 8.54% 报错率过高；排查发现日表只有 `failure_events` 总数，看不出「网络差」还是「服务挂」 |
| 补丁 | **`sql/reports/t080_translate_model_perf_reason_patch.sql`**（§0→§4，一次跑完，重复跑幂等） |
| 改动 | 日表加 8 列：`fail_network` / `fail_timeout` / `fail_auth` / `fail_quota` / `fail_provider` / `fail_invalid_resp` / `fail_render` / `fail_other`；**TASK definition 同步重建** |
| 不动 | dim 表 `imm_translate_model_map` |
| 执行顺序 | ① 跑补丁 → ② 跑补丁 §4 验收（**§4.2 原因合计 = failure_events，diff 必须为 0**）→ ③ Superset 两个 Dataset **Edit SQL → SAVE → COLUMNS → SYNC COLUMNS FROM SOURCE → 再 SAVE**（列数应变多：day 15→23、window 10→18）→ ④ 建图 7 |
| 定稿 | `t080_translate_model_perf_etl.sql` 已同步含原因列（即最终完整版） |
| 收尾 | 补丁验收通过后**并入定稿并删除本 patch** |

### 补丁执行后复检（本仓只读，2026-10-21 全部通过）

| 检查项 | 结果 |
|--------|------|
| 新列落库 | 25 列，8 个 `fail_*` 全在 ✅ |
| 新鲜度 / grain | 4,900 行；`MAX(dt_bj)=2026-10-20`；grain **4,900 = 4,900** ✅ |
| **8 桶之和 = failure_events** | 1,715,627 = 1,715,627，**diff = 0** ✅ |
| 抽日对账 10-20 | events **1.0000**、failure **1.0000** ✅ |
| TASK | Started、DELETE+INSERT 俱全；definition 含 `count_if(failure_reason=…)` 8 个新桶 ✅ |
| 挂板 SQL 两段 | 在真实表跑通（0.5s / 0.4s），`fail_*` 列正常返回 ✅ |

> 复检时踩到的自查坑：`SHOW TASKS` 的 definition 里**不会出现 `fail_network` 这个列名**
> （INSERT 是位置对应，没写列名），要找的是 `count_if(failure_reason = 'network_error')` 这类源表达式。
> 用列名去 grep 会误判成「TASK 没更新」。

只读预校验（执行前）：14 天窗口 grain 唯一 854=854；8 桶之和 394,790 = 394,790；90 天回填约 65 秒。
实测 `fail_timeout` 与 `fail_other` 恒为 0（插件未产出 timeout reason），列保留备用。

### 图 7 / 图 5 校验值（近 30 日，主流集）

| model_label | 失败数 | network | 429 | 5xx | invalid_resp | auth |
|-------------|-------|---------|-----|-----|--------------|------|
| `[未映射] google-free` | 236,816 | 36,021 | 646 | 21,757 | **178,169** | 139 |
| `[未映射] trial-pro` | 83,678 | 38,319 | 32,759 | 5,486 | 7,107 | 5 |
| `[未映射] free-model` | 81,133 | 20,503 | 2,158 | 496 | **57,052** | 649 |
| `[未映射] bing-free` | 74,581 | 36,554 | 783 | 453 | 36,739 | 18 |
| `DeepSeek-V4.1-Flash` | 34,460 | **28,976 (84%)** | 1,439 | 188 | 3,840 | 15 |
| `[未映射] babelfast-pro` | 21,562 | 19,608 (91%) | 110 | 339 | 1,482 | 23 |
| `gpt-6-luna` | 15,849 | 5,130 | **8,932 (56%)** | 106 | 1,663 | 9 |
| `gemini-3-flash-preview` | 8,816 | 1,559 | **5,088 (58%)** | 93 | 2,073 | 0 |
| `glm-4.5-air` | 5,510 | 81 | 2 | 10 | 83 | **5,334 (97%)** |
| `gpt-6.1-sol` | 5,199 | 650 | **3,007 (58%)** | 4 | 1,538 | 0 |

单日校验（2026-10-20）：`free-model` 失败 1,999（net 446 / 429 71 / invalid 1,390 / auth 22）；
`DeepSeek-V4.1-Flash` 失败 1,325（net 1,042 / 429 99 / invalid 174）；
`gpt-6-luna` 失败 540（net 202 / 429 264 / invalid 72）。

> 读法：`glm-4.5-air` 97% 是 auth → 上游鉴权挂了（最硬的故障）；
> `DeepSeek-V4.1-Flash` 84% 是 network、`gpt-6-luna` 56% 是 429 → **两者性质完全不同，不能放一起比高低**。

## 已排除的备选源

| 备选 | 结论 |
|------|------|
| `ex_char_arg8`（free-model 真实 provider） | **0/2,824,221 全空**，不可用 |
| `translate_page_performance` 事件 | 量更大（1,420 万/3 天）但**所有 `ex_int_arg*` 全空**、无失败语义 |
| `ex_char_arg1` 服务维度 | 22,268 个随机后缀值，未归一 |
| `direct_model_mapping`（库内表） | 粒度是 `providername × reported_model`，**本埋点不带 provider/model 字段，接不上**；它是 token 计费那条链路的映射 |

## 留档

- 探查预览 SQL：`sql/adhoc/t080_model_preview.sql`【仅探查·勿挂板】——已被定稿 ETL 取代，保留作口径推导留档
- 插件代码依据：`F:\extension`（commit `5ba7d8c`，未 pull 最新）
