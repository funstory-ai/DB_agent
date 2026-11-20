# `immdata.imm_translate_model_daily_perf`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_translate_model_daily_perf` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 6784 |
| 创建时间 | 2026-10-23 02:00:52.812173 |
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
| 1 | `dt_bj` | `date` | YES |  |  |
| 1 | `translation_service` | `varchar(16382)` | YES |  |  |
| 1 | `model_label` | `varchar(16382)` | YES |  |  |
| 1 | `model_group` | `varchar(16382)` | YES |  |  |
| 1 | `real_model` | `varchar(16382)` | YES |  |  |
| 1 | `events` | `bigint` | YES |  |  |
| 1 | `failure_events` | `bigint` | YES |  |  |
| 1 | `fail_network` | `bigint` | YES |  |  |
| 1 | `fail_timeout` | `bigint` | YES |  |  |
| 1 | `fail_auth` | `bigint` | YES |  |  |
| 1 | `fail_quota` | `bigint` | YES |  |  |
| 1 | `fail_provider` | `bigint` | YES |  |  |
| 1 | `fail_invalid_resp` | `bigint` | YES |  |  |
| 1 | `fail_render` | `bigint` | YES |  |  |
| 1 | `fail_other` | `bigint` | YES |  |  |
| 1 | `error_rate` | `double` | YES |  |  |
| 1 | `req_ms_cnt` | `bigint` | YES |  |  |
| 1 | `req_ms_sum` | `bigint` | YES |  |  |
| 1 | `req_ms_avg` | `double` | YES |  |  |
| 1 | `req_ms_p50` | `double` | YES |  |  |
| 1 | `req_ms_p95` | `double` | YES |  |  |
| 1 | `total_ms_cnt` | `bigint` | YES |  |  |
| 1 | `total_ms_sum` | `bigint` | YES |  |  |
| 1 | `total_ms_avg` | `double` | YES |  |  |
| 1 | `total_ms_p50` | `double` | YES |  |  |
| 1 | `total_ms_p95` | `double` | YES |  |  |
| 1 | `failure_missing_ms` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_translate_model_daily_perf LIMIT 20;
```
