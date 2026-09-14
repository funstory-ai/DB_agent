# `immdata.dwd_order_clean`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.dwd_order_clean` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 1574390 |
| 创建时间 | 2026-04-01 09:15:32.058693 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：由 checkout + 订单等清洗得到的分析宽表（DWD）
- **同步方式**：ETL 产出（非原始业务表）
- **更新频率**：随 ETL（以表内 `order_day`/`checkout_day` 为准）
- **业务含义**：统一订单分析口径，带 `is_*` 标志位
- **建议粒度**：订单/会话分析行（含 `user_id`）
- **主键 / 唯一键**：常见用 `order_id` / `checkoutsessionid`（先确认是否唯一）
- **常用过滤**：
  - 付费：`is_paid_order=1`
  - 有效单：`is_valid_order=1`
  - 试用：`is_trial_order=1`
  - 会员相关：`is_membership_order=1`
- **关联建议**：`user_id` → `imt_userinfo.id`；首单画像见 `dws_order_user_firsts`
- **勿想当然**：优先用本表标志位，而不是只看原始 `orderstatus='finished'`
- **可用性（P012）**：历史任务过程表，**默认不可用**；近窗订单请用 `imt_subscriptiongoodsorder`

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `user_id` | `bigint` | YES |  |  |
| 1 | `checkoutsessionid` | `varchar(16382)` | YES |  |  |
| 1 | `checkout_ts` | `timestamp` | YES |  |  |
| 1 | `checkout_day` | `date` | YES |  |  |
| 1 | `checkoutsessionstatus` | `varchar(16382)` | YES |  |  |
| 1 | `order_id` | `bigint` | YES |  |  |
| 1 | `order_ts` | `timestamp` | YES |  |  |
| 1 | `order_day` | `date` | YES |  |  |
| 1 | `orderstatus` | `varchar(16382)` | YES |  |  |
| 1 | `amount` | `decimal(18, 4)` | YES |  |  |
| 1 | `amountpaid` | `bigint` | YES |  |  |
| 1 | `currency` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptiontype` | `varchar(16382)` | YES |  |  |
| 1 | `dateperiod` | `varchar(16382)` | YES |  |  |
| 1 | `membership` | `varchar(16382)` | YES |  |  |
| 1 | `membertype` | `varchar(16382)` | YES |  |  |
| 1 | `subscriptionday` | `bigint` | YES |  |  |
| 1 | `trialperioddays` | `bigint` | YES |  |  |
| 1 | `ordertype` | `varchar(16382)` | YES |  |  |
| 1 | `payment_channel` | `varchar(16382)` | YES |  |  |
| 1 | `is_checkout_start` | `tinyint unsigned` | YES |  |  |
| 1 | `is_valid_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_membership_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_trial_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_paid_order` | `tinyint unsigned` | YES |  |  |
| 1 | `is_trial_then_paid_candidate` | `tinyint unsigned` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.dwd_order_clean LIMIT 20;
```
