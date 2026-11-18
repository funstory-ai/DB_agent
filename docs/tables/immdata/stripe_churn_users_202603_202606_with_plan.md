# `immdata.stripe_churn_users_202603_202606_with_plan`

> ⚠️ **僵尸表（2026-11-18 实测）**：本文档仍在，但**库里该表已不存在**。不要写 SQL 查它；Stripe 取消/流失数据走只读 API 直读，见 [`docs/stripe/README.md`](../../stripe/README.md) 与任务 T127/T128。下方字段仅作历史留档。

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.stripe_churn_users_202603_202606_with_plan` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 13470 |
| 创建时间 | 2026-07-03 03:33:18.804576 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：待补充
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：待补充（易误用字段、同名异义等）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `email` | `varchar(16382)` | YES |  |  |
| 1 | `name` | `varchar(16382)` | YES |  |  |
| 1 | `customer_id` | `varchar(16382)` | YES |  |  |
| 1 | `subscription_id` | `varchar(16382)` | YES |  |  |
| 1 | `status` | `varchar(16382)` | YES |  |  |
| 1 | `cancel_at_period_end` | `varchar(16382)` | YES |  |  |
| 1 | `subscription_created` | `varchar(16382)` | YES |  |  |
| 1 | `canceled_at` | `varchar(16382)` | YES |  |  |
| 1 | `ended_at` | `varchar(16382)` | YES |  |  |
| 1 | `current_period_end` | `varchar(16382)` | YES |  |  |
| 1 | `cancel_action_at` | `varchar(16382)` | YES |  |  |
| 1 | `paid_invoice_cnt` | `varchar(16382)` | YES |  |  |
| 1 | `total_amount_paid` | `varchar(16382)` | YES |  |  |
| 1 | `first_paid_at` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_at` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_membership_type` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_invoice_id` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_price_id` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_plan_id` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_line_description` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_line_amount` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_line_period_start` | `varchar(16382)` | YES |  |  |
| 1 | `last_paid_line_period_end` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.stripe_churn_users_202603_202606_with_plan LIMIT 20;
```
