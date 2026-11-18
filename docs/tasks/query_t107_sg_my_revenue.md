# T107 · 新加坡/马来西亚地区收入趋势（已验收）

- **需求编号**: T107
- **规范大类**: query
- **需求**：查 SG/MY 近期收入是否增加；先确认能否区分这两个地区。后续按用户要求扩展为：按月→按周→货币视角→去年同期同比→货币构成→CNY 用户的翻译语言（VPN 探针）。
- **日期**：2026-11-10（续做至 11-16）
- **状态**：已验收
- **定稿 SQL**：`sql/reports/query_t107_sg_my_revenue.sql`

## 初始需求

用户："查一下新加坡马来西亚地区近期的收入有没有增加，先看下这些地方能不能区分出来。" 后续多轮追问：按周算、从货币角度拉一版、去年同期按周、图片同款去年表、这两个地区用户支付用什么货币、CNY 里有多少人平时翻译语言是简中（VPN）。

## 能否区分（recon 结论）

- 地区维度 `real_geo` 为 2 位 ISO 国家码，SG/MY 为独立值，可清晰区分（历史 2024-10 起连续）；最近窗口去重设备 SG≈37.8 万、MY≈3.65 万。
- 但**收入没有现成地区分表**：`imm_regional_income`（按语言对，非国家）与 `imm_regional_conversion_geo` 当前只读账号不可见；权威收入表 `imt_subscriptiongoodsorder` 与 `imt_deviceinfo` 均无国家字段。
- **替代字段核查**：`imt_userinfo` 无国家/语言字段；订单币种 SGD/MYR 仅 1,150 单（<0.2%，仅 app-store 本地币），覆盖太低；目标语言不能分离 SG/MY（SG/MY 翻译目标语言第一是 zh-CN，与全球/中国相同）。
- 结论：库内唯一尝试标识国家的字段是 `real_geo`（IP 国家），无全覆盖更干净替代。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | 今年 2025-11~2026-11；去年同期 2024-11~2025-11（北京时间 createtime+8h）；VPN 探针同今年窗 |
| 主体 | userid（付费订单 userid → imt_deviceinfo deviceid → imm_regional_activation 取全历史最常出现 real_geo 主导归属）；无账号不计 |
| 分母 / 分子 | 收入¥ = (amountpaid/100) × exchangerate(CNY=1，币种 UPPER 按 P046)；VPN 探针为去重用户数（有 CNY 订单者中主导 target_language='zh-CN' 的占比） |
| 付费单口径 | orderstatus='finished' 且 (amountpaid>0 或 ordertype='code' 或 subscriptiontype LIKE 'onetime%')，剔除 isdeleted（P013） |
| 周粒度 | date_trunc('week', date_add(hour,8,createtime))，周一起算；首/末不完整周排除 |
| 移动端缺口 | iOS/安卓设备号多不在 imt_deviceinfo → 归入 NO_GEO，SG/MY 为下界非全量（P037） |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 能否区分 SG/MY | recon：real_geo 可区分、收入无分表 | 完成 |
| 近12月收入趋势（月） | sg_my_monthly_revenue_202511_202611.xlsx | 完成 |
| 按周收入趋势 | sg_my_weekly_revenue_202511_202611.xlsx | 完成 |
| 货币视角 SGD/MYR 交叉校验 | sg_my_revenue_by_currency_202511_202611.xlsx | 完成 |
| 去年同期按周 + 同比 | sg_my_weekly_revenue_yoy_202411_202511.xlsx | 完成 |
| 去年图片同款 5 列表 | sg_my_weekly_lastyear_simple_202411_202511.xlsx | 完成 |
| 两地区用户支付货币构成 | sg_my_currency_mix_202411_202611.xlsx | 完成 |
| CNY 用户翻译语言 VPN 探针 | sg_my_cny_payers_translation_lang_202511_202611.xlsx | 完成 |
| 最终结论（VPN 重构） | 见下「最终结论」 | 完成 |

## 关键结论（各版原始数字）

