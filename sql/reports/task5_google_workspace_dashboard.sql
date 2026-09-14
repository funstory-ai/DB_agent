-- Google Workspace 插件看板 SQL（Superset · 模块明细）
-- 按日累计看板请用：sql/reports/task5_google_workspace_daily_board.sql
-- 留档：docs/tasks/dashboard_google_workspace_20260814.md
-- 源表：immdata.user_behaviour；事件前缀 workspace_*；产品标记 ex_char_arg1='google_docs'（click 等）
-- 时间：默认近 30 天；Superset 用过滤器替换 DATEADD 条件
-- 主体：默认 device_id（含未登录）；若要账号可用 ex_int_arg1（仅登录，P006）

-- =============================================================================
-- 0. 可行性速览用：近窗事件量（上线初期数据很少，先跑这个确认有数）
-- =============================================================================
SELECT
  event_name,
  COUNT(*) AS pv,
  COUNT(DISTINCT device_id) AS device_uv,
  COUNT(DISTINCT ex_int_arg1) AS login_uv
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND lower(event_name) LIKE 'workspace%'
GROUP BY event_name
ORDER BY pv DESC;


-- =============================================================================
-- 1. 核心数据概览（与需求表对齐）
--    去重用户默认 device_id；若只要登录账号改用 ex_int_arg1
-- =============================================================================
SELECT
  -- 插件活跃用户：workspace_open 去重
  COUNT(DISTINCT CASE WHEN event_name = 'workspace_open' THEN device_id END)
    AS plugin_active_uv,
  -- 翻译用户数：workspace_translate_click 去重
  COUNT(DISTINCT CASE WHEN event_name = 'workspace_translate_click' THEN device_id END)
    AS translate_user_uv,
  -- 翻译次数：workspace_translate_click PV
  COUNT(CASE WHEN event_name = 'workspace_translate_click' THEN 1 END)
    AS translate_click_pv,
  -- 翻译成功率：success / click（PV）
  COUNT(CASE WHEN event_name = 'workspace_translate_success' THEN 1 END) * 1.0
    / NULLIF(COUNT(CASE WHEN event_name = 'workspace_translate_click' THEN 1 END), 0)
    AS translate_success_rate,
  -- 人均翻译次数：click PV / click UV
  COUNT(CASE WHEN event_name = 'workspace_translate_click' THEN 1 END) * 1.0
    / NULLIF(
        COUNT(DISTINCT CASE WHEN event_name = 'workspace_translate_click' THEN device_id END),
        0
      ) AS translate_per_user
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name IN (
    'workspace_open',
    'workspace_translate_click',
    'workspace_translate_success'
  );


-- =============================================================================
-- 2. 核心漏斗：打开插件 → 点击翻译 → 翻译成功（设备 UV，按日可选）
--    Superset Funnel / 或自算转化率
-- =============================================================================
-- 2a 总漏斗（整段时间窗）
WITH base AS (
  SELECT
    device_id,
    MAX(CASE WHEN event_name = 'workspace_open' THEN 1 ELSE 0 END) AS has_open,
    MAX(CASE WHEN event_name = 'workspace_translate_click' THEN 1 ELSE 0 END) AS has_click,
    MAX(CASE WHEN event_name = 'workspace_translate_success' THEN 1 ELSE 0 END) AS has_success
  FROM immdata.user_behaviour
  WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
    AND event_name IN ('workspace_open', 'workspace_translate_click', 'workspace_translate_success')
    AND device_id IS NOT NULL AND device_id <> ''
  GROUP BY device_id
)
SELECT
  COUNT_IF(has_open = 1) AS step1_open_uv,
  COUNT_IF(has_open = 1 AND has_click = 1) AS step2_click_uv,
  COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) AS step3_success_uv,
  COUNT_IF(has_open = 1 AND has_click = 1) * 1.0
    / NULLIF(COUNT_IF(has_open = 1), 0) AS open_to_click_rate,
  COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) * 1.0
    / NULLIF(COUNT_IF(has_open = 1 AND has_click = 1), 0) AS click_to_success_rate,
  COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) * 1.0
    / NULLIF(COUNT_IF(has_open = 1), 0) AS open_to_success_rate
