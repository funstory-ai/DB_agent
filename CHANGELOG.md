# 变更日志

> 本仓为沉浸式翻译插件的**只读查数仓库**（范围 `immdata`）。本文件记录阶段性发版内容，便于 clone 后了解每批新增了什么能力。

## v2026.11.18 — Stripe 直读能力 + 近 7 天查数成果

### 新增：Stripe 只读直读（外部数据源）
不落库、不建同步任务；只读 Key 经 API 拉取 → 缓存 `output/` → 内存 join `immdata` → 出结论。Key 只放本地 `.env`（已 gitignore），文档/脚本/Git 均无真实 Key 值。

- **引导文档**：`docs/stripe/README.md`（连接/权限矩阵/关联键/坑/脚本清单）、`docs/stripe/resources.md`（14 个资源实测字段，3 个 403）。
- **客户端**：`scripts/stripe_client.py`（唯一网络出口，严格 GET/list + 429 退避）。
- **分析任务**（均走 wf 门禁、只读）：
  - T124 直读可行性调研（账号版本、权限矩阵、关联键实测）。
  - T126 Stripe × 行为 商业分析（近 30 天实付/退款争议/结构/价值分层，含对账样本）。
  - T127 主动取消流失 × 流失前行为（comment 多语种归类、核心组对照、时间趋势假象更正）。
  - T128 流失组 vs 对照组同锚点日配对（活跃度/定价页/错误弹窗行为差异）。
- **入口挂载**：`AGENTS.md`、`docs/onboarding.md`、`.cursor/rules/stripe-readonly.mdc`、`docs/tables/README.md`；两张僵尸表文档标注「库里已不存在」。
- **关联键**：`imt_subscriptiongoodsorder.invoiceid/subscriptionid/priceid`（`in_`/`sub_`/`price_`）+ `imt_userinfo.email`；退款/争议链路 `invoice → payment_intent → charge → refund/dispute`（不依赖无权限的 checkout session）。

### 新增：Google Ads 数据接入（T119）
- 一步直写脚本（API → `immdata.google_ads_*`，6 张 ODS 表）、`sql/schema/` 下 DDL。
- CSV 校验、渠道转化基线、飞书繁体网页翻译日表取数 SQL 与交接指引（`docs/guides/`）。
- 依赖：`google-ads`、`google-auth-oauthlib`；凭证 `config/google-ads.yaml` 已加入 gitignore。

### 其它查数成果（11-11 ~ 11-18）
- T125 推文 datapack Q2→Q3 迁移（格式基准固化，迁移脚本禁重跑）。
- MI browser 可识别性/平台分布、SG/MY 收入同比、Tab2 移动端与留存核对、繁体官网 PV/UV、直播助手桌面端接入核查、同语种/运行时压力 Toast、UCloud luna 比率与账单、移动端 top pages、赠礼周漏斗刷新等任务留档与定稿 SQL。

### 安全 / 工程
- `.gitignore` 新增 `config/*client_secret*.json`、`config/*service-account*.json`、`config/google-ads.yaml`、`.vendor/`。
- `.env.example` 新增 `STRIPE_API_KEY` 占位（仅类型说明，无真实值）。
- 全仓扫描确认无真实 Key 值；修正 onboarding 历史坏链。
