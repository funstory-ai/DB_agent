# Stripe 数据直读（只读，不落库）

本项目除 `immdata` 外，**唯一允许直读的外部数据源是 Stripe**，用途是和 `immdata` 的行为/订单数据 join 做商业分析。本目录是这套能力的**入口与基础文档**：clone 下来后照本文即可自行连通、按口径取数。

**核心形态**：Stripe 侧**不落库、不做同步任务**。用受限只读 Key 通过 API 按需拉取 → 缓存到 `output/` → 在内存里和我方 `immdata` join → 产出 Excel/结论。相关历史任务：T124（可行性）→ T126（商业分析）→ T127（主动取消流失）→ T128（对照组行为）。

## 1. 能不能用 / 边界

- ✅ **API 可达**：`api.stripe.com:443` 直连即可，**不需要** Google Ads 那套 `127.0.0.1:7897` 代理。
- ✅ **Key**：只能用**受限只读 Key（RAK，`rk_live_...`）**，在 Stripe Dashboard 建，只勾 Read、Write 全 None。核心交易资源可读（见 [resources.md](resources.md)）。
- ❌ **当前 Key 读不到**：`checkout/sessions`（缺 `checkout_session_read`）、`account`/`accounts`（缺 `connected_account_read`）。要这两块得让管理员在 Dashboard 给 Key 补权限；403 响应里带直达授权链接。
- ❌ **不能做单次点击级归因**：`imt_campaigninfo.reference` 里 gclid 命中 0；Stripe 也没有 gclid。
- ⚠️ **Stripe 只覆盖它自己的渠道**：`in_*` invoice 只代表 Stripe 收的单。兑换码（`ordertype=code`）、iOS、Google Play、微信支付不进 Stripe ⇒ **不能当全量收入**。

## 2. 配置（clone 后一次性）

1. 依赖：`pip install -r requirements.txt`（`stripe` SDK 6.4.0、`requests`、`python-dotenv`、`pandas`、`openpyxl` 已在内；SDK 绑 API 版本 2023-08-16，账号默认版本 2022-11-15）。
2. 复制 `.env.example` 为 `.env`（**`.env` 已被 gitignore，绝不提交**）。
3. 找管理员要一个受限只读 Key，写入 `.env`：

```
STRIPE_API_KEY=rk_live_你的只读key
```

4. 自检（**只显示前缀和长度，不回显完整 Key**）：

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); k=os.environ.get('STRIPE_API_KEY',''); print('loaded',bool(k),'len',len(k),'prefix',k[:7])"
python scripts/stripe_client.py        # 应打印 balance GET status: 200
```

**凭证纪律**：Key 只从本地 `.env` 读、由客户端从环境变量加载，**禁止写进代码/文档/Git/对话**。注意 Stripe 的 403 错误体会回显 Key 尾缀（形如 `rk_live_...ASay`）——**不要把原始错误响应贴进 issue/群聊/日志**。

## 3. 只读客户端（`scripts/stripe_client.py`）

复用它，**不要自己新写 HTTP 调用**。设计约束：

- 唯一网络出口是 **GET/list**，模块内禁止 POST/DELETE/UPDATE；429/5xx 指数退避；分页用 `starting_after` 游标（避开 offset 漂移）。
- Key 从环境读、不打印；需要固定 API 版本时传 `api_version='2023-08-16'`，否则用账号默认（2022-11-15）——正式取数**要显式固定版本**，避免字段漂移。

```python
import sys; sys.path.insert(0, 'scripts')
import stripe_client as sc

st, body = sc.get('/invoices', {'limit': 5})
for inv in sc.iterate('/invoices',
                      {'created[gte]': 1792339200, 'created[lt]': 1794931200, 'status': 'paid'},
                      page_limit=100, max_pages=600):
    ...   # 逐条 yield，不要 fetchall
