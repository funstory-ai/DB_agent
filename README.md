# databend_sql

**沉浸式翻译插件** 数据只读查数仓库，范围限定库 **`immdata`**。禁止改库、造数；默认不查其他 schema。内部同事一律 **只读账号**，上手见 [`docs/onboarding.md`](docs/onboarding.md)。

## 快速开始

```bash
pip install -r requirements.txt
copy .env.example .env   # 填你自己的只读密码，勿提交
python scripts/db.py
```

Agent 摘要：[`AGENTS.md`](AGENTS.md)。任务模板：[`docs/tasks/_TEMPLATE.md`](docs/tasks/_TEMPLATE.md)。

## 工作重点

详见 [`docs/workflow.md`](docs/workflow.md)：

1. 每次查询前读 [`docs/pitfalls.md`](docs/pitfalls.md)
2. 每次用表前核 [`docs/tables/OVERVIEW.md`](docs/tables/OVERVIEW.md) 与单表文档
3. 开查前对照 [`docs/tasks/`](docs/tasks/) 与 `sql/reports/` 是否有可映证的历史任务
4. 讨论确认有坑 → 立刻记入 pitfalls，并改正表文档
5. 涉及次数/明细交付前做 [`docs/sample_validation.md`](docs/sample_validation.md) 抽样复核（**按任务核关键字段**，见 P019；勿为抽样重跑全量）
6. 交付后**留档**并**清零试错产物**（见 [`docs/tasks/README.md`](docs/tasks/README.md)）

## 目录

| 路径 | 用途 |
|------|------|
| `sql/adhoc/` | 临时探查（结束后清零） |
| `sql/reports/` | 定稿可复用 SQL |
| `docs/tasks/` | **任务留档**（口径/产物/映证） |
| `scripts/db.py` | 只读连接（写操作拦截） |
| `docs/pitfalls.md` | 避坑指南 |
| `docs/anomaly_review.md` | **异常数据审查（举例+占比，便于判断）** |
| `docs/tables/` | immdata 表结构与来源 |
| `docs/sample_validation.md` | **抽样复核（交付前强制）** |
| `scripts/sample_validate_task1.py` | 任务一分层抽样交叉验证 |
| `scripts/anomaly_checks.py` | 异常检查脚本（`--check p014|p015|all`） |
| `.cursor/rules/` | Agent 规范 |

表结构刷新：`python scripts/sync_table_catalog.py`
