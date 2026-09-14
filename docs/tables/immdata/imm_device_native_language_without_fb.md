# `immdata.imm_device_native_language_without_fb`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_device_native_language_without_fb` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | ~3.5e7（同步时以 INDEX 为准） |
| 表注释 | 设备母语（无 interface_language fallback） |

## 来源与用途（手工维护）

- **数据来源**：与 `imm_device_native_language` 同族；表名 `without_fb` = **without fallback**
- **业务含义**：仅用目标语路径推断母语，**不用** `interface_language` 兜底；覆盖设备数少于主表属预期
- **建议粒度**：设备一行（`device_id`）
- **主键 / 唯一键**：预期按 `device_id`
- **关联建议**：同主表；**默认按语言拆分用 `imm_device_native_language`**，本表仅在明确要求「不要 UI 语言兜底」时使用
- **勿想当然**：无 `userid` 列（相对主表）；账号级同样按 P020：经 deviceinfo 挂 userid 后，按语言 SUM(cnt) 取最大

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `cnt` | `bigint` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |
| 1 | `install_day` | `date` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_device_native_language_without_fb
ORDER BY update_time DESC
LIMIT 20;
```
