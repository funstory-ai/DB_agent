-- =============================================================================
-- Google Workspace 日汇总中间表 + 增量 TASK（写仓执行）
-- 覆盖需求模块：核心概览 / 同人日漏斗 / 范围·模式·服务 / 失败率 /
--               错误分桶（仅 translate_fail）/ Auth Fail·弹窗为可选字段
-- 规范：P022、P023；docs/norms/dashboard.md；task5 需求对照验收
-- 北京自然日边界同 imm_user_target_lan_stats
-- 本查数仓库只读，勿在只读账号执行本文件
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0) 清除旧版（重建前先跑；已存在则必须）
-- -----------------------------------------------------------------------------
ALTER TASK IF EXISTS update_imm_workspace_daily_kpi SUSPEND;
ALTER TASK IF EXISTS update_imm_workspace_daily_dim SUSPEND;

DROP TASK IF EXISTS update_imm_workspace_daily_kpi;
DROP TASK IF EXISTS update_imm_workspace_daily_dim;

DROP TABLE IF EXISTS immdata.imm_workspace_daily_kpi;
DROP TABLE IF EXISTS immdata.imm_workspace_daily_dim;


-- -----------------------------------------------------------------------------
-- 1) 建表
-- -----------------------------------------------------------------------------
CREATE TABLE immdata.imm_workspace_daily_kpi (
  dt_bj DATE,
  -- 1 核心概览
  plugin_active_uv BIGINT,
  translate_user_uv BIGINT,
  translate_click_pv BIGINT,
  translate_success_pv BIGINT,
  translate_success_rate DOUBLE,
  translate_per_user DOUBLE,
  -- 健康：失败 / Auth / 弹窗
  translate_fail_pv BIGINT,
  translate_fail_rate DOUBLE,
  auth_fail_pv BIGINT,
  auth_fail_uv BIGINT,
  error_modal_pv BIGINT,
  error_modal_uv BIGINT,
  -- 2 同人日漏斗（当日同一 device：open → click → success）
  funnel_open_uv BIGINT,
  funnel_open_click_uv BIGINT,
  funnel_open_click_success_uv BIGINT,
  funnel_open_to_click_rate DOUBLE,
  funnel_click_to_success_rate DOUBLE,
  funnel_open_to_success_rate DOUBLE,
  update_time TIMESTAMP
);

CREATE TABLE immdata.imm_workspace_daily_dim (
  dt_bj DATE,
  -- area | mode | service | error_bucket | error_modal_trigger
  dim_type VARCHAR,
  dim_value VARCHAR,
  pv BIGINT,
  uv BIGINT,
  share_ratio DOUBLE,   -- 勿用 share：Databend 保留字（P023）
  update_time TIMESTAMP
);


