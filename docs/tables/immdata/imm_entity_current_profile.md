# `immdata.imm_entity_current_profile`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_entity_current_profile` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 26114467 |
| 创建时间 | 2026-03-09 15:02:43.196434 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：实体（用户/分析主体）当前画像
- **同步方式**：ETL
- **业务含义**：母语、安装日周、设备数等
- **建议粒度**：`analyze_id` / `userid`（字段均为 VARCHAR，注意类型）
- **常用过滤**：按需
- **关联建议**：与 BIGINT 用户 id 关联需 cast；先抽样对齐
- **勿想当然**：`install_day` 口径是否排除 1970 占位需过滤

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `analyze_id` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |
| 1 | `install_week` | `date` | YES |  |  |
| 1 | `device_count` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_entity_current_profile LIMIT 20;
```
