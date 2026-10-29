# Agent 约定（databend_sql）

本仓是 **沉浸式翻译 `immdata` 只读查数**。所有使用者（含内部同事）均为只读账号。细则在 `.cursor/rules/`（Cursor 自动加载）与 `docs/`；**Codex 等其它 Agent 不会自动读 `.cursor/rules/`，开查必须先读本文件与 `docs/onboarding.md`、`docs/workflow.md`。**

## 硬限制

- 只读：禁止 `INSERT`/`UPDATE`/`DELETE`/`MERGE`/`TRUNCATE`/`DROP`/`ALTER`/`CREATE`/`REPLACE`/`COPY INTO` 等。ETL 可 **撰写** 到 `sql/reports/*_etl.sql`，**禁止代跑**。
- 默认只查 `immdata`。其它 schema 须用户明确要求并说明用途。
- 密码只在本地 `.env`；禁止写入代码、文档、Git。
- 禁止臆造字段或按名字像就 join；用表前核 `docs/tables/`。
- `user_behaviour`：必须对 `created_ts` 做范围过滤；禁止对时间列套 `DATE()`/`to_date()` 后再过滤。
- **转化主体（P018）**：有账号归 `userid`，没有账号用 `device_id`；不要按设备把同一账号拆成多次转化。同一 `deviceid`、同一 `installtime`、多个 userid 时，去重必须有唯一决胜键；这台是否付过费看任一账号（P018-E）。
- **已交付的格子（P044）**：解释某个已交付数字，必须用同一次查询、同一粒度、同一时间锚点。重跑变了先对差异。禁止用另一次跑的子集去减旧总数，禁止用倒推锚点的另一批人顶替这一格。
- **移动端（P037）**：android/ios/ipados 的 `device_id` 大部分不在 `imt_deviceinfo`。结果里含移动端时，必须说明这个缺口，不要只用设备表覆盖。
- **结论必须有证据（P043）**：可以提出猜测，但必须标明是猜测，并写清已看到的事实和还缺什么才能证实。禁止把猜的原因说成答案。付费前出现过的事件不是付费原因；登录墙不是付费原因。碰不到 MySQL 源库、同步作业、支付后台时，不要判断它们里面有什么。业务表经 `H:\imt_data_synch` 北京每天 01:00 日更；副本停在约 01:xx 是正常水位。

## Codex：写 SQL 前就看这里

Cursor 每轮自动加载 `.cursor/rules/`。**Codex 不会。** 本文件以外的规范，不打开就等于没有。不要用「我读过 pitfalls」代替下面几条；写 SQL 前先用一两句话写出本题口径，再查。

- **某国 / 某语言用户**：默认 `imm_device_native_language` 的母语，不是 `real_geo`。`real_geo` 只表示当时 IP。设备和账号母语、IP 地区说不清时先问。结论里写明主体是设备还是账号。叫「泰国用户」而实际过滤的是 `real_geo='TH'`，算错。
- **转化 / 漏斗 / 转化率**：有账号归 **userid**（同一账号多设备只算 1 人）；没有账号才用 `device_id`。按设备数转化，算错。同一设备多行账号见 P018-E：去重要有唯一决胜键；付过费看任一账号。
- **已交付的格子（P044）**：同一个格子必须来自同一次查询。重跑变了先对差异，再决定是否替换。不要用另一次的子集去减旧总数。
- **设备级新装（P034）≠ 真新账号**：`is_new_user_today` 含重装老号。**新付费墙类只出剔老号一版（P039，不必再问，也不要再附含老号全量）**；刀法 `userinfo.createtime < 激活−1天`；不要用 `deviceinfo` 时间判老号。
- **AB / 实验须限版本（P040，不必再问）**：实验起始版或近 N 版；用 semver 数值比较，禁止字符串 `version >= 'x.y.z'`（会漏 `1.32.10`）；老客户端带 `ab_tag` ≠ 当期实验流量。
- **核心月报正文（P041）**：对齐上月截图版式；段末「整体来看 / 收入叙事 / 注」须按当月数据与季节重写，禁止换数字照抄上月。细则见 `docs/norms/query.md`「月报正文格式」。
- **点击→订单漏斗（P042）**：CTA/去付费归因成单时，订单时间相对点击**默认前放宽 1 天**；不改累计付费锚点窗。
- **移动端**：不要只用 `imt_deviceinfo` 覆盖 android/ios/ipados。
- `user_behaviour` 必须限 `created_ts` 范围，不要对时间列套函数。
- **付费和试用分开（P013）**：付费 = `amountpaid>0`，或兑换码（淘宝购买：`ordertype=code` 或 snap `onetime*`，金额经常为空）。试用 = `amountpaid=0` 且不是兑换码。兑换码算付费，不要放进试用，也不要叫 0 元单。
- **没有证据不要下结论（P043）**：猜测必须标明，并附已看到的事实与尚缺的证实条件。禁止把副本时间落后说成同步故障或源库没单。付费前出现过的事件不是付费原因；登录墙不是付费原因；归类只跟决定性的那一条事件。代码里的条件必须保留，不能说成所有人都会。

## 开查 5 步

1. `docs/norms/README.md` 定一个大类：`query` | `anomaly` | `dashboard` | `audit`。
2. `docs/tasks/README.md` 占 `T###`，用 `docs/tasks/_TEMPLATE.md` 建档。
3. 读对应 `docs/norms/<大类>.md` + 相关 `docs/pitfalls.md`。
4. 对照需求做潜在口径审查（P032）；细节未写清先问（P025）。交付形态未说明先问汇总 vs Excel。
5. 映证 `docs/tasks/` 与 `sql/reports/` 是否已有相近口径。

埋点/墙/AB 对不上：`git pull` 插件仓再搜（`docs/norms/extension.md`）；路径默认 `F:\extension`，用户机器不同则以其告知的路径为准。

## 交付

- 正式交付前按任务抽样（P019）：既验 SQL，也要判断数字是否合理（假零/串组/量级）；不要默认验翻译次数；不要为抽样重跑全量。
- 留档：`docs/tasks/`（大类 + 需求覆盖对照）+ 定稿 SQL 进 `sql/reports/`；过程 `*_patch`/`*_fix` 并入后删除。
- 清零试错：`sql/adhoc/`、过期 `output/`、`_tmp_*.py`。抽样结果不落文件。
- 未对照需求逐项验收，不得称完成。

## 入口

上手：`docs/onboarding.md` · 工作流：`docs/workflow.md` · 表：`docs/tables/`
