# 硬流程门禁（wf）

> 目的：把"口径先行、抽样后交付、验收才算完成"从**散文约定**变成**代码强制**，
> 模型跳步/绕过会被 `scripts/wf.py` 直接拒绝，不由自觉决定。
> 设计搬运自 `H:\opencode-workhard` 的 control-plane 哲学：
> 状态在模型之外持久化（SQLite）、非法转换失败即拒、"完成"只能由唯一权威判定。

## 状态机（顺序不可跳级）

```
briefed ──▶ caliber(口径) ──▶ queried(写SQL) ──▶ sampled(抽样复核) ──▶ delivered(交付) ──▶ audited(验收)
```

- `caliber`：任务文档 `## 口径` 的**时间窗**必须已填，否则拒绝。
- `sampled`：`## 抽样复核` 不能是模板占位（P019 证据必须落地），否则拒绝。
- `deliver` / `audit`：**必须已过 `sampled`**，否则拒绝（"没抽样不准交付"在代码层锁死）。
- `audit` 是唯一"完成"权威；在此之前的"看起来做完了"不算完成。

## 模型开查前的强制动作

1. 新需求：`python scripts/wf.py open T### --cat <query|anomaly|dashboard|audit> --title "..." --doc docs/tasks/<文件>.md`
   历史已归档但未注册的任务也要补 `wf open`（否则审计报 `untracked_in_wf`）。
2. 跑任何 SQL 前，先填 `## 口径` 时间窗——不允许"先跑再看"。
3. 调 canonical 导出脚本交付 Excel 时**必须**带 `WF_TASK=T###`：
   ```bash
   WF_TASK=T108 python scripts/export_monthly_report.py --month 202610
   WF_TASK=T108 python scripts/export_gift_weekly_funnel.py --asof 2026-11-02
   ```
   未过 `sampled` 时脚本直接非零退出，文件跑不出来。
4. 交付前完成 P019 抽样并写入 `## 抽样复核`，再 `wf sampled T###`。
5. 完成只能 `wf audit T###`；禁止自称"已完成/已交付/验收通过"。
6. 改动 `sql/reports/` 或任务文档后，跑 `python scripts/wf_audit.py` 自检。

## 命令速查

```bash
python scripts/wf.py open    T108 --cat query --title "..." --doc docs/tasks/xxx.md
python scripts/wf.py caliber T108
python scripts/wf.py queried T108
python scripts/wf.py sampled T108
python scripts/wf.py deliver T108
python scripts/wf.py audit   T108
python scripts/wf.py require T108 sampled   # 给导出脚本 import 用，过不了非零退出
python scripts/wf.py check   T108           # 打印 口径/覆盖/抽样 PASS-FAIL
python scripts/wf.py status  T108
python scripts/wf.py list
python scripts/wf_audit.py                    # 扫全量，输出漂移报告（exit!=0 表示有违规）
```

## 已知归档待修项

见 `docs/tasks/_INVENTORY_20261110.md`「三、索引 / 数据质量待修项」（2026-11-10 已修订）：

- ~~T079 重复：已删逐字节相同的裸名 `query_sales_discount_2026.md`，保留 README 已链接的日期版。~~ ✅ 已解决
- ~~缺 `需求编号` 头：T093 / T107 / T098 三份已于 2026-11-10 补 `需求编号`。~~ ✅ 已解决
- ~~README 索引过期：经核对 T100–T106 实际已在表，仅补齐 T107 行，"下一可用编号"改为 T108。~~ ✅ 已解决
- 部分历史任务缺 `## 口径`/`## 抽样复核`：属历史质量债，`wf_audit.py` 会列出（当前约 missing_caliber 49 / done_without_sampling 39 / missing_coverage 22），按需回填（新任务必须齐全）。

## 限制（诚实说明）

本环境没有 OpenCode 式的"工具前置钩子"能按状态机拦截模型工具调用，因此强制点落在
**交付脚本内的 `wf.require`** 与**事后 `wf_audit`** 两处。模型仍可绕过（如手搓一次性脚本），
所以 `wf_audit.py` 是兜底：定期跑能抓出"自称完成却无抽样/未注册"的漂移。需要更强约束时，
可把 `wf.require` 接进所有导出脚本，或加每日自动化跑审计。
