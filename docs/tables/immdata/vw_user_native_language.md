# `immdata.vw_user_native_language`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.vw_user_native_language` |
| 类型 | VIEW / VIEW |
| 约行数 | 未知 |
| 创建时间 | 2026-04-03 02:13:13.753098 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：用户母语视图
- **业务含义**：母语映射封装
- **关联建议**：用户 id；与设备级主表 `imm_device_native_language`（P020）可能不同源，**按语言拆分默认用设备表再归并**，引用本视图前先核对定义
- **勿想当然**：先看视图定义再 join

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.vw_user_native_language LIMIT 20;
```
