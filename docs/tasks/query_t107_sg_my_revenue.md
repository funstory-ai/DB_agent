# T107 · 新加坡/马来西亚地区近12个月收入趋势

- **需求编号**: T107
- **需求**：查 SG/MY 近期收入是否增加；先确认能否区分这两个地区。
- **日期**：2026-11-10
- **状态**：已交付

## 能否区分（recon 结论）
- 地区维度 `real_geo` 为 2 位 ISO 国家码，SG/MY 为独立值，可清晰区分（历史 2024-10 起连续）。
- 但**收入没有现成地区分表**：`imm_regional_income`（按语言对，非国家）与 `imm_regional_conversion_geo` 当前只读账号不可见；权威收入表 `imt_subscriptiongoodsorder` 与 `imt_deviceinfo` 均无国家字段。
- **替代字段核查**：
  - `imt_userinfo` 无国家/语言字段；
  - 订单币种 SGD/MYR 仅 **1,150 单（<0.2%）**——仅苹果/谷歌应用商店本地币种部分，Stripe(网页) SG/MY 付 USD，故币种覆盖太低，只能当交叉校验；
  - 目标语言**不能**分离 SG/MY：SG/MY 翻译目标语言第一是 `zh-CN`（≈21.9万设备），与全球第一（194万）及中国相同，按语言会主要捞到 CN。
- 结论：库内唯一尝试标识国家的字段是 `real_geo`（IP 国家），无全覆盖更干净替代。

## 口径（与用户确认）
- **real_geo 主导国家**：付费订单 userid → `imt_deviceinfo` deviceid → `imm_regional_activation` 取用户最常出现国家；VPN 噪声用主导值稀释。SG/MY 分别出 + 合并出；近12个月（2025-11~2026-11，北京月）。
- 金额 = (amountpaid/100) × `exchangerates`（CNY=1 基准；amountpaid 为分）。
- 移动端（iOS/安卓）设备号多不在 `imt_deviceinfo` → 归入 NO_GEO，SG/MY 为下界非全量。

## 关键结论
- SG+MY 地理可见收入：**2026-06 峰值 ¥151,465**，此后回落，**2026-10 ¥107,764（-28.8% vs 峰值）**；近一季（8–10月）均值较前一季（5–7月）**-15.9%**。即近期未增、反而走弱。
- 拆分：**SG 是拖累项**（6月 ¥132,625 → 10月 ¥91,585，-30.9%）；**MY 基本平稳**（¥16–19k 区间波动）。
- ⚠️ 但 NO_GEO（取不到国家，主为移动端）由 ~¥10万(2025末) 增至 **~¥23万(2026-10)**，增长约 2 倍；近期 SG/MY 地理可见部分回落可能部分由移动端测量缺口造成，**真实 SG/MY 总量趋势不确定**。
- 2026-11 为不完整月（截至 ~11-09），不参与趋势判断。
- 抽样校验：单用户 real_geo 高度碎片化（VPN/漫游），主导地理已缓解但 SG/MY 绝对值带噪声；趋势比绝对值可靠。

## 留档
- 脚本：`scripts/export_t107_sg_my_revenue.py`
- SQL：`sql/reports/query_t107_sg_my_revenue.sql`
- 交付：`output/sg_my_revenue/sg_my_monthly_revenue_202511_202611.xlsx`（月度收入 / 分币种 / 结论与口径）
- 校验脚本（已清理）：`_recon_sg_my_geo.py`、`_t107_validate_geo.py`
