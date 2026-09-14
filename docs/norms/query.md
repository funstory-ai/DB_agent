# 大类：`query` — 查询类

## 判定

要**查数并给出答案或交付明细/汇总**：人数、次数、转化、字段核对、完备性占比、Excel 一人一行等。

**本类不做**：建中间表、CREATE TASK、挂 Superset 看板（那些属 `dashboard`）；原表 vs 新表加工审核属 `audit`。查数过程中撞上脏数据审查 → 可叠读 `anomaly`，但仍以 query 为主流程。

## 开查

1. 读本文件 + 相关 pitfalls + 目标表文档
2. **占需求编号**：`docs/tasks/README.md` 取下一 `T###`，建档并列入「进行中」（命名见该 README）
3. **交付形态未说明先问**：汇总数字 vs Excel 一人一行（非正式口头结论除外）
4. **细节易分歧先问（P025）**：时间窗对齐、事件范围、是否活跃、兑换码等；禁止擅自加口径再当正式结论
5. **对照需求做潜在口径审查（P032，强制）**：处理变量会不会改写分母/分子？本题要完整漏斗还是条件转化？已知表约束（如 deviceinfo 仅注册）乘上本题会不会选错 join？说不清先问，禁止「表会用就开写」
6. 涉及主要翻译功能事件 → 先读 [`translate_biz.md`](translate_biz.md)
7. 映证 `docs/tasks/` 是否有相近口径

## 类内共通流程

```
需求 → 潜在口径审查(P032) → 定主体与时间窗 → 选表 → 写只读 SQL
  → 小范围核对 →（正式交付）按任务抽样复核 P019
  → 留档 tasks/reports → 清零试错
```

### 正式交付（Excel / 汇总报表）

- **正式交付**：口径写进任务文档；SQL 进 `sql/reports/`；任务文档含**需求覆盖对照**（条目→落点→✅/不做）
- **抽样**：验本任务关键断言（P019）
- **交付验收**：对照初始需求逐项打勾后再称完成（见 `docs/norms/README.md`）

### 非正式小问（对话占比/完备性等）

- 默认抽样或 **1～7 天**短窗；标明是否抽样（P021）
- 一条 SQL 出结论；禁止半小时起步式 behaviour 串行大扫
- 禁止为小问题重跑 cohort 全量

## 查数红线（补充）

- **先问（P025）**：细节易分歧先问用户；禁止擅自加「活跃」或缩短匹配窗后，把低匹配甩给原表。
- **潜在口径（P032）**：写 SQL 前对照需求推演分母/分子/观察窗偏倚；表文档有事实 ≠ 本题口径已正确。
- **时间窗与需求对齐**：需求近 N 天，订单与行为匹配窗同对齐，除非用户另定。
- **效率（P026）**：behaviour 匹配用一次半连接；禁止默认串行大 `IN`。
- **设备级「新装 / 激活」（默认，P034）**：
  - **新装**：`event_name='init_page_daily' AND is_new_user_today='1'` → `COUNT(DISTINCT device_id)`
  - **激活**：`event_name='translate_page' AND is_new_user_today='1'`（同日激活率场景）
  - **禁止**默认用「首条 `translate_page` + `install_day`」冒充新装分母（那是激活/翻译进组，会随晚到首译膨胀已闭合安装周）
  - 看板摘要见 [`dashboard.md`](dashboard.md) §3.1；实验/漏斗分母未另说明时按本条
- **注册墙类实案（P031）**：分母用**设备级埋点新装**（默认同 P034）；`deviceinfo` 只 LEFT JOIN；禁止 INNER JOIN 把未注册踢出后再比转化。
- **账号级新装转化（P033）**：勿裸用 `min(installtime)`；须按三过滤剔老号（安装前现金 / 现金早于账号 / 账龄≥30 天）；禁止用 `iospay_renew` 当老客过滤；复用 `sql/reports/query_new_install_user_filter_20260831.sql`。
- 发现低匹配：先查自身 SQL，再怀疑原表。

## 样例任务

task1 / task2（Excel cohort）、task3（平台/母语/deviceinfo 探查） → 现编号 T001–T003，文档见 `docs/tasks/README.md`