```

**性能坑（实测）**：`/invoices` 全状态 + `expand[]=data.customer` 每页很重，2.7 万条曾 6 分钟只拉到 1.2 万；改 `status=paid` + **不 expand**、userid 用我方订单的 `invoiceid` 桥（不需要 Stripe 邮箱）后，26,176 条约 418 秒拉完。`refunds`/`disputes` 单独小任务 10 秒。`/subscriptions?status=canceled` 全量 >4 万条（400 页打满），用 `created[gte]` 预过滤（取消紧跟创建）后 2.8 万条/362 秒。

## 4. 和我方 `immdata` 的关联键（已实测）

| Stripe 侧 | 我方表 / 字段 | 说明 |
|-----------|--------------|------|
| Invoice `id` = `in_*` | `imt_subscriptiongoodsorder.invoiceid` | **主桥**，实付 invoice 映射率 99.9%（13,503/13,508） |
| Subscription `id` = `sub_*` | `imt_subscriptiongoodsorder.subscriptionid` | 覆盖约 82.5% 订单 |
| Checkout Session `id` = `cs_*` | `imt_checkoutsession.checkoutsessionid` | 覆盖约 48% 订单；⚠️ 当前 Key 读不到 session 明细 |
| Price `id` = `price_*` | `imt_subscriptiongoodsorder.priceid` | 覆盖约 90% 订单；判套餐档位 |
| Customer `email` | `imt_userinfo.email` → `userid` | 可解析；脱敏后可见。`expand[]=data.customer` 可一次性带出 |
| Invoice → `payment_intent` → `charge` → `refund`/`dispute` | 我方**无** payment_intent（`outtradeno` 命中 `pi_*` 为 0） | 退款/争议链路由 Stripe 侧取，不是从 checkout session 反取 |

**主体去重**：有账号归 `userid`，无账号用 `device_id`（P018）。金额单位是**分**、时间戳是 **UTC**；我方 `createtime` 是 UTC naive，`created_ts` 过滤须限范围、不要套 `to_date()` 后再过滤。

## 5. 已知坑（务必带进口径）

1. **`status=paid` 不等于有收入**：`amount_paid=0` 的 paid invoice 是试用开通（T126 有 12,668 笔 `subscription_create` 的 "Trial period Pro/Max"），必须单列，不要当脏数据、也不要算进收入。
2. **退款/争议是我方库可能漏记的收入信号**：近 30 天 CNY 退款约 ¥25.6 万 ≈ 实付的 11%；争议 4 笔。
3. **流失原因两层**：`cancellation_details.reason` 100% 有值（主动取消 `cancellation_requested` / 支付失败 `payment_failed`），但自由文本 `comment` 只有约 8%（窗口内 189/2,425）填了，且是多语种；归类只能当 P043 猜测。
4. **支付失败那批接不上行为**：`payment_failed` 的 `latest_invoice` 是未付发票，我方库只记 `finished` 订单，invoice→userid 命中 0%（主动取消批 99.4%）。
5. **相对取消日的行为曲线会骗人**：流失用户"有行为比例"随绝对日期 9 月 11%→11 月 36% 单调上升（登录事件覆盖/产品增长），按相对天画就成了"越接近流失越活跃"的假象。**正确做法**：流失组 vs 对照组按锚点日**同日配对**，在同一绝对窗口比人均强度（T128）；覆盖率/活跃人数不可解读为行为变化。
6. **两张历史表是僵尸表**：`immdata.stripe_users`、`immdata.stripe_churn_users_*` **文档还在、库里已不存在**；不要依赖它们，只能直读 API（见 `docs/tables/immdata/stripe_users.md` 的提示）。
7. **已交付数字按 P044 走原查询**，不要拿 Stripe 的新结果去减旧总数。

## 6. 做一次分析的流程

和本项目其它需求一样，Stripe 分析也必须走硬门禁 `scripts/wf.py`（briefed→caliber→queried→sampled→delivered→audited）：

1. `docs/tasks/README.md` 占 `T###`，建任务档，**时间窗必填**（Stripe 侧按 `canceled_at`/`created` 的北京日，行为侧按 `created_ts`）。
2. 用 [resources.md](resources.md) 确认资源与字段、用第 4 节确认关联键，写清口径（含排除项、配对方式等 P043 猜测）。
3. 取数：复用 `scripts/stripe_client.py` + 参考下面的脚本骨架；结果缓存 `output/`（不提交）。
4. 抽样复核 P019（验字段真伪、映射命中、量级），写进任务档的 `## 抽样复核`。
5. canonical 导出脚本带 `WF_TASK=T###`；`wf audit` 唯一权威。

**可复用脚本（本仓已有，照抄改窗口即可）**：

| 脚本 | 用途 |
|------|------|
| `scripts/stripe_client.py` | 只读 GET/list 客户端（唯一网络出口） |
| `scripts/stripe_probe_20261118.py` | 权限/字段/链路探测（T124） |
| `scripts/stripe_extract_20261118.py` | 30 天 invoices/refunds/disputes 提取（T126） |
| `scripts/stripe_behavior_report_20261118.py` | 收入质量 + 价值分层报告（T126） |
| `scripts/stripe_churn_extract_20261118.py` | 全量取消订阅提取（T127） |
| `scripts/stripe_churn_report_20261118.py` | 取消原因归类 + 流失前曲线（T127） |
| `scripts/stripe_churn_control_20261118.py` | 流失 vs 对照组同锚点日配对（T128） |

定稿 SQL 在 `sql/reports/query_stripe_*`。任务档在 `docs/tasks/query_stripe_*`。

## 7. 入口索引

- Stripe 资源与全部字段：[resources.md](resources.md)
- 本项目上手总入口：[docs/onboarding.md](../onboarding.md)
- 表结构与关联：[docs/tables/README.md](../tables/README.md)
