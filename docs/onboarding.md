# 内部上手（只读）

给公司同事用的 **沉浸式翻译 `immdata` 查数仓**。本仓所有人、所有账号都按 **只读** 使用：禁止改库、造数、代跑建表/TASK。

## 10 分钟能开始

1. 克隆本仓（公司 Git）。**不要提交 `.env`。**
2. Python 3 + 依赖：

```bash
pip install -r requirements.txt
copy .env.example .env
```

3. `.env` 填 **你自己的** Databend **只读** 账号（找仓库管理员要账号，不要用别人的密码）。
4. 用 **Cursor** 打开本仓，开 Agent。`.cursor/rules/` 会自动约束口径与只读。  
   若用 **Codex**：clone 与 `.env` 相同；规则**不会**自动加载 Cursor 的 `.cursor/rules/`。开查前让 Agent 先读根目录 [`AGENTS.md`](../AGENTS.md) 与本页，并遵守 `docs/workflow.md`。定稿 SQL / `scripts/db.py` 与 IDE 无关，可直接跑。
5. 自检：`python scripts/db.py` 能连上即可。

无 Cursor / Codex 时：直接跑 `sql/reports/` 定稿 SQL，或用 `scripts/db.py` 执行 `SELECT`。口径仍以 `docs/norms/`、`docs/pitfalls.md`、`docs/tables/` 为准。

## 你能做什么 / 不能做什么

| 可以 | 不可以 |
|------|--------|
| `SELECT` / `EXPLAIN` / 只读元数据 | `INSERT` `UPDATE` `DELETE` `CREATE` `DROP` 等 |
| 结果落到本地 `output/`（勿提交） | 把密码写进代码、文档、Git |
| 撰写 ETL SQL 给人执行（`*_etl.sql`） | 用本仓账号代跑写仓语句 |
| 默认只查 `immdata` | 默认查 `babel_novel` / `webdata` 等其它 schema |

看板中间表由写仓同学执行；本仓 Agent **不代跑** DDL/TASK。

## 接到需求后怎么走

1. 读 [`docs/workflow.md`](workflow.md)（约 1 分钟）。
2. [`docs/norms/README.md`](norms/README.md) 判定一个大类：`query` / `anomaly` / `dashboard` / `audit`。
3. 在 [`docs/tasks/README.md`](tasks/README.md) 占下一号 `T###`，复制 [`tasks/_TEMPLATE.md`](_TEMPLATE.md) 建任务文档。
4. 用表前核 [`docs/tables/`](tables/)；相关坑读 [`docs/pitfalls.md`](pitfalls.md)。
5. 交付：定稿 SQL → `sql/reports/`；抽样按 P019；验收后更新任务索引。

历史相近口径先扫 `docs/tasks/` 与 `sql/reports/`，不要重造。

## 埋点对不上时

插件代码不在本仓。本机默认路径见 [`docs/norms/extension.md`](norms/extension.md)（示例：`F:\extension`）。

你的机器若路径不同：先自己 clone 插件仓，**查前 `git pull`**，并在对话里告诉 Agent 实际路径。只读，不要改插件。

## 角色

| 角色 | 本仓 |
|------|------|
| 分析 / 查数 | 只读账号 + Cursor Agent 或手跑 SQL |
| 写仓 | 可在本仓 **写** ETL 脚本；**执行**用写仓账号，不在本仓只读账号上跑 |
| 只看结果 | 读 `docs/tasks/` 与 `sql/reports/`，不必连库 |

## 还要读的入口

- 工作流：[`workflow.md`](workflow.md)
- Agent 摘要：[根目录 `AGENTS.md`](../AGENTS.md)
- 表目录：[`tables/README.md`](tables/README.md)
