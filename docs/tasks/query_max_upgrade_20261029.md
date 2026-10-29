# T093 — Max 会员「存量升级补差价」现状核查（→ P047）

- **类型**：query（避坑取证）
- **日期**：2026-10-29
- **状态**：✅
- **关联**：P047（新建）；表文档 `docs/tables/immdata/imt_subscriptiongoodsorder.md`

## 需求 / 背景

用户指出：Max 升级用户一般是由**已有会员升级到 Max**，金额按**差价**补；若只筛选 `membership='max'`（或 `subscriptiontype LIKE 'max%'`），会误当成**全新年费**。

按 P043（结论须有证据）要求，先用数据核验，再写避坑条目。

## 口径

- 来源：`immdata.imt_subscriptiongoodsorder`，`orderstatus='finished'` + `COALESCE(isdeleted,0)=0`
- Max 识别：`membership='max'`（finished 共 73,126 单）
- 升级识别：同一 `userid` 在**首笔 Max 付费单之前**已有非 Max 会员付费单（`subscriptiontype IN ('monthly','yearly','two_yearly')` 且 `amountpaid>0`）
- 金额：`amountpaid` 为最小货币单位整数（分），P008/P046 已说明单位与币种

## 查询

- 复现脚本：`scripts/query_max_upgrade_share_20261029.py`
- 关键 SQL 见 `docs/pitfalls.md` P047 示例段

## 结果

| 指标 | 值 |
|------|-----|
| 有 Max 付费单的 userid 数 | **5,844** |
| 其中「升级自存量会员」的 userid 数 | **1,645** |
| 升级占比（保守下限） | **28.15%** |
| `max_yearly` 付费单 `amountpaid` 最小 | **¥1.15** |
| `max_yearly` 付费单 `amountpaid` 最大 | **¥5,988,000** |
| `max_yearly` 中 ≤¥10 的小额单 | 13 单 |
| `max_yearly` 中 ≤¥100 的小额单 | 111 单 |

## 结论

1. **28.15% 的 Max 付费用户此前已是付费会员**（下限；未含试用转正 / 兑换码会员 / 旧单失效 / 换号，真实升级占比更高）。把他们当「全新年费」会**虚增新获取**。
2. **Max 单 `amountpaid` 是差价不是全价**：¥1.15 的 `max_yearly` 不可能是全新年费，只能是补差价。直接拿 `amountpaid` 求和既不等于「Max 全价 × 人数」也不等于真实新增 ARPU。
3. 据此落地 **P047**：统计 Max 全新年费 / 新增收入必须剔存量升级；Max 收入按 Max 标准定价而非订单差价求和。

## 下一步

- 若后续要做「Max 真实新增 / Max 档 ARPU」，按 P047 的「剔升级 + 标准价」口径重建，不要复用裸 `membership='max'`。
- 本任务未立项为 T 编号分析，仅作避坑取证；如要正式口径的数字，另开 query 任务。
