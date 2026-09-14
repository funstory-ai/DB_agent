# 任务五：Google Workspace 插件看板

- **需求编号**: T005
- **规范大类**: `dashboard`
- **状态**: ✅ 已完成
- **日期**: 2026-08-14；修订 2026-08-17

- **源**：`immdata.user_behaviour`，`event_name` 前缀 `workspace_*`
- **定稿 SQL**：
  - 写仓 ETL（建表/回填/TASK）：`sql/reports/task5_google_workspace_daily_etl.sql`
  - Superset 读中间表：`sql/reports/task5_google_workspace_daily_board.sql`
  - 模块探查明细（勿挂看板）：`sql/reports/task5_google_workspace_dashboard.sql`

## 本任务流程摘要（映证大类）


```
需求模块清单 → 直查实测过慢 → kpi+dim 中间表+TASK（写仓）
  → 抽日对账 → board SQL 分段 → **Superset 挂板对照表**（下节）
  → 按表逐行建 Chart → 看板验收
```

## 存储方案选择（实测后改判）


| 方案 | 结论 |
|------|------|
| 单 SQL 直查 `user_behaviour` | **否**：看板核心按日 90 天实测 **≈52.7s** |
| **日汇总中间表 + CRON TASK** | **是**：昨日增量窗实测 **≈0.9s**；读 `imm_workspace_daily_*` |

## Superset 数据集（纯 SQL，勿 Jinja）


**A. `ws_daily_kpi`** → `immdata.imm_workspace_daily_kpi`（概览 / 漏斗 / 失败率）

```sql
SELECT *
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
```

**B. `ws_daily_dim`** → `immdata.imm_workspace_daily_dim`（结构 / 错误桶）

```sql
SELECT *
FROM immdata.imm_workspace_daily_dim
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
```

时间用图表 Filter on `dt_bj`。分段查询见 `task5_google_workspace_daily_board.sql`。

## Superset 挂板对照表（挂板时只打开本表）


**Dashboard 名**：`Google Workspace`（自定）  
**全局**：Dashboard 时间筛选 → `dt_bj`；数据集 `ws_daily_kpi` / `ws_daily_dim` 见上节 SQL。

| 图# | 需求来源 | 指标 / 模块 | 数据集 | 图表类型 | X 轴 | Metrics（Y） | Series | Chart Filter | 备注 |
|-----|----------|-------------|--------|----------|------|--------------|--------|--------------|------|
| 1 | 需求#1 | 插件活跃用户 | `ws_daily_kpi` | Line Chart | `dt_bj` | `plugin_active_uv` | - | - | |
| 2 | 需求#1 | 翻译用户数 | `ws_daily_kpi` | Line Chart | `dt_bj` | `translate_user_uv` | - | - | |
| 3 | 翻译次数 PV | `ws_daily_kpi` | Line Chart | `dt_bj` | `translate_click_pv` | - | - | 段 A |
| 4 | 翻译成功率 | `ws_daily_kpi` | Line Chart | `dt_bj` | `translate_success_rate` | - | - | 或 Metric=`SUM(success_pv)/SUM(click_pv)` |
| 5 | 人均翻译次数 | `ws_daily_kpi` | Line Chart | `dt_bj` | `translate_per_user` | - | - | 段 A |
| 6 | 累计 click/success PV | `ws_daily_kpi` | Line Chart | `dt_bj` | `cum_translate_click_pv`, `cum_translate_success_pv` | - | - | board 段 B |
| 7 | 同人日漏斗 UV | `ws_daily_kpi` | **Mixed Chart** | `dt_bj` | Bar:`funnel_open_uv`,`funnel_open_click_uv`,`funnel_open_click_success_uv` | - | - | Line 右轴:`funnel_open_to_success_rate`；段 C |
| 8 | 打开→点击转化率 | `ws_daily_kpi` | Line Chart | `dt_bj` | `funnel_open_to_click_rate` | - | - | 段 C |
| 9 | 翻译范围构成 | `ws_daily_dim` | Stacked Bar | `dt_bj` | `pv` | `dim_value` | `dim_type` = `area` | 段 D；`SUM(pv)` |
| 10 | 翻译模式构成 | `ws_daily_dim` | Stacked Bar | `dt_bj` | `pv` | `dim_value` | `dim_type` = `mode` | 段 D |
| 11 | 翻译服务 Top | `ws_daily_dim` | Bar Chart | `dt_bj` | `pv` | `dim_value` | `dim_type` = `service` | 段 D |
| 12 | 翻译失败率 | `ws_daily_kpi` | Line Chart | `dt_bj` | `translate_fail_rate` | - | - | 或 `SUM(fail_pv)/SUM(click_pv)`；段 E |
| 13 | 错误原因 Top | `ws_daily_dim` | Bar Chart | `dt_bj` | `pv` | `dim_value` | `dim_type` = `error_bucket` | 段 F；须与 fail 同事件集 |
| 14 | 加项·近窗 | 近窗翻译成功率（卡片） | `ws_daily_kpi` | Big Number | - | `translate_success_rate` | - | - | 无 dt_bj |
| 15 | 加项·近窗 | 近窗失败率（卡片） | `ws_daily_kpi` | Big Number | - | `translate_fail_rate` | - | - | 无 dt_bj |