FROM base;

-- 2b 按日漏斗（折线/多步）
WITH daily AS (
  SELECT
    CAST(created_ts AS DATE) AS dt,
    device_id,
    MAX(CASE WHEN event_name = 'workspace_open' THEN 1 ELSE 0 END) AS has_open,
    MAX(CASE WHEN event_name = 'workspace_translate_click' THEN 1 ELSE 0 END) AS has_click,
    MAX(CASE WHEN event_name = 'workspace_translate_success' THEN 1 ELSE 0 END) AS has_success
  FROM immdata.user_behaviour
  WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
    AND event_name IN ('workspace_open', 'workspace_translate_click', 'workspace_translate_success')
    AND device_id IS NOT NULL AND device_id <> ''
  GROUP BY CAST(created_ts AS DATE), device_id
)
SELECT
  dt,
  COUNT_IF(has_open = 1) AS open_uv,
  COUNT_IF(has_open = 1 AND has_click = 1) AS click_uv,
  COUNT_IF(has_open = 1 AND has_click = 1 AND has_success = 1) AS success_uv
FROM daily
GROUP BY dt
ORDER BY dt;


-- =============================================================================
-- 3. 翻译使用情况
-- =============================================================================
-- 3.1 翻译范围：全文 document / 局部 selection
-- 推荐：用 workspace_translate_click.translation_area（真实发起翻译时的范围）
-- 若坚持 toggle 事件，见 3.1b（toggle=偏好切换次数，≠使用分布）
SELECT
  CASE
    WHEN translation_area = 'document' THEN '全文翻译'
    WHEN translation_area = 'selection' THEN '局部翻译'
    ELSE CONCAT('其他:', COALESCE(translation_area, 'null'))
  END AS translate_area_label,
  COUNT(*) AS pv,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS share_ratio
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_translate_click'
GROUP BY
  CASE
    WHEN translation_area = 'document' THEN '全文翻译'
    WHEN translation_area = 'selection' THEN '局部翻译'
    ELSE CONCAT('其他:', COALESCE(translation_area, 'null'))
  END
ORDER BY pv DESC;

-- 3.1b（可选，不推荐当使用率）toggle 次数分布
SELECT
  CASE
    WHEN translation_area = 'document' THEN '全文翻译'
    WHEN translation_area = 'selection' THEN '局部翻译'
    ELSE CONCAT('其他:', COALESCE(translation_area, 'null'))
  END AS translate_area_label,
  COUNT(*) AS toggle_pv,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS share_ratio
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_toggle_translate_area'
GROUP BY 1
ORDER BY toggle_pv DESC;

-- 3.2 翻译模式：双语 dual / 仅译文 translation
-- 推荐：workspace_translate_click.translation_mode
SELECT
  CASE
    WHEN translation_mode = 'dual' THEN '双语对照'
    WHEN translation_mode = 'translation' THEN '仅译文'
    ELSE CONCAT('其他:', COALESCE(translation_mode, 'null'))
  END AS translation_mode_label,
  COUNT(*) AS pv,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS share_ratio
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_translate_click'
GROUP BY 1
ORDER BY pv DESC;

-- 3.3 翻译服务（真实使用分布）——必须用 click 上的 translation_service
-- 禁止用 workspace_change_translate_service 次数当使用率（该事件里常见 from_to 拼接）
SELECT
  COALESCE(translation_service, '(null)') AS translation_service,
  COUNT(*) AS pv,
  COUNT(DISTINCT device_id) AS device_uv,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS share_ratio
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_translate_click'
GROUP BY COALESCE(translation_service, '(null)')
ORDER BY pv DESC;


