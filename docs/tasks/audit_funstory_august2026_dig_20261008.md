# 审核：Funstory UCloud 8 月账单对账续查

- **需求编号**: T059
- **规范大类**: `audit`
- **状态**: ⏸ **搁置**（2026-10-12：团队版已排除；2026-10-20 与 T073 一起等计费 v2.4 + 路由账本 v1.1 上生产后看 log。8 月对不上 request_id）
- **日期**: 2026-10-08（搁置 10-09；10-10 形状×时间/团队版；10-12 再搁置）
- **阻塞/续跟**: 上游 `request_id` / 账单 text_output 口径；团队版补不了 luna out 缺口
- **上级**: T042
- **账单**: `C:\Users\86933\Downloads\Funstory.ai Limited 推文科技有限公司-8月份账单（20260801-20260901）.xlsx`
- **定稿 SQL**: `sql/reports/audit_funstory_august2026.sql`
- **探查**: `scripts/_t059_funstory_aug_dig.py` / `_t059_funstory_aug_dig2.py`（交付后删）

## 初始需求

之前月度账单对不上；先回忆结论，再查哪里对不上。

## 回忆（T042）

| 项 | 结论 |
|----|------|
| 抬头推文/Funstory | **我方公司**，不是卖方 |
| 卖方 | **UCloud**（对比 T039 的 GCP/Vertex） |
| 整票应付 | **$13,873.86** |
| AW 估价（主模型） | ~**$7.4k** |
| 对得上？ | **否** |
| 主缺口 | **gpt-5.6-luna output**：账单 9.24B vs AW 3.07B（约 1/3）；差额 ≈ **$5.9k** |
| 次缺口 | 中台 Key 的 gpt-5.4（$302）不进 AW；terra ~+7% |

## 本轮复验（同窗、同单价）

| 模型 | 账单 USD | AW in | AW out | AW 估价 | 对账 |
|------|----------|------:|-------:|--------:|------|
| gpt-5.6-luna | 11,326.65 | 15.162B | 3.066B | **5,369.79** | input≈账单；**out≈账单 33%** |
| gpt-5.6-terra | 2,019.56 | 0.514B | 0.110B | 1,878.57 | ~−7%（可接受量级） |
| gpt-5.4 | 509.12（含中台） | 52.0M | 11.3M | 179.87 | 仅 aw-测试 Key；中台不在 AW |
| gpt-5-mini | 14.50 | 9.4M | 2.5M | 4.47 | 小额 |

数字与 T042 **一致**（未漂移）。

## 哪里对不上（细查）

### 1) 不是 Excel 加错

支付汇总现金合计 13,873.86；luna 订单汇总 output 主档 9,239,221,162 Token × $0.96/1M ≈ $8,872.61，与明细加总一致。

### 2) 不是漏了别的 provider

同窗 `gpt-5.6-luna` 另有 OneRouter out 0.16B、OpenRouter out 0.057B；三者合计 out **3.285B**，仍只有账单 out 的 **~35.5%**。主路径仍是 UCloud。

### 3) 不是「部分行缺 output」

UCloud×luna×capture：4935 万行里 out=0 仅 **17** 行。行级 out/in 均值约 **0.20**；账单日级 out/in 约 **0.52～0.70**。  
例 **08-06**：账单 in 588M≈AW 590M（齐）；账单 out **414M** vs AW **126M**（AW≈账单 30%）。全日性，非坏账日。

### 4) 不是藏在 cache / delta

- AW `cachedinputusage` 全 0（账单有少量 cache，金额仅约二十美元级，解释不了 $5.9k）
- `delta` = in+out，无额外 token
- `usageunit` 仅 `token`；counter 三档（订阅/加油包/新手）都带正常 out，无「只记 in」的独立 counter

### 5) 对不上的位置（结论）

| 位置 | 说明 |
|------|------|
| **主** | `token_used_aw` 对 UCloud/`gpt-5.6-luna` 的 **`outputusage` 系统性约为账单 text_output 的 1/3**（input 对齐） |
| **次** | 中台 Key `gpt-5.4` 应付 $302 **不进** AW |
| **次** | terra / aw-Key gpt-5.4 常规数个百分点残差 |

根因候选（待产品/采集侧确认，本仓只读无法改数）：账单把 reasoning / 工具 / 流式补记等算进 text_output，而 AW 只落了 completion 一部分；或上报链路对 output 折算/截断。**已排除**：加总错误、错窗、漏 Key（除中台）、漏其它 provider、大量零 output 行。

