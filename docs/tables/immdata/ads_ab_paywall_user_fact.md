# `immdata.ads_ab_paywall_user_fact`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.ads_ab_paywall_user_fact` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 709511 |
| 创建时间 | 2026-04-01 11:13:32.543497 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：2026-03 付费墙实验用户事实；**已过期，勿挂本轮监测看板**
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：日常监测用 `imm_paywall_daily_*`（task6）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `experiment_name` | `varchar(16382)` | YES |  |  |
| 1 | `variant_name` | `varchar(16382)` | YES |  |  |
| 1 | `is_control` | `int` | YES |  |  |
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `user_id` | `bigint` | YES |  |  |
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |
| 1 | `activate_day` | `date` | YES |  |  |
| 1 | `activate_ts` | `timestamp` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `interface_language` | `varchar(16382)` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `version` | `bigint` | YES |  |  |
| 1 | `user_cohort_type` | `varchar(16382)` | YES |  |  |
| 1 | `is_trial_before_activate` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_before_activate` | `tinyint unsigned` | YES |  |  |
| 1 | `is_register_wall_show` | `tinyint unsigned` | YES |  |  |
| 1 | `is_register_success` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paywall_show` | `tinyint unsigned` | YES |  |  |
| 1 | `is_checkout_start` | `tinyint unsigned` | YES |  |  |
| 1 | `is_trial_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_trial_then_paid` | `tinyint unsigned` | YES |  |  |
| 1 | `is_d1_retained` | `tinyint unsigned` | YES |  |  |
| 1 | `is_d7_retained` | `tinyint unsigned` | YES |  |  |
| 1 | `is_d7_9_retained` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_within_d4` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_within_d7` | `tinyint unsigned` | YES |  |  |
| 1 | `first_register_wall_ts` | `timestamp` | YES |  |  |
| 1 | `register_ts` | `timestamp` | YES |  |  |
| 1 | `first_paywall_ts` | `timestamp` | YES |  |  |
| 1 | `first_checkout_ts` | `timestamp` | YES |  |  |
| 1 | `first_trial_order_ts` | `timestamp` | YES |  |  |
| 1 | `first_paid_order_ts` | `timestamp` | YES |  |  |
| 1 | `trial_membership` | `varchar(16382)` | YES |  |  |
| 1 | `trial_dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `trial_membertype` | `varchar(16382)` | YES |  |  |
| 1 | `trial_payment_channel` | `varchar(16382)` | YES |  |  |
| 1 | `paid_membership` | `varchar(16382)` | YES |  |  |
| 1 | `paid_dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `paid_membertype` | `varchar(16382)` | YES |  |  |
| 1 | `paid_payment_channel` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.ads_ab_paywall_user_fact LIMIT 20;
```
