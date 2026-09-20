# Agent 约定（databend_sql）

本仓是 **沉浸式翻译 `immdata` 只读查数**。所有使用者（含内部同事）均为只读账号。细则在 `.cursor/rules/`（Cursor 自动加载）与 `docs/`；**Codex 等其它 Agent 不会自动读 `.cursor/rules/`，开查必须先读本文件与 `docs/onboarding.md`、`docs/workflow.md`。**

## 硬限制

- 只读：禁止 `INSERT`/`UPDATE`/`DELETE`/`MERGE`/`TRUNCATE`/`DROP`/`ALTER`/`CREATE`/`REPLACE`/`COPY INTO` 等。ETL 可 **撰写** 到 `sql/reports/*_etl.sql`，**禁止代跑**。
- 默认只查 `immdata`。其它 schema 须用户明确要求并说明用途。
- 密码只在本地 `.env`；禁止写入代码、文档、Git。
- 禁止臆造字段或按名字像就 join；用表前核 `docs/tables/`。
- `user_behaviour`：必须对 `created_ts` 做范围过滤；禁止对时间列套 `DATE()`/`to_date()` 后再过滤。
- **转化主体（P018）**：有账号归 `userid`，没有账号用 `device_id`；不要按设备把同一账号拆成多次转化。
- **移动端（P037）**：android/ios/ipados 的 `device_id` 大部分不在 `imt_deviceinfo`。结果里含移动端时，必须说明这个缺口，不要只用设备表覆盖。

## Codex：写 SQL 前就看这里

Cursor 每轮自动加载 `.cursor/rules/`。**Codex 不会。** 本文件以外的规范，不打开就等于没有。不要用「我读过 pitfalls」代替下面几条；写 SQL 前先用一两句话写出本题口径，再查。

- **某国 / 某语言用户**：默认 `imm_device_native_language` 的母语，不是 `real_geo`。`real_geo` 只表示当时 IP。设备和账号母语、IP 地区说不清时先问。结论里写明主体是设备还是账号。叫「泰国用户」而实际过滤的是 `real_geo='TH'`，算错。
- **转化 / 漏斗 / 转化率**：有账号归 **userid**（同一账号多设备只算 1 人）；没有账号才用 `device_id`。按设备数转化，算错。
- **移动端**：不要只用 `imt_deviceinfo` 覆盖 android/ios/ipados。
- `user_behaviour` 必须限 `created_ts` 范围，不要对时间列套函数。

## 开查 5 步

1. `docs/norms/README.md` 定一个大类：`query` | `anomaly` | `dashboard` | `audit`。
2. `docs/tasks/README.md` 占 `T###`，用 `docs/tasks/_TEMPLATE.md` 建档。
3. 读对应 `docs/norms/<大类>.md` + 相关 `docs/pitfalls.md`。
4. 对照需求做潜在口径审查（P032）；细节未写清先问（P025）。交付形态未说明先问汇总 vs Excel。
5. 映证 `docs/tasks/` 与 `sql/reports/` 是否已有相近口径。

埋点/墙/AB 对不上：`git pull` 插件仓再搜（`docs/norms/extension.md`）；路径默认 `F:\extension`，用户机器不同则以其告知的路径为准。

## 交付

- 正式交付前按任务抽样（P019）；不要默认验翻译次数；不要为抽样重跑全量。
- 留档：`docs/tasks/`（大类 + 需求覆盖对照）+ 定稿 SQL 进 `sql/reports/`；过程 `*_patch`/`*_fix` 并入后删除。
- 清零试错：`sql/adhoc/`、过期 `output/`、`_tmp_*.py`。抽样结果不落文件。
- 未对照需求逐项验收，不得称完成。

## 入口

上手：`docs/onboarding.md` · 工作流：`docs/workflow.md` · 表：`docs/tables/`
