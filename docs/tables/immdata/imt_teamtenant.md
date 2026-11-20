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

### 字段速记（手工维护，放在自动段外，避免被同步冲掉）

| 字段 | 说明 |
|------|------|
| `id` | 租户 ID（= 用量表 `tenantid`） |
| `tenantname` / `email` | 租户名称 / 联系邮箱 |
| `userid` | 关联账号 |
| `memberlimit` | 席位上限 |
| `starttime` / `expiretime` | 合约起止 |
| `tokensquotapro` / `tokensquotamax` 等 | 各类配额（上限，非日用量） |
| `isdeleted` | 软删 |

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `tenantname` | `varchar(16382)` | YES |  |  |
| 1 | `email` | `varchar(16382)` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `memberlimit` | `int` | YES |  |  |
| 1 | `starttime` | `timestamp` | YES |  |  |
| 1 | `expiretime` | `timestamp` | YES |  |  |
| 1 | `tokensquotapro` | `bigint` | YES |  |  |
| 1 | `tokensquotamax` | `bigint` | YES |  |  |
| 1 | `comicsquota` | `bigint` | YES |  |  |
| 1 | `pdfproquota` | `bigint` | YES |  |  |
| 1 | `babeldocquota` | `bigint` | YES |  |  |
| 1 | `asraudioquota` | `bigint` | YES |  |  |
| 1 | `storagealias` | `varchar(16382)` | YES |  |  |
| 1 | `storageusage` | `bigint` | YES |  |  |
| 1 | `provider` | `varchar(16382)` | YES |  |  |
| 1 | `bucket` | `varchar(16382)` | YES |  |  |
| 1 | `region` | `varchar(16382)` | YES |  |  |
| 1 | `remark` | `varchar(16382)` | YES |  |  |
| 1 | `ext1` | `varchar(16382)` | YES |  |  |
| 1 | `ext2` | `varchar(16382)` | YES |  |  |
| 1 | `ext3` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `asraudioquotadefaultlimit` | `bigint` | YES |  |  |
| 1 | `babeldocquotadefaultlimit` | `bigint` | YES |  |  |
| 1 | `comicsquotadefaultlimit` | `bigint` | YES |  |  |
| 1 | `pdfproquotadefaultlimit` | `bigint` | YES |  |  |
| 1 | `tokensquotamaxdefaultlimit` | `bigint` | YES |  |  |
| 1 | `tokensquotaprodefaultlimit` | `bigint` | YES |  |  |
| 1 | `seatversion` | `bigint` | YES |  |  |

<!-- AUTO:SCHEMA:END -->
