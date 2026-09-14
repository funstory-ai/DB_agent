# `immdata.vw_device_user_language_map`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.vw_device_user_language_map` |
| 类型 | VIEW / VIEW |
| 约行数 | 未知 |
| 创建时间 | 2026-04-02 13:12:25.312806 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：设备-用户-语言映射视图
- **业务含义**：设备与用户语言桥接
- **关联建议**：埋点 `device_id` ↔ 用户
- **勿想当然**：一对多时会放大行数，先去重或选主设备规则

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `hybrid_id` | `varchar(16382)` | YES |  |  |
| 1 | `canonical_device_id` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.vw_device_user_language_map LIMIT 20;
```
