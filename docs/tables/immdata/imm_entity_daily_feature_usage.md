# `immdata.imm_entity_daily_feature_usage`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_entity_daily_feature_usage` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 90739221 |
| 创建时间 | 2026-03-10 06:01:09.828806 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：实体日功能使用
- **同步方式**：ETL
- **业务含义**：功能使用日汇总
- **建议粒度**：实体 × 日 × 功能维（以字段为准）
- **常用过滤**：日期
- **关联建议**：同 entity 体系
- **勿想当然**：功能枚举以实际字段/探查为准

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | YES |  |  |
| 1 | `analyze_id` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |
| 1 | `install_week` | `date` | YES |  |  |
| 1 | `feature_name` | `varchar(16382)` | YES |  |  |
| 1 | `used_flag` | `tinyint` | YES |  |  |
| 1 | `use_cnt` | `bigint` | YES |  |  |
| 1 | `first_use_ts` | `timestamp` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_entity_daily_feature_usage LIMIT 20;
```
