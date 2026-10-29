# 查询：单用户月度 token 消耗（kjzkg84ctb@privaterelay.appleid.com）

- **需求编号**: T094
- **规范大类**: query
- **状态**: ✅ 已完成
- **日期**: 2026-10-29
- **定稿 SQL**: `sql/reports/query_user_token_kjzkg84ctb_20261029.sql`
- **交付物**: `output/user_token_kjzkg84ctb_20261029.xlsx`、`output/user_token_kjzkg84ctb_20261029.csv`

## 初始需求

> 查一下 kjzkg84ctb@privaterelay.appleid.com 从 2026.01.27 开始每个月的使用额度。

澄清后口径：**每月 token 消耗量**（用户选项「每月 token 消耗量」，同类 T074/T075）。

## 口径

| 项 | 定义 |
|----|------|
| 主体 | 账号级 `imt_userinfo.id = 609408`（由 email 定位，唯一账号、未软删） |
| 指标 | token 消耗 = `inputusage + outputusage`；成功扣费行 `recordtype='capture'` |
| 来源 | `token_used_aw`（明细，≈2026-03-02 起有数）/ `imm_token_used`（日汇总，≈2025-09-30 起有数） |
| 时间窗 | 2026-01-27 ~ 2026-10-29，按月 |

## 核心结论

**该账号 2026-01-27 起每个月记录的 token 消耗均为 0。**

证据链（P043，非猜测）：
1. 账号定位：`kjzkg84ctb@privaterelay.appleid.com` → `imt_userinfo.id=609408`（accounttype=normal，createtime=2024-07-24，未软删）。
2. 两表全局零值确认：对 `userid=609408` 无时间过滤，`token_used_aw`=0 行、`imm_token_used`=0 行。
3. 表健康度对照：`token_used_aw` 全库 18.4 亿行（min 2026-03-02）、`imm_token_used` 全库 856 万行（min 2025-09-30）→ 表本身有数，非故障导致空。
4. 账号背景：连续 **Pro 月付会员**，`imt_subscriptiongoodsorder` 28 笔 ¥69/月（amountpaid=6900），自 2024-07-27 起每月 27 日续费至 2026-10-27，从未中断。
5. 实际使用极轻：`user_translate_day` 仅 2026-04/07/08/09/10 有记录，共 **61 次翻译、26 个活跃天** → 与「几乎无 token 消耗」自洽。

**解释（标明为推测性结论）**：该用户是长期付费 Pro 会员但产品实际使用极少，且少量翻译可能走免费/未计量路径，故两表均无 token 扣费行。这不等于「额度没给」，而是「几乎没产生可计量的 token 消耗」。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 该邮箱每月 token 消耗 | 交付物月度表（全部 0） + 全局零值确认 | ✅ |
| 起点 2026.01.27 | 月度骨架 2026-01 ~ 2026-10 | ✅ |
| 数据可用性说明 | 备注列 + 证据页（token_used_aw 仅 2026-03-02 起有数） | ✅ |

## 抽样复核（P019）

- 非「跑通即交付」：已用全局零值确认 + 表级健康度 + 订阅/活跃交叉验证，排除「查错用户 / 表坏 / 时间窗错」。
- 风险点：Jan/Feb 2026 在 `token_used_aw` 中结构性为空（该表 2026-03-02 才起数）；但本账号 3~10 月亦为 0，结论不受影响。

## 备注

- 可用作同类单用户 token 查询模板（先 email→id，再双表全局零值确认 + 月度聚合 + 活跃交叉验证）。
