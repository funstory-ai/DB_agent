# `immdata.imt_open_id`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_open_id` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 4511586 |
| 创建时间 | 2026-03-27 16:46:54.714623 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：第三方登录 OpenID 绑定（Google / 微信等）
- **同步方式**：业务库 → Databend
- **更新频率**：随 OAuth
- **业务含义**：`uid` 与外部 `app_open_id` 映射
- **建议粒度**：绑定行
- **主键 / 唯一键**：`id`；业务上关注 `(app_name, uid)` / open_id
- **常用过滤**：按 `app_name`（如 Google、CNWeChatWeb）
- **关联建议**：`uid` 与 `imt_userinfo` 的 `id`/`uid` 对齐方式需抽样确认，**禁止想当然**
- **勿想当然**：含 token 类字段，分析时不要选出敏感列到本地宽表

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `app_name` | `varchar(16382)` | YES |  |  |
| 1 | `uid` | `bigint` | NO |  |  |
| 1 | `app_open_id` | `varchar(16382)` | YES |  |  |
| 1 | `app_access_token` | `varchar(16382)` | YES |  |  |
| 1 | `app_id_token` | `varchar(16382)` | YES |  |  |
| 1 | `create_time` | `timestamp` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |
| 1 | `session_key` | `varchar(16382)` | YES |  |  |
| 1 | `union_id` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_open_id LIMIT 20;
```
