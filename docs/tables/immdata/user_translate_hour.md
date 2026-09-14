# `immdata.user_translate_hour`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_translate_hour` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 191157092 |
| 创建时间 | 2026-04-08 13:33:58.746831 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：翻译行为按小时汇总
- **同步方式**：ETL
- **业务含义**：`hour_ts_utc` × 用户翻译次数（时间戳为 UTC）
- **建议粒度**：小时 × `userid`（BIGINT）
- **主键 / 唯一键**：预期 (`hour_ts_utc`,`userid`)
- **常用过滤**：时间窗（注意 UTC vs 北京时间）
- **关联建议**：`userid` → 用户 id
- **勿想当然**：与日表时区不一致时会导致对不齐

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `hour_ts_utc` | `timestamp` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `translate_cnt` | `bigint` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_translate_hour LIMIT 20;
```
