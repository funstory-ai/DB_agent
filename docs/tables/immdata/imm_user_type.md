# `immdata.imm_user_type`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_user_type` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 2192967 |
| 创建时间 | 2025-06-24 06:54:50.033304 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：用户类型标注表
- **同步方式**：ETL/规则产出
- **业务含义**：用户类型分类（具体枚举探查后用）
- **建议粒度**：用户级
- **关联建议**：用户 id
- **勿想当然**：与埋点字段 `user_type` 可能同名异义，禁止混用未核对

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `varchar(16382)` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |
| 1 | `if_academic` | `int` | YES |  |  |
| 1 | `if_entertaining` | `int` | YES |  |  |
| 1 | `if_engineer` | `int` | YES |  |  |
| 1 | `if_finance` | `int` | YES |  |  |
| 1 | `if_web3` | `int` | YES |  |  |
| 1 | `if_medicine` | `int` | YES |  |  |
| 1 | `if_law` | `int` | YES |  |  |
| 1 | `if_e_commerce` | `int` | YES |  |  |
| 1 | `if_paid` | `int` | YES |  |  |
| 1 | `if_trial` | `int` | YES |  |  |
| 1 | `if_ao3` | `int` | YES |  |  |
| 1 | `if_youtube` | `int` | YES |  |  |
| 1 | `if_axriv` | `int` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_user_type LIMIT 20;
```
