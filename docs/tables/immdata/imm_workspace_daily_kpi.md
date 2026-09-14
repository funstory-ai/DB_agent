# `immdata.imm_workspace_daily_kpi`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_workspace_daily_kpi` |
| 类型 | BASE TABLE（写仓建表；建好后 sync INDEX） |
| 表注释 | Google Workspace：按日核心 KPI + 同人日漏斗 + 健康汇总 |

## 来源与用途（手工维护）

- **数据来源**：Task `update_imm_workspace_daily_kpi`
- **上游**：`user_behaviour`（workspace_open / click / success / fail / auth_fail / show_error_modal）
- **同步**：全量回填 + 北京昨日增量 `REPLACE ON (dt_bj)`
- **粒度**：`dt_bj` 一行
- **漏斗口径**：当日同一 `device_id`：`open` → 且有 `click` → 且有 `success`（按日同人，非跨天窗口同人）
- **DDL**：`sql/reports/task5_google_workspace_daily_etl.sql`
- **勿想当然**：跨多日卡片 UV 勿对日 UV 简单求和当窗口去重（P022）

## 字段（建表定义）

| 字段 | 说明 |
|------|------|
| `plugin_active_uv` 等 | 核心概览 |
| `translate_fail_*` / `auth_fail_*` / `error_modal_*` | 健康汇总 |
| `funnel_open_*` / `funnel_*_rate` | 同人日漏斗 |
| `update_time` | 写入时间 |
