# GPT 月度 token：含 UCloud / 不含 UCloud

- **需求编号**: T073
- **规范大类**: query
- **状态**: ⏸ 搁置（2026-10-20：与 T071 / T042 一起暂挂；等计费 v2.4 + 路由账本 v1.1 正式上线后看生产 log）
- **日期**: 2026-10-15
- **定稿 SQL**: `sql/reports/query_gpt_token_monthly_ucloud_20261015.sql`

## 初始需求

只看 GPT 的 token 消耗，按月给出含 UCloud 与不含 UCloud，判断 10 月上旬的下跌是不是只有 UCloud。

## 口径（P032）

| 项 | 定义 |
|----|------|
| 要答的问题 | GPT token 月度量，以及 10/10 下跌是否只发生在 UCloud |
| GPT | `actualresourceid LIKE 'gpt-%'` |
| 用量 | `token_used_aw`，`recordtype='capture'`；input 与 output 分开加总 |
| 含 UCloud | 全部 provider |
| 不含 UCloud | `providername <> 'UCloud'` |
| 时间 | 北京 2025-01-01 起扫到 2026-10-15。实际有数从 2026-03-02 起。10/15 当天不完整，日均用 10/1–10/14 |
| 主体 | token 行，不是人 |

## 结果（拉到有数起点）

GPT capture 从北京 **2026-03-02** 起，再早没有行。日均按有数天数。10/1–10/14 全站 input 日均 **7.61** 亿（10/15 不完整）。

单位：亿 token。

| 北京月 | 天数 | 全部 in/日 | 全部 out/日 | 去掉 UCloud in/日 | 仅 UCloud in/日 | 全部 in | 全部 out |
|--------|-----:|----------:|------------:|------------------:|----------------:|--------:|---------:|
| 2026-03 | 30 | 6.69 | 1.66 | 6.69 | 0 | 200.7 | 49.7 |
| 2026-04 | 30 | 5.69 | 1.43 | 5.43 | 0.26 | 170.8 | 42.8 |
| 2026-05 | 31 | 5.71 | 1.33 | 0.21 | 5.50 | 177.0 | 41.2 |
| 2026-06 | 30 | 6.02 | 1.35 | 0.21 | 5.81 | 180.6 | 40.4 |
| 2026-07 | 31 | 6.16 | 1.36 | 0.97 | 5.19 | 190.9 | 42.2 |
| 2026-08 | 31 | 7.02 | 1.47 | 1.94 | 5.08 | 217.6 | 45.4 |
| 2026-09 | 30 | 7.34 | 1.64 | 6.21 | 1.13 | 220.3 | 49.1 |
| 2026-10 至 14 日 | 14 | 7.61 | 1.91 | 2.41 | 5.20 | 106.5 | 26.8 |

含 UCloud 的全站日均没有跌。去掉 UCloud 后 5–6 月掉到每天 0.2 亿，是那些月的量记在 UCloud 上。

## 6–10 月分项（前一版）

单位：亿 token。10 月到 10-15，当天流水滞后。

| 北京月 | 全部 in | 全部 out | UCloud in | UCloud out | 不含 UCloud in | 不含 UCloud out |
|--------|--------:|---------:|----------:|-----------:|---------------:|----------------:|
| 2026-06 | 180.6 | 40.4 | 174.3 | 40.2 | 6.3 | 0.2 |
| 2026-07 | 190.9 | 42.2 | 160.8 | 36.8 | 30.0 | 5.3 |
| 2026-08 | 217.6 | 45.4 | 157.4 | 31.9 | 60.2 | 13.5 |
| 2026-09 | 220.3 | 49.1 | 34.0 | 8.1 | 186.3 | 41.0 |
| 2026-10 至 15 日 | 108.1 | 27.2 | 72.9 | 18.4 | 35.2 | 8.7 |

同长度对照：9/1–9/15 全部 in 108.9 / out 24.1；10/1–10/15 全部 in 108.1 / out 27.2。

10/10 起 UCloud 的量回到 OneRouter。10/11–10/14 全站 GPT input 每天约 6.6–8.0 亿，与 9/20–9/23（当时几乎全在 OneRouter）同一量级。input 与 output 一起走，不是只少 output。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 只看 GPT | `actualresourceid LIKE 'gpt-%'` | ✅ |
| 每个月 | 有数范围 2026-03-02 至 2026-10-15；6 月与上一版 180.6 亿 input 一致 | ✅ |
| 含 / 不含 UCloud | 上表 | ✅ |
| 是否只有 UCloud | 总消耗没掉；10/10 起从 UCloud 切回 OneRouter | ✅ |

## 复核：接上 UCloud 之后是不是一直走 UCloud

按周重算 input 里 `providername='UCloud'` 的份额。供应商只有 `UCloud` / `OpenAI` / `OneRouter` / `OpenRouter` / `Unknown`，没有别的写法。

