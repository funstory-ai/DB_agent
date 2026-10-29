-- =============================================================================
-- T025 一次性修复：周留存 TASK 早于上游周表 → 看板停在上上周、最新周 W1=0
-- 规范：dashboard / P028 / P035；供写仓同学整文件一次跑完（本仓只读勿代跑）
--
-- 根因（2026-09-28 只读核对）→ 已记 **P038**（docs/pitfalls.md；dashboard.md 上下游调度）：
--   · 上游 update_imm_device_event_by_utf8_week：周一 00:02 UTC ≈ 北京 08:02
--   · 原留存 TASK：周一 06:00 / 06:30 上海 → 早于上游约 2 小时
--   · 今日上游已有 week=2026-09-21，留存表仍 max=2026-09-14 且该周 W1=0
--
-- 本文件做两件事：
--   1) 改 Cron 到上游之后（周一 10:00 / 10:30 上海）
--   2) 立刻全量重算一次，当天看板即可对齐 09-21
--
-- 勿 DROP 留存表；勿再跑旧 06:00 Cron 的建 TASK 片段覆盖本修复
-- =============================================================================


-- =============================================================================
-- §0 挂起并重建：分业务周留存 TASK（周一 10:00 上海）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_translate_biz_firstuse_weekly_retention SUSPEND;
DROP TASK IF EXISTS update_imm_translate_biz_firstuse_weekly_retention;

