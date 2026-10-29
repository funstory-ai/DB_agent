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

- **数据来源**：视图（2026-10-20 从 `information_schema.views` 取定义）
- **业务含义**：一行一台设备。已在 `imt_deviceinfo` 挂上 userid 的设备，`hybrid_id = 'U_' || userid`（同一账号多台设备共用一个 hybrid）；不在设备表里、但在 `imm_device_native_language` 的设备，`hybrid_id = 'D_' || device_id`。两边都没有的设备不在视图里
- **母语**：用主表 `imm_device_native_language`（含界面语兜底），按 `hybrid_id` 把 `cnt` 求和后取最大。登录用户的语言是账号下多台设备合计，不一定等于这一台设备自己的语言
- **关联建议**：埋点 `device_id` 对视图 `device_id`。要设备数用 `device_id`；要用 hybrid 须知道登录用户会被并成一人
- **勿想当然**：一对多（一台设备多个 userid）时 `COUNT(DISTINCT hybrid_id)` 会放大；`LEFT JOIN` 后再滤 `native_language` 会丢掉没语言的设备

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