- **地理版·月**：SG+MY 2026-06 峰值 ¥151,465 → 2026-10 ¥107,764（-28.8%）；近季均值 -15.9%。SG 拖累、MY 平稳。NO_GEO（移动端漏算）由 ~¥10万增至 ~¥23万（2x）。
- **地理版·周**：10 月低谷 ¥18.9k → 近 4 周均 ¥27.8k 小幅反弹，仍远低于 6 月峰值 ¥44.6k/周；单周样本小、看 4 周滚动。
- **货币版（SGD/MYR）**：全量 ~1,150 单、全年 ~¥1.2k/周走平，**无 6 月峰值** → 推翻地理版"峰值/回落"叙事。
- **去年同期**：去年 11-03 当周 ¥36,561 为全年峰值；今年同比从年初 +100% 量级塌到最近几周≈0/转负（去年基数已高）。
- **货币构成**：SG/MY 用户付费绝大多数是 CNY（SG 89.7% / MY 77.8%），本地币 SGD/MYR 仅 1.3%/4.7%（仅 app-store 移动端）。币种由支付渠道决定、不随地理走；插件侧只有 CNY/TWD/USD，无 SGD/MYR。另有 currency=NULL 或加密货币链名的脏值（按 P046 折算 ¥0）。

## 最终结论（VPN 探针重构，交付口径）

- **T107f VPN 探针**：CNY 付费、主导 real_geo 归入 SG/MY 的用户共 2,721 人，其中 **2,698 人（99.2%）主导翻译语言 = zh-CN 简中**（SG 99.2%、MY 98.7%）；对照非 CNY 付费者 zh-CN 占比仅 81.3%。
- **推论（证据强，但未见 VPN 日志，属 P043 标注的强证据推论）**：地理版看到的"SG/MY 收入增长/6 月峰值/回落"大头是**中国用户用 VPN 使 IP 落在 SG/MY、以 CNY 在网页/插件付费**造成的噪声，不是新马本地需求。
- **回答原问题**：真实本地（非 VPN，即 SGD/MYR 应用商店）收入**没有增加**、全年走平；此前"增加/峰值"几乎全是中国 VPN 用户的 CNY 付费噪声。
- ⚠️ 2026-11 为不完整月（截至 ~11-09），不参与趋势判断；单用户 real_geo/语言高度碎片化，主导值已稀释 VPN 尖峰。

## 抽样复核（P019）

- **单位与折算**：CNY 订单 amount=579.60 / amountpaid=57960（×100，分为最小单位）；USD amountpaid=999=9.99 美元确认。SGD 汇率 5.4023（CNY=1），11-02 周 6 笔真付费合计 87.90 新元 ×5.4023 ≈ ¥475，与交付表一致；9 笔 amountpaid=0 试用已剔除。
- **单用户地理噪声**：抽查 400 名随机付费用户，real_geo 高度碎片（如某用户 CN:478/JP:313/TW:95/SG:82；某"SG 归属"用户 SG:34 vs US:33）→ 主导地理已缓解、绝对值带噪声、趋势比绝对值可靠。
- **VPN 探针量级合理性**：CNY 用户 99.2% 简中 vs 非 CNY 81.3%，差异方向与"CNY=网页插件付费=中国用户"一致；剩余 1% 为 en/zh-TW/th/zh-HK/ko 各 1~12 人，零散合理；排除的 NO_GEO 为移动端缺口。判断为通过。
- 抽样结果仅记于此，不另存文件。

## 留档

- 脚本：`scripts/export_t107_sg_my_revenue.py`（月）/ `export_t107b_sg_my_revenue_weekly.py`（周）/ `export_t107c_sg_my_revenue_by_currency.py`（货币）/ `export_t107d_sg_my_revenue_weekly_yoy.py`（去年同比）/ `export_t107e_sg_my_currency_mix.py`（货币构成）/ `export_t107f_sg_my_cny_zhcn.py`（VPN 探针）
- SQL：`sql/reports/query_t107_sg_my_revenue.sql`
- 交付目录：`output/sg_my_revenue/`（7 个 xlsx）
- 技术注：Databend `date_add(hour,8,ts)`（非 INTERVAL）；分组中引用汇率子查询列须包 MAX()；`date_trunc('week',...)` 周一起算。
