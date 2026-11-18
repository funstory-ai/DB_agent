# Stripe × 行为数据 商业分析试水（近 30 天）

- **需求编号**: T126
- **规范大类**: query
- **状态**: 进行中
- **日期**: 2026-11-18
- **定稿 SQL**: `sql/reports/query_stripe_behavior_business_20261118.sql`
- **关联前置**: T124（Stripe 直读可行性，Key 已实测可读）；wf 状态机受门禁约束

## 初始需求

用户："先做一下商业数据分析试一下，要结合 stripe 数据和我们的行为数据"。这是能力试水，不是定案月报；目标是给出一份**真实取数、可解释、有商业含义**的快报，并诚实呈现两侧能结合到什么程度。

## 口径（开查前定，禁止先跑再看）

| 项 | 定义 |
|----|------|
| 时间窗 | **北京日 2026-10-19 ~ 2026-11-17（30 个完整日）**。Stripe `created` 用 UTC 边界 `[2026-10-18 16:00, 2026-11-17 16:00)`；行为 `created_ts` 同 UTC 窗口。今日 11-18 未完整，不纳入 |
| 收入主体 | Stripe **paid invoice**：`status=paid` 且 `amount_paid>0`；我方对照 `imt_subscriptiongoodsorder` 的 `invoiceid LIKE 'in_%' AND orderstatus='finished' AND amountpaid>0` |
| 主体 | 付费用户以 **userid** 为主：Stripe `invoice.customer → customer.email → imt_userinfo.email → id`；行为关联 `user_behaviour.ex_int_arg1=userid`（仅登录事件带，覆盖率须披露，P006）。**无账号者不进入行为分层**，只进收入统计 |
| 退款/争议 | 窗口内 Stripe `refunds`（`status=succeeded`）、`disputes`，经 `payment_intent` 反查 invoice/order |
| 币种 | 按 invoice 原币种统计；跨币种合计仅作参考，不伪造统一口径；CNY 为主，不写死汇率 |
| 行为强度 | 翻译成功类事件（以 `translate_page` 为主，按库内实际事件名确认），窗口内事件数 + 活跃北京日数 |
| 新/续 | `invoice.billing_reason`：`subscription_create`=新订，`subscription_cycle`=续费，`subscription_update`=升级/改档 |
| 边界 | checkout/sessions 与 account 无权限（T124）；移动端 device 缺口（P037）；P013 兑换码不走 Stripe；**P044 不拿本次数字减任何已交付数**；P043 不把相关当因果 |

## 拟回答的商业问题

1. 近 30 天 Stripe 实付规模、退款/争议"漏损"有多大？
2. 新订 vs 续费 vs 改档的收入结构与ARPU？
3. 付费用户里，"翻译用得多"和"用得少"的人群金额是否不同？（价值分层）
4. 我方订单金额 vs Stripe 实付，差异集中在哪？（对账线索）

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| Stripe 实付/退款/争议规模 | 收入质量表 | 进行中 |
| 新订/续费/改档结构 | 结构表 | 进行中 |
| 付费用户行为价值分层 | 分层表 | 进行中 |
| 我方 vs Stripe 金额对账 | 对账表 | 进行中 |
| 抽样复核 P019 | 抽样复核 | 待完成 |

## 数据源与取数方式

- Stripe：`scripts/stripe_client.py`（只读封装，从 `.env` 读 Key，GET/list + 429 退避，不打印 Key）；list 游标批量，不逐条 retrieve 全量。
- 行为/订单/用户：`scripts/db.py.query()`（代码层只读）。
- 结合点：Stripe invoiceID ↔ 我方 `invoiceid`；Stripe customer.email ↔ `imt_userinfo.email`；userid ↔ `user_behaviour.ex_int_arg1`。
- 产出：`output/stripe_behavior/` 多 sheet Excel + 结论；**不写库、不建同步/定时任务**。

## 取数结果（真实读 Stripe + 我方库，窗口北京日 10-19~11-17）

产物：`output/stripe_behavior/stripe_behavior_analysis_20261118.xlsx`（8 sheet）；原始缓存 `output/stripe_behavior/*.json`；只读客户端 `scripts/stripe_client.py`；取数 `scripts/stripe_extract_20261118.py`；报告 `scripts/stripe_behavior_report_20261118.py`；定稿 SQL `sql/reports/query_stripe_behavior_business_20261118.sql`（Q1~Q4）。

### 1. 收入规模与质量

