# 任务六：付费墙监测看板（日常 + 实验）

- **需求编号**: T006
- **规范大类**: `dashboard`
- **状态**: ✅ 已完成
- **日期**: 2026-08-17；定稿收尾 2026-08-21

- **不用**：`ads_ab_paywall_metrics_daily` / `ads_ab_paywall_user_fact`（2026-03 一次性实验）
- **插件核对**：`F:\extension`；本地 HEAD `58f079445`（2026-07-24）
- **定稿 SQL（仅此 3 个 · 过程 `*_patch`/`*_fix` 已删）**：
  1. 写仓主 ETL：`sql/reports/task6_paywall_daily_etl.sql` — first_device / kpi（含退款、金额无 checkout 放大）/ dim + TASK
  2. 写仓宽表：`sql/reports/task6_paywall_wide_etl.sql` — wide_hit / wide_paywall_rate（六维 dau）+ TASK
  3. Superset 挂板：`sql/reports/task6_paywall_daily_board.sql` — 仅 `ds_paywall_wide_*` + `ds_paywall_kpi_*`

## 需求两层


| 层 | 主轴 | 用途 |
|----|------|------|
| 1 日常 | 首次触墙日 | 触墙规模、转化率、收入、语言基准对照 |
| 2 实验 | 激活日 × `ab_tag` | A/B/C/D；C/D 宽限期内可能无触墙 |

## 初始需求原文 ↔ 现落地（为何对不上名字）


原始表述（2026-08-17）假定用 **`ads_ab_paywall_*`**（`variant_name` / `experiment_name` / `user_id` 挂订单算 ROI）。  
你方 8/18 确认：**那两张表是 3 月一次性实验、停更，不用**；从 behaviour + 订单重做；**ROI 先不算**。  
**2026-08-20**：收入/整单退款要做；**不做净收入（收入不扣退款）**；成本/ROI 仍不做。

因此看板字段名会换成新中间表口径，**不是漏做，是换轨**。

| 初始原文 | 现落点 | 对应关系 |
|----------|--------|----------|
| 每日触墙人数 | `paywall_uv`（当日任意硬墙）+ `first_paywall_uv`（首次） | ✅ 覆盖；拆成「当日」与「首次 cohort」两列 |
| 软/硬墙维度 | 日常主轴 = **仅硬墙** `freeUsageLimitModal`；软墙 8/10 后近窗≈0，**未单独做软墙日维**；注册墙仅 `register_wall_uv` | ⚠️ 改口径：现网不是 3 月的 loose/strict |
| 实验组 | `ab_tag`（a–j）+ 预留 `exp_group`（A/B/C/D 映射表，实验上线后填） | ⚠️ **不是** `variant_name`/`experiment_name`（那是旧 ADS 字段） |
| checkout / trial / paid | `checkout_users` / `trial_users` / `paid_users`（**仅首次硬墙后 30d 内**；未触墙直试用不算） | ✅ **8/20 验收** |
| D4 / D7 付费人数 | `d4_paid_users` / `d7_paid_users`（另有 d1/d14/d30） | ✅ |
| 触墙率 / checkout rate / paid rate / D7 pay rate | kpi 日率 + `ds_paywall_kpi_window` 近窗率 | ✅ |
| 按 `platform_type` / `campaign` / `install_from` 拆 | **`ds_paywall_wide_*`** 六列 Filter | ✅ |
| 按 `interface_language` 拆 | 现为 **`lang_bucket`（母语两桶）** | ⚠️ 你确认用母语表后改的 |
| 按 `variant_name` / `experiment_name` 拆 | 用 `ab_tag` / `exp_group`；映射空时 exp=`(unset)` | ⚠️ 等实验上线填映射表 |
| 触墙后 1/4/7/14/30 天付费金额 CNY | `d1`…`d30_revenue_cny` | ✅ |
| 退款 | `d*_refund_users` / `d*_refund_cny`（整单 `refunded`） | ✅ Part2；写仓跑 refund 补丁后可读 kpi |
| 净收入 / ROI / 成本 | **不做** | ❌ 8/20：收入不扣退款；成本未定义 |

