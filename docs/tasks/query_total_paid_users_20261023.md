# 总付费用户（累计 lifetime）

- **需求编号**: T082
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-10-23
- **定稿 SQL**: `sql/reports/query_total_paid_users_20261023.sql`
- **数据水位**: 订单日更（北京每日 01:00，`H:\imt_data_synch`）；结果约截至前一日收盘，非实时 intraday

## 需求

查「总付费用户」有多少——即当前累计口径，**包含曾经付过费但当前已流失/过期的用户**（不是仅当前在订会员）。

## 口径（写 SQL 前先定）

1. **表**：`immdata.imt_subscriptiongoodsorder`（业务订单副本，碰不到源库）。
2. **付费定义（P013，已确认）**：`orderstatus='finished'` 且下述任一：
   - `COALESCE(amountpaid,0) > 0`（应用内现金单）；或
   - 兑换码（淘宝等站外）：`LOWER(ordertype)='code'` 或 `subscriptiongoodssnap` 中 `"SubscriptionType":"onetime*"`。
   - **试用不算付费**：`finished` 但 `amountpaid=0` 且非兑换码（trial/iospay_trial/…）。
3. **主体（P018-D）**：付费分子走**订单 userid**；同一账号多设备只算 1 人；`userid IS NOT NULL`。
4. **排除**：订单软删 `COALESCE(isdeleted,0)=0`；`refunded` 不计入付费（与 P013 一致）；不限时间窗 = 累计至今。
5. **同一数字同源（P044）**：仅一条查询、同一粒度（userid）、同一锚点（lifetime）产出。

## 结果（2026-10-23 跑）

| 指标 | 值 | 说明 |
|------|-----|------|
| **总付费用户（累计，含已流失）** | **153,644** | 主答案 |
| 其中账号仍有效（imt_userinfo 未软删） | 153,634 | “当前有效”口径，仅比上方少 10 |
| 账号已软删/找不到 | 354 | 付过费但账户不再有效，占比 0.23% |
| 走现金付费的用户 | 121,413 | |
| 走兑换码付费的用户 | 38,417 | 含与现金重叠 |
| 仅兑换码（无现金）付费用户 | 32,231 | |

## 抽样复核（P019）

- 用独立路径（`COUNT(DISTINCT CASE WHEN …)` 直接在明细上算）重跑：
  - `paid_users = 153,644` ✓ 与原查询一致
  - `cash_users = 121,413` ✓、`code_users = 38,417` ✓
- 合理性：`finished` 订单覆盖 457,237 个 userid，付费率 153,644 / 457,237 ≈ 33.6%，量级合理，无假零/串组。
- 已交付数字仅来自本查询 `sql/reports/query_total_paid_users_20261023.sql` 一次结果（P044）。

## 需求覆盖对照

| 需求条目 | 落点 | 状态 |
|----------|------|------|
| 总付费用户数（累计含已流失） | 主查询 `total_paid_users` | ✅ 153,644 |
| 当前有效口径 | `acct_not_deleted` | ✅ 153,634（差 10，可忽略） |
| 兑换码纳入付费（P013） | `users_code_only`=32,231 | ✅ 已含 |
| 试用不混入付费 | 付费定义不含 trial | ✅ |

## 备注 / 如需调整

- 若“付费用户”要**仅当前在订会员**（有效订阅未过期），口径不同，需基于 `subscriptionday`/到期判断，非本需求所指。
- 若要把 `refunded` 也算“曾经付过费”，可去掉 `orderstatus='finished'` 限制重算（会略增）。
