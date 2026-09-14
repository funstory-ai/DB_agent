-- =============================================================================
-- T025 §B：分业务首次使用周 → W1～W4 留存（替换原并集表）
-- 规范大类：dashboard；P022 / P028 / P035
-- 任务：docs/tasks/dashboard_translate_weekly_retention_20260831.md
-- 本查数仓库只读，勿在只读账号执行
--
-- 前置：周表须已含 image_client / area_select / pdf / pdf_pro / hover / ebook
--       （定稿：dashboard_t025_week_event_expand_etl.sql §3 TASK）
-- 业务口径：docs/norms/translate_biz.md
-- 含未满窗 cohort；源尚无的 Wn → 0
--
-- 本文件会 DROP 旧并集中间表与 TASK（不可逆，写仓确认后再跑）
-- =============================================================================


-- =============================================================================
-- §0 删除旧并集留存表 / TASK
-- =============================================================================
ALTER TASK IF EXISTS update_imm_translate_firstuse_weekly_retention SUSPEND;
DROP TASK IF EXISTS update_imm_translate_firstuse_weekly_retention;
DROP TABLE IF EXISTS immdata.imm_translate_firstuse_weekly_retention;


-- =============================================================================
-- §1 新表：业务 × 首次周
-- =============================================================================
ALTER TASK IF EXISTS update_imm_translate_biz_firstuse_weekly_retention SUSPEND;
DROP TASK IF EXISTS update_imm_translate_biz_firstuse_weekly_retention;
DROP TABLE IF EXISTS immdata.imm_translate_biz_firstuse_weekly_retention;

CREATE TABLE immdata.imm_translate_biz_firstuse_weekly_retention (
  biz_code VARCHAR,             -- web / video / ...
  biz_name VARCHAR,             -- 中文名（挂板用）
  event_name VARCHAR,           -- 周表 event_name（合成事件见 expand SQL）
  cohort_week_start DATE,       -- 该业务首次使用周（周一）
  cohort_devices BIGINT,
  ret_w1_devices BIGINT,
  ret_w2_devices BIGINT,
  ret_w3_devices BIGINT,
  ret_w4_devices BIGINT,
  w1_retention_rate DOUBLE,
  w2_retention_rate DOUBLE,
  w3_retention_rate DOUBLE,
  w4_retention_rate DOUBLE,
  update_time TIMESTAMP
);


-- =============================================================================
-- §2 全量回填
-- =============================================================================
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
  -- 未满窗也保留；源周表尚无的 Wn → r=0
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


-- =============================================================================
-- §3 周更 TASK（周一 06:00 上海；全量重算；P028 BEGIN…END；P035 六段 cron）
-- =============================================================================
CREATE TASK update_imm_translate_biz_firstuse_weekly_retention
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 0 6 * * 1' 'Asia/Shanghai'
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

ALTER TASK update_imm_translate_biz_firstuse_weekly_retention RESUME;


-- =============================================================================
-- §4 验收（只读）
-- =============================================================================
-- SELECT biz_code, biz_name, count(*) AS weeks,
--   min(cohort_week_start), max(cohort_week_start), sum(cohort_devices)
-- FROM immdata.imm_translate_biz_firstuse_weekly_retention
-- GROUP BY 1, 2
-- ORDER BY 1;
--
-- -- grain
-- SELECT count(*) AS cnt,
--   count(DISTINCT concat(biz_code, ':', cast(cohort_week_start AS string))) AS dist
-- FROM immdata.imm_translate_biz_firstuse_weekly_retention;
--
-- SHOW TASKS LIKE 'update_imm_translate_biz_firstuse_weekly_retention';
-- SHOW TASKS LIKE 'update_imm_translate_firstuse_weekly_retention';  -- 应不存在
;