# UCloud 各模型明细（7月起到现在，脱敏）

- **需求编号**: T081
- **规范大类**: query
- **状态**: ✅ 已完成（2026-10-22）
- **日期**: 2026-10-22
- **定稿 SQL**: `sql/reports/query_ucloud_model_detail_202607_20261022.sql`
- **交付物**: `output/ucloud_model_detail_202607_20261022.xlsx`

## 初始需求

拉取 UCloud 供应商自 2026-07 起至当前的各模型用量明细，Excel 格式；要汇总也要单条明细，字段 input/output 即可，注意脱敏（数据会对外给供应商）。

## 口径（P032）

| 项 | 定义 |
|----|------|
| 数据源 | `immdata.token_used_aw`（只读） |
| 过滤 | `providername='UCloud'`、`recordtype='capture'`（本窗 UCloud 仅 capture） |
| 时间窗 | 北京 2026-07-01 至 2026-10-22；按 `timestamp+8h` 归北京日。2026-10-22 为查询当日，不完整 |
| 汇总粒度 | `actualresourceid`（真实模型）全窗合计 |
| 单条明细粒度（第一版） | 北京日 × `actualresourceid`（已脱敏聚合，**不含任何 userid/设备号/IP/业务单号**） |
| 逐请求粒度（用户真正要的） | 表内**每一行 = 一次 API 调用**的 input/cached/output token；本窗 UCloud 约 1.3 亿行，Excel 单表上限 ~105 万，**全量装不下**。故交付**脱敏随机样本**（约 52 万行，rand()<0.004）让用户看到每条请求长什么样；全量须走 CSV/Parquet 内部导出 |
| 字段 | 输入=inputusage；缓存输入=cachedinputusage（本窗全 0）；输出=outputusage |
| 金额 | 本次不做金额估算，仅 token 用量 |
| 脱敏 | 文件仅含 日期/模型/资源名/聚合 token 计数，可直接对外给供应商 |

## 结果

3 张表：`汇总`（17 个模型）、`按日明细`（549 行 = 日×模型）、`说明`（口径与脱敏声明）。

全量合计（UCloud 全部模型，北京 2026-07-01..10-22）：
- 输入 token：**430.36 亿**
- 缓存输入：0
- 输出 token：**96.93 亿**
- 行数：约 1.30 亿（capture 行）

Top 模型（全窗输入 token）：

| 模型 | 资源名 | 输入 | 输出 |
|------|--------|----:|-----:|
| gpt-5-mini | openai | 155.82 亿 | 35.76 亿 |
| gpt-5.6-luna | openai | 152.52 亿 | 30.86 亿 |
| gpt-6-luna | openai | 104.96 亿 | 26.12 亿 |
| gpt-5.4 | openai_gpt_41 | 6.35 亿 | 1.39 亿 |
| gpt-5.6-terra | openai_gpt_41 | 5.74 亿 | 1.23 亿 |
| kimi-k2.6 | Kimi_K2_0905 | 2.37 亿 | 0.88 亿 |
| gpt-6-sol | openai_gpt_41 | 2.52 亿 | 0.68 亿 |
| 其余 10 个模型 | — | 各 < 0.03 亿输入 | — |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| UCloud 供应商 | `providername='UCloud'` | ✅ |
| 7月起到现在 | 北京 2026-07-01..2026-10-22 | ✅ |
| 各模型明细 | `actualresourceid` 拆分 | ✅ |
| 汇总 | `汇总` sheet | ✅ |
| 单条明细（日×模型聚合） | `按日明细` sheet | ✅ |
| 单条明细（逐请求 row-level） | `ucloud_raw_sample_202607_20261022.xlsx` 的「逐笔样本(脱敏)」sheet（约 52 万行脱敏样本） | ✅ 样本；全量需 CSV/Parquet |
| input/output | 输入/输出 token 列 | ✅ |
| 脱敏 + 对外 | 仅聚合计数，无 PII；`说明` sheet 声明 | ✅ |
| Excel 格式 | xlsx，三 sheet | ✅ |

## 抽样复核（P019）

通过。

