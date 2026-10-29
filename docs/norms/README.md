# 规范库（按任务大类）

> **强制**：开查前判定**大类**（不是单个需求编号），读该类一份规范 + 全局底线。  
> **补充原则**：只有出现**新大类**（流程骨架不同）才新建类型文件；同类内部差异写在 pitfalls / 任务留档，不要一个需求一个类型。

## 怎么用

```
新需求
  → 对大类（查询 / 异常验证 / 建看板 / 数据审核 / …）
  → 读 docs/norms/<大类>.md（通常只选 1 个主类）
  → 在 docs/tasks/README.md 分配需求编号 T###，建档并列入「进行中」
  → 全局：pitfalls、tables、交付形态
  → 映证 docs/tasks/ 同类任务
  → 交付后更新索引状态 + 留档；若是新大类或该类新增硬流程 → 才改本规范库
```

## 全局底线（每类都要守）

| 项 | 文档 / 规则 |
|----|-------------|
| 只读 + 仅 `immdata` | `project-readonly` |
| 避坑 | `docs/pitfalls.md` |
| **结论必须有证据（P043）** | 猜测可提，须标明并附依据；禁止揣测后当成答案。见 pitfalls P043 |
| **已交付的格子（P044）** | 同一个数字必须来自同一次查询。重跑变了先对差异。见 pitfalls P044 |
| 选表 | `docs/tables/OVERVIEW.md` |
| 埋点/墙/实验对不上 | [extension.md](extension.md)：先 `git pull` `F:\extension` 再查插件 |
| **主要翻译业务事件/合成口径** | [translate_biz.md](translate_biz.md)（网页/PDF/电子书/悬浮/划词…；跨 query/dashboard 复用） |
| 留档清零 + **定稿收尾（过程补丁并入后删除）** | `docs/tasks/README.md`、`.cursor/rules/archive-cleanup` |
| **需求编号 T### + 命名/索引** | [`docs/tasks/README.md`](../tasks/README.md)「需求编号与命名」；开查占号、收工改状态 |

## 任务大类索引

| 大类 ID | 一句话 | 规范 | 样例 |
|---------|--------|------|------|
| `query` | 查数出结论/明细/汇总；**不建表、不挂看板** | [query.md](query.md) | T001–T003 |
| `anomaly` | 脏数据/极端值/口径异常的验证与汇报 | [anomaly.md](anomaly.md) | T012、T014、T016 |
| `dashboard` | 建/改 Superset 按日看板；任务文档须含 **Superset 挂板对照表**（指标→数据集→图→轴→字段） | [dashboard.md](dashboard.md) | T005（样板）、T006 |
| `audit` | 对照加工规则审已有产物（原 Excel vs 新表等） | [audit.md](audit.md) | T010 datapack |

未命中 → 先挂最接近的大类做完；确认「流程骨架不同」后再**新增一个大类**，不要拆成细类型。

## 何时才新建大类

满足**多数**再开新文件，例如：

- 交付物形态或执行通道不同（如：只读查数 vs 写仓 ETL vs 异常审查模板 vs 原表对照审核）
- 开查步骤骨架不同（例如看板必须实测选型；查询禁止建中间表）
- 预计后续会反复遇到，而不是一次性需求细节

**不要**为「试用 cohort」「流失 cohort」「Workspace 事件」各建一类——这些属于 `query` / `dashboard` 内部口径，写在 `docs/tasks/` 与 Pxxx。

## 交付验收（各大类通用）

交付声称「对齐初始需求」前必须：

1. 任务文档列出**初始需求条目**与落点（SQL/表/字段）对照  
2. 逐项 ✅ 或写明「不做 + 原因」  
3. 有可核对结果时做与口径匹配的抽检（query 见 P019；dashboard 见该类「交付验收」；audit 见该类「核对要点」）  

禁止只靠「跑通了」代替需求覆盖验收。

1. 改或新建对应 `docs/norms/<大类>.md`
2. 更新本 README 索引（仅大类行）
3. 可复用坑 → `pitfalls.md`；单次口径 → `docs/tasks/`
4. 任务文档头部：`规范大类: query|anomaly|dashboard|audit`

## 分层

| 层 | 放什么 |
|----|--------|
| `docs/norms/` | **少数大类**的流程骨架与红线 |
| `docs/pitfalls.md` | 跨任务数据/性能坑 |
| `docs/tasks/` | 单次需求口径与产物 |
| `.cursor/rules/` | Agent 强制约束 |
