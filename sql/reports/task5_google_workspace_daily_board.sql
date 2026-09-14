-- =============================================================================
-- Google Workspace：按日累计看板（读中间表 · Superset）
-- 前置：写仓执行 task5_google_workspace_daily_etl.sql（含漏斗/错误分桶）
-- 规范：P022；交付验收见 docs/tasks/dashboard_google_workspace_20260814.md + docs/norms/dashboard.md
-- =============================================================================

-- A. 核心概览 · 按日
SELECT
  dt_bj,
  plugin_active_uv,
  translate_user_uv,
  translate_click_pv,
  translate_success_pv,
  translate_success_rate,
  translate_per_user
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- B. 累计 PV / 成功率（UV 勿简单累加）
SELECT
  dt_bj,
  translate_click_pv AS day_click_pv,
  translate_success_pv AS day_success_pv,
  SUM(translate_click_pv) OVER (ORDER BY dt_bj) AS cum_translate_click_pv,
  SUM(translate_success_pv) OVER (ORDER BY dt_bj) AS cum_translate_success_pv,
  SUM(translate_success_pv) OVER (ORDER BY dt_bj) * 1.0
    / NULLIF(SUM(translate_click_pv) OVER (ORDER BY dt_bj), 0) AS cum_translate_success_rate
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- C. 同人日漏斗 · 按日
SELECT
  dt_bj,
  funnel_open_uv,
  funnel_open_click_uv,
  funnel_open_click_success_uv,
  funnel_open_to_click_rate,
  funnel_click_to_success_rate,
  funnel_open_to_success_rate
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- D. 翻译范围 / 模式 / 服务
SELECT dt_bj, dim_type, dim_value, pv, uv, share_ratio
FROM immdata.imm_workspace_daily_dim
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  AND dim_type IN ('area', 'mode', 'service')
ORDER BY dt_bj, dim_type, pv DESC;


-- E. 失败率 / Auth / 弹窗总览 · 按日
SELECT
  dt_bj,
  translate_click_pv,
  translate_fail_pv,
  translate_fail_rate,
  auth_fail_pv,
  auth_fail_uv,
  error_modal_pv,
  error_modal_uv
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- F. 错误分桶 Top（仅 translate_fail；与 translate_fail_pv 同事件集）
SELECT dt_bj, dim_value AS error_bucket, pv, uv, share_ratio
FROM immdata.imm_workspace_daily_dim
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  AND dim_type = 'error_bucket'
ORDER BY dt_bj, pv DESC;


-- G. （可选）错误弹窗按 trigger — 非初始健康度
SELECT dt_bj, dim_value AS modal_trigger, pv, uv, share_ratio
FROM immdata.imm_workspace_daily_dim
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  AND dim_type = 'error_modal_trigger'
ORDER BY dt_bj, pv DESC;


-- H. 近窗卡片（PV/率精确；日 UV 之和非窗口去重）
SELECT
  SUM(translate_click_pv) AS translate_click_pv,
  SUM(translate_success_pv) * 1.0
    / NULLIF(SUM(translate_click_pv), 0) AS translate_success_rate,
  SUM(translate_fail_pv) * 1.0
    / NULLIF(SUM(translate_click_pv), 0) AS translate_fail_rate,
  SUM(auth_fail_uv) AS sum_day_auth_fail_uv_note_not_dedup,
  SUM(error_modal_uv) AS sum_day_error_modal_uv_note_not_dedup
FROM immdata.imm_workspace_daily_kpi
WHERE dt_bj >= DATEADD(day, -30, CAST(DATEADD(hour, 8, NOW()) AS DATE));