- 扫描一次 `GROUP BY 北京日, actualresourceid, resourcename` 得 549 组，Python roll up 出 17 模型汇总；两表同源，无双计。
- 量级合理：gpt-5-mini 全窗 155.82 亿输入 ≈ 4.5 亿/月，与 T073 中 7 月 UCloud GPT 量级一致；gpt-6-luna 自 9/24 起量，全窗 104.96 亿符合其高峰窗口。
- 无假零：17 个模型 input/output 均 > 0；cache 全 0（与 T071 窗口观察一致）。
- 末日 2026-10-22 仍有行（qwen3.5-plus 等），为当日不完整而非缺口。
- 已知历史口径（内部，未写入对外文件）：8 月 `gpt-5.6-luna` output 库内约为账单 1/3（T042/T059，未决）；本次仅给 raw token 计数，未做金额折算，故不影响对外数据本身。

## 补充：逐请求（row-level）明细

用户于交付后明确「单条明细」指**逐请求**——即表里每一行就是一次 API 调用、记录该次请求花了多少 token，而非日×模型聚合。

- 本窗 UCloud 约 **1.3 亿** capture 行；Excel 单表上限约 **105 万行**，全量无法放进一个 Excel。
- 故先交付**脱敏随机样本**：`output/ucloud_raw_sample_202607_20261022.xlsx`（「逐笔样本(脱敏)」sheet，519,625 行），字段含 北京时间 / provider / productline / categoryname / resourcename / actualresourceid(模型) / input / cached_input / output / usageunit / recordtype / countername / counterperiod；**已剔除 userid/tenantid/clientip**，无 PII，可对外。
- 抽样脚本：`scripts/_t081_raw_sample.py`（rand()<0.004，约 0.4%）。
- **全量 1.3 亿行**如确需对外/核对，须改用 CSV/Parquet 内部导出（同样脱敏），另行执行。

## 对账验证（用户要求：明细/汇总/历史对账单 三者能否对上）

结论：**全部对上**（库内口径自洽；与历史对账单的唯一定价差在 8 月 luna 的库内-vs-账单，属 T042/T059 已知项，不影响库内对账）。

- **A. 全量明细(月×模型) = T081 汇总** ✅：7 主力模型 live vs 汇总差异均 <0.4%（差异来自汇总四舍五入 2 位小数）；其余 10 个长尾模型（各 <0.03 亿输入）在明细与汇总里都在 → 全部逐请求明细汇总 = 汇总。
- **B1. live 月度 UCloud-GPT vs T073 月报** ✅：7月 160.8/160.8、8月 157.4/157.4、9月 34.0/34.0、10月 75.7 vs 72.9（差 3.9%，因 T073 的 10月只到 15 日、且 10/10 后 UCloud 切回 OneRouter 量骤降，正常）。
- **B2. live 逐模型 北京 9/15–10/15 vs T071 表** ✅：gpt-6-luna 102.68/102.11、gpt-6-sol 2.52/2.52、gpt-5-mini 0.57/0.57、gpt-5.6-terra 0.0322/0.0322、gpt-5.6-luna 0.0124/0.0124、gpt-5.4 0.0008/0.0008；最大差异 1.46%。
- **已知偏差（非对账失败）**：8 月 UCloud gpt-5.6-luna output 库内 0.20 vs 账单 0.61（input 15.18B vs 15.16B 对齐）。这是库内记录 vs 供应商账单的缺口（T042/T059，未决），库内口径自洽，不影响上面 A/B 的库内对账。

对账脚本：`scripts/_t081_reconcile2.py`（A+B1）、`scripts/_t081_b2.py`（B2 修正窗口）。交付：`output/ucloud_month_model_202607_20261022.xlsx`（live 月×模型全量）。

## 供应商对账单对照（用户复核：我们汇总数 vs UCloud 账单）

用户要确认"我们记得的汇总数"和"供应商(UCloud)给的对账单"是否差不多。数据源：Downloads 下 **Funstory.ai Limited 推文科技有限公司 6/7/8 月份账单**（UCloud 卖方，我方抬头=Funstory/推文），逐模型取「订单汇总」的计费单元 input/output 用量；库内取 `immdata.token_used_aw` 同北京账期窗。

结论：**主流模型（gpt-5-mini / luna / terra）输入基本能对上；已知两处系统性缺口**（与 T019/T042/T059/T017 完全一致）：

