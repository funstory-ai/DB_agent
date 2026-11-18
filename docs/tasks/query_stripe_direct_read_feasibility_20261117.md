# Stripe 直读 + 库内分析 可行性调研

- **需求编号**: T124
- **规范大类**: query
- **状态**: 进行中（先行调研；未拿到 KEY，未读 Stripe 侧任何数据）
- **日期**: 2026-11-17
- **定稿 SQL**: 无 / 仅对话汇总（本次为元数据与 ID 覆盖探针，非业务取数）

## 初始需求

用户希望在本项目中让 agent **直接读 Stripe 数据**（给 KEY 的方式），结合 `immdata` 自有库做分析；**暂不向数据库同步**（以后可能再做）。先做先行调研，判断可行性与所需条件，不实际读 Stripe。

## 结论（先行判定）

**技术可行，且有明确分析价值；推荐路线＝只读受限 Key（RAK）+ 按需直读 + 本地 Python 与 `immdata` 只读结果 join，全程不落库。** 关键前提与边界见下，没有 KEY 之前不臆测 Stripe 侧任何数值。

## 已核事实（本机只读勘察，非 Stripe 数据）

| 维度 | 事实 | 影响 |
|------|------|------|
| 网络 | `api.stripe.com:443` 直连通；无 KEY 访问 `/v1/customers` 返回 401，证明端点可达 | 不需要 Google Ads 那种 `127.0.0.1:7897` 代理 |
| SDK | `stripe` 6.4.0（绑定 API `2023-08-16`）、`requests` 已装 | 读取核心资源够用；6.4.0 偏旧，若要新字段建议后续升级（改环境需用户同意） |
| 凭证 | 项目已有 `.env`、`config/*.yaml` 两套 gitignored 凭证位；`scripts/db.py` 代码层只读 | Stripe Key 可放 `.env`/`config`，补 `.gitignore`；只读纪律不变 |
| 历史 Stripe 表 | `docs/tables/immdata/stripe_users.md`、`stripe_churn_users_202603_202606_with_plan.md` 有档，但 `SHOW TABLES FROM immdata LIKE 'stripe%'` 返回空 | 这两张表已不存在（文档陈旧，疑 T066 僵尸表清理时删）。**不能依赖历史落地表，必须直读** |
| 用户邮箱 | `imt_userinfo.id → email` 已验证可解析 | 可用 email 作为 Stripe Customer ↔ 我方 userid 的弱连接键 |

### 关联键覆盖（`imt_subscriptiongoodsorder`，总 929,725 行）

| 我方字段 | 原生 Stripe ID 形态 | 命中行 | 占比 |
|----------|--------------------|--------|------|
| `invoiceid` | `in_*` | 767,209 | 82.5% |
| `subscriptionid` | `sub_*` | 767,209 | 82.5% |
| `checkoutsessionid` | `cs_*` | 448,436 | 48.2% |
| `priceid` | `price_*` | 836,613 | 90.0% |

- `ordertype` 分布：`trial` 304,834 / `subscription` 286,159 / `NULL` 109,394 / `normal` 81,233 / `code` 50,593 / `iospay_trial` 46,546 / `iospay_renew` 33,298 / `upgrade` 5,701 / `googleplay*` 11,788 / `wechat` 179。
- **关键边界**：`code`（兑换码）、`iospay_*`、`googleplay*`、`wechat` 无 `in_*` ID → 不进 Stripe。Stripe 直读只覆盖「Stripe 渠道」这部分，**不能当全量收入**。
- `imt_checkoutsession`：`checkoutsessionid LIKE 'cs_*'` 1,623,007 行，`subscriptionid LIKE 'sub_*'` 432,031；但 `outtradeno`（payment_intent）**0 命中 `pi_*`** → 我方库没有 PI，需从 Stripe Checkout Session 反取 `payment_intent → charge → refund/dispute`。

### Stripe 侧官方约束（已查官方文档）

