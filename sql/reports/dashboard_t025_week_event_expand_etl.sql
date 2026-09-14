-- =============================================================================
-- T025：周表扩事件（定稿）
-- 规范大类：dashboard（P022 / P028 / P035 / P036）
-- 任务：docs/tasks/dashboard_translate_weekly_retention_20260831.md
-- 本查数仓库只读，勿在只读账号执行
--
-- 现行周表事件：原 8 + image_client / area_select / mouse_hover_translate
--   + 合成 translate_pdf / translate_pdf_pro / translate_ebook
-- §2 历史回填仅供重建参考；**日常勿重跑全量回填**（T025 已落库）。
-- 改日更口径：只改 §3 TASK（须含 hover + ebook 合成）。
-- =============================================================================


-- =============================================================================
-- §0 执行前核对（只读）
-- =============================================================================
-- SHOW TASKS LIKE 'update_imm_device_event_by_utf8_week';
-- SELECT event_name, count(*) AS rows, min(week_start_day), max(week_start_day)
-- FROM immdata.imm_device_event_by_utf8_week
-- WHERE event_name IN (
--   'translate_image_client','screenshot_area_translate',
--   'translate_pdf','translate_pdf_pro'
-- )
-- GROUP BY 1;


-- =============================================================================
-- §1 暂停周表 TASK
-- =============================================================================
ALTER TASK IF EXISTS update_imm_device_event_by_utf8_week SUSPEND;


-- =============================================================================
-- §2 新事件历史回填（只写 4 个新 event_name；不碰旧 8 事件）
-- 窗口：北京自然周 [week_start, next_week)；UTC =
--   [add_hours(week_start,-8), add_hours(next_week,-8))
-- 可按季度重跑；REPLACE ON 主键幂等。
-- 若单段超时，把日期改成更短窗顺序执行。
-- =============================================================================

-- ---------- 2024-Q4 ----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
  'translate_image_client' AS event_name,
  device_id,
  to_start_of_week(min(install_day), 1) AS install_week_start_day,
  count(*) AS event_count,
  now() AS update_time
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-09-22 16:00:00'
  AND created_ts <  '2024-12-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
  'translate_pdf' AS event_name,
  device_id,
  to_start_of_week(min(install_day), 1) AS install_week_start_day,
  count(*) AS event_count,
  now() AS update_time
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-09-22 16:00:00'
  AND created_ts <  '2024-12-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
  'translate_pdf_pro' AS event_name,
  device_id,
  to_start_of_week(min(install_day), 1) AS install_week_start_day,
  count(*) AS event_count,
  now() AS update_time
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-09-22 16:00:00'
  AND created_ts <  '2024-12-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

-- ---------- 2025-Q1 ----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_image_client',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-12-29 16:00:00'
  AND created_ts <  '2025-03-30 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-12-29 16:00:00'
  AND created_ts <  '2025-03-30 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf_pro',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2024-12-29 16:00:00'
  AND created_ts <  '2025-03-30 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

-- ---------- 2025-Q2 ----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_image_client',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-03-30 16:00:00'
  AND created_ts <  '2025-06-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-03-30 16:00:00'
  AND created_ts <  '2025-06-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf_pro',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-03-30 16:00:00'
  AND created_ts <  '2025-06-29 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

-- ---------- 2025-Q3 ----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_image_client',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-06-29 16:00:00'
  AND created_ts <  '2025-09-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-06-29 16:00:00'
  AND created_ts <  '2025-09-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf_pro',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-06-29 16:00:00'
  AND created_ts <  '2025-09-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

-- ---------- 2025-Q4 ----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_image_client',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-09-28 16:00:00'
  AND created_ts <  '2025-12-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-09-28 16:00:00'
  AND created_ts <  '2025-12-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf_pro',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-09-28 16:00:00'
  AND created_ts <  '2025-12-28 16:00:00'
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

-- ---------- 2026-H1（至当前已闭合周上界：本周一 北京 0 点对应 UTC）----------
-- 上界与周 TASK 一致：不含「本周未闭合」；写仓执行日若已过周一，可保持；
-- 若需刷到最新已闭合周，将下界/上界按需改到 date(add_hours(now(),8)) 对齐的周一。
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_image_client',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_image_client'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-12-28 16:00:00'
  AND created_ts <  add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'screenshot_area_translate',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'screenshot_area_translate'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-12-28 16:00:00'
  AND created_ts <  add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-12-28 16:00:00'
  AND created_ts <  add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐

REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'translate_pdf_pro',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND page_type = 'pdfProReader'
  AND main_frame = '1'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-12-28 16:00:00'
  AND created_ts <  add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐


-- ---------- 圈选（量小，单独全历史至本周一）----------
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  to_start_of_week(add_hours(created_ts, 8), 1),
  'screenshot_area_translate',
  device_id,
  to_start_of_week(min(install_day), 1),
  count(*),
  now()
FROM immdata.user_behaviour
WHERE event_name = 'screenshot_area_translate'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND created_ts >= '2025-01-01'
  AND created_ts <  add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
GROUP BY 1, 2, 3;  -- 须与 REPLACE ON (week_start_day, event_name, device_id) 三列对齐


-- =============================================================================
-- §3 重建周表 TASK（保留原增量窗；白名单 + 合成 PDF）
-- =============================================================================
DROP TASK IF EXISTS update_imm_device_event_by_utf8_week;

CREATE TASK update_imm_device_event_by_utf8_week
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 2 0 * * 1' 'UTC'
AS
REPLACE INTO immdata.imm_device_event_by_utf8_week (
  week_start_day, event_name, device_id, install_week_start_day, event_count, update_time
) ON (week_start_day, event_name, device_id)
SELECT
  week_start_day,
  event_name,
  device_id,
  to_start_of_week(min(install_day), 1) AS install_week_start_day,
  count(
    IF(
      event_name = 'translate_page' AND main_frame = '1'
      OR event_name <> 'translate_page',
      1,
      NULL
    )
  ) AS event_count,
  now() AS update_time
FROM (
  SELECT
    to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
    event_name,
    device_id,
    install_day,
    main_frame
  FROM immdata.user_behaviour
  WHERE event_name IN (
      'translate_page',
      'translate_manga',
      'translate_input',
      'translate_image',
      'translate_video_subtitle',
      'selection_translate',
      'use_ai_subtitle',
      'translateTextInSidePanel',
      'translate_image_client',
      'screenshot_area_translate',
      'mouse_hover_translate'
    )
    AND version <> '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND created_ts < add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
    AND created_ts >= add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -176)

  UNION ALL

  SELECT
    to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
    'translate_pdf' AS event_name,
    device_id,
    install_day,
    main_frame
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND page_type = 'pdfReader'
    AND main_frame = '1'
    AND version <> '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND created_ts < add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
    AND created_ts >= add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -176)

  UNION ALL

  SELECT
    to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
    'translate_pdf_pro' AS event_name,
    device_id,
    install_day,
    main_frame
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND page_type = 'pdfProReader'
    AND main_frame = '1'
    AND version <> '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND created_ts < add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
    AND created_ts >= add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -176)

  UNION ALL

  SELECT
    to_start_of_week(add_hours(created_ts, 8), 1) AS week_start_day,
    'translate_ebook' AS event_name,
    device_id,
    install_day,
    main_frame
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND page_type = 'ebookBuilder'
    AND main_frame = '1'
    AND version <> '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND created_ts < add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -8)
    AND created_ts >= add_hours(to_start_of_week(date(add_hours(now(), 8)), 1), -176)
) src
GROUP BY week_start_day, event_name, device_id;


-- =============================================================================
-- §4 恢复周表 TASK
-- =============================================================================
ALTER TASK update_imm_device_event_by_utf8_week RESUME;


-- =============================================================================
-- §5 验收（只读）
-- =============================================================================
-- SELECT event_name, count(*) AS rows, min(week_start_day), max(week_start_day)
-- FROM immdata.imm_device_event_by_utf8_week
-- WHERE event_name IN (
--   'translate_image_client','screenshot_area_translate','mouse_hover_translate',
--   'translate_pdf','translate_pdf_pro','translate_ebook'
-- )
-- GROUP BY 1
-- ORDER BY 1;
--
-- SHOW TASKS LIKE 'update_imm_device_event_by_utf8_week';
;