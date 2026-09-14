# `immdata.imm_paywall_daily_dim`

> **已废弃（2026-08-27）**：需求#2 图2 不要；六维挂板已迁 `imm_paywall_daily_wide_*`。  
> 写仓清理：`sql/reports/task6_paywall_daily_dim_deprecate.sql`（DROP TASK + DROP TABLE）。

## 基本信息（历史）

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_paywall_daily_dim` |
| 类型 | BASE TABLE（写仓建表，**已删**） |
| 原 Task | `update_imm_paywall_daily_dim`（**已删**） |

## 废弃原因

- 长表 + `dim_type` 模型已由宽表六 Filter 替代
- 唯一挂板消费者 `ds_paywall_wide_wall_kind`（图2 软/硬/注册墙）确认不做
- 生产 TASK 曾仅 DELETE、无 INSERT，表停更于 2026-07-18

## 替代

| 原 dim_type | 现读 |
|-------------|------|
| cohort 六维 | `imm_paywall_daily_wide_*` + `ds_paywall_wide_cohort` |
| 当日触墙 | `imm_paywall_daily_wide_hit` |
| wall_kind | **不做** |
