# 新账本（计费 v2.4 / 路由 v1.1）接入 immdata

- **需求编号**: T095
- **规范大类**: dashboard（涉及写仓建表 + 中间层 + 每日调度；本要求也见下方「与 dashboard 规范的偏差」）
- **状态**: 进行中（阻塞：见「阻塞项」四条，缺一不能投产）
- **日期**: 2026-10-29
- **定稿 SQL**: `sql/reports/dashboard_t095_ingest_ledger_20261029_etl.sql`（ETL 草案，供写仓同学执行）

## 初始需求

把后端新上线的账单追踪账本（对象存储 parquet）接进 `immdata`，使 UCloud 账单可以做**逐请求（request 级）对账**；替代此前依赖 `immdata.token_used_aw` 只能做汇总级对账、且 `businessid` 为 UUID 无法 join 的局面。

来源 triggered：后端《账本变更说明》（2026-10-19）称计费 v2.4 + 路由账本 v1.1 已部署测试环境、待发车；2026-10-29 实测生产已开始写入。

## 与 dashboard 规范的偏差（记录）

本任务**不挂 Superset 看板**，交付物是两张源表 + 每日入湖任务，因此不填「Superset 挂板对照表」。挂最接近的 `dashboard` 大类是因为流程骨架一致（写仓 ETL + 中间层 + TASK）。若后续要按日监控账本覆盖率，再单独开 dashboard 任务挂板。

## 数据源（已实测确认）

| 项 | 值 |
|----|----|
| 存储 | Oracle Cloud Object Storage（S3 兼容），同风控 geo ap-seoul-1 |
| endpoint | `https://ax9rsosmvaht.compat.objectstorage.ap-seoul-1.oraclecloud.com` |
| bucket | `billing-ledger` |
| 生产前缀 | `imt-prod/billing-ledger/{temp\|hourly\|daily}/{yyyy}/{mm}/{dd}/`<br>`imt-prod/routing-ledger/raw/{yyyy}/{mm}/{dd}/{hh}/` |
| 计费账本版本 | v2.4（27 列）；2026-10-29 起生产与 v2.1（19 列）并存 |
| 路由账本版本 | v1.1（35 列）；2026-10-29 起生产开始写，**此前生产无此账本** |

已实测：2026-10-29 生产 `routing-ledger/raw` 持续产出 v1.1 文件（观测区间内 404 → 457 个）；`billing-ledger` 10-28 及之前全为 v2.1，10-29 出现 v2.1 与 v2.4 并存 —— 与《账本变更说明》描述的"一刀切切换、当天两版本共存"一致，**确认发车**。

## 口径

| 项 | 定义 |
|----|------|
| 目标表 1 | `immdata.imt_routing_ledger`（35 列，一行 = 一次实际发给上游的 HTTP 请求） |
| 目标表 2 | `immdata.imt_billing_ledger`（27 列，前 19 列与 `token_used_aw` 同名同义） |
| 两表关联 | `billing.route_attempt_id = routing.route_attempt_id`（多对一）；辅以 `trace_id`（多对多） |
| 对账 join 键 | `routing.upstream_request_id`，对 UCloud = 响应头 `x-request-id` |
| 有效，可 join 的行 | `request_id_state = 'captured'` 且 `outcome = 'success'`（两者缺一不可） |
| 时间基准 | `started_at` 为 UTC；北京日需 `date_add(hour, 8, …)`，与 T081 口径一致 |
| 旧基线表 | `immdata.token_used_aw`（12.49 亿行），UCloud 口径 `providername='UCloud' AND recordtype='capture'` |

## ★ 前置发现：UCloud 流量已于 2026-10-20 断崖式下跌

接入之前先记录这条，它直接决定"建成了有没有东西可对"。

`immdata.token_used_aw`，`providername='UCloud' AND recordtype='capture'`，按北京日：

| 北京日 | 行数 | 主力模型 |
|--------|-----:|----------|
| 10-16 | 145,925 | gpt-6-luna |
| 10-17 | 128,328 | gpt-6-luna |
| 10-18 | 136,127 | gpt-6-luna |
| 10-19 | 90,416 | **gpt-6-luna 90,184** |
| 10-20 | **691** | gpt-6-luna 降至 109 |
| 10-21 | 136 | gpt-6-luna 12 |
| 10-22 ~ 10-29 | 31 ~ 434 | 仅 kimi-k2.6 / glm-5.3-flash / qwen3.5-plus 长尾 |

对照同期其他供应商（10-28 全天）：BabelFast 156 万、OneRouter 138 万、Sophnet 110 万、Google 106 万 —— **`token_used_aw` 本身没有断流**，是 UCloud 单方面掉量。且 `recordtype` 一直是 `capture`，可排除"改了记录类型"的可能。

另有两点与接入排期有关：

- **同步节奏**：`token_used_aw` 最新数据截止 UTC 上一天 23:59:59（全部 provider 一致），查"当天"要等次日；账本入湖也应约定 T+1 加载。
- **跨仓边界**：写路由账本、填充 `UpstreamRequestId` 的代码**不在 `imt-api` 仓库**（全仓 `git log --all -S "UpstreamRequestId"` 为空），因此取值配置的实际状态只能向开发确认，不能在代码侧自证。