## 本地代码（`H:\imt-api`）哪里会少记

对照 luna 主路径：`ProxyOpenAIController` → `BillingContext` → `BillingLedger` → `token_used_aw`。

### 会少记 / 记偏的点

| # | 位置 | 行为 | 与 luna 缺口匹配度 |
|---|------|------|-------------------|
| 1 | `ProxyOpenAIController` settle（非流/流式） | `OutputUsage = completionTokens`；**`CachedInputUsage = 0` 写死** | cache 故意不记（文档 MVP）；金额级解释不了 $5.9k，但 AW cache 全 0 与此一致 |
| 2 | 同上 + `AiMetrics` | `ReasoningTokens` **只进 Prometheus `thinking`，不加算进 `OutputUsage`** | UCloud 探针里 `completion_tokens` **已含** `reasoning_tokens`（high：1582 含 259；`total=prompt+completion`），故「漏加 reasoning」**解释不了 3× out 缺口**；若账单 text_output **另计/高于** API `completion_tokens`，则 AW 会系统性偏低而 input 仍齐 |
| 3 | 流式 `finalUsage == null` | 打 `stream_usage_unavailable`，**整单不 settle**（in/out 都不记） | 会造成双边漏；与「input 齐、只少 out」**不符**（dig：零 out 行仅 17） |
| 4 | 流式 `Delta = GetTotalTokenByProxyName(total)`（×`TokenMagnification`），非流式 `Delta = totalTokens`（未乘） | `TokenUsageAllocator` 要求 `Delta == in+cache+out`，否则 fallback **整笔记入 Input、Output=0** | 若 mag≠1 会扭曲 in/out；dig 显示多数行 `delta=in+out` 且 out 非零，**不是主因** |
| 5 | `BillingLedgerService`：`CounterName` 空 | **跳过账本写入**（扣费可继续） | 偶发漏行；非全日性 1/3 |
| 6 | BabelFast split sibling 失败（`R21-cr8`） | 已成功 segment usage 可丢 | **非** UCloud luna 主路径 |

### 代码侧结论（相对账单）

- AW 对 luna **按上游 `usage.completion_tokens` 如实落 `outputusage`**，没有再乘系数、也没有 `completion − reasoning`。
- 本地明确少记且与字段对得上的是：**cache 恒 0**；reasoning **不单独入账**（但 UCloud 响应里已含在 completion 内）。
- **无法在代码里找到「把 output 固定记成约 1/3」的折算**；与 dig 的「行行有 out、比值系统性 ~0.20 vs 账单 ~0.61」更吻合的是：**账单 text_output 与 AW/API completion 口径不一致**，而非 settle 漏乘 reasoning。

### 映证 T017（AstraFlow 明细窗 2026-06-25 16:00～06-26 16:00 UTC）

- 文件：`AstraFlow_model_logs_20260625_160000_to_20260626_155900_exported_20260825_084807.xlsx`（gpt-5.4 / AW Key）。
- **id join**：Astra `request_id` ↔ AW `businessid` **仍 0 命中**。
- **形状×时间（2026-10-10）**：形状=`(inputusage, outputusage)`；AW `timestamp` 与 Astra `start_time`（ms epoch）按**同一 UTC 墙钟字面**对齐（文件名窗）；勿把 AW 再当北京−8h。
  - Astra 成功 gpt-5.4 ≈ **105.8k** 行（sheet3 XML 截断，最晚约 UTC 10:52）；AW capture ≈ **54.1k**。
  - 同形状可配对（贪心）≈ **41.2k**（Astra 侧 39% / AW 侧 **76%**）。
  - **唯一形状**（两侧各恰 1 条，n=10,609）：**|Δt|≤60s = 98.7%**，p50≈**1.9s**，p90≈**4.0s**；AW 几乎总略晚（settle）。
  - 贪心全量配对：≤60s **88.6%**，p50≈**1.3s**（重复形状池有误配尾巴）。