## 已确认口径（2026-08-18 + Part2 2026-08-20）


| 项 | 结论 |
|----|------|
| 触墙（日常付费墙） | **仅付费硬墙**：`user_need_pro` 且 `trigger='freeUsageLimitModal'` |
| 触墙率分母 | **DAU** = 当日 `translate_page` 设备 UV |
| 转化/收入窗 | 首次触墙后 1/4/7/14/30 天（cohort 按 userid） |
| 漏斗关联 | checkout / trial / paid / 收入 / 退款 **均挂首次硬墙**；`createtime >= first_paywall_ts`；未触墙不进分母也不进分子 |
| 收入 | `finished` + `amountpaid>0` → CNY；**不扣退款** |
| 退款 | `orderstatus='refunded'` + `amountpaid>0`（整单）；`createtime` ∈ [首次触墙, +N 天) |
| ROI / 成本 / uplift | 本期不做 |

## 需求覆盖对照（与挂板「需求#」同号）


| 需求# | 初始原文 | 字段 / 数据集 | 状态 |
|-------|----------|---------------|------|
| 1 | 每日触墙人数 | `paywall_uv` · **`ds_paywall_wide_hit`** | ✅ **2026-08-27 停更已修复** |
| 2 | 软/硬墙或实验组维度 | `wall_kind` · ~~`ds_paywall_wide_wall_kind`~~ | ❌ **2026-08-27 确认不做图2**；实验组走 `exp_group`/`ab_tag` Filter |
| 3 | checkout 人数 | `checkout_users` · **`ds_paywall_wide_cohort`** | ✅ **触墙后漏斗** |
| 4 | trial 人数 | `trial_users` · **`ds_paywall_wide_cohort`** | ✅ **触墙后漏斗** |
| 5 | paid 人数 | `paid_users` · **`ds_paywall_wide_cohort`** | ✅ **触墙后漏斗** |
| 6 | D4 付费人数 | `d4_paid_users` · **`ds_paywall_wide_cohort`** | ✅ |
| 7 | D7 付费人数 | `d7_paid_users` · **`ds_paywall_wide_cohort`** | ✅ |
| 8 | 触墙率 | **`ds_paywall_wide_paywall_rate`** · SUM/SUM | ✅ |
| 9 | checkout rate | **`ds_paywall_wide_cohort`** · SUM/SUM | ✅ |
| 10 | paid rate | **`ds_paywall_wide_cohort`** · SUM/SUM | ✅ |
| 11 | D7 pay rate | **`ds_paywall_wide_cohort`** · SUM/SUM | ✅ |
| 12 | 按 variant / experiment / platform / language / campaign / install_from 拆分 | **六列各一个 Filter** | ✅ |
| 13 | N 天收入 CNY | `d*_revenue_cny` · **`ds_paywall_wide_cohort`** / `ds_paywall_kpi_revenue` | ✅ Part2 |
| 14 | ARPU / ARPPU / 触墙人均收入 | `arpu_30d` / `arppu_30d` / `rev_per_paywall_user_30d` · **`ds_paywall_kpi_revenue`** | ✅ Part2（无 Filter 总数） |
| 15 | N 天退款人数/金额 | `d*_refund_*` · **`ds_paywall_wide_cohort`** / `ds_paywall_kpi_refund` | ✅ Part2；须跑 refund 补丁后 kpi 可读 |
| 16 | 预期付费对照 | `expected_paid_users` · **`ds_paywall_kpi_expected`** | ✅ 加项 |
| — | ROI / 净收入 / 成本 | — | ❌ 8/20 确认不做 |

**口径摘要**

