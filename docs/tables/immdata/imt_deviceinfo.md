# `immdata.imt_deviceinfo`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_deviceinfo` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 7234304 |
| 创建时间 | 2026-03-27 16:45:40.920745 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库设备表同步
- **同步方式**：业务库 → Databend
- **更新频率**：随业务同步
- **业务含义**：设备维度安装/登录信息，含 UTM、安装渠道、浏览器等
- **建议粒度**：设备一行（`id`）；业务键常看 `deviceid` + `userid`
- **主键 / 唯一键**：`id`；`deviceid` 可能一对多历史，关联前先核对
- **常用过滤**：`COALESCE(isdeleted,0)=0`
- **关联建议**：`userid` → `imt_userinfo.id`；埋点 `device_id` ↔ 本表 `deviceid`（行为并表主路径之一，**须与 `ex_int_arg1` 并用**，P016）
- **勿想当然**：
  - 仅注册用户有本表数据；能试用/付费均应能挂上 userid
  - **P037**：移动端埋点 `device_id` 已基本不进本表（短窗：移动端约 13% 能对上，桌面约 48%）。含移动端的分析禁止把本表当设备全集
  - **P015**：历史曾有 `(userid,deviceid)` 重复，**2026-08-12 已按 MAX(id) 清理并通过复核**；分析侧可保留防御性 `DISTINCT`
  - `installchannel` 主流为 chrome_store / edge_store / firefox_store / safari 等；存在 `dev` 渠道

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
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
| 1 | `lastlogintime` | `timestamp` | YES |  |  |
| 1 | `lastloginip` | `varchar(16382)` | YES |  |  |
| 1 | `extenddata` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `usercreatetime` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_deviceinfo LIMIT 20;
```
