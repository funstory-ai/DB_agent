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
  - **`createtime` = 账号注册时间**（判老号/新号用本字段，见 P033 / P039）；关联键是本表 **`id`**（订单/`deviceinfo.userid`/`ex_int_arg1` 对齐 `id`，勿与 `uid` 混用）
  - 与设备级 P034 激活比先后时：默认 **`createtime < first_ts − 1 天`** 才算老号（1 天缓冲，避免同会话先注册再译误伤，P039）；严格 `< first_ts` 会误伤新号
  - `deviceid` 字段大量为空或不可靠，判「最早设备」请用 `imt_deviceinfo` 按 `userid` 取最早 `installtime`/`createtime`，不要依赖本表 `deviceid`

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