- **需求1 触墙人数**：当日硬墙设备 UV（`user_need_pro` + `freeUsageLimitModal`），字段 `paywall_uv`。
- **需求3–7、9–11**：首次触墙 cohort，按 **userid**；归因日 = 首次触墙北京日。
- **需求8 触墙率**：`paywall_uv / DAU`；DAU = 当日 `translate_page` 设备 UV。
- **拆分维字段映射**（原文 → **数据集列名**，各建一个 Filter）：

| 原文 | 列名（cohort / hit / rate 宽表均有，除 wall_kind） |
|------|------------------------------------------------------|
| `variant_name` | **`ab_tag`** |
| `experiment_name` | **`exp_group`** |
| `platform_type` | **`platform_type`** |
| `interface_language` | **`lang_bucket`** |
| `campaign` | **`campaign`** |
| `install_from` | **`install_from`** |
| 软/硬墙（需求2） | **`wall_kind`**（仅 `ds_paywall_wide_wall_kind`） |

---

## Superset 挂板说明


**挂板依据**：本节 + 「挂板对照表」。board SQL：`sql/reports/task6_paywall_daily_board.sql`。

**写仓前置**：须已有中间表（由定稿 `task6_paywall_daily_etl.sql` + `task6_paywall_wide_etl.sql` 写出）。board **只读**中间表，禁止 behaviour 直查。

### 挂板模型（六维 = 六个 Filter，禁止 dim_type）


**错法（你截图里的）**：一个 Filter 绑 `dim_type`，选 `hit_campaign` → 只是在长表里切换「按哪一维展开」，**不是**按 campaign 过滤。

**对法**：宽表每维一列 → **6 个独立 Filter**，与需求原文一一对应：

| Filter 名称（展示名） | 绑定的列 | 类型 |
|----------------------|----------|------|
| install_from | `install_from` | 多选；空=不限 |
| platform_type | `platform_type` | 多选 |
| campaign | `campaign` | 多选 |
| interface_language | `lang_bucket` | 多选 |
| variant_name | `ab_tag` | 多选 |
| experiment_name | `exp_group` | 多选 |
| 时间 | `dt_bj` | 范围 |

| Filter 状态 | 效果 |
|-------------|------|
| **六维都空** | 全量（Chart 上 SUM 所有行 = 总数） |
| **只选 install_from 几个** | 只统计这些渠道 |
| **再选 platform 等** | **交集**进一步收窄 |
| **要看分线** | Chart 里 **Series** 选某一列（如 `install_from`），Filter 仍可同时收窄其它维 |

- **每个指标 1 张 Chart**；checkout / trial / paid **各一张 Line**，勿 Mixed（加项除外）。
- **需求#1 用 Line**（X=`dt_bj`）；Big Number 近窗是**加项**，勿绑六维 Filter。

### Dashboard 全局


| 项 | 设置 |
|----|------|
| 名称 | 付费墙监测（自定） |
| 时间 Filter | `dt_bj` · Temporal · 默认近 90 天 |

### Dashboard Filter 怎么建（逐步）


1. Edit Dashboard → **Filters** → **Add filter**
2. 重复 **6 次**，每次：
   - Dataset = 该 Chart 用的 wide 数据集（cohort 图用 `ds_paywall_wide_cohort`，触墙用 `ds_paywall_wide_hit`）
   - Column = 上表列名
   - Filter type = **Value**
   - **Allow multiple values** = 开
   - 默认不选 = 不限
3. **Scoping**：六维 Filter 勾 **同一套 Chart**（cohort 图勾 B 组，触墙/触墙率勾 A 组）
4. **删除** 原来的 `dim_type` / `dim_value` Filter

**A 组**（图 1、8）：`ds_paywall_wide_hit` / `ds_paywall_wide_paywall_rate`  
**B 组**（图 3–7、9–11）：`ds_paywall_wide_cohort`  
**需求#2 软/硬墙**：另建 Filter `wall_kind` → 只勾 `ds_paywall_wide_wall_kind` 的图（或加项 Line）

