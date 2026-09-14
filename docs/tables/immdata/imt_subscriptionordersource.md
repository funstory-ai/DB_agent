# `immdata.imt_subscriptionordersource`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_subscriptionordersource` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 1502045 |
| 创建时间 | 2026-03-27 08:54:47.100767 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库订单来源/归因快照
- **同步方式**：业务库 → Databend
- **更新频率**：随 checkout/下单
- **业务含义**：下单时的设备、UTM、AB、是否试用等归因信息
- **建议粒度**：来源行；经 `checkoutsessiontableid` 关联 checkout
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`checkoutsessiontableid` → `imt_checkoutsession.id`；`userid` → 用户；`deviceid` → 设备
- **勿想当然**：`extenddata` JSON 内可能有 `orderFrom` / `abField`，解析前先抽样

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `checkoutsessiontableid` | `bigint` | YES |  |  |
| 1 | `istrial` | `tinyint` | YES |  |  |
| 1 | `abfield` | `varchar(16382)` | YES |  |  |
| 1 | `deviceid` | `varchar(16382)` | YES |  |  |
| 1 | `platform` | `varchar(16382)` | YES |  |  |
| 1 | `appversion` | `varchar(16382)` | YES |  |  |
| 1 | `browser` | `varchar(16382)` | YES |  |  |
| 1 | `browseruseragent` | `varchar(16382)` | YES |  |  |
| 1 | `utmcampaign` | `varchar(16382)` | YES |  |  |
| 1 | `utmmedium` | `varchar(16382)` | YES |  |  |
| 1 | `utmsource` | `varchar(16382)` | YES |  |  |
| 1 | `installtime` | `timestamp` | YES |  |  |
| 1 | `installchannel` | `varchar(16382)` | YES |  |  |
| 1 | `interfacelang` | `varchar(16382)` | YES |  |  |
| 1 | `targetlanguage` | `varchar(16382)` | YES |  |  |
| 1 | `lastlogintime` | `timestamp` | YES |  |  |
| 1 | `lastloginip` | `varchar(16382)` | YES |  |  |
| 1 | `usercreatetime` | `timestamp` | YES |  |  |
| 1 | `extenddata` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `currency` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_subscriptionordersource LIMIT 20;
```
