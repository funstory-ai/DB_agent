# `immdata.imt_subscriptiongoodsorder`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imt_subscriptiongoodsorder` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 816496 |
| 创建时间 | 2026-03-27 16:30:46.764214 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：业务库订阅商品订单（MySQL；本仓只读 Databend 副本，碰不到源库）
- **同步方式**：`H:\imt_data_synch` Extract→OSS→Load MERGE；job `order_subscription_goods`
- **更新频率**：**日更**（CronJob 北京 `0 1 * * *` / Asia/Shanghai）；查「今天白天」会看不到下一跑之前的新单，属正常水位
- **业务含义**：订阅订单明细（Stripe/各渠道成交记录）
- **建议粒度**：订单行（`id`）
- **主键 / 唯一键**：`id`
- **常用过滤**：`COALESCE(isdeleted,0)=0`；有效成交看 `orderstatus='finished'`（另有 `refunded`）
- **试用/付费口径（P013，已确认）**：付费和试用分开计。
  - 付费：`finished`，且（`COALESCE(amountpaid,0)>0` **或** 兑换码）。兑换码是淘宝等站外购买：`LOWER(ordertype)='code'`，或 snap 里 `SubscriptionType` 以 `onetime` 开头。金额经常为空，仍算付费。
  - 试用：`finished` 且 `COALESCE(amountpaid,0)=0`，且不是兑换码。常见 `trial` / `iospay_trial` / `googleplay_trial`。
- **关联建议**：`userid` → `imt_userinfo.id`；行为分析再经 `imt_deviceinfo` → `user_behaviour`
- **勿想当然**：
  - 不要只用 `ordertype='trial'` 定义试用；不要把 `onetime_*` / `ordertype=code` 当试用；不要只用 `amountpaid>0` 定义付费
  - `amount` 与 `amountpaid` 单位/币种可能不同（P008）
  - `dwd_order_clean` 近窗过程表默认不用（P012）
  - **Max 会员（`membership='max'` / `subscriptiontype LIKE 'max%'`）含大量「从已有会员补差价升级」的单子**：单笔 `amountpaid` 是差价、不是 Max 全价；统计 Max 全新年费/新增订阅必须剔掉存量升级用户（**P047**）

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
| 1 | `subscriptiongoodssnap` | `varchar(16382)` | YES |  |  |
| 1 | `orderstatus` | `varchar(16382)` | YES |  |  |
| 1 | `operator` | `varchar(16382)` | YES |  |  |
| 1 | `updatetime` | `timestamp` | YES |  |  |
| 1 | `createtime` | `timestamp` | YES |  |  |
| 1 | `isdeleted` | `tinyint` | YES |  |  |
| 1 | `dataversion` | `int` | YES |  |  |
| 1 | `subscriptionday` | `bigint` | YES |  |  |
| 1 | `subscriptiontype` | `varchar(16382)` | YES |  |  |
| 1 | `invoiceid` | `varchar(16382)` | YES |  |  |
| 1 | `invoicestatus` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptionid` | `varchar(16382)` | YES |  |  |
| 1 | `checkoutsessionid` | `varchar(16382)` | YES |  |  |
| 1 | `amount` | `decimal(18, 4)` | YES |  |  |
| 1 | `amountpaid` | `bigint` | YES |  |  |
| 1 | `remark` | `varchar(16382)` | YES |  |  |
| 1 | `trialdeeplcharacterquota` | `bigint` | YES |  |  |
| 1 | `trialopenaitokenquota` | `bigint` | YES |  |  |
| 1 | `trialperioddays` | `bigint` | YES |  |  |
| 1 | `currency` | `varchar(16382)` | YES |  |  |
| 1 | `trialmathpixquota` | `bigint` | YES |  |  |
| 1 | `ext1` | `varchar(16382)` | YES |  |  |
| 1 | `ext2` | `varchar(16382)` | YES |  |  |
| 1 | `ext3` | `varchar(16382)` | YES |  |  |
| 1 | `ordertype` | `varchar(16382)` | YES |  |  |
| 1 | `trialasraudioquota` | `bigint` | YES |  |  |
| 1 | `couponid` | `varchar(16382)` | YES |  |  |
| 1 | `couponname` | `varchar(16382)` | YES |  |  |
| 1 | `promotioncodeid` | `varchar(16382)` | YES |  |  |
| 1 | `trialbabeldocquota` | `bigint` | YES |  |  |
| 1 | `dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `membership` | `varchar(16382)` | YES |  |  |
| 1 | `membertype` | `varchar(16382)` | YES |  |  |
| 1 | `trialmaxaiquota` | `bigint` | YES |  |  |
| 1 | `trialaisubtitlesquota` | `bigint` | YES |  |  |
| 1 | `apptransactionid` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imt_subscriptiongoodsorder LIMIT 20;
```
