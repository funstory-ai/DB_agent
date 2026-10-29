# T093 — Max 会员「存量升级补差价 + 到期截断」现状核查（→ P047 / P048）

- **类型**：query（避坑取证）
- **日期**：2026-10-29
- **状态**：✅
- **关联**：P047（升级界定/差价）、P048（cover_end 截断旧有效期，新建）；表文档 `docs/tables/immdata/imt_subscriptiongoodsorder.md`

## 需求 / 背景

用户指出三点，需先查证再写避坑：
1. Max 升级用户一般是由**已有会员升级到 Max**，金额按**差价**补；
2. 记得有个 **`upgrade` 字段**可作为升级标记；
3. 记得 **Max 的到期时间有问题**（升级单的覆盖到期算错）。

按 P043（结论须有证据）要求，先查数据核验，再落避坑条目。

## 口径

- 来源：`immdata.imt_subscriptiongoodsorder`，`orderstatus='finished'` + `COALESCE(isdeleted,0)=0`
- Max 识别：`membership='max'`（finished 共 73,126 单）
- 升级识别（双口径）：① 显式 `ordertype='upgrade'`；② 行为口径 = 同一 `userid` 在**首笔 Max 付费单之前**已有未到期非 Max 会员付费单（`cover_end > Max 下单日`）
- 覆盖到期：`cover_end = createtime + subscriptionday`（见 `sql/reports/query_max_users_lang_1y_20260924.sql` 第 15 行）
- 金额：`amountpaid` 为最小货币单位整数（分），P008/P046 已说明单位与币种

## 查询

- 复现脚本：`scripts/query_max_upgrade_share_20261029.py`（含升级占比 / 差价分桶 / cover_end 截断三段）
- 关键 SQL 见 `docs/pitfalls.md` P047、P048 示例段

## 结果

| 指标 | 值 | 对应坑 |
|------|-----|--------|
| 有 Max 付费单的 userid 数 | **5,844** | P047 |
| 其中「升级自存量会员」的 userid 数（行为口径） | **1,645**（28.15%，保守下限） | P047 |
| `ordertype='upgrade'` 的 Max finished 单（显式标记） | **1,734** | P047 |
| `max_yearly` 付费单 `amountpaid` 最小 / 最大 | **¥1.15** / **¥5,988,000** | P047 |
| `max_yearly` 中 ≤¥10 / ≤¥100 的差价小额单 | 13 单 / 111 单 | P047 |
| 有 prior 非 Max 会员的 Max `upgrade` 单 userid | **1,115** | P048 |
| 其中升级时旧会员仍有效（cover_end 被截断） | **1,106（99.19%）** | P048 |
| 截断幅度抽样（若按旧到期顺延应多给的天数） | **411~735 天** | P048 |

## 结论

1. **升级界定（P047）**：Max 升级有明确信号 `ordertype='upgrade'`（1,734 单），行为口径下限 28.15%。把 `membership='max'` 当「全新年费/新增获取」会虚增新获取。
2. **金额是差价（P047）**：¥1.15 的 `max_yearly` 不可能是全新年费，只能是补差价；直接拿 `amountpaid` 求和既不等于「Max 全价×人数」也不等于真实新增 ARPU。Max 标准价（记忆 2026-10-26）：年费 ¥1599 / 月费 ¥199。
3. **到期截断（P048，即用户说的「Max 到期时间有问题」）**：升级单 `cover_end = 下单日 + subscriptionday` 从升级日重算，未承接旧会员剩余有效期。99.19% 的升级单发生时旧会员仍有效，截断幅度高达数百天（例：旧年费本到 2027-07-05，升级后 Max 到期只到 2025-07-31）。任何用 `cover_end` 判断「仍在 Max / 续费 / 有效天数」的口径都会被低估或误伤，须先拆出升级单。

## 下一步

- 若后续做「Max 真实新增 / Max 档 ARPU / Max 续费」，按 P047（剔升级 + 标准价）+ P048（升级单 cover_end 须接旧剩余之后或单列）重建，不要复用裸 `membership='max'` 或裸 `createtime+subscriptionday`。
- 本任务仅作避坑取证；如要正式口径数字，另开 query 任务。
