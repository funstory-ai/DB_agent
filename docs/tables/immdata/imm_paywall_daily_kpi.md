# `immdata.imm_paywall_daily_kpi`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_paywall_daily_kpi` |
| 类型 | BASE TABLE（写仓建表；建好后 sync INDEX） |
| 表注释 | 付费墙监测：按日 DAU/当日触墙 + 首次硬墙 cohort 漏斗与收入 |

## 来源与用途（手工维护）

- **数据来源**：Task `update_imm_paywall_daily_kpi`（近 31 个首次触墙日滚动 REPLACE）
- **上游**：`imm_paywall_first_device`、`user_behaviour`（`translate_page` / `user_need_pro`）、`imt_subscriptiongoodsorder`、`imt_checkoutsession`、`exchangerates`
- **粒度**：`dt_bj` 一行。`dt_bj` 同时表示：当日 DAU/当日硬墙 UV，以及「该北京日首次触墙」的 cohort
- **DDL**：`sql/reports/task6_paywall_daily_etl.sql`
- **看板**：`sql/reports/task6_paywall_daily_board.sql`
- **勿用**：`ads_ab_paywall_metrics_daily`（2026-03 一次性实验，已过期）

## 字段（建表定义）

| 字段 | 说明 |
|------|------|
| `dau` | 当日 `translate_page` 设备 UV |
| `paywall_uv` | 当日任意付费硬墙设备 UV（非仅首次） |
| `register_wall_uv` | 当日 `unregisteredUsageLimitModal` 设备 UV（注册墙参考，不算日常付费墙） |
| `first_paywall_uv` | 该日首次硬墙设备数 |
| `first_paywall_userid_cnt` | 首次硬墙对应 userid 去重（转化分母） |
| `first_paywall_uv_zh_cn` / `_other` | 语言桶（优先设备母语）；基准预期用 |
| `expected_paid_users` | 简中 UV×1.08% + 其他×0.89% |
| `checkout_users` / `trial_users` / `paid_users` | 触墙后 30 天 userid（P013/P024） |
| `d1/d4/d7/d14/d30_paid_users` | 触墙后 N 日付费 userid |
| `d*_revenue_cny` | 触墙后 N 天收入（`amountpaid>0`，P008；不算退款） |
| `paywall_rate` 等 | 日粒度率；窗口率用 `SUM` 分子/`SUM` 分母 |
| `update_time` | 写入时间 |

## 勿想当然

- 日 `dau`/`paywall_uv` 求和 ≠ 窗口去重 UV
- `first_paywall_uv` 每设备只记首次日，窗口内 SUM 可当窗内首次设备数
- 转化用 userid，触墙人数用 device（P018）
