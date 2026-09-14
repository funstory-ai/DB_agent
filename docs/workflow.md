# 工作重点

本项目是 **沉浸式翻译插件（`immdata`）只读查数**：答业务问题、写 SQL、完善表口径与避坑。不改库、不造数；**不默认查其他 schema**。内部使用者均为只读；新人先看 [`onboarding.md`](onboarding.md)。

## 优先级（从高到低）

1. **只读 + 仅 immdata**
2. **判定任务大类并读规范** — `docs/norms/README.md` → `query` / `anomaly` / `dashboard` / `audit`（勿拆太细）
3. **先读避坑** — `docs/pitfalls.md`（相关 P）
4. **先核表结构/来源** — `docs/tables/OVERVIEW.md` → 单表文档
5. **埋点/墙/实验对不上** — 先 `git pull` `F:\extension` 再查插件（见 `docs/norms/extension.md`）
6. **口径正确优先** — 小范围核对后再出数
7. **交付前抽样复核** — 正式 query 交付见 P019；禁止为抽样重跑全量
8. **交付后留档并清零试错** — `docs/tasks/` + `sql/reports/`
9. **补规范库** — 仅**新大类**或该类硬流程变更时更新 `docs/norms/`；单次口径进 tasks / pitfalls
10. 新坑：未确认先问；已确认可直接写 pitfalls

## 单次查询标准流程

```
需求
  → 【大类】norms/README → 读 query|anomaly|dashboard|audit 之一
  →（query）交付形态未说明先问
  → pitfalls + 表文档；映证 docs/tasks/
  → 按大类流程执行
  → 【需求验收】对照初始需求逐项 ✅/不做（dashboard 另抽日对账）
  → 正式交付则抽样复核 → 留档（注明规范大类）→ 清零
  → 仅新大类/硬流程变化时改 docs/norms/
```

## 规范库

入口：[docs/norms/README.md](norms/README.md)  
四大类：`query`（查数）· `anomaly`（库内异常）· `dashboard`（建看板）· `audit`（数据审核）。  
原则：一个需求不算一类；流程骨架不同才开新大类。

## 留档与试错清零

见 `docs/tasks/README.md`。

## 抽样复核

见 `docs/sample_validation.md` 与 **P019**。

## 异常数据审查

见 `docs/anomaly_review.md`；主需求为库内异常排查时大类用 `anomaly`。  
原表 vs 新表 / datapack 加工审核用 `audit`（`docs/norms/audit.md`）。

## user_behaviour 性能

- 限时；不对 `created_ts` 套函数后再过滤
- 非正式小问：P021（属 `query` 内分支）
- 按日看板：P022（属 `dashboard`，须实测）
