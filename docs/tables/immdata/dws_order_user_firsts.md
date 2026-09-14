# `immdata.dws_order_user_firsts`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.dws_order_user_firsts` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 782318 |
| 创建时间 | 2026-04-01 09:26:39.253453 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：订单域用户首次行为汇总（DWS）
- **同步方式**：ETL
- **业务含义**：用户首次 checkout / 试用 / 付费时间及对应套餐渠道
- **建议粒度**：`user_id` 一行
- **主键 / 唯一键**：`user_id`（预期唯一）
- **常用过滤**：`has_paid` / `has_trial` / `has_checkout`
- **关联建议**：`user_id` → `imt_userinfo.id`
- **勿想当然**：`has_trial=1` 且 `has_paid=0` 表示试用未转付费（截至汇总时点）
- **可用性（P012）**：历史任务过程表，**默认不可用**

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `user_id` | `bigint` | YES |  |  |
| 1 | `first_checkout_ts` | `timestamp` | YES |  |  |
| 1 | `first_trial_order_ts` | `timestamp` | YES |  |  |
| 1 | `first_paid_order_ts` | `timestamp` | YES |  |  |
| 1 | `has_checkout` | `tinyint unsigned` | YES |  |  |
| 1 | `has_trial` | `tinyint unsigned` | YES |  |  |
| 1 | `has_paid` | `tinyint unsigned` | YES |  |  |
| 1 | `first_trial_membership` | `varchar(16382)` | YES |  |  |
| 1 | `first_trial_dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `first_trial_membertype` | `varchar(16382)` | YES |  |  |
| 1 | `first_trial_payment_channel` | `varchar(16382)` | YES |  |  |
| 1 | `first_paid_membership` | `varchar(16382)` | YES |  |  |
| 1 | `first_paid_dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `first_paid_membertype` | `varchar(16382)` | YES |  |  |
| 1 | `first_paid_payment_channel` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.dws_order_user_firsts LIMIT 20;
```
