# 审核：UCloud gpt-5.4 Funstory vs AW（2026-06 起）

- **需求编号**: T017
- **规范大类**: `audit`
- **状态**: ⏸ **搁置**（2026-08-27；根因待定，**优先级中等**）
- **日期**: 2026-08-27
- **Vendor**: Funstory / UCloud（`api.umodelverse.ai`）
- **AW Key（翻译）**: `uminferapikey-1oi5nqr7oa83`
- **库内对照**: `immdata.token_used_aw`（`resourcename='openai_gpt_41'`，`actualresourceid='gpt-5.4'`，`providername='UCloud'`）
- **单价**: input $1.5 / 1M，output $9 / 1M（与 Funstory 明细一致）
- **代码侧线索**: `H:\imt-api`（Billing Ledger / ProxyOpenAI 流式 settle）

## 需求覆盖对照

| 需求项 | 状态 |
|--------|------|
| 6 月 Funstory AW Key vs AW 金额能否对上 | ✅ 对不上，缺口 **~$243/月（~10.7%）** |
| 其它模型是否同样有问题 | ✅ **仅 gpt-5.4 明显**；gpt-5-mini ~1% |
| 能否 request 级指认 AW 漏单 | ❌ **不能**（`businessid`=UUID，无 gateway request_id） |
| AstraFlow 2 天窗结构性对账 | ✅ 条数差大、净 USD 接近；in/out 分项反向 |
| imt-api 根因定案 | ⏸ **未做**（流式未 settle / 团队不写 AW 等为假设） |
| 整月逐日 Excel / 定稿 SQL 归档 | ⏸ 部分产出已清理；恢复时重写 |

## 已确认结论（摘要）

1. **账单级（6 月 AW Key）**：Funstory **$2,272** vs AW UCloud **$2,029** → **vendor 多 ~$243**；非单价问题。
2. **仅 gpt-5.4**：gpt-5-mini 同 Key **~1%** 偏差；整月缺口几乎全在 gpt-5.4。
3. **后台 Key**（`…bp1j20`）另计 **~$599/月**，AW 详单基本无——与翻译 AW Key 分开看。
4. **不能逐单 join**：Astra `request_id` 与 AW `businessid` **0 命中**；最多 `(in,out)` 形状 + 时间最近邻配对。
5. **形状命中 ⇒ 时间也对**（T059 2026-10-10）：唯一 `(in,out)` 子集 **|Δt|≤60s ≈ 98.7%**，p50≈2s；AW 略晚。说明两侧同一请求在 token 形状一致时时间轴一致，缺口是 **AW 缺行 / Astra 多行**，不是时钟漂移。
6. **条数 vs 金额**：Astra 可多于 AW **~40%+ 条数**；`(182,11)` 等极小对 **条数多、美元少**（单次 ~$0.00037）；整月 **~$243** 主要来自正常量级 token 少记（input/output 各 ~$100+）。
7. **6/26 12–13（北京）**：Astra 洪峰、AW 极少；**(182,11)** 集中此时段；**非** AW「同 token 高频可疑名单」用户（与 5～8 月 anomaly 任务不同：那边是 **AW 有单**）。
8. **imt-api 代码**：AW 仅 **成功 settle** 写 capture；`ProxyOpenAI` 流式 **`finalUsage=null` 则不记账**；文档称 client 断连 **fire-and-forget**（AutoTranslate 已 drain+settle，gpt-5.4 路径未对齐）。

## AstraFlow 明细（已有，不必再要「单次」同形态）

- 文件：`C:\Users\86933\Downloads\AstraFlow_model_logs_20260625_160000_to_20260626_155900_exported_20260825_084807.xlsx`
- 窗：**UTC** `2026-06-25 16:00`～`06-26 16:00`（与文件名一致；AW `timestamp` 按同字面墙钟比，勿再−8h）；Key=`uminferapikey-1oi5nqr7oa83`
- 字段含：`request_id`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`cache_*`、`is_stream`、`model_name` 等
- **教训**：有对方请求级明细仍 **无法** id join；形状+时间可对齐但定不了漏单行号；再要明细须带可 join 键

## 恢复时建议步骤

1. 向运维确认 **UCloud Key 是否独占 imt-api**；团队 gpt-5.4 是否走同一 Key。
2. **6/26 12–13** imt-api 日志 / `stream_usage_unavailable` / fallback 计数。
3. 可选：全月 AstraFlow 导出 → 日复核；或 AW 侧存 upstream request_id。
4. 研发：`ProxyOpenAIController` 流式对齐 AutoTranslate **drain+settle**。

## 参考产物（会话内曾生成，output 可能已清理）

- `output/audit_ucloud_gpt54_expand_20260827.xlsx`（provider / hourly / summary）
- 2 日窗 Astra：上表 xlsx
- Funstory 6 月：`C:\Users\86933\Downloads\Funstory.ai Limited*20260601-20260701*.xlsx`

## 定稿 SQL

- 无（搁置；恢复时再入 `sql/reports/`）

## 相关任务

- [audit_funstory_july2026.md](audit_funstory_july2026.md)（T019）
- [audit_funstory_august2026.md](audit_funstory_august2026.md)（T042；luna output ~1/3，**另一量级问题**）
- [audit_funstory_august2026_dig_20261008.md](audit_funstory_august2026_dig_20261008.md)（T059）