-- -----------------------------------------------------------------------------
-- 2) 全量回填：昨天及以前各北京自然日
-- -----------------------------------------------------------------------------
REPLACE INTO immdata.imm_workspace_daily_kpi
(
  dt_bj,
  plugin_active_uv, translate_user_uv, translate_click_pv, translate_success_pv,
  translate_success_rate, translate_per_user,
  translate_fail_pv, translate_fail_rate,
  auth_fail_pv, auth_fail_uv, error_modal_pv, error_modal_uv,
  funnel_open_uv, funnel_open_click_uv, funnel_open_click_success_uv,
  funnel_open_to_click_rate, funnel_click_to_success_rate, funnel_open_to_success_rate,
  update_time
)
ON (dt_bj)
WITH day_device AS (
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    device_id,
    MAX(CASE WHEN event_name = 'workspace_open' THEN 1 ELSE 0 END) AS has_open,
    MAX(CASE WHEN event_name = 'workspace_translate_click' THEN 1 ELSE 0 END) AS has_click,
    MAX(CASE WHEN event_name = 'workspace_translate_success' THEN 1 ELSE 0 END) AS has_success
  FROM immdata.user_behaviour
  WHERE event_name IN (
      'workspace_open',
      'workspace_translate_click',
      'workspace_translate_success'
    )
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2
),
funnel AS (
  SELECT
    dt_bj,
    COUNT_IF(has_open = 1) AS funnel_open_uv,
    COUNT_IF(has_open = 1 AND has_click = 1) AS funnel_open_click_uv,
    COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) AS funnel_open_click_success_uv
  FROM day_device
  GROUP BY dt_bj
),
metrics AS (
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_open' THEN device_id END) AS plugin_active_uv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_translate_click' THEN device_id END) AS translate_user_uv,
    COUNT(CASE WHEN event_name = 'workspace_translate_click' THEN 1 END) AS translate_click_pv,
    COUNT(CASE WHEN event_name = 'workspace_translate_success' THEN 1 END) AS translate_success_pv,
    COUNT(CASE WHEN event_name = 'workspace_translate_fail' THEN 1 END) AS translate_fail_pv,
    COUNT(CASE WHEN event_name = 'workspace_auth_request_fail' THEN 1 END) AS auth_fail_pv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_auth_request_fail' THEN device_id END) AS auth_fail_uv,
    COUNT(CASE WHEN event_name = 'workspace_show_error_modal' THEN 1 END) AS error_modal_pv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_show_error_modal' THEN device_id END) AS error_modal_uv
  FROM immdata.user_behaviour
  WHERE event_name IN (
      'workspace_open',
      'workspace_translate_click',
      'workspace_translate_success',
      'workspace_translate_fail',
      'workspace_auth_request_fail',
      'workspace_show_error_modal'
    )
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1
)
SELECT
  m.dt_bj,
  m.plugin_active_uv,
  m.translate_user_uv,
  m.translate_click_pv,
  m.translate_success_pv,
  m.translate_success_pv * 1.0 / NULLIF(m.translate_click_pv, 0) AS translate_success_rate,
  m.translate_click_pv * 1.0 / NULLIF(m.translate_user_uv, 0) AS translate_per_user,
  m.translate_fail_pv,
  m.translate_fail_pv * 1.0 / NULLIF(m.translate_click_pv, 0) AS translate_fail_rate,
  m.auth_fail_pv,
  m.auth_fail_uv,
  m.error_modal_pv,
  m.error_modal_uv,
  COALESCE(f.funnel_open_uv, 0) AS funnel_open_uv,
  COALESCE(f.funnel_open_click_uv, 0) AS funnel_open_click_uv,
  COALESCE(f.funnel_open_click_success_uv, 0) AS funnel_open_click_success_uv,
  COALESCE(f.funnel_open_click_uv, 0) * 1.0
    / NULLIF(COALESCE(f.funnel_open_uv, 0), 0) AS funnel_open_to_click_rate,
  COALESCE(f.funnel_open_click_success_uv, 0) * 1.0
    / NULLIF(COALESCE(f.funnel_open_click_uv, 0), 0) AS funnel_click_to_success_rate,
  COALESCE(f.funnel_open_click_success_uv, 0) * 1.0
    / NULLIF(COALESCE(f.funnel_open_uv, 0), 0) AS funnel_open_to_success_rate,
  NOW() AS update_time
FROM metrics m
LEFT JOIN funnel f ON f.dt_bj = m.dt_bj;


REPLACE INTO immdata.imm_workspace_daily_dim
(dt_bj, dim_type, dim_value, pv, uv, share_ratio, update_time)
ON (dt_bj, dim_type, dim_value)
SELECT
  dt_bj,
  dim_type,
  dim_value,
  pv,
  uv,
  pv * 1.0 / SUM(pv) OVER (PARTITION BY dt_bj, dim_type) AS share_ratio,
  NOW() AS update_time
FROM (
  -- 3.① 翻译范围（真实使用 = click）
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    'area' AS dim_type,
    CASE
      WHEN translation_area = 'document' THEN '全文翻译'
      WHEN translation_area = 'selection' THEN '局部翻译'
      ELSE CONCAT('其他:', COALESCE(translation_area, 'null'))
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  -- 3.② 翻译模式
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    'mode' AS dim_type,
    CASE
      WHEN translation_mode = 'dual' THEN '双语对照'
      WHEN translation_mode = 'translation' THEN '仅译文'
      ELSE CONCAT('其他:', COALESCE(translation_mode, 'null'))
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  -- 3.③ 翻译服务
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    'service' AS dim_type,
    COALESCE(translation_service, '(null)') AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  -- 4 错误原因分桶（严格对齐需求：仅 workspace_translate_fail → Auth/Network/Timeout/Quota/Other）
  -- 勿混入 auth_request_fail / show_error_modal（否则 PV 会大于 translate_fail_pv）
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    'error_bucket' AS dim_type,
    CASE
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%auth%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%unauthorized%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%login%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%token%'
        OR COALESCE(trigger, '') = 'login_required'
        THEN 'Auth'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%network%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%offline%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%fetch%'
        THEN 'Network'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%timeout%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%timed out%'
        THEN 'Timeout'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%quota%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%limit%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%subscription%'
        THEN 'Quota'
      ELSE 'Other'
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_fail'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  -- （可选加分，非初始「产品健康度」）错误弹窗按 trigger
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    'error_modal_trigger' AS dim_type,
    COALESCE(trigger, '(null)') AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_show_error_modal'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3
) t;


