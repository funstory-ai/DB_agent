# `immdata.ads_member_valid_daily_snapshot`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.ads_member_valid_daily_snapshot` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 29380 |
| 创建时间 | 2026-03-30 10:24:26.585557 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：ADS 层会员有效日快照
- **同步方式**：ETL
- **业务含义**：每日有效会员规模类指标（以字段为准）
- **建议粒度**：日快照
- **常用过滤**：快照日
- **关联建议**：会员分析优先 ADS/DWS，原始订单作核对
- **勿想当然**：快照时点与「当日曾有效」口径可能不同

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `stat_date` | `date` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptiontype` | `varchar(16382)` | YES |  |  |
| 1 | `valid_member_cnt` | `bigint` | YES |  |  |
| 1 | `created_at` | `timestamp` | YES | CAST(now() AS Timestamp NULL) |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.ads_member_valid_daily_snapshot LIMIT 20;
```