**Series（分线，可选）**：Filter 管「筛谁」；Series 管「按谁画多条线」。例如 Filter 不限 platform，Series = `install_from` → 按渠道分色。

---

## Superset 挂板对照表


| 图# | 需求来源 | 指标 | 数据集 | 图表 | X | Metrics | Series | Dashboard Filter | 备注 |
|-----|----------|------|--------|------|---|---------|--------|------------------|------|
| 1 | 需求#1 | 每日触墙人数 | **`ds_paywall_wide_hit`** | **Line** | `dt_bj` | `paywall_uv` SUM | 可选列 | A 六维 + 时间 | 勿 Big Number+dim_type |
| 2 | 需求#2 | 软/硬墙 | **`ds_paywall_wide_wall_kind`** | Line | `dt_bj` | `paywall_uv` SUM | `wall_kind` | 时间 | 实验组走 exp_group Filter |
| 3 | 需求#3 | checkout 人数 | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | `checkout_users` SUM | 可选 | B 六维 + 时间 | |
| 4 | 需求#4 | trial 人数 | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | `trial_users` SUM | 可选 | B | |
| 5 | 需求#5 | paid 人数 | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | `paid_users` SUM | 可选 | B | |
| 6 | 需求#6 | D4 付费人数 | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | `d4_paid_users` SUM | 可选 | B | |
| 7 | 需求#7 | D7 付费人数 | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | `d7_paid_users` SUM | 可选 | B | |
| 8 | 需求#8 | 触墙率 | **`ds_paywall_wide_paywall_rate`** | Line | `dt_bj` | **SUM(paywall_uv)/SUM(dau)** | 可选 | A | 勿 AVG 日率 |
| 9 | 需求#9 | checkout rate | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | **SUM/SUM** | 可选 | B | |
| 10 | 需求#10 | paid rate | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | **SUM/SUM** | 可选 | B | |
| 11 | 需求#11 | D7 pay rate | **`ds_paywall_wide_cohort`** | Line | `dt_bj` | **SUM/SUM** | 可选 | B | |
| 12 | 需求#12 | 拆分 | 同上 | — | — | — | — | 六 Filter | 不增图 |
| 13 | 需求#13 | 付费金额 CNY | **`ds_paywall_wide_money_window`** | Line | `dt_bj` | `revenue_cny` SUM | 可选 | B + **窗长单选** + 时间 | 默认 window_days=30 |
| 14 | 需求#14 | ARPU 30d | **`ds_paywall_kpi_revenue`** | Line | `dt_bj` | `arpu_30d` | — | 时间 | 无六维；仍为 30 日 |
| 15 | 需求#14 | ARPPU 30d | **`ds_paywall_kpi_revenue`** | Line | `dt_bj` | `arppu_30d` | — | 时间 | |
| 16 | 需求#15 | 退款金额 CNY | **`ds_paywall_wide_money_window`** | Line | `dt_bj` | `refund_cny` SUM | 可选 | B + **窗长** + 时间 | |
| 17 | 需求#15 | 退款人数 | **`ds_paywall_wide_money_window`** | Line | `dt_bj` | `refund_users` SUM | 可选 | B + **窗长** + 时间 | |
| 18 | 需求#16 | 实际 vs 预期 | **`ds_paywall_kpi_expected`** | Line | `dt_bj` | `paid_users` / `expected_paid_users` | — | 时间 | 加项 |

---

### 需求#1：每日触墙人数


**状态**：✅  

| 项 | 填什么 |
|----|--------|
| 数据集 | **`ds_paywall_wide_hit`** |
| 字段 | **`paywall_uv`** |
| Chart | **Line Chart**（X=`dt_bj`） |
| Metrics | `paywall_uv` · Sum |
| Filter | **install_from / platform_type / campaign / lang_bucket / ab_tag / exp_group** 各一；全空=总数 |
| Series | 可选：选某一列分线（如 `install_from`） |

