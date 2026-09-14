# `immdata.ads_ab_paywall_metrics_daily`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.ads_ab_paywall_metrics_daily` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 28022 |
| 创建时间 | 2026-04-01 11:15:44.698935 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：2026-03 付费墙 A/B（control/loose/strict）一次性实验日指标；**已过期，勿挂本轮付费墙监测看板**
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：日常监测用 `imm_paywall_daily_*`（task6）；本表分组不是下周 A/B/C/D

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `experiment_name` | `varchar(16382)` | YES |  |  |
| 1 | `variant_name` | `varchar(16382)` | YES |  |  |
| 1 | `is_control` | `int` | YES |  |  |
| 1 | `activate_day` | `date` | YES |  |  |
| 1 | `interface_language` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `user_cohort_type` | `varchar(16382)` | YES |  |  |
| 1 | `is_trial_before_activate` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_before_activate` | `tinyint unsigned` | YES |  |  |
| 1 | `activate_users` | `bigint unsigned` | YES |  |  |
| 1 | `register_wall_users` | `bigint unsigned` | YES |  |  |
| 1 | `register_users` | `bigint unsigned` | YES |  |  |
| 1 | `paywall_users` | `bigint unsigned` | YES |  |  |
| 1 | `d1_retained_users` | `bigint unsigned` | YES |  |  |
| 1 | `d7_retained_users` | `bigint unsigned` | YES |  |  |
| 1 | `d7_9_retained_users` | `bigint unsigned` | YES |  |  |
| 1 | `eligible_pay_users` | `bigint unsigned` | YES |  |  |
| 1 | `checkout_users` | `bigint unsigned` | YES |  |  |
| 1 | `trial_users` | `bigint unsigned` | YES |  |  |
| 1 | `paid_users` | `bigint unsigned` | YES |  |  |
| 1 | `trial_then_paid_users` | `bigint unsigned` | YES |  |  |
| 1 | `d4_paid_users` | `bigint unsigned` | YES |  |  |
| 1 | `d7_paid_users` | `bigint unsigned` | YES |  |  |
| 1 | `register_wall_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `register_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `paywall_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `d1_retention_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `d7_retention_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `d7_9_retention_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `checkout_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `trial_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `paid_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `trial_then_paid_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `trial_to_paid_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `d4_pay_rate` | `decimal(28, 7)` | YES |  |  |
| 1 | `d7_pay_rate` | `decimal(28, 7)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.ads_ab_paywall_metrics_daily LIMIT 20;
```
