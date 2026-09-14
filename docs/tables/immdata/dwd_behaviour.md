# `immdata.dwd_behaviour`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.dwd_behaviour` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 27840583 |
| 创建时间 | 2026-03-26 11:21:17.438159 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：`user_behaviour` 的裁剪/清洗子集（字段更少，含 `dt`、`user_id`）
- **同步方式**：ETL；行数远小于原始 behaviour，但仍需按 `dt` 过滤
- **业务含义**：分析用行为明细；`user_id` 可能为空（匿名）
- **建议粒度**：事件行；按 `dt` 分区思维查询
- **主键 / 唯一键**：无
- **常用过滤**：`dt`；`event_name`
- **关联建议**：有 `user_id` 时可关联用户；否则用 `device_id`
- **勿想当然**：不是全量 `user_behaviour`；覆盖事件/时间范围需先核 min/max(`dt`)

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `trigger` | `varchar(16382)` | YES |  |  |
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `interface_language` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_today` | `varchar(16382)` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `source_language` | `varchar(16382)` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `translation_service` | `varchar(16382)` | YES |  |  |
| 1 | `user_type` | `varchar(16382)` | YES |  |  |
| 1 | `version` | `int` | YES |  |  |
| 1 | `created_ts` | `timestamp` | YES |  |  |
| 1 | `dt` | `date` | YES |  |  |
| 1 | `user_id` | `int` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.dwd_behaviour LIMIT 20;
```