**勿用** `dim_type` Filter；**勿** Big Number 绑宽表（近窗 Big Number 见加项）。

---

### 需求#2：软/硬墙或实验组维度


**状态**：✅  

| 场景 | 怎么做 |
|------|--------|
| 软/硬/注册墙 | 图2 · `ds_paywall_wide_wall_kind` · Series=`wall_kind` |
| 实验组 / variant | 任意 cohort/触墙 wide 图 · Filter **`exp_group`** / **`ab_tag`** |

---

### 需求#3 – #7、#9 – #11


**状态**：✅ — 数据集均为 **`ds_paywall_wide_cohort`**，**六维 Filter + 时间**；Metrics 见对照表。  
比率用 **SUM(分子)/SUM(分母)**，勿 AVG 日率。

---

### 需求#8：触墙率


**状态**：✅ — 数据集 **`ds_paywall_wide_paywall_rate`**；Metrics = **SUM(paywall_uv)/SUM(dau)**。

---

### 需求#12：按 … 拆分


**状态**：✅ — 六个 Filter 列；不增 Chart。

---

### 数据集一览（挂板）


| 数据集 | 用途 |
|--------|------|
| **`ds_paywall_wide_hit`** | 图1 · 读 **`imm_paywall_daily_wide_hit`** |
| **`ds_paywall_wide_cohort`** | 图3–7、9–11、13、16–17 · 读 `imm_paywall_first_device` 聚合（含收入/退款） |
| **`ds_paywall_wide_paywall_rate`** | 图8 · 读 **`imm_paywall_daily_wide_paywall_rate`** |
| **`ds_paywall_wide_wall_kind`** | ~~图2 软/硬墙~~ | **作废 · Superset 删除** |
| **`ds_paywall_kpi_revenue`** | 图14–15 · ARPU/ARPPU/N 天收入总数 |
| **`ds_paywall_kpi_refund`** | 退款总数对账（写仓跑补丁后） |
| **`ds_paywall_kpi_expected`** | 图18 · 预期付费 |
| `ds_paywall_kpi_*` | 抽日对账、加项（近窗 window 等） |

**库表 `imm_paywall_daily_dim`**：**已废弃**（2026-08-27）；写仓跑 `task6_paywall_daily_dim_deprecate.sql`；Superset 删 `ds_paywall_wide_wall_kind`。

---

### 作废清单 · Superset / board 清理（2026-08-19）


以下因「长表 + dim_type Filter」模型废弃，**请删除 Superset Virtual Dataset** 并删 Dashboard 上 `dim_type` / `dim_value` Filter：

| 作废 Virtual Dataset | 替代 |
|----------------------|------|
| `ds_paywall_dim_hit` | `ds_paywall_wide_hit` |
| `ds_paywall_dim_cohort` | `ds_paywall_wide_cohort` |
| `ds_paywall_dim_paywall_rate` | `ds_paywall_wide_paywall_rate` |
| `ds_paywall_dim_dau` | 已并入 `ds_paywall_wide_paywall_rate` |

board.sql 中上述四段 **已删除**。Chart 若仍绑 kpi 或 dim 数据集 → 改绑 wide 或删。

**中间表**：`imm_paywall_daily_kpi` + 宽表 **`imm_paywall_daily_wide_*`**；~~dim 长表~~ 已废弃。

---

## 写仓执行清单（仅定稿；过程补丁已删）


| 步 | 文件 | 产出 |
|----|------|------|
| 1 | `task6_paywall_daily_etl.sql` | first_device / kpi（含退款、金额无 fanout）+ TASK（**无 dim**） |
| 2 | `task6_paywall_wide_etl.sql` | `wide_hit` / `wide_paywall_rate`（六维 dau）+ TASK |
| 3 | `task6_paywall_daily_board.sql` | Superset Virtual Dataset（只读） |

