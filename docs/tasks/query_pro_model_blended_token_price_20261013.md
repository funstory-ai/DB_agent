# Pro 档模型近月混算百万 token 成本单价

- **需求编号**: T068
- **规范大类**: query
- **状态**: ✅ 已完成（**用户验收 2026-10-13**）
- **日期**: 2026-10-13
- **定稿 SQL**: 无 / 仅对话汇总

## 初始需求

算现在一个月百万 token 单价；只算 pro 模型；input/output 混在一起；粗略即可。

## 口径

| 项 | 定义 |
|----|------|
| 要答的问题 | Pro 档模型近一个月用量加权后的混算成本（USD / 百万 token） |
| 时间窗 | 主：北京 2026-09 UTC `[2026-08-31 16:00, 2026-09-30 16:00)`；对照近 30 日至 10-12 |
| Pro 模型 | `tmp_model_price.model_tier = 'pro'`（不含 max） |
| 用量 | `token_used_aw`，`recordtype='capture'`，按 `resourcename` 对齐价表 |
| token | `inputusage + outputusage`（cached 不进混算分母） |
| 成本 | 折后价：`in/1e6×input_price_per_1m + out/1e6×output_price_per_1m` |
| 混算单价 | `总成本 USD / (总 token / 1e6)` |
| 交付 | 对话汇总（非正式粗算） |

## 结果（粗算）

| 窗 | 总 token (in+out) | 估成本 USD | 混算 USD/1M |
|----|-------------------|------------|-------------|
| 北京 2026-09 | ~85.2B | ~$28.2k | **~$0.33** |
| 近 30 日（至 10-12） | ~79.3B | ~$27.2k | ~$0.34 |
| 9 月且 `categoryname=pro-token` | ~84.7B | ~$28.0k | ~$0.33 |

9 月用量大头：deepseek / openai(gpt-5-mini) / gemini(flash)；in 约占 83%。

未进价表或属 max 的大流量（如 `auto`、`deepl`、`Kimi_K2_0905`、`openai_gpt_41`）未计入。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 一个月 | 北京 2026-09（附近 30 日） | ✅ |
| 只算 pro 模型 | model_tier=pro | ✅ |
| in/out 混算 | 单一 USD/1M | ✅ |
| 粗略 | 对话数字 | ✅ |

## 抽样复核

非正式粗算：量级与结构合理（in:out≈83:17；混算落在廉价 deepseek 与较贵 gemini 之间）；未另抽明细。