| 指标 | 数值 |
|------|------|
| Stripe `status=paid` 且金额>0 的 invoice | 13,508 |
| 其中 CNY | 9,331 笔，实付 ¥2,315,886.08（¥248.19/笔） |
| `status=paid` 但金额=0（**试用开通**） | 12,668（其中 Pro 8,209 / Max 4,449） |
| 窗口内退款（succeeded） | 637 笔；CNY 退款 ¥255,846.82 ≈ CNY 实付的 **11.0%** |
| 窗口内争议 | 4 笔（2 lost / 2 needs_response） |

### 2. 新订 / 续费 / 改档（全币种笔数）

| billing_reason | 笔数 | 占比 | CNY 实付 |
|----------------|------|------|----------|
| `subscription_cycle`（续费） | 10,622 | 78.6% | ¥1,813,772.72 |
| `subscription_create`（新订） | 2,227 | 16.5% | ¥329,164 |
| `subscription_update`（改档） | 659 | 4.9% | ¥172,949.36 |

窗口内"新订有实付"2,227 vs "0 元试用开通"12,668 ⇒ 同期试用开通远多于立刻付费单；但两者不是同一 cohort（试用可能在窗口外转化），**不作为转化率定案**（P043）。

### 3. 付费用户行为价值分层（仅 CNY、可映射 userid、30 天窗口）

| 累计实付档 | 用户数 | 有行为用户 | 覆盖率 | 人均实付 | 译文页事件 | 字幕事件 | 人均事件 |
|-----------|--------|-----------|--------|---------|-----------|---------|---------|
| ¥30–99 | 5,691 | 4,171 | 73.3% | ¥68.89 | 670,630 | 292,766 | 231.0 |
| ¥100–299 | 164 | 141 | 86.0% | ¥198.86 | 29,945 | 17,933 | 339.6 |
| ¥300–999 | 2,830 | 2,398 | 84.7% | ¥507.58 | 357,026 | 169,604 | 219.6 |
| ≥¥1000 | 168 | 137 | 81.5% | ¥1,392.31 | 15,538 | 10,970 | 193.5 |

⚠️ **不能读作"付得越多用得越少"**（P043）：¥300–999 档代表套餐是 Pro 年费 ¥588（1,502 单）/ ¥579.6（1,199 单），≥¥1000 档是 Max 年费 ¥1,599（145 单）/ Pro 家庭版 ¥1,188 —— 年费金额压在单月窗、且含尚未活跃的年费用户；¥30–99 档几乎全是 Pro 月付 ¥69。行为只覆盖能映射到 userid 的登录事件（40–45%），非登录/移动端未进。

### 4. 我方 vs Stripe 对账（5 笔样本，P019）

5/5 的 `amount_paid`(分) 与币种与我方 `amountpaid` 完全一致：¥411.60 / ¥69 / ¥69 / A$14.99 / NT$1,923.60，状态 paid↔finished。这是样本，**不是全量差异结论**。

## 抽样复核（P019）

1. **金额自洽**：CNY 实付 ¥2,315,886.08 = 9,331 笔 `amount_paid/100` 独立重算一致；平均 ¥248.19 与"月付 ¥69 + 年付 ¥588 混合"量级合理。
2. **零额归因**：12,668 笔零额 paid 的 `billing_reason` 97% 是 `subscription_create`，描述 100% 是 "Trial period/试用期 Pro/Max" ⇒ 证实是试用开通，不是脏数据/漏付。
3. **退款量级**：637 笔全 succeeded；CNY 退款占实付 11%，与 KRW 13% / JPY 11% 同量级，无串币种、无负值。
4. **主体核对**：DB 独立查"有 userid 的付费用户"12,856，与本分析可映射 invoice 12,982 同量级（差异来自同人多笔 invoice 去重口径）。
5. **分层反直觉项**：已查代表套餐描述，确认为年费压缩窗效应，已写入 caveat，不下因果结论。
6. **对账样本**：5/5 金额+币种一致（见上）。

## 结论与边界

- 两侧**能结合**：invoiceid 桥 userid 覆盖 96%（12,982/13,508），行为分层可用；这证明"Stripe 直读 + 行为库"的混合分析落地可行。
- 商业上最硬的三条：① 续费占 78.6% 笔数，是收入基本盘；② CNY 退款占实付 11%，是可量化的漏损；③ 同期试用开通 12,668 ≫ 立刻付费 2,227，但**不能当转化率**。
- **边界**：金额按原币种主单位、跨币种不合计；退款按 created 落窗，非严格同期 cohort；行为仅登录事件（40–45%），移动端/未登录缺口未补；无 checkout/account 权限；P044 不用于解释已交付数字。
- 本单是能力试水，非定案月报；未写库、未建同步/定时任务，Key 只在本地 `.env`。