## 阻塞项（缺一不能投产）

| # | 事项 | 性质 | 证据 / 依据 |
|---|------|------|------------|
| B1 | 向开发申请**生产只读 AK/SK**（专用子账号） | 待提供 | 现状 `SHOW STAGES` 仅 3 个 stage，无一指向该桶 |
| B2 | 修复 **hourly/daily 聚合丢失 `trace_id` / `route_attempt_id`** | 后端 bug，阻塞级 | 同批数据：temp 原始 2/2 有值 → 同天 hourly 60 行两个键全为 0 |
| B3 | 请开发给路由账本补一层 **daily 聚合** | 需求申请 | 现只有 raw（一天数百小文件），跨境拉不可行；《账本变更说明》明确邀请提此需求 |
| B4 | 确认 **UCloud 流量是否还会回来** | 业务确认 | 见上节，10-20 起掉至 ~200 行/天 |

> B1 的安全提示：不要沿用 `deploy/Test/appsettings.json` 里那对测试凭据 —— 实测它能读取 `imt-prod` 前缀，本身即属越权，不适合也不能用于生产 ETL。

## 已知坑（写入 SQL 文件，执行前必读）

1. **版本号不可写死**：同一天可能有 v2.1/v2.4、v1.0/v1.1 并存。文件名过滤必须把版本号当可变段（`.*-v1\.[0-9]+\.parquet`），写死 `-v1.1.parquet` 会静默漏数据。
2. **缺列容忍**：旧版本文件加载进新列数的表，需 `MISSING_FIELD_AS = NULL`。
3. **覆盖重跑与去重**：Databend 按已加载文件清单跳重，但《账本变更说明》说聚合重跑会用同名对象覆盖；覆盖后同名对象不会重新加载，数据修正不会生效 → 约定 T+1 全天加载，必要时 `FORCE`。
4. **`outcome` 必须过滤 `success`**：失败/重发的路由行也可能捕获到 request id（实测 40 行属此类），但 UCloud 账单没有对应计费项，不滤会造成"我方多、对方少"的假不一致。
5. **不要把路由账本行数当"我方条数"**：它含重试与失败行，天生多于计费；基准条数应取计费事件（现为 `token_used_aw`，未来为 billing 账本）。
6. **path-style 寻址**：OCI 不支持 virtual-host 风格，stage 必须 `ENABLE_VIRTUAL_HOST_STYLE = FALSE`，否则签名不匹配。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 确认生产已发车 | 对象存储实测 10-29 产出 v1.1 / v2.4 | ✅ |
| 定两套表的结构与口径 | SQL §2 DDL | ✅ |
| 定关联方式 | 计费 ↔ 路由 via `route_attempt_id`；账单 join via `upstream_request_id` | ✅ |
| 明确 B1–B4 阻塞项 | 本表 + SQL 文末 | ✅ |
| 落 ETL 草案（stage / DDL / COPY / TASK / 验收 / 排错） | `sql/reports/dashboard_t095_ingest_ledger_20261029_etl.sql` | ✅ |
| PoC：跨境连通 + infer_schema 校准 + 计时 | SQL §1，**待写仓同学执行** | 阻塞 → 进行中 |
| 拿到生产只读 AK/SK | 待开发提供（B1） | 阻塞 → 进行中 |
| 聚合丢键修复上线 | 待后端修（B2） | 阻塞 → 进行中 |
| 路由账本 daily 层 | 待后端加（B3） | 阻塞 → 进行中 |
| UCloud 流量是否恢复 | 待业务确认（B4） | 阻塞 → 进行中 |
| 建表 + TASK 投产 | 待 B1–B4 后 | ❌ 未开始 |
| 表文档 `docs/tables/immdata/imt_billing_ledger.md` / `imt_routing_ledger.md` | 投产后再写 | ❌ 未开始 |
| Superset 挂板 | 本任务不做（见「偏差」） | 不做 |

## 抽样复核（P019）

投产前做一次：

- 取一天 UCloud `ProviderName='UCloud'`，比对 `count(billing capture 行数)` 与 `count(routing success 行数)`；账本少多少即暴露 coverage gap 或尽力而为丢行。
- 抽 20 条 `request_id_state='captured'` 的 `upstream_request_id`，确认值形状一致（UUID 形态）且能落到想象口径。
- 核对 `token_used_aw` 同天同模型的输入 token 合计与新账本是否吻合（两者应接近，若差异大则先查计量口径而非急着投产）。

## 映证

- T081（`query_ucloud_model_detail_202607_20261022.md`）：本任务的对账出发点，旧口径依赖 `token_used_aw` 且 `businessid` 为 UUID 无法 join。
- T042 / T059 / T017（搁置）：历史 luna output 缺口与 gpt-5.4 中台 Key 问题，彼时的结论是"等计费 v2.4 + 路由账本 v1.1 上生产后复核"，本任务即该前置条件。
- 《账本变更说明》（后端出具，2026-10-19）：两账本结构、关联键、版本并存规则的权威依据。
