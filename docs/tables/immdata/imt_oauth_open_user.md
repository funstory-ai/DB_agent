# `immdata.imt_oauth_open_user`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_oauth_open_user` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 5305097 |
| 创建时间 | 2025-09-03 09:09:45.988642 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：OAuth 开放用户映射（如 imt-web）
- **同步方式**：业务库 → Databend
- **业务含义**：`client_id` + `open_id`/`subject` → `uid`
- **建议粒度**：映射行
- **主键 / 唯一键**：关注 `uid` / `open_id`
- **常用过滤**：按 `client_id`
- **关联建议**：`uid` → 用户体系；与埋点 device 无直接键
- **勿想当然**：与 `imt_open_id` 不是同一张表

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | YES |  |  |
| 1 | `client_id` | `varchar(16382)` | YES |  |  |
| 1 | `open_id` | `varchar(16382)` | YES |  |  |
| 1 | `subject` | `varchar(16382)` | YES |  |  |
| 1 | `uid` | `bigint` | NO |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_oauth_open_user LIMIT 20;
```
