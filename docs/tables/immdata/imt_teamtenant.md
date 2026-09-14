# `immdata.imt_teamtenant`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_teamtenant` |
| 类型 | BASE TABLE |
| 约行数 | ~22（租户维表，体量小） |
| 表注释 | 团队/企业租户档案 |

## 来源与用途（手工维护）

- **数据来源**：业务库团队租户同步（`imt_*`）
- **业务含义**：租户主数据：名称、管理员邮箱/userid、席位与各类额度配额、有效期、存储配置
- **建议粒度**：租户一行（`id`）
- **主键 / 唯一键**：`id`（= 用量表 `tenantid`）
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`id` = `imt_teamusagedaily.tenantid`；看板展示名用 `tenantname`
- **勿想当然**：配额字段（`tokensquotapro` 等）是额度上限，不是日用量；日用量在 `imt_teamusagedaily`

<!-- AUTO:SCHEMA:START -->
## 字段结构（探查补充，可被 sync 覆盖）

| # | 字段 | 类型 | 可空 | 注释 |
|---|------|------|------|------|
| 1 | `id` | BIGINT | NO | 租户 ID |
| 1 | `tenantname` | VARCHAR | YES | 租户名称 |
| 1 | `email` | VARCHAR | YES | 联系邮箱 |
| 1 | `userid` | BIGINT | YES | 关联账号 |
| 1 | `memberlimit` | INT | YES | 席位上限 |
| 1 | `starttime` / `expiretime` | TIMESTAMP | YES | 合约起止 |
| 1 | `tokensquotapro` / `tokensquotamax` 等 | BIGINT | YES | 各类配额 |
| 1 | `isdeleted` | TINYINT | YES | 软删 |
| 1 | `createtime` / `updatetime` | TIMESTAMP | YES | |

<!-- AUTO:SCHEMA:END -->