- 3 月、4 月前三周：UCloud 为 0，大头是 `OpenAI`（3/15 的 gpt-5-mini 5.58 亿在 OpenAI）。
- 4/27 那周升到 56%，5 月起至 7/27 前约 **96%**。5/15 的 gpt-5-mini 5.25 亿已在 UCloud，量级与 3/15 的 OpenAI 相同。
- 中间三次离开：7/28 起约一周主路径变 OneRouter；8/31 起主路径先 OpenRouter 再 OneRouter，9 月前三周 UCloud 份额约 0%–0.4%（9/15 的 gpt-5.6-luna 7.39 亿在 OneRouter）；10/10 起 gpt-6-luna 回到 OneRouter（10/13：OneRouter 6.57 亿，UCloud 0.73 亿）。

月表把 9 月平均成 UCloud 15%，把这几段离开抹平了。

全站 input / output 从 3/2 到 10/14 共 227 天无缺日。日 input 变异系数 16%，output 17%。完整周的 output/input 在 0.20–0.26。供应商切换的那几周总量没有台阶式下跌。偏低日 input 与 output 同比例下降。

本地只有 UCloud 6–8 月三张账单（Downloads 里的 Funstory 账单）。用账单「订单汇总」的未缓存 input / text output，对 AW `providername='UCloud'`、`recordtype='capture'`、北京账期窗。

6–7 月 gpt-5-mini、gpt-5.4（aw-测试 Key）以及 8 月 terra 的 out/in 都在 0.21–0.23，与库内一致。8 月 gpt-5.6-luna 账单 0.61、库内 0.20：input 15.18B vs 15.16B 对齐，output 账单 9.24B、库内 3.07B。中台 Key 不进 AW，不拿来比比值。

思考模式假设（2026-10-15）：库内 0.20 与 mini/5.4/terra 账单同档，异常的是 luna 账单 0.61。要靠思考 token 补到 3 倍，思考量须约为我们记下的 output 的 2 倍。T059 探针里 reasoning 只占 completion 的 259/1582（16%），且已含在 `completion_tokens` 里，抬不了 3 倍。同月 terra 账单比值 0.22，也不是整户打开思考。

库内各供应商 GPT（input≥0.2B，2026-03-02 至 10-14）out/in 大多在 0.18–0.28。8 月 UCloud luna 为 0.202，同月 OneRouter luna 0.197、OpenRouter luna 0.235。没有第二组到 0.6。略高的是 8 月 OpenAI gpt-5-mini 0.316（0.29B）、9 月 OneRouter gpt-5-mini 0.329（0.44B）。`Unknown`/`gpt-1` 各月 output 为 0，另案。和账单比，只有 8 月 UCloud luna 的 0.61 明显偏离。

## 搁置（2026-10-20）

用户要求：供应商对账和后端账本变更说明一起暂挂，等正式上线后再看 log。8 月历史不回填，不再追。

上线前已对齐的事实（后端说明，写作 2026-10-19，当时只在测试环境）：

- 计费账本 v2.1（19 列）→ v2.4（末尾加 8 列）。关联用第 26 列 `TraceId`、第 27 列 `RouteAttemptId`。Credit 五列生产开关关着，预期为空。不改历史文件。切换当天同一小时/同一天会并存 v2.1 与 v2.4，两份都要读。
- 路由账本生产从 v1.1（35 列）起，只有 `raw/` 小文件。一行一次实际上游 HTTP。`UpstreamRequestId` 是给供应商对单的号。第 35 列 `RawUsageJson` 留上游 `usage` 原文。UCloud 取值位置：`x-request-id`、`x-modelverse-request-id`、`x-trace-id`、响应体 `u_trace_id`。OpenRouter 的 `UpstreamRequestId` 为空，id 在 `UpstreamResponseId`。
- 普通付费代理：计费行 `RouteAttemptId` → 路由行 → `UpstreamRequestId`。自动翻译汇总结算这一列为空（BabelFast，自有服务，不纳入这次对账）。两个账本都是尽力而为，不能拿路由账本对计费总额。
- 当前 `immdata.token_used_aw` 仍是 v2.1 的 19 列。上线后先看对象存储里的生产 log；仓内表要等同步才有新列。

## 抽样复核

通过。加长扫描后 2026-06 全部 input 仍是 180.59 亿，与上一版相同。10-15 UCloud input 14,342,840，与 T071 当天下午的 gpt-6-luna 行一致。10-01 UCloud input 7.61 亿，与 T071 当天 gpt-6-luna 7.41 亿 + gpt-6-sol 0.18 亿及少量旧模型同量级。`Unknown` 各月 output 为 0、input 约 6 亿且平稳，不是 10/10 的去向。
