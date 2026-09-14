# `immdata.imm_workspace_daily_dim`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_workspace_daily_dim` |
| 类型 | BASE TABLE（写仓建表） |
| 表注释 | Google Workspace：按日维度分布（使用 + 错误） |

## 来源与用途（手工维护）

- **Task**：`update_imm_workspace_daily_dim`
- **dim_type**：
  - `area` / `mode` / `service`：来自 `workspace_translate_click`（真实使用）
  - `error_bucket`：仅 `workspace_translate_fail` 归并为 Auth / Network / Timeout / Quota / Other（与 `translate_fail_pv` 同事件；勿混弹窗/auth_fail）
  - `error_modal_trigger`：可选；`workspace_show_error_modal.trigger`
- **粒度**：`dt_bj` × `dim_type` × `dim_value`
- **列**：`pv` / `uv` / `share_ratio`（勿用保留字 `share`，P023）
- **DDL**：`sql/reports/task5_google_workspace_daily_etl.sql`
