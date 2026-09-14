# `immdata.imm_entity_daily_funnel`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_entity_daily_funnel` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 649845277 |
| 创建时间 | 2026-03-09 15:35:35.173303 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：实体日漏斗（安装→激活→转化等，以字段为准）
- **同步方式**：ETL；行数很大，必须按日过滤
- **业务含义**：漏斗分析宽表
- **建议粒度**：实体 × 日
- **常用过滤**：日期字段（以结构段为准）
- **关联建议**：经 `analyze_id`/`userid` 与画像表对齐
- **勿想当然**：禁止无日期全表扫描

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
| 1 | `is_dau` | `tinyint` | YES |  |  |
| 1 | `is_new_install` | `tinyint` | YES |  |  |
| 1 | `is_new_activation` | `tinyint` | YES |  |  |
| 1 | `pay_today` | `tinyint` | YES |  |  |
| 1 | `pay_ever` | `tinyint` | YES |  |  |
| 1 | `translate_page_cnt` | `bigint` | YES |  |  |
| 1 | `first_event_ts` | `timestamp` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_entity_daily_funnel LIMIT 20;
```