| 月 | 模型 | 账单 in / out (B) | 库内 in / out (B) | 输入差 | 输出差 | 判定 |
|----|------|-------------------|-------------------|--------|--------|------|
| 7 | gpt-5-mini | 15.49 / 3.58 | 15.50 / 3.56 | +0.06% | −0.66% | ✅ 对得上 |
| 7 | gpt-5.4 | 0.747 / 0.188 | 0.582 / 0.128 | −22.1% | −31.8% | 中台 Key 不进 AW（T017） |
| 8 | gpt-5.6-luna | 15.18 / 9.24 | 15.16 / 3.07 | −0.11% | **−66.8%** | **INPUT齐 / OUTPUT仅1/3**（T042/T059 未决） |
| 8 | gpt-5.6-terra | 0.543 / 0.118 | 0.514 / 0.110 | −5.5% | −7.1% | 量级对得上（类 T019） |
| 8 | gpt-5.4 | 0.103 / 0.039 | 0.052 / 0.011 | −49.6% | −70.8% | 中台 Key 不进 AW |
| 8 | gpt-5-mini | 0.010 / 0.003 | 0.009 / 0.003 | −1.9% | −1.5% | ✅ 对得上 |
| 6 | gpt-5-mini / gpt-5.4 | 见账单 | 见库内 | — | — | 6月结论同 T017（gpt-5.4 中台 Key ~10.7%） |

- **核心结论**：我们记的汇总数 ≈ 供应商账单，在 **输入侧**绝大多数模型差% 在 ±5% 内；**输出侧**除 luna(8月) 与 gpt-5.4(中台) 外也对得上。
- **两个已知未决缺口**（不影响"库内自洽"，但对外给供应商按 output 对账会有差，需单独说明）：
  1. **8 月 gpt-5.6-luna output** 库内系统性约为账单 1/3（输入齐）。根因待计费 v2.4 + 路由账本 v1.1 上生产后复核（T042/T059 暂挂）。
  2. **gpt-5.4 中台/团队 Key** 不写入 `token_used_aw`，库内偏低（T017/T042）。
- 交付：`output/ucloud_vs_supplier_bill_2026_6_8.xlsx`（6/7/8 月逐模型对照 3 表 + 说明）。
- 脚本：`scripts/_t081_billcmp.py`（DB 拉 6–8 月 + 账单解析 + 对照 Excel）。

## 全量逐请求明细（用户修正：范围收敛为八月第一周）

- 用户原话："全量明细拿八月第一周的即可" —— 即放弃全窗 1.3 亿行导出，只取**北京 2026-08-01 ~ 08-07** 的**全量逐请求**（每一行=一次 API 调用，含 input/cached/output token）。
- 约束：该周约 **496 万行**，其中 08-06 / 08-07 各约 200 万行 > Excel 单表 ~105 万上限 → 用 **CSV 按日拆分**（可用 Excel 直接打开），并附一个汇总 xlsx（每日行数/用量 + 说明）。
- 脱敏：SELECT 不取 userid/tenantid/clientip；已确认 CSV 14 列无 PII，可对外给供应商。
- 脚本 `scripts/_t081_export_augwk.py`（流式 `get_cursor`+`fetchmany`，按 bj_date 路由到 7 个 day-CSV）。
- 全窗 1.3 亿行的 `scripts/_t081_export_full.py` 已**终止并删除**，其 `output/ucloud_full/` 大文件（Jul 6.19GB + Aug 部分）已清理。

## 留档

- 定稿 SQL：`sql/reports/query_ucloud_model_detail_202607_20261022.sql`
- 交付：`output/ucloud_model_detail_202607_20261022.xlsx`（汇总+按日明细）
- 交付：`output/ucloud_raw_sample_202607_20261022.xlsx`（逐请求脱敏样本）
- 交付：`output/ucloud_month_model_202607_20261022.xlsx`（对账用 月×模型）
- 交付：`output/ucloud_vs_supplier_bill_2026_6_8.xlsx`（我们汇总数 vs UCloud 6/7/8 月账单 对照）
- 交付：`output/ucloud_augwk_perrequest_summary.xlsx`（八月第一周逐请求每日汇总 + 说明）
- 交付：`output/ucloud_augwk/ucloud_perrequest_2026-08-DD.csv`（DD=01..07，共 7 个，全量逐请求明细，脱敏）
- 临时脚本 `scripts/_t081_discover.py`、`scripts/_t081_build.py`、`scripts/_t081_raw_sample.py`、`scripts/_t081_reconcile.py`、`scripts/_t081_reconcile2.py`、`scripts/_t081_b2.py`、`scripts/_t081_billcmp.py`、`scripts/_t081_export_augwk.py` 保留待清理。
