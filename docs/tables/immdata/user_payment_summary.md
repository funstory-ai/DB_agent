# `immdata.user_payment_summary`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_payment_summary` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 93468 |
| 创建时间 | 2026-06-09 13:04:40.206599 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：支付/会员结果汇总（ETL）
- **同步方式**：ETL
- **业务含义**：用户支付侧摘要（具体字段见结构段）
- **建议粒度**：用户级摘要
- **关联建议**：与订单清洗表核对口径后再用
- **勿想当然**：行数远小于注册用户，仅为有支付相关行为子集

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `total_paid_amount` | `decimal(18, 2)` | YES |  |  |
| 1 | `paid_order_count` | `int` | YES |  |  |
| 1 | `first_paid_date` | `date` | YES |  |  |
| 1 | `last_paid_date` | `date` | YES |  |  |
| 1 | `update_date` | `date` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_payment_summary LIMIT 20;
```