CREATE TASK update_imm_translate_biz_firstuse_weekly_retention
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 0 10 * * 1' 'Asia/Shanghai'
AS BEGIN
  DELETE FROM immdata.imm_translate_biz_firstuse_weekly_retention;
  INSERT INTO immdata.imm_translate_biz_firstuse_weekly_retention
  WITH biz_map AS (
    SELECT 'web' AS biz_code, '网页翻译' AS biz_name, 'translate_page' AS event_name
    UNION ALL SELECT 'video', '视频翻译', 'translate_video_subtitle'
    UNION ALL SELECT 'ai_subtitle', 'AI字幕', 'use_ai_subtitle'
    UNION ALL SELECT 'image_pro', '图片翻译', 'translate_image'
    UNION ALL SELECT 'image_free', '免费图片', 'translate_image_client'
    UNION ALL SELECT 'manga', '漫画翻译', 'translate_manga'
    UNION ALL SELECT 'selection', '划词翻译', 'selection_translate'
    UNION ALL SELECT 'input_space', '空格翻译', 'translate_input'
    UNION ALL SELECT 'side_panel', '侧边栏', 'translateTextInSidePanel'
    UNION ALL SELECT 'area_select', '圈选翻译', 'screenshot_area_translate'
    UNION ALL SELECT 'pdf', 'PDF', 'translate_pdf'
    UNION ALL SELECT 'pdf_pro', 'PDFPro', 'translate_pdf_pro'
    UNION ALL SELECT 'hover', '悬浮翻译', 'mouse_hover_translate'
    UNION ALL SELECT 'ebook', '电子书', 'translate_ebook'
  ),
  act AS (
    SELECT
      m.biz_code,
      m.biz_name,
      m.event_name,
      w.device_id,
      w.week_start_day
    FROM immdata.imm_device_event_by_utf8_week w
    INNER JOIN biz_map m ON m.event_name = w.event_name
    GROUP BY 1, 2, 3, 4, 5
  ),
  firsts AS (
    SELECT biz_code, biz_name, event_name, device_id, min(week_start_day) AS first_week
    FROM act
    GROUP BY 1, 2, 3, 4
  ),
  labeled AS (
    SELECT
      f.biz_code,
      f.biz_name,
      f.event_name,
      f.first_week,
      f.device_id,
      max(CASE WHEN a.week_start_day = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
      max(CASE WHEN a.week_start_day = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
      max(CASE WHEN a.week_start_day = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
      max(CASE WHEN a.week_start_day = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
    FROM firsts f
    LEFT JOIN act a
      ON a.biz_code = f.biz_code
     AND a.device_id = f.device_id
     AND a.week_start_day >= date_add(day, 7, f.first_week)
     AND a.week_start_day <= date_add(day, 28, f.first_week)
    GROUP BY 1, 2, 3, 4, 5
  )
  SELECT
    biz_code,
    biz_name,
    event_name,
    first_week,
    count(*),
    sum(r1), sum(r2), sum(r3), sum(r4),
    sum(r1) * 1.0 / count(*),
    sum(r2) * 1.0 / count(*),
    sum(r3) * 1.0 / count(*),
    sum(r4) * 1.0 / count(*),
    now()
  FROM labeled
  GROUP BY 1, 2, 3, 4;
END;


-- =============================================================================
-- §1 立刻全量重算：分业务周留存（当天对齐上游 09-21）
-- =============================================================================
DELETE FROM immdata.imm_translate_biz_firstuse_weekly_retention;
INSERT INTO immdata.imm_translate_biz_firstuse_weekly_retention
WITH biz_map AS (
  SELECT 'web' AS biz_code, '网页翻译' AS biz_name, 'translate_page' AS event_name
  UNION ALL SELECT 'video', '视频翻译', 'translate_video_subtitle'
  UNION ALL SELECT 'ai_subtitle', 'AI字幕', 'use_ai_subtitle'
  UNION ALL SELECT 'image_pro', '图片翻译', 'translate_image'
  UNION ALL SELECT 'image_free', '免费图片', 'translate_image_client'
  UNION ALL SELECT 'manga', '漫画翻译', 'translate_manga'
  UNION ALL SELECT 'selection', '划词翻译', 'selection_translate'
  UNION ALL SELECT 'input_space', '空格翻译', 'translate_input'
  UNION ALL SELECT 'side_panel', '侧边栏', 'translateTextInSidePanel'
  UNION ALL SELECT 'area_select', '圈选翻译', 'screenshot_area_translate'
  UNION ALL SELECT 'pdf', 'PDF', 'translate_pdf'
  UNION ALL SELECT 'pdf_pro', 'PDFPro', 'translate_pdf_pro'
  UNION ALL SELECT 'hover', '悬浮翻译', 'mouse_hover_translate'
  UNION ALL SELECT 'ebook', '电子书', 'translate_ebook'
),
act AS (
  SELECT
    m.biz_code,
    m.biz_name,
    m.event_name,
    w.device_id,
    w.week_start_day
  FROM immdata.imm_device_event_by_utf8_week w
  INNER JOIN biz_map m ON m.event_name = w.event_name
  GROUP BY 1, 2, 3, 4, 5
),
firsts AS (
  SELECT biz_code, biz_name, event_name, device_id, min(week_start_day) AS first_week
  FROM act
  GROUP BY 1, 2, 3, 4
),
labeled AS (
  SELECT
    f.biz_code,
    f.biz_name,
    f.event_name,
    f.first_week,
    f.device_id,
    max(CASE WHEN a.week_start_day = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
    max(CASE WHEN a.week_start_day = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
    max(CASE WHEN a.week_start_day = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
    max(CASE WHEN a.week_start_day = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
  FROM firsts f
  LEFT JOIN act a
    ON a.biz_code = f.biz_code
   AND a.device_id = f.device_id
   AND a.week_start_day >= date_add(day, 7, f.first_week)
   AND a.week_start_day <= date_add(day, 28, f.first_week)
  GROUP BY 1, 2, 3, 4, 5
)
SELECT
  biz_code,
  biz_name,
  event_name,
  first_week AS cohort_week_start,
  count(*) AS cohort_devices,
  sum(r1) AS ret_w1_devices,
  sum(r2) AS ret_w2_devices,
  sum(r3) AS ret_w3_devices,
  sum(r4) AS ret_w4_devices,
  sum(r1) * 1.0 / count(*) AS w1_retention_rate,
  sum(r2) * 1.0 / count(*) AS w2_retention_rate,
  sum(r3) * 1.0 / count(*) AS w3_retention_rate,
  sum(r4) * 1.0 / count(*) AS w4_retention_rate,
  now() AS update_time
FROM labeled
GROUP BY 1, 2, 3, 4;

ALTER TASK update_imm_translate_biz_firstuse_weekly_retention RESUME;


-- =============================================================================
-- §2 挂起并重建：BabelDoc 周留存 TASK（周一 10:30 上海）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_babeldoc_firstuse_weekly_retention SUSPEND;
DROP TASK IF EXISTS update_imm_babeldoc_firstuse_weekly_retention;

CREATE TASK update_imm_babeldoc_firstuse_weekly_retention
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 30 10 * * 1' 'Asia/Shanghai'
AS BEGIN
  DELETE FROM immdata.imm_babeldoc_firstuse_weekly_retention;
  INSERT INTO immdata.imm_babeldoc_firstuse_weekly_retention
  WITH act AS (
    SELECT
      userid,
      to_start_of_week(useddate, 1) AS week_start
    FROM immdata.imm_babel_doc_record
    WHERE userid IS NOT NULL
      AND userid <> ''
      AND to_start_of_week(useddate, 1) < to_start_of_week(date(add_hours(now(), 8)), 1)
    GROUP BY 1, 2
  ),
  firsts AS (
    SELECT userid, min(week_start) AS first_week
    FROM act
    GROUP BY 1
  ),
  labeled AS (
    SELECT
      f.first_week,
      f.userid,
      max(CASE WHEN a.week_start = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
      max(CASE WHEN a.week_start = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
      max(CASE WHEN a.week_start = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
      max(CASE WHEN a.week_start = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
    FROM firsts f
    LEFT JOIN act a
      ON a.userid = f.userid
     AND a.week_start >= date_add(day, 7, f.first_week)
     AND a.week_start <= date_add(day, 28, f.first_week)
    GROUP BY 1, 2
  )
  SELECT
    'babeldoc',
    'BabelDoc',
    first_week,
    count(*),
    sum(r1), sum(r2), sum(r3), sum(r4),
    sum(r1) * 1.0 / count(*),
    sum(r2) * 1.0 / count(*),
    sum(r3) * 1.0 / count(*),
    sum(r4) * 1.0 / count(*),
    now()
  FROM labeled
  GROUP BY 1, 2, 3;
END;


-- =============================================================================
-- §3 立刻全量重算：BabelDoc
-- =============================================================================
DELETE FROM immdata.imm_babeldoc_firstuse_weekly_retention;
INSERT INTO immdata.imm_babeldoc_firstuse_weekly_retention
WITH act AS (
  SELECT
    userid,
    to_start_of_week(useddate, 1) AS week_start
  FROM immdata.imm_babel_doc_record
  WHERE userid IS NOT NULL
    AND userid <> ''
    AND to_start_of_week(useddate, 1) < to_start_of_week(date(add_hours(now(), 8)), 1)
  GROUP BY 1, 2
),
firsts AS (
  SELECT userid, min(week_start) AS first_week
  FROM act
  GROUP BY 1
),
labeled AS (
  SELECT
    f.first_week,
    f.userid,
    max(CASE WHEN a.week_start = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
    max(CASE WHEN a.week_start = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
    max(CASE WHEN a.week_start = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
    max(CASE WHEN a.week_start = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
  FROM firsts f
  LEFT JOIN act a
    ON a.userid = f.userid
   AND a.week_start >= date_add(day, 7, f.first_week)
   AND a.week_start <= date_add(day, 28, f.first_week)
  GROUP BY 1, 2
)
SELECT
  'babeldoc' AS biz_code,
  'BabelDoc' AS biz_name,
  first_week AS cohort_week_start,
  count(*) AS cohort_users,
  sum(r1) AS ret_w1_users,
  sum(r2) AS ret_w2_users,
  sum(r3) AS ret_w3_users,
  sum(r4) AS ret_w4_users,
  sum(r1) * 1.0 / count(*) AS w1_retention_rate,
  sum(r2) * 1.0 / count(*) AS w2_retention_rate,
  sum(r3) * 1.0 / count(*) AS w3_retention_rate,
  sum(r4) * 1.0 / count(*) AS w4_retention_rate,
  now() AS update_time
FROM labeled
GROUP BY 1, 2, 3;

ALTER TASK update_imm_babeldoc_firstuse_weekly_retention RESUME;


-- =============================================================================
-- §4 验收（写仓跑完后执行；期望当日）
-- =============================================================================
-- SELECT
--   (SELECT max(week_start_day) FROM immdata.imm_device_event_by_utf8_week) AS src_week_max,
--   (SELECT max(cohort_week_start) FROM immdata.imm_translate_biz_firstuse_weekly_retention) AS biz_max,
--   (SELECT max(cohort_week_start) FROM immdata.imm_babeldoc_firstuse_weekly_retention) AS babel_max;
-- -- 期望：biz_max = src_week_max（今日应为 2026-09-21）
--
-- SELECT cohort_week_start, cohort_devices, ret_w1_devices, w1_retention_rate,
--        ret_w2_devices, w2_retention_rate
-- FROM immdata.imm_translate_biz_firstuse_weekly_retention
-- WHERE biz_code = 'web'
-- ORDER BY cohort_week_start DESC
-- LIMIT 5;
-- -- 期望：09-21 行存在（W1 可为 0）；09-14 的 W1 > 0
--
-- SHOW TASKS LIKE 'update_imm_translate_biz_firstuse_weekly_retention';
-- SHOW TASKS LIKE 'update_imm_babeldoc_firstuse_weekly_retention';
-- -- 期望：Started；schedule 含 10:00 / 10:30 Asia/Shanghai；definition 含 DELETE+INSERT
;