日常靠 TASK 日更；**仅全量重建**时按 1→2 整段跑。已跑通的生产库**不必**因本次收尾重跑。

---

## Part2 · 收入 / 退款（2026-08-20）


### 口径


| 项 | 定义 |
|----|------|
| 收入 | `finished` 且 `amountpaid>0` → CNY（`exchangerates`）；**不扣退款** |
| 退款归因 | 首次触墙后 N 天内下单（`createtime`），且订单最终 `orderstatus='refunded'`、`amountpaid>0`（整单） |
| 人数 | 退款 userid 去重；金额 SUM 折算 CNY |
| 不做 | 净收入、ROI、成本、uplift、部分退款 |

### 探查（只读，2026-08-20）


| 范围 | 结果 |
|------|------|
| 2026-07-01～08-20 订单 | `finished` 57094；`refunded` 890（其中 amount>0：853） |
| 2026-05-07～08-20 退款（amount>0） | 约 2040 单 / 2008 userid / ~97.6 万 CNY |
| 首次触墙日 **2026-08-01** cohort | d30 付费 17 人 / ~7303 CNY；d30 退款 **2** 人 / **1176** CNY |

### 写仓与挂板


退款列与金额防 fanout 已并入定稿 **`task6_paywall_daily_etl.sql`**。挂板用 **`ds_paywall_wide_money_window`** / kpi money_window（见 board）；按挂板对照表图 13–18。

### 需求#13–#16 挂板要点（窗长用 Filter，勿拆 5 张图）


**模型**：长表数据集 + Dashboard Filter **`window_days`**（取值 1/4/7/14/30）。

| 图 | 数据集 | Metrics | Filter |
|----|--------|---------|--------|
| 付费金额 CNY | **`ds_paywall_wide_money_window`** | `revenue_cny` SUM | **窗长单选** + B 六维 + 时间 |
| 退款金额 CNY | 同上 | `refund_cny` SUM | 同上 |
| 退款人数 | 同上 | `refund_users` SUM | 同上 |
| ARPU / ARPPU | `ds_paywall_kpi_revenue` | `arpu_30d` / `arppu_30d` | 仅时间（仍为 30 日窗） |
| Big Number 近窗 | **`ds_paywall_wide_money_window`**（要六维）或 `ds_paywall_kpi_money_window`（仅总数） | `revenue_cny` / `refund_*`；近 7 日日值 AVG | **窗长单选** + 时间（+ 可选六维） |

**窗长 Filter 强制**：

- 类型 Value，**单选**（关掉 Allow multiple）
- **默认 = 30**；禁止空选（空选会把 5 个窗的行一起 SUM，D1⊂D30 会重复放大）
- 展示名可用「触墙后 N 天」

**退款人数 / 金额正确性（2026-08-20）**：`money_window` 已改为 **userid×触墙日只保留最早触墙设备** 再挂订单；六维 Filter 全空时 `SUM(refund_users)` 与全日去重一致。请在 Superset **刷新** `ds_paywall_wide_money_window` / `ds_paywall_kpi_money_window` SQL。

**不做净收入**（收入不扣退款）；收入与退款分两张图。

旧图若已挂死 `d30_revenue_cny`：改绑 `ds_paywall_wide_money_window` + `revenue_cny`，并加窗长 Filter。

---

### 挂板验收清单


| 项 | 标准 | 状态 |
|----|------|------|
| Filter | **6 个业务维 Filter**，无 `dim_type` | Part1 ✅ |
| Filter 全空 | SUM = kpi 总数 | Part1 ✅ |
| 多选 install_from 等 | 交集过滤生效 | Part1 ✅ |
| 需求#1 | Line + `ds_paywall_wide_hit` | Part1 ✅ **2026-08-27 停更修复后复检 ✅** |
| 漏斗口径 | checkout/trial/paid 仅首次硬墙后；未触墙直试用不算 | **8/20 ✅** |
| Part2 收入/退款近窗 | wide + `window_days`；08-13～08-19 AVG 与库内一致（1/4/7/14/30） | **8/20 ✅** |
| Part2 不做 | 净收入 / ROI / 成本 | ❌ 确认不做 |

