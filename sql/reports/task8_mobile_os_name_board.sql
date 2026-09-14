-- =============================================================================
-- 移动端看板：统一 os_name 大小写（Superset 数据集 SQL）
-- 规范大类：dashboard
-- 标准取值：Android / iOS / iPadOS（大小写不敏感归并后再写出）
-- 用法：替换现有 Virtual Dataset 内层 SQL；图表 Filter 用 os_name = Android / iOS / iPadOS
-- 说明：外层 to_start_of_day / LIMIT 由图表生成，不必写进数据集
-- =============================================================================

-- 统一表达式（四处相同）
-- CASE LOWER(os_name)
--   WHEN 'android' THEN 'Android'
--   WHEN 'ios' THEN 'iOS'
--   WHEN 'ipados' THEN 'iPadOS'
--   ELSE os_name
-- END


-- -----------------------------------------------------------------------------
-- A. 原数据集：imm_app_new_event_device_count_by_utf8_day
--    该表 TASK 已把 app_active 的 android→Android，近窗本身已是 Title Case；
--    仍套 CASE，避免以后混入小写。
-- -----------------------------------------------------------------------------
SELECT
  dates AS event_datetime,
  os_name,
  browser_version,
  SUM(IF(event_name = 'translate_page', device_count, 0)) AS dau,
  SUM(IF(event_name = 'translate_page', event_count, 0)) AS eventCount,
  SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS translated_new_user,
  SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_user,
  SUM(IF(event_name = 'translate_video_subtitle', device_count, 0)) AS translate_video_subtitle,
  SUM(IF(event_name = 'translate_video_subtitle', event_count, 0)) AS translate_video_subtitle_event,
  SUM(IF(event_name = 'translate_manga', device_count, 0)) AS translate_manga,
  SUM(IF(event_name = 'translate_manga', event_count, 0)) AS translate_manga_event,
  SUM(IF(event_name = 'translate_input', device_count, 0)) AS translate_input,
  SUM(IF(event_name = 'translate_input', event_count, 0)) AS translate_input_event,
  SUM(IF(event_name = 'translate_image', device_count, 0)) AS translate_image,
  SUM(IF(event_name = 'translate_image', event_count, 0)) AS translate_image_event,
  SUM(IF(event_name = 'use_ai_subtitle', device_count, 0)) AS use_ai_subtitle,
  SUM(IF(event_name = 'use_ai_subtitle', event_count, 0)) AS use_ai_subtitle_event,
  SUM(IF(event_name = 'selection_translate', device_count, 0)) AS selection_translate,
  SUM(IF(event_name = 'selection_translate', event_count, 0)) AS selection_translate_event,
  SUM(IF(event_name = 'app_active', device_count, 0)) AS app_active,
  SUM(IF(event_name = 'app_active', event_count, 0)) AS app_active_event
FROM (
  SELECT
    dates,
    event_name,
    CASE LOWER(os_name)
      WHEN 'android' THEN 'Android'
      WHEN 'ios' THEN 'iOS'
      WHEN 'ipados' THEN 'iPadOS'
      ELSE os_name
    END AS os_name,
    browser_version,
    device_count,
    new_device_count,
    event_count
  FROM immdata.imm_app_new_event_device_count_by_utf8_day
) t
GROUP BY dates, os_name, browser_version;


-- -----------------------------------------------------------------------------
-- B. 原数据集：imm_app_active_new_device_by_os_day
--    TASK 直出 user_behaviour.os_name，Android 侧实际是小写 android。
-- -----------------------------------------------------------------------------
SELECT
  dates,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END AS os_name,
  SUM(device_count) AS device_count
FROM immdata.imm_app_active_new_device_by_os_day
GROUP BY
  dates,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END;


-- -----------------------------------------------------------------------------
-- C. 原数据集：app_text_translate（imm_event_device_count_by_utf8_day）
--    近窗 App 事件 os_name = android（小写）；过滤 Android 会得到空。
--    必须在聚合前归并，并保留 os_name 供看板 Filter。
-- -----------------------------------------------------------------------------
SELECT
  dates AS event_datetime,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END AS os_name,
  -- 列名与旧图表指标 SUM("sum(device_count)") 对齐，避免切数据集后 Metrics 被清空
  SUM(device_count) AS "sum(device_count)"
FROM immdata.imm_event_device_count_by_utf8_day
WHERE event_name = 'app_text_translate'
GROUP BY
  dates,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END;


-- -----------------------------------------------------------------------------
-- D. 原数据集：全局翻译相关事件（imm_event_device_count_by_utf8_day）
--    原稿按日汇总时丢掉了 os_name，看板平台过滤加了也无效。
-- -----------------------------------------------------------------------------
SELECT
  dates AS event_datetime,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END AS os_name,
  SUM(IF(event_name = 'webview_ao3_click', device_count, 0)) AS ao3_dau,
  SUM(IF(event_name = 'epub_reader_init', device_count, 0)) AS epub_dau,
  SUM(IF(event_name = 'global_ball_start', device_count, 0)) AS global_ball_start_dau,
  SUM(IF(event_name = 'global_input_box_start', device_count, 0)) AS global_input_box_start_dau,
  SUM(IF(event_name = 'app_global_translate_swipe', device_count, 0)) AS app_global_translate_swipe_dau,
  SUM(IF(event_name = 'app_global_translate_input_box', device_count, 0)) AS app_global_translate_input_box_dau
FROM immdata.imm_event_device_count_by_utf8_day
WHERE event_name IN (
  'webview_ao3_click',
  'epub_reader_init',
  'global_ball_start',
  'global_input_box_start',
  'app_global_translate_swipe',
  'app_global_translate_input_box'
)
GROUP BY
  dates,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END;


-- -----------------------------------------------------------------------------
-- E. 新用户周留存（imm_app_new_device_event_by_utf8_week × app_active）
--    表内 Android 侧全是小写 android；内层已有 os_name，Filter Android 会空。
--    指标列名与旧图一致，避免切数据集后 Metrics 被清空。
-- -----------------------------------------------------------------------------
SELECT
  install_week_start_day AS event_datetime,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END AS os_name,
  COUNT(DISTINCT device_id) AS new_user_count,
  COUNT(DISTINCT IF(add_days(install_week_start_day, 7) = week_start_day, device_id, NULL)) AS one_week_retention,
  COUNT(DISTINCT IF(add_days(install_week_start_day, 14) = week_start_day, device_id, NULL)) AS two_week_retention,
  COUNT(DISTINCT IF(add_days(install_week_start_day, 21) = week_start_day, device_id, NULL)) AS three_week_retention
FROM immdata.imm_app_new_device_event_by_utf8_week
WHERE event_name = 'app_active'
  AND install_week_start_day > '2024-09-18'
  AND install_week_start_day < to_start_of_week(now(), 1)
  AND browser_version >= '2.0.0'
GROUP BY
  install_week_start_day,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END;


-- -----------------------------------------------------------------------------
-- F. 周活（同表；图表仍按周 COUNT DISTINCT，不按 os 拆列）
--    SELECT * 时 os_name 仍是 android；若看板要加平台 Filter，必须先 CASE。
-- -----------------------------------------------------------------------------
SELECT
  week_start_day,
  week_start_day AS event_datetime,
  event_name,
  device_id,
  install_week_start_day,
  event_count,
  CASE LOWER(os_name)
    WHEN 'android' THEN 'Android'
    WHEN 'ios' THEN 'iOS'
    WHEN 'ipados' THEN 'iPadOS'
    ELSE os_name
  END AS os_name,
  browser_version
FROM immdata.imm_app_new_device_event_by_utf8_week;
