-- =============================================================================
-- translate_page 常用指标 · 剔 Rule A 油猴集成（与 T028 日看板一致）
-- 踢：official_userscript × (ios×Safari | macos×Maxthon)
-- 留：ImtiOS_* 等 App UA 的 userscript
-- 任务：T029 docs/tasks/query_translate_page_ruleA_active_retention_20260903.md
-- 口径：docs/pitfalls.md P034
-- =============================================================================

-- 【Rule A 条件 · 各查询共用】
-- AND NOT (
--   LOWER(TRIM(install_from)) = 'official_userscript'
--   AND (
--     (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
--     OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
--   )
-- )


-- =============================================================================
-- 1) 近 30 天活跃（相对 yesterday() 闭开区间，与你原窗一致）
-- =============================================================================
SELECT COUNT(DISTINCT device_id) AS active_30d
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND version != '1.11.4'
  AND created_ts >= date_add(day, -30, yesterday())
  AND created_ts < yesterday()
  AND NOT (
    LOWER(TRIM(install_from)) = 'official_userscript'
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
  );


-- =============================================================================
-- 2) 自然月活（例：2026-08；改日期即可）
-- =============================================================================
SELECT COUNT(DISTINCT device_id) AS mau
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND version != '1.11.4'
  AND created_ts >= '2026-08-01'
  AND created_ts < '2026-09-01'
  AND NOT (
    LOWER(TRIM(install_from)) = 'official_userscript'
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
  );


-- =============================================================================
-- 3) 新装月留存 M1～M6（每月跑一次）
-- =============================================================================
SELECT
  install_month_start_day AS month_start_day,
  COUNT(DISTINCT device_id) AS new_user_count,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 1) = month_start_day, device_id, NULL)) AS one_month_ret,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 2) = month_start_day, device_id, NULL)) AS two_month_ret,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 3) = month_start_day, device_id, NULL)) AS three_month_ret,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 4) = month_start_day, device_id, NULL)) AS four_month_ret,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 5) = month_start_day, device_id, NULL)) AS five_month_ret,
  COUNT(DISTINCT IF(add_months(install_month_start_day, 6) = month_start_day, device_id, NULL)) AS six_month_ret
FROM (
  SELECT
    to_start_of_month(add_hours(created_ts, 8)) AS month_start_day,
    event_name,
    device_id,
    to_start_of_month(min(install_day)) AS install_month_start_day,
    COUNT(
      IF(
        (event_name = 'translate_page' AND main_frame = '1')
        OR event_name != 'translate_page',
        1,
        NULL
      )
    ) AS event_count,
    now() AS update_time
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND version != '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND NOT (
      LOWER(TRIM(install_from)) = 'official_userscript'
      AND (
        (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
        OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
      )
    )
  GROUP BY
    to_start_of_month(add_hours(created_ts, 8)),
    event_name,
    device_id
) t
GROUP BY install_month_start_day
ORDER BY install_month_start_day DESC
;
