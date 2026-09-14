# `immdata.imt_checkoutsession`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_checkoutsession` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 1603533 |
| 创建时间 | 2026-03-27 16:38:34.304270 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库结账会话（Checkout Session）
- **同步方式**：业务库 → Databend
- **更新频率**：随下单流程同步
- **业务含义**：发起支付/试用的会话；含 Stripe/Google Play/iOS 等字段
- **建议粒度**：会话行（`id`）；业务键常看 `checkoutsessionid`
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`；`orderstatus` 含 `created`/`finished` 等
- **关联建议**：`userid` → 用户；下游订单、`imt_subscriptionordersource.checkoutsessiontableid`
- **勿想当然**：会话 `created` 很多未支付；不要把 checkout 数当付费数

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `id` | `bigint` | NO |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `useremail` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptiongoodsid` | `bigint` | YES |  |  |
| 1 | `priceid` | `varchar(16382)` | YES |  |  |
| 1 | `quantity` | `bigint` | YES |  |  |
| 1 | `subscriptionday` | `bigint` | YES |  |  |
| 1 | `subscriptiontype` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptiongoodssnap` | `varchar(16382)` | YES |  |  |
| 1 | `orderstatus` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptionid` | `varchar(16382)` | YES |  |  |
| 1 | `invoiceid` | `varchar(16382)` | YES |  |  |
| 1 | `checkoutsessionid` | `varchar(16382)` | YES |  |  |
| 1 | `checkoutsessionstatus` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `ordertype` | `varchar(16382)` | YES |  |  |
| 1 | `amount` | `decimal(18, 4)` | YES |  |  |
| 1 | `paytime` | `timestamp` | YES |  |  |
| 1 | `productname` | `varchar(16382)` | YES |  |  |
| 1 | `amountpaid` | `decimal(18, 4)` | YES |  |  |
| 1 | `outtradeno` | `varchar(16382)` | YES |  |  |
| 1 | `ext1` | `varchar(16382)` | YES |  |  |
| 1 | `ext2` | `varchar(16382)` | YES |  |  |
| 1 | `ext3` | `varchar(16382)` | YES |  |  |
| 1 | `iosoriginaltransactionid` | `varchar(16382)` | YES |  |  |
| 1 | `trackercampaign` | `varchar(16382)` | YES |  |  |
| 1 | `googleplaytransactionid` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_checkoutsession LIMIT 20;
```
