# `immdata.user_churn_signal_day`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_churn_signal_day` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 139711352 |
| 创建时间 | 2026-06-09 13:02:59.193630 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：流失信号日表（ETL）
- **同步方式**：ETL
- **业务含义**：用户每日流失相关信号
- **建议粒度**：用户 × 日
- **常用过滤**：`dt`
- **关联建议**：用户 id；可与 `user_payment_summary` 交叉
- **勿想当然**：信号定义以字段注释/探查为准，禁止按表名臆造

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `max_daily_translate_30d` | `int` | YES |  |  |
| 1 | `active_days_30d` | `int` | YES |  |  |
| 1 | `active_days_7d` | `int` | YES |  |  |
| 1 | `is_churn_risk` | `tinyint` | YES |  |  |
| 1 | `first_active_date` | `date` | YES |  |  |
| 1 | `active_day_1` | `int` | YES | 0 |  |
| 1 | `active_cnt_first_3d` | `int` | YES | 0 |  |
| 1 | `is_short_term_churn` | `tinyint` | YES | 0 |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_churn_signal_day LIMIT 20;
```