- **结论**：**形状能对上的单子，时间也能对上**（秒级）；缺口主要是 **Astra 多、AW 无对应行**（及少量 AW 独有形状），不是「对上形状但时间漂」。
- **对 T059**：luna「out≈1/3」仍是另一量级；点名漏单仍要 upstream `request_id`。脚本：`scripts/_t059_astra_shape_time.py`（临时，勿当长期 ETL）。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 回忆此前结果 | 上文 T042 摘要 | ✅ |
| 查哪里对不上 | luna output 少记 + 中台 | ✅ |
| 排除易混淆因 | provider/零行/cache/delta | ✅ |
| 本地代码少记点 | 上节 imt-api settle / cache / reasoning / allocator | ✅ |
| 采集侧 vs 账单根因定论 | 映证 T017：不能 id join；**形状命中则时间亦对齐（≤1min~99%）**；luna 另案 | ⏸ 等上游 request_id |
| 形状对上后时间能否对齐 | 上节唯一形状 p50≈2s、≤60s 98.7% | ✅ |
| 团队版不写 AW，能否补 luna out 缺口 | 下节 2026-10-10：**不能** | ✅ |

## 2026-10-10：团队版能否补缺口

**代码（`H:\imt-api`）**：`BillingLedgerService.RecordBilling` 在 `TenantId > 0` 时直接 `return`，**不写** `token_used_aw`；团队用量走 `CalculateForTenantMember` → Redis/`imt_teamusagedaily`（映证 T004 / R22p）。

**8 月 `imt_teamusagedaily`**：

| 项 | 量级 |
|----|------|
| 含 luna / gpt-5.6 / gpt-5.4 的 modelname | **0** |
| OpenAIPro 仅 `*Output` 合计 | ~**0.327B** |
| luna 账单 out − AW out 缺口 | ~**6.17B** |

团队全品类 output 也远小于缺口，且**没有 luna 行**。

**结构上也不像**：若团队走同一 UCloud Key 且只是 AW 漏记，应 **input/out 双边都少**；实际 AW **input≈账单、只少 out** → 与「整段团队流量未进 AW」不符。

结论：**团队版不记 AW 是真的，但补不上本题 luna output 缺口。**
| AW 是否因空名/变体漏汇总 | 下节 2026-10-10 探查 | ✅ 排除（不是我方 SUM 滤漏） |
| AW 落库上游 request_id | 积分详单同事推进（2026-10-10 口头） | ⏸ 阻塞中 |

## 2026-10-10：AW 详单是否「自己汇总错了」

窗：`timestamp ∈ [2026-07-31 16:00, 2026-08-31 16:00)`，`recordtype=capture`。

| 嫌疑 | 结果 |
|------|------|
| `providername` / `actualresourceid` 空或空白 | **整窗 0 行**；无空名漏滤 |
| UCloud 大小写/空白变体 | 仅精确 `'UCloud'`（len=6）一种 |
| luna 挂在别的名字上 | 含 `luna` 的只有 `gpt-5.6-luna` × UCloud / OneRouter / OpenRouter 三桶；无别名桶 |
| UCloud 下其它模型误漏 | top out 即 luna/terra/5.4/mini；其余 out 可忽略 |
| `recordtype` 非 capture 藏了 luna out | luna×UCloud **仅 capture** |
| 时间窗 ±1 天 | luna out 几乎不变（3.066B → 3.067B） |
| `delta ≠ in+cache+out` | bad 行 **0**；out_bad=0 |
| 误按 `resourcename` 汇总 | `resourcename='openai'`、`actualresourceid='gpt-5.6-luna'`；定稿 SQL 用 **actual**，正确。若误用 resource=luna 会得到 **空**（不是少记 1/3） |

**全站 `gpt-5.6-luna` out**：UCloud 3.066B + OneRouter 0.162B + OpenRouter 0.057B = **3.286B** ≈ 账单 text_output 9.24B 的 **35.5%**（与 T042/T059 前结论一致）。把其它供应商并进来也补不齐缺口。

**结论**：不是「空供应商/空模型 / 大小写 / recordtype / 窗边界 / delta」导致我方 SUM 漏了大半 output；缺口仍在 **行内 outputusage 相对账单系统性偏低**（或账单口径不同）。

探查脚本：`scripts/_t059_aw_agg_leak_probe.py`（一次性，可删）。

## 抽样复核

08-06 日：账单 in≈AW in；账单 out≈3.3×AW out。✅ 支持「output 少记」定性。  
UCloud luna 探针（`openspec/.../luna-reasoning/luna-ucloud-high-*.json`）：completion 含 reasoning，total=prompt+completion。✅ 支持「代码未再加 reasoning ≠ 3×缺口主因」。  
2026-10-10：空名/变体探查与主口径 luna out **3.066B** 交叉一致。✅