- 官方**明确推荐给 AI agent 用 RAK（restricted API key，`rk_live_`/`rk_test_`）**，按资源设 Read/Write/None；只用读权限，泄漏也可控。
- 只读所需资源全部设 `Read`、`Write=None`：Charges / PaymentIntents / Invoices / Subscriptions / Customers / Checkout Sessions / Refunds / Disputes / Prices / Products / Balance Transactions / Payouts。
- 限流：live 全局 100 req/s、单 endpoint 25 req/s；429 需指数退避。**逐条 retrieve 77 万 invoice 不可行**（25/s 下约 8.5 小时）；必须 `list` + `created` 游标批量，或按「近 N 天 / 特定 cohort」增量拉。
- Stripe 自己建议数据密集分析用 Sigma / Data Pipeline —— 正对应「以后可能同步」的路径。

## 分析可能性（KEY 到位后，结合 `immdata`）

| 方向 | 连接键 | 能回答什么 | 备注 |
|------|--------|-----------|------|
| 收入对账 | `invoiceid in_*` → Invoice/Charge；`subscriptionid sub_*` → Subscription | 我方 `amountpaid`/`currency`/`orderstatus` vs Stripe `amount_paid`/`paid`/`refunded`；找退款/争议漏记 | 两边付费口径不同（P013：我方含兑换码，Stripe 无），不能直接比总数 |
| 真实到手收入 | Checkout Session → `payment_intent` → Balance Transaction | 净额（扣手续费/退款）vs 我方订单金额 | 我方库无 PI，PI 只能从 Stripe 反取 |
| 订阅生命周期 | `sub_*` + `useremail → imt_userinfo` | 续费/流失真因；对照 `ads_member_valid_daily_snapshot` | 遵守 P043：不把登录墙当原因 |
| 渠道/UTM 补全 | `cs_*` → Checkout Session 的 UTM/引用 | 补渠道归因；能否补 gclid **待验证（猜测）** | 既往结论 gclid 未落库，Stripe Session 是否带需实测 |
| 国别/币种 | Charge `billing_details`/支付方式 | 补 T107/T112 移动端 NO_GEO 缺口 **待验证（猜测）** | 需实测 Stripe 是否带 geo |
| Max 升级补差价 | Invoice `lines` | 验证 P047/P048 升级单真实构成 | 只读 line items |

## 限制与坑（务必带进后续立项）

1. **覆盖不全**：仅 Stripe 渠道订单有 `in_*`；iospay/googleplay/wechat/兑换码不进 Stripe → 只能按渠道对账，不能当全量。
2. **口径不可直接比**：我方付费含兑换码（`ordertype=code`），Stripe 无此概念（P013）。
3. **时区**：Stripe 时间戳为 Unix 秒(UTC)，我方北京日 = +8h；统一到北京日再对。
4. **单位/币种**：Stripe `amount` 为最小货币单位（分）；`currency` 大小写（`cny`/`CNY`）需归一。
5. **P044**：已交付数字（如月报 MRR、T105 多计）解释必须用原查询；Stripe 是第二数据源，不能拿去减旧总数。
6. **凭证安全**：Key 不打印、不进日志/git；只读 RAK；用完可 revoke。绝不贴对话正文。
7. **不擅自同步**：不建定时任务、不落中间表；日后同步须另立任务并经用户批准（T119 教训）。

## 推荐架构（不落库）

- 新增 `scripts/stripe_client.py`：只读封装（强制 GET/list，禁 POST 写端点，429 退避，分页游标），仿 `db.py` 的风格。
- 按需脚本 `scripts/export_stripe_*_YYYYMMDD.py`：拉 Stripe → 内存/pandas → `db.query()` 拉我方对应行 → Python join → Excel/结论到 `output/`。
- 全程不写 Databend。日后若要同步，另立任务，走 `H:\imt_data_synch` 并由用户批准。

## 需要用户提供的东西

1. **KEY 类型**：只读 RAK（`rk_live_...`）；权限按上文清单设 Read、Write 全 None。可先给 `rk_test_` 验证脚本再切 live。
2. **账号范围**：单个 Stripe account 还是 Connect 多账号。
3. **首批分析主题**（决定拉哪些对象/时间窗）：建议先做「近 90 天 Stripe 收入 vs 库内订单对账」。
4. **交付方式**：写入本地 `.env`（`STRIPE_API_KEY=...`）或 `config/stripe.yaml`，**不要贴对话**；我只读文件不打印。
5. **是否接受本地缓存**：拉取结果缓存到 `output/`（不落库，符合「暂不同步」）。