## 需求 ↔ 字段 ↔ 建议图表（初始需求 · 与上表对应）


### 1 核心概览（kpi）


| 需求 | 口径 | 字段 | 挂板 |
|------|------|------|------|
| 插件活跃用户 | `workspace_open` 去重 | `plugin_active_uv` | 图 1 |
| 翻译用户数 | click 去重 | `translate_user_uv` | 图 2 |
| 翻译次数 | click PV | `translate_click_pv` | 图 3 |
| 翻译成功率 | success/click | `translate_success_rate` | 图 4 |
| 人均翻译次数 | click_pv/click_uv | `translate_per_user` | 图 5 |

### 2 核心漏斗 · 同人按日（kpi）


| 需求 | 字段 | 挂板 |
|------|------|------|
| 打开 / 打开且翻译 / 打开且成功 | `funnel_open_uv` → `funnel_open_click_uv` → `funnel_open_click_success_uv` | 图 7 Mixed |
| 打开→点击 / 点击→成功 / 打开→成功 | 三个 `funnel_*_rate` | 图 7 右轴 / 图 8 |

### 3 使用结构（dim）


| 需求 | dim_type | 挂板 |
|------|----------|------|
| 翻译范围 | `area` | 图 9 |
| 翻译模式 | `mode` | 图 10 |
| 翻译服务 | `service` | 图 11 |

### 4 产品健康度


| 需求 | 字段 | 挂板 |
|------|------|------|
| 翻译失败率 | `translate_fail_rate` | 图 12 |
| 错误原因 Top | `error_bucket` | 图 13 |

### 可选（非初始健康度）


| 项 | 字段 |
|----|------|
| Auth Fail | `auth_fail_pv` / `auth_fail_uv` |
| 错误弹窗 | `error_modal_*` / `error_modal_trigger` |

## 需求覆盖对照（验收用）


| 初始需求模块 | 中间表字段 / dim_type | 看板 SQL 段 | 状态 |
|--------------|----------------------|-------------|------|
| 1 核心概览 5 指标 | `plugin_active_uv`…`translate_per_user` | A / B / H | ✅ |
| 2 核心漏斗（同人） | `funnel_open_*` 及转化率 | C | ✅ |
| 3.①～③ 范围/模式/服务 | `area` / `mode` / `service` | D | ✅ |
| 4 失败率 | `translate_fail_*` | E / H | ✅ |
| 4 错误原因 Top5 | `error_bucket`（仅 fail） | F | ✅ |
| （可选）Auth / 弹窗 | 见上 | E / G | 可选 |
| toggle 使用率 | — | — | 刻意不做 |
| 跨多日严格 UV | — | — | 卡片用 PV/率 |

## 口径注意


1. 范围/模式/服务用 **click** 字段。
2. 漏斗默认 `device_id`。
3. **error_bucket 只含 translate_fail**。
4. Auth Fail / 弹窗为可选，不写入健康度最小集。

## 量级


事件偏少时日指标会抖，属早期正常。
