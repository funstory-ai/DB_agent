# `immdata.imt_userinfo`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_userinfo` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 6962515 |
| 创建时间 | 2026-03-27 08:44:12.137377 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库用户表同步（IMT 账号体系）
- **同步方式**：业务库 → Databend（`imt_*` 前缀）
- **更新频率**：随业务同步（约 2023-08 起有数据）
- **业务含义**：注册用户主档：邮箱、openid、账号类型等
- **建议粒度**：用户一行（`id`）
- **主键 / 唯一键**：`id`；另有 `uid`（勿与 `id` 混用，关联前先核对）
- **常用过滤**：`COALESCE(isdeleted,0)=0`（存在少量软删）
- **关联建议**：订单/设备多用 `userid` 指向本表 `id`（仍需在具体表文档确认）
- **勿想当然**：
  - `accounttype`：`normal` / `oauth` / `api_key`
  - `platform` 大量为空或 `''`，`cn` 表示国内相关渠道，不可当操作系统

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `username` | `varchar(16382)` | YES |  |  |
| 1 | `email` | `varchar(16382)` | YES |  |  |
| 1 | `nickname` | `varchar(16382)` | YES |  |  |
| 1 | `lastlogintime` | `varchar(16382)` | YES |  |  |
| 1 | `openid` | `varchar(16382)` | YES |  |  |
| 1 | `deviceid` | `varchar(16382)` | YES |  |  |
| 1 | `accounttype` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `uid` | `bigint` | YES |  |  |
| 1 | `platform` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_userinfo LIMIT 20;
```