---

## 探查 / 插件 / 触墙白名单（口径依据，挂板可跳过）


- 硬墙 = `user_need_pro` + `trigger='freeUsageLimitModal'`；软墙 8/10 后≈0；注册墙 = `unregisteredUsageLimitModal`
- 日常触墙人数 = 当日该 trigger 设备 UV → 字段 **`paywall_uv`**
- 详情见本文件 Git 历史或 `docs/tasks/` 前版；插件 HEAD `58f079445`

---

## 中间表


| 表 | 粒度 | TASK（UTC） |
|----|------|-------------|
| `imm_paywall_exp_group_map` | `ab_tag` × 生效日 | 人工 INSERT |
| `imm_paywall_first_device` | 一设备一行 | 21:20 |
| `imm_paywall_daily_kpi` | `dt_bj` | 21:30 |
| ~~`imm_paywall_daily_dim`~~ | — | **废弃** |
| **`imm_paywall_daily_wide_hit`** | `dt_bj` × 六维 | **21:50** |
| **`imm_paywall_daily_wide_paywall_rate`** | 同上 + dau | **21:55** |
| ~~`imm_paywall_daily_dim`~~ | — | **已废弃 2026-08-27**（见 deprecate SQL） |

## 异常：图1「每日触墙人数」停更（2026-08-27 · **已修复**）


**规范大类**：`dashboard` + 叠 `anomaly`（写仓 TASK 缺陷）

### 现象（已消除）


Superset 卡片「每日触墙人数（7天平均）」曾停在 **2026-07-20**；checkout / trial / paid 等到 **2026-08-26**。

### 根因（留档）


| 问题 | 说明 |
|------|------|
| TASK 仅 DELETE | 8/19 部署时 Databend 多语句 TASK 未用 `AS BEGIN … END;`，生产只保留 DELETE |
| 7/27+ 叠层 2× | refill 回填后六维 grain 重复；dedupe 清 7/27+ 单层重插 |

定稿 `task6_paywall_wide_etl.sql` §3 已改为 `BEGIN…END`；过程 `refill_fix` / `dedupe_fix` 已跑完并删除。

### 最终验收（2026-08-27 dedupe 后）


| 项 | 结果 |
|----|------|
| `max(dt_bj)` wide_hit / rate | **2026-08-26** ✅ |
| 抽日 SUM vs kpi（7/26、7/27、8/1、8/26） | ratio **1.0007–1.0017**，diff ≤19 ✅ |
| 8/26 grain 唯一 | 765 行 = 765 distinct grain ✅ |
| TASK definition | **DELETE + INSERT** 均已存在 ✅ |

Superset：刷新 `ds_paywall_wide_hit` / `ds_paywall_wide_paywall_rate` 数据集即可。

---

## 交付 / 收尾 / 下一步


- **2026-08-20 验收（用户确认）**：漏斗挂触墙；收入/退款近窗对账 ✅；wide 可挂六维 Big Number
- **2026-08-21 定稿收尾**：10 个过程 `*_patch`/`*_fix` 已并入上述 3 个最终文件并删除；仓库不再保留过程补丁
- **2026-08-27**：图1 wide_hit 停更+叠层已修复 ✅（P028/P027）
- **2026-08-27**：废弃 `imm_paywall_daily_dim` + TASK（图2 不做）；写仓 `task6_paywall_daily_dim_deprecate.sql`
- **未做**：ROI、成本、净收入；实验层 `exp_group` 映射上线后填 `imm_paywall_exp_group_map`
- **重建写仓**（仅当需要全量重建时）：按顺序跑 `daily_etl.sql` → `wide_etl.sql`；日常靠 TASK，勿重复全量