-- -----------------------------------------------------------------------------
-- 3) 日更 TASK：昨天北京自然日
-- -----------------------------------------------------------------------------
DROP TASK IF EXISTS update_imm_workspace_daily_kpi;
CREATE TASK IF NOT EXISTS update_imm_workspace_daily_kpi
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 30 21 * * *' 'UTC'
COMMENT = 'Google Workspace 看板：昨天 KPI+同人日漏斗'
AS
REPLACE INTO immdata.imm_workspace_daily_kpi
(
  dt_bj,
  plugin_active_uv, translate_user_uv, translate_click_pv, translate_success_pv,
  translate_success_rate, translate_per_user,
  translate_fail_pv, translate_fail_rate,
  auth_fail_pv, auth_fail_uv, error_modal_pv, error_modal_uv,
  funnel_open_uv, funnel_open_click_uv, funnel_open_click_success_uv,
  funnel_open_to_click_rate, funnel_click_to_success_rate, funnel_open_to_success_rate,
  update_time
)
ON (dt_bj)
WITH day_device AS (
  SELECT
    device_id,
    MAX(CASE WHEN event_name = 'workspace_open' THEN 1 ELSE 0 END) AS has_open,
    MAX(CASE WHEN event_name = 'workspace_translate_click' THEN 1 ELSE 0 END) AS has_click,
    MAX(CASE WHEN event_name = 'workspace_translate_success' THEN 1 ELSE 0 END) AS has_success
  FROM immdata.user_behaviour
  WHERE event_name IN (
      'workspace_open',
      'workspace_translate_click',
      'workspace_translate_success'
    )
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY device_id
),
funnel AS (
  SELECT
    COUNT_IF(has_open = 1) AS funnel_open_uv,
    COUNT_IF(has_open = 1 AND has_click = 1) AS funnel_open_click_uv,
    COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) AS funnel_open_click_success_uv
  FROM day_device
),
metrics AS (
  SELECT
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_open' THEN device_id END) AS plugin_active_uv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_translate_click' THEN device_id END) AS translate_user_uv,
    COUNT(CASE WHEN event_name = 'workspace_translate_click' THEN 1 END) AS translate_click_pv,
    COUNT(CASE WHEN event_name = 'workspace_translate_success' THEN 1 END) AS translate_success_pv,
    COUNT(CASE WHEN event_name = 'workspace_translate_fail' THEN 1 END) AS translate_fail_pv,
    COUNT(CASE WHEN event_name = 'workspace_auth_request_fail' THEN 1 END) AS auth_fail_pv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_auth_request_fail' THEN device_id END) AS auth_fail_uv,
    COUNT(CASE WHEN event_name = 'workspace_show_error_modal' THEN 1 END) AS error_modal_pv,
    COUNT(DISTINCT CASE WHEN event_name = 'workspace_show_error_modal' THEN device_id END) AS error_modal_uv
  FROM immdata.user_behaviour
  WHERE event_name IN (
      'workspace_open',
      'workspace_translate_click',
      'workspace_translate_success',
      'workspace_translate_fail',
      'workspace_auth_request_fail',
      'workspace_show_error_modal'
    )
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
)
SELECT
  add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
  m.plugin_active_uv,
  m.translate_user_uv,
  m.translate_click_pv,
  m.translate_success_pv,
  m.translate_success_pv * 1.0 / NULLIF(m.translate_click_pv, 0),
  m.translate_click_pv * 1.0 / NULLIF(m.translate_user_uv, 0),
  m.translate_fail_pv,
  m.translate_fail_pv * 1.0 / NULLIF(m.translate_click_pv, 0),
  m.auth_fail_pv,
  m.auth_fail_uv,
  m.error_modal_pv,
  m.error_modal_uv,
  f.funnel_open_uv,
  f.funnel_open_click_uv,
  f.funnel_open_click_success_uv,
  f.funnel_open_click_uv * 1.0 / NULLIF(f.funnel_open_uv, 0),
  f.funnel_open_click_success_uv * 1.0 / NULLIF(f.funnel_open_click_uv, 0),
  f.funnel_open_click_success_uv * 1.0 / NULLIF(f.funnel_open_uv, 0),
  NOW()