## 口径

| 项 | 定义 |
|----|------|
| 时间窗 | 本次为可行性调研，不产出业务数字；所跑只读 SQL 均为元数据 / ID 覆盖探针，无业务时间窗。正式分析时间窗待 KEY 到位后按首批主题（建议近 90 天）在立项时填写 |
| 分母 / 分子 | 暂不适用；对账方向的分子/分子待首批主题立项确定 |
| 主体 | 有账号归 `userid`，无账号用 `device_id`（P018）；Stripe 侧 Customer 以 email 弱连接，须标不确定性 |
| 数据源边界 | Stripe 只读（待 KEY）；`immdata` 只读（已有）；**不写库、不建同步任务** |

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 直读 Stripe 的技术可行性（网络/SDK/凭证） | 已核事实表 | ✅ |
| 与自有库能否关联（键与覆盖率） | 关联键覆盖表 | ✅ |
| 结合分析的可能性与边界 | 分析可能性表 + 限制与坑 | ✅ |
| 不落库的实现路径 | 推荐架构 | ✅ |
| 用户需提供的条件 | 需要用户提供的东西 | ✅ |
| 实际读 Stripe 并产出结论 | 待 KEY + 首批主题立项 | 进行中（阻塞于 KEY） |

## 11-18 KEY 实测（只读 Key 到位后，全部只读 GET）

用户提供只读 RAK Key（**完整值只在本地 `.env`，不进文档/对话/Git**）。探查脚本 `scripts/stripe_probe_20261118.py`：唯一网络出口为 GET/list，带 429 指数退避，不打印 Key。账号 `acct_1J52ioGc8iUjvqOF`（由权限错误响应确认，live 模式），账号默认 API 版本 `2022-11-15`（响应头 `Stripe-Version`）。

### 权限矩阵（14 个资源逐个 `list limit=1`）

| 资源 | 结果 | 资源 | 结果 |
|------|------|------|------|
| customers | ✅ 可读 | prices / products | ✅ 可读 |
| invoices | ✅ 可读 | balance_transactions | ✅ 可读 |
| subscriptions | ✅ 可读 | payouts | ✅ 可读 |
| charges | ✅ 可读 | coupons | ✅ 可读 |
| payment_intents | ✅ 可读 | events | ✅ 可读 |
| refunds | ✅ 可读 | **checkout/sessions** | ❌ 403 |
| disputes | ✅ 可读 | **account / accounts** | ❌ 403 |

- 缺 `checkout_session_read`（Checkout Sessions Read）与 `connected_account_read`（Accounts Read）。**Key 是"部分只读"而非全量只读**；这两块要做需用户去 Dashboard 给 Key 补权限（链接已在 Stripe 错误响应里）。

### 真实 ID 反查（验证"两边能否对上"）

| 我方 ID | Stripe 结果 | 关键字段 |
|---------|------------|----------|
| `in_1Ucomd…GscXHk12` | ✅ 200 | `amount_paid=6900 cny`、`status=paid`、`billing_reason=subscription_cycle`、`payment_intent=pi_3Ucpiq…`、`customer=cus_ULXg5bf…`、line 描述 `1 × Immersive Translate Pro (at ¥69.00 / month)` |
| `sub_1U5Svg…jqaKgbfP` | ✅ 200 | `status=active`、`current_period_end=2026-12-17 23:58(BJ)`、`cancel_at_period_end=false` |
| `price_1NVaOb…6aMc` | ✅ 200 | `unit_amount=6900 cny`、`recurring=month` |
| `cs_live_bgYhsd…yLvVJ` | ❌ 403 | 缺 `checkout_session_read`，未能反查（非"对不上"） |

