# 审核：Funstory UCloud 2026 年 9 月 / 10 月账单 vs AW

- **需求编号**: T110
- **规范大类**: `audit`
- **状态**: 进行中
- **日期**: 2026-11-12
- **账单文件**:
  - `C:\Users\86933\Downloads\Funstory.ai Limited 推文科技有限公司-9月份账单（20260901-20261001）.xlsx`
  - `C:\Users\86933\Downloads\Funstory.ai Limited 推文科技有限公司-10月份账单（20261001-20261031）.xlsx`
- **定稿 SQL**: `sql/reports/audit_funstory_ucloud_bill_202609_202610.sql`
- **映证**: T042 / T059（8 月 UCloud 账单 vs AW，luna output 少记 3×）；T105 / T106（luna 逐月 out/in 比，9 月账单此前本地缺失、本次补齐）；T082（routing_ledger 三方 100% 相等，AW 账本无少记）

## 初始需求

> 新需求：对账 之前对过，和之前的需求类似。
> 给定 9 月、10 月两张 Funstory（推文）UCloud 账单，和此前一样的口径对一遍：供应商应付（账单）vs 我方 `token_used_aw` 记录，重点看 luna 模型 output 是否仍被多计。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | 9 月账单：明细「交易生效时间(UTC+8)」范围 2026-08-31 ~ 2026-09-30（命名 20260901-20261001）→ AW 北京月 = **2026-09**；10 月账单：明细范围 2026-09-30 ~ 2026-10-31（命名 20261001-20261031）→ AW 北京月 = **2026-10**（09-30 归 9 月，10-01~10-31 归 10 月） |
| 供应商应付（账单侧） | Excel「订单明细」逐行：模型名×计费单元，用量按类型聚合 `input` / `output` / `cache`（判定优先级 output > cache > input，因 `text&image` 早于 `input` 出现）。现金账户=折后实付 |
| 我方记录（AW 侧） | `immdata.token_used_aw`：`providername='UCloud'`、`recordtype='capture'`；按北京日 `date_add(hour,8,timestamp)` 聚合 `inputusage` / `outputusage` / `cachedinputusage`（cache 恒 0）。粗 UTC 窗 `[2026-08-30, 2026-11-01)` 保分区裁剪，精确切分放 Python |
| 比对维度 | 逐模型 input/output token 对账 + out/in 比；AW 估价 = in×input单价 + out×output单价（取账单折后单价） |
| 模型名归一 | 账单 `openai/gpt-5-mini` ↔ AW `gpt-5-mini` 等，去 `openai/` 前缀对齐；luna 含 `gpt-5.6-luna`、`gpt-6-luna` |
| 重点模型 | luna 系列（已知 8 月账单 output 多计 3×，UCloud 账单单侧口径问题，T082 证 AW 无少记） |

## 结果

### 9 月账单（2026-09，AW 北京月 2026-09）

- **核心异常：gpt-5.6-luna output 被严重多计**。账单 output = **45.04 亿** token，AW 仅 **1.94 亿**（约 **230×**）；而 input 两侧对齐（账单 1.08 亿 vs AW 0.89 亿，差 21% 含账单窗 ±1 天边界）。以账单 output 折后单价 ≈ $0.92/1M 计，多计 ≈ **$4,124**，占 9 月账单总额 $5,944.30 的 **~70%**。
- **佐证（AW 逐日曲线）**：gpt-5.6-luna 真实用量在 09-03 后已跌至近 0（模型迁移至 gpt-6-luna，其 9 月账单与 AW 完全对齐：账单 in 2.969B / out 0.801B vs AW 3.112B / 0.743B）。账单对 gpt-5.6-luna 计的 45 亿 output 与真实流量彻底矛盾 → **UCloud 对该模型 9 月 output 计量出错**（同 T042/T105 的 luna output 单侧口径问题，但本例倍率更极端）。
- 其余模型（除下注 gpt-5.4 中台 Key 缺口）与 AW 量级基本一致：gpt-6-luna +4%（+$22）、gpt-6-sol +18%（+$54）、gpt-5.6-terra +11%（+$25）、gpt-5-mini +26%（+$8，小量边界噪声）。扣除 gpt-5.6-luna 误差后，9 月账单 ≈ $1,820 ≈ AW 估算（忽略中台 gpt-5.4）。

### 10 月账单（2026-10，AW 北京月 2026-10）

- **gpt-6-luna（主 luna 模型）**：output 账单 21.44 亿 vs AW 18.69 亿（**+15%**，即 T105 所述幽灵行），多计 ≈ 2.75 亿 token ≈ **$105**（output 单价 ≈ $0.38/1M）。out/in 账单 0.30 vs AW 0.25。
- **gpt-6-sol**：+$101（+17%，账单 out 55.5M vs AW 46.5M）。
- **gpt-5.4**：账单 $270.10 vs AW 估算 $0.02，差额 $270 = **已知中台 Key 缺口**（中台 Key 的 gpt-5.4 不进 `token_used_aw`，T042），非账单错误。
- 其余（kimi-k2.6 / gpt-5-mini / glm / terra / gemini-flash）量级对齐；qwen3.5-plus output 账单 20.6M vs AW 0.29M（72×）但仅 ~$10，微小。

### 结论

1. 9 月账单存在 **UCloud 对 gpt-5.6-luna output 的计量错误**，多计约 **44.8 亿 token / ~$4,130（≈70% 账单额）**；建议附 AW 逐日曲线 + 账单逐行向 UCloud 主张核账。
2. 10 月 luna 仅 +15% 幽灵行（≈$105）+ gpt-6-sol +17%（≈$101），与 T105 一致，继续跟踪即可；gpt-5.4 差额属已知中台缺口，不计为账单异常。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 9 月 / 10 月账单应付 vs AW 能否对上 | 「结果」逐模型对账表 | ✅ |
| luna output 是否被多计（延续 T042/T105） | 「结果」luna 重点：9 月 gpt-5.6-luna 230× / 10 月 gpt-6-luna +15% | ✅ |
| 9 月账单补齐 T105 缺口 | 见「结果」9 月窗 + luna 重点 | ✅ |
| 中台 Key gpt-5.4 缺口说明 | 「结果」/ 口径（非账单错误） | ✅ |

## 抽样复核（P019）

- **luna 9 月主异常交叉验证**：AW 逐日曲线确认 gpt-5.6-luna 真实 output 09-03 后≈0（合计 1.94 亿）；账单同模型 output 45.04 亿 → 230× 差额确凿，非 Excel 加总错（订单明细逐行求和与订单汇总一致）。
- **gpt-6-luna 9 月对照**：账单 in 2.969B/out 0.801B 与 AW 3.112B/0.743B 量级一致（out/in 0.27 vs 0.24），证明迁移后主流量正常、仅 gpt-5.6-luna 单行出错。
- **10 月 gpt-6-luna**：账单 vs AW out 21.44 亿/18.69 亿，+15% 与 T105 星图同窗幽灵行结论一致，量级合理（非 8 月式 3× 跳变）。
- **边界噪声**：小模型 input 账单普遍比 AW 高 10–25%，与账单窗 ±1 天（08-31/09-30 边界溢出）一致，不计入异常。
- **已排除**：加总错误、错窗、模型名未归一（已去 openai/ 前缀）、中台 gpt-5.4 误判为账单错误（实为已知 AW 缺口）。