FROM metrics m
CROSS JOIN funnel f;


DROP TASK IF EXISTS update_imm_workspace_daily_dim;
CREATE TASK IF NOT EXISTS update_imm_workspace_daily_dim
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 35 21 * * *' 'UTC'
COMMENT = 'Google Workspace 看板：昨天 area/mode/service/error'
AS
REPLACE INTO immdata.imm_workspace_daily_dim
(dt_bj, dim_type, dim_value, pv, uv, share_ratio, update_time)
ON (dt_bj, dim_type, dim_value)
SELECT
  dt_bj,
  dim_type,
  dim_value,
  pv,
  uv,
  pv * 1.0 / SUM(pv) OVER (PARTITION BY dt_bj, dim_type) AS share_ratio,
  NOW() AS update_time
FROM (
  SELECT
    add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
    'area' AS dim_type,
    CASE
      WHEN translation_area = 'document' THEN '全文翻译'
      WHEN translation_area = 'selection' THEN '局部翻译'
      ELSE CONCAT('其他:', COALESCE(translation_area, 'null'))
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  SELECT
    add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
    'mode' AS dim_type,
    CASE
      WHEN translation_mode = 'dual' THEN '双语对照'
      WHEN translation_mode = 'translation' THEN '仅译文'
      ELSE CONCAT('其他:', COALESCE(translation_mode, 'null'))
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  SELECT
    add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
    'service' AS dim_type,
    COALESCE(translation_service, '(null)') AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_click'
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  -- 错误原因分桶：仅 translate_fail（与全量回填口径一致）
  SELECT
    add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
    'error_bucket' AS dim_type,
    CASE
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%auth%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%unauthorized%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%login%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%token%'
        OR COALESCE(trigger, '') = 'login_required'
        THEN 'Auth'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%network%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%offline%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%fetch%'
        THEN 'Network'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%timeout%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%timed out%'
        THEN 'Timeout'
      WHEN lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%quota%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%limit%'
        OR lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5))
           LIKE '%subscription%'
        THEN 'Quota'
      ELSE 'Other'
    END AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_translate_fail'
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3

  UNION ALL

  SELECT
    add_days(date(add_hours(now(), 8)), -1) AS dt_bj,
    'error_modal_trigger' AS dim_type,
    COALESCE(trigger, '(null)') AS dim_value,
    COUNT(*) AS pv,
    COUNT(DISTINCT device_id) AS uv
  FROM immdata.user_behaviour
  WHERE event_name = 'workspace_show_error_modal'
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1, 2, 3
) t;


ALTER TASK IF EXISTS update_imm_workspace_daily_kpi RESUME;
ALTER TASK IF EXISTS update_imm_workspace_daily_dim RESUME;

-- ALTER TASK IF EXISTS update_imm_workspace_daily_kpi SUSPEND;
-- ALTER TASK IF EXISTS update_imm_workspace_daily_dim SUSPEND;


-- -----------------------------------------------------------------------------
-- 4) 口径纠偏后重刷 error_bucket（写仓执行）
-- 背景：旧版 error_bucket 混入 auth_fail / error_modal，PV 会 > translate_fail_pv
-- 步骤：删旧桶 → 再跑上文「2) 全量回填」里 dim 的 REPLACE 段（或整段 dim 回填）
-- 验收：每日 SUM(error_bucket.pv) = 当日 kpi.translate_fail_pv
-- -----------------------------------------------------------------------------
-- DELETE FROM immdata.imm_workspace_daily_dim WHERE dim_type = 'error_bucket';
-- 然后重新执行本文件中 REPLACE INTO imm_workspace_daily_dim ... 全量回填；
-- 并 CREATE OR REPLACE / 重建 update_imm_workspace_daily_dim TASK 后 RESUME。