- **重要修正（对比 11-17 预判）**：昨天写"我方库无 payment_intent（outtradeno 0 命中 `pi_*`），退款/争议需从 Checkout Session 反取"。实测发现 **Invoice 自带 `payment_intent`，且 Key 可读 `payment_intents`/`charges`/`refunds`/`disputes`** ⇒ 正确链路是 `invoice(in_*) → payment_intent → charge → refund/dispute`，**不依赖 checkout session**。Checkout Session 反而读不了。
- `invoice.customer → /customers/{id}` 可读到 email（脱敏后形如 `PT***@immersivetranslate.com`）⇒ email join 到 `imt_userinfo` 可行；但 `address.country=None`。

### 时区对齐（Stripe `created` vs 我方 `createtime`，4 条样本）

| invoice | Stripe created(BJ) | 我方 createtime(naive) | Stripe UTC vs DB |
|---------|--------------------|------------------------|------------------|
| in_1UcpkBGc… | 2026-11-18 01:00:31 | 2026-11-17 17:00:34 | 差 3 秒 |
| in_1UcomdGc… | 2026-11-17 23:58:59 | 2026-11-17 16:59:16 | 差约 1 小时 |
| in_1UcphDGc… | 2026-11-18 00:57:27 | 2026-11-17 16:57:30 | 差 3 秒 |
| in_1UcojEGc… | 2026-11-17 23:55:28 | 2026-11-17 16:55:58 | 差约 1 小时 |

- 我方 `createtime` 存 **UTC naive**：2 条样本 Stripe `created` 的 UTC 与之仅差 3 秒；另 2 条约差 1 小时。**推测**（P043）：后者是续费/周期类发票，`invoice.created` 用周期锚点、订单 `createtime` 是实际下单时刻，属事件语义差异；正式对账须逐条确认，不据此改任何已交付数字。

### 退款/争议量级（近 30 天，最多翻 3 页×100）

- `refunds`：≥300 笔（3 页仍未翻完），多币种（CNY 主、TWD/USD/KRW/JPY 等）。
- `disputes`：仅 4 笔，但金额含 TWD 279,900 / CNY 64,860（最小单位）。
- 这是我方库可能漏记的收入侧信号，值得作为首批对账主题。

### 猜测状态更新

| 11-17 猜测 | 实测状态 |
|-----------|---------|
| geo 可补移动端 NO_GEO 缺口 | **仍未证实**：`customer.address.country=None`；charge 侧本次 `pi.charges` 返 0 条（取法需改为 `/v1/charges?payment_intent=` 或 expand），下次验证 |
| UTM/gclid 可从 Checkout Session 补 | **仍未证实**：Key 无 `checkout_session_read`；invoice `metadata` 为空 |
| email join 可行 | ✅ 已证实可读到 email |

### 对方案的影响

1. 推荐架构仍成立；只读客户端按 **12 个已验证可读资源**设计，`checkout/sessions`、`accounts` 先不接。
2. 首批"近 90 天收入对账"可行：`invoice → payment_intent → charge → refund/dispute` 链路通。
3. 若用户要 Checkout Session 维度（UTM 补全）或账号身份，需先给 Key 补权限。
4. **版本要固定**：账号默认 `2022-11-15`，本地 SDK 6.4.0 绑 `2023-08-16`；正式取数统一显式指定一个 `Stripe-Version`，避免字段漂移。
5. Key 可在 Stripe Dashboard 随时 revoke；调研完成前不扩大权限、不落库、不建同步。

## 抽样复核（正式交付）

- **权限**：14 个资源逐个 `list limit=1`，结果与 Stripe 403 响应里的权限名一致（P019 方法层）。
- **ID 反查**：4 类真实 ID 中 3 类 200 命中、字段自洽（`amount_paid`/`currency`/`payment_intent`/line 描述与我方订单语义一致），1 类因权限 403（非数据问题）。
- **时区**：4 条逐条对照，未见"Stripe 与我方对不上"的反转；差异方向一致（DB 晚 0 或约 1 小时）。
- **量级**：refunds/disputes 按币种最小单位求和，无负值、无串币种；disputes 笔数少（4）符合预期。
- 结论：Key 可用于只读调研；无 Stripe 业务数字写入任何交付物，未触发 429。