-- =============================================================================
-- 4. 产品健康度
-- =============================================================================
-- 4.1 翻译失败率 = fail PV / translate_click PV（可按日）
SELECT
  CAST(created_ts AS DATE) AS dt,
  COUNT_IF(event_name = 'workspace_translate_click') AS click_pv,
  COUNT_IF(event_name = 'workspace_translate_fail') AS fail_pv,
  COUNT_IF(event_name = 'workspace_translate_fail') * 1.0
    / NULLIF(COUNT_IF(event_name = 'workspace_translate_click'), 0) AS fail_rate
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name IN ('workspace_translate_click', 'workspace_translate_fail')
GROUP BY CAST(created_ts AS DATE)
ORDER BY dt;

-- 4.2 错误原因归并 Top（Auth / Network / Timeout / Quota / Other）
-- 说明：当前埋点原始码在 ex_char_arg2~4 / trigger，需映射；上线初期以原始码对照为准
WITH err AS (
  SELECT
    event_name,
    device_id,
    ex_int_arg1 AS userid,
    COALESCE(trigger, '') AS trigger_v,
    COALESCE(ex_char_arg2, '') AS arg2,
    COALESCE(ex_char_arg3, '') AS arg3,
    COALESCE(ex_char_arg4, '') AS arg4,
    COALESCE(ex_char_arg5, '') AS arg5,
    lower(CONCAT_WS(' ', trigger, ex_char_arg2, ex_char_arg3, ex_char_arg4, ex_char_arg5)) AS blob
  FROM immdata.user_behaviour
  WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
    AND event_name IN (
      'workspace_translate_fail',
      'workspace_auth_request_fail',
      'workspace_show_error_modal'
    )
)
SELECT
  CASE
    WHEN event_name = 'workspace_auth_request_fail'
      OR blob LIKE '%auth%'
      OR blob LIKE '%unauthorized%'
      OR blob LIKE '%login%'
      OR blob LIKE '%token%'
      OR trigger_v = 'login_required'
      THEN 'Auth'
    WHEN blob LIKE '%network%' OR blob LIKE '%offline%' OR blob LIKE '%fetch%' THEN 'Network'
    WHEN blob LIKE '%timeout%' OR blob LIKE '%timed out%' THEN 'Timeout'
    WHEN blob LIKE '%quota%'
      OR blob LIKE '%limit%'
      OR blob LIKE '%subscription%'
      THEN 'Quota'
    ELSE 'Other'
  END AS error_bucket,
  COUNT(*) AS pv,
  COUNT(DISTINCT device_id) AS device_uv
FROM err
GROUP BY 1
ORDER BY pv DESC;

-- 4.2b 原始错误码明细（便于核对映射是否合理）
SELECT
  event_name,
  COALESCE(trigger, '(null)') AS trigger_v,
  COALESCE(ex_char_arg2, '(null)') AS arg2,
  COALESCE(ex_char_arg3, '(null)') AS arg3,
  COALESCE(ex_char_arg4, '(null)') AS arg4,
  COUNT(*) AS pv,
  COUNT(DISTINCT device_id) AS device_uv
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name IN (
    'workspace_translate_fail',
    'workspace_auth_request_fail',
    'workspace_show_error_modal'
  )
GROUP BY 1, 2, 3, 4, 5
ORDER BY pv DESC
LIMIT 50;

-- 4.3 Auth Request Fail UV（单独卡片）
SELECT
  COUNT(*) AS auth_fail_pv,
  COUNT(DISTINCT device_id) AS auth_fail_device_uv,
  COUNT(DISTINCT ex_int_arg1) AS auth_fail_login_uv
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_auth_request_fail';

-- 4.4 看到错误弹窗的用户（辅助）
SELECT
  COALESCE(trigger, '(null)') AS modal_trigger,
  COUNT(*) AS pv,
  COUNT(DISTINCT device_id) AS device_uv
FROM immdata.user_behaviour
WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
  AND event_name = 'workspace_show_error_modal'
GROUP BY COALESCE(trigger, '(null)')
ORDER BY pv DESC;
