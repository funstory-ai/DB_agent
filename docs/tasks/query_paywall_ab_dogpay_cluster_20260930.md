# 7d 付费异动：订单多字段深挖（DogPay/USDT 簇）

- **需求编号**: T055
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-09-30
- **定稿 SQL**: `scripts/export_t055_order_fields_dig.py`；复核 `scripts/_tmp_dogpay_check.py`（可并入任务后删）
- **关联**: T054（口径/脏数据初筛）

## 初始需求

继续找；数据库表内字段很多——从原始字段挖有没有垃圾数据/特殊订单簇导致 BCD 7d 付费异动。

## 方法

BCD（及复核 ABCD）激活 cohort：语义化 ≥1.32.6 + 剔老号；取锚点后 7d 首笔 `is_paid` 订单。  
对照周 **08/31 vs 09/07**，拆订单字段：`subscriptiontype` / `currency` / `subscriptiongoodsid` / `ordertype` / `amountpaid` / `membership` / `operator` / `coupon*`，以及行为 `campaign` / `browser` / `real_geo` / `target_language`。再拉 09/14、09/21 看该簇是否消失。

## 找到的原始数据簇（有意义）

09/07 相对 08/31，付费首单里同步暴增、且高度同构的一簇：

| 字段 | 08/31（BCD） | 09/07（BCD） | Δ |
|------|--------------|--------------|--:|
| `subscriptiontype = onetime_dogpay_monthly` | 0 | **26** | +26 |
| `currency` 含 `tron:usdt` | ~1 | **~26** | +25 |
| `subscriptiongoodsid = 53` | 0 | **26** | +26 |
| `amountpaid` 落在 500–1999 | 10 | 35 | +25 |
| 付费设备 `real_geo = la` | 0 | **~18** | +18 |

按组×周复核（含 A）：

| 周 | A dogpay | B | C | D |
|----|----------|--:|--:|--:|
| 08/31 | 2 | 1 | 0 | 0 |
| **09/07** | **7** | **13** | **5** | **9** |
| 09/14 | 0 | 0 | 2 | 0 |
| 09/21 | 2 | 0 | 0 | 0 |

- 09/07：BCD 合计 DogPay **27** 台（上周合计 1）。  
- 09/14 起该簇基本消失 → 与「先暴增再降」时间形状一致。  
- 金额中位约 **999**（USDT 通道），`operator=webhook`，不是兑换码 `code` 字段（走 cash 分支，仍进现行付费口径）。  
- `geo=la`（老挝）与该簇高度同现，像特定支付通道/投放，不像有机四组均匀噪声。

另：`ordertype=code` 09/07 也 +10（尤其 C），属已知口径敏感；但 **DogPay/USDT/goods53 是新发现的主簇**。

## 对异动的解释力

| 问题 | 结论 |
|------|------|
| 是否脏数据/特殊订单？ | **是：DogPay 月付 USDT（goodsid=53）在 09/07 周灌进付费分子** |
| 是否 AB 墙配置？ | **否**；四组都有，BCD 更多；配置无关 |
| 能否解释 09/07 抬升？ | **能解释一大部分**（BCD DogPay 净 +26 量级） |
| 能否解释随后回落？ | **能对齐**：09/14 后该簇近乎为 0 |
| 09/21 未满 7d | 仍成立（T054），与本簇叠加 |

现行 T018 付费口径把 `amountpaid>0` 的 DogPay 算真付费；若 AB 只要「正规卡支付转化」，应对 **`subscriptiontype` LIKE '%dogpay%'** 或 `currency` LIKE '%usdt%' / goodsid=53 做剔除或单列。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 用更多表字段继续找 | 订单+行为多维 Δ | ✅ |
| 垃圾/特殊数据？ | DogPay/USDT/g53/la 簇 | ✅ |

## 抽样复核

goodsid53、usdt、dogpay 三计数在 09/07 各组几乎锁死同数；09/14 归零。**通过**。
