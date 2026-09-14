-- T035: 近 30 天泰语母语设备：数量 + 翻译业务功能 UV + platform/os
-- 时间窗：[2026-08-11, 2026-09-11)
-- 泰国：设备母语 P020，LOWER(native_language)='th' 或 LIKE 'th-%'
-- 主体：device_id；活跃=窗内有 translate_biz 相关事件
-- 功能：docs/norms/translate_biz.md（web 含全部 translate_page；pdf/ebook 为切片）
-- 设备：每设备取窗内事件众数 platform_type / os_name

WITH th_dev AS (
  SELECT DISTINCT device_id
  FROM immdata.imm_device_native_language
  WHERE device_id IS NOT NULL AND CAST(device_id AS STRING) <> ''
    AND native_language IS NOT NULL AND native_language <> ''
    AND (
      LOWER(native_language) = 'th'
      OR LOWER(native_language) LIKE 'th-%'
    )
),
beh AS (
  SELECT
    b.device_id,
    b.event_name,
    b.page_type,
    b.main_frame,
    b.platform_type,
    b.os_name,
    CASE
      WHEN b.event_name = 'translate_page'
        AND b.page_type = 'pdfReader' AND CAST(b.main_frame AS STRING) = '1'
        THEN 'pdf'
      WHEN b.event_name = 'translate_page'
        AND b.page_type = 'pdfProReader' AND CAST(b.main_frame AS STRING) = '1'
        THEN 'pdf_pro'
      WHEN b.event_name = 'translate_page'
        AND b.page_type = 'ebookBuilder' AND CAST(b.main_frame AS STRING) = '1'
        THEN 'ebook'
      WHEN b.event_name = 'translate_page' THEN 'web'
      WHEN b.event_name = 'translate_video_subtitle' THEN 'video'
      WHEN b.event_name = 'use_ai_subtitle' THEN 'ai_subtitle'
      WHEN b.event_name = 'translate_image' THEN 'image_pro'
      WHEN b.event_name = 'translate_image_client' THEN 'image_free'
      WHEN b.event_name = 'translate_manga' THEN 'manga'
      WHEN b.event_name = 'selection_translate' THEN 'selection'
      WHEN b.event_name = 'translate_input' THEN 'input_space'
      WHEN b.event_name = 'translateTextInSidePanel' THEN 'side_panel'
      WHEN b.event_name = 'screenshot_area_translate' THEN 'area_select'
      WHEN b.event_name = 'mouse_hover_translate' THEN 'hover'
      ELSE NULL
    END AS biz_code
  FROM immdata.user_behaviour b
  INNER JOIN th_dev t ON b.device_id = t.device_id
  WHERE b.created_ts >= '2026-08-11' AND b.created_ts < '2026-09-11'
    AND b.event_name IN (
      'translate_page',
      'translate_video_subtitle',
      'use_ai_subtitle',
      'translate_image',
      'translate_image_client',
      'translate_manga',
      'selection_translate',
      'translate_input',
      'translateTextInSidePanel',
      'screenshot_area_translate',
      'mouse_hover_translate'
    )
),
active AS (
  SELECT DISTINCT device_id FROM beh
),
biz_uv AS (
  SELECT
    biz_code,
    COUNT(DISTINCT device_id) AS devices,
    COUNT(*) AS events
  FROM beh
  WHERE biz_code IS NOT NULL
  GROUP BY biz_code
),
dev_plat AS (
  SELECT device_id, platform_type
  FROM (
    SELECT
      device_id,
      COALESCE(NULLIF(platform_type, ''), '(null)') AS platform_type,
      ROW_NUMBER() OVER (
        PARTITION BY device_id
        ORDER BY COUNT(*) DESC, COALESCE(NULLIF(platform_type, ''), '(null)')
      ) AS rn
    FROM beh
    GROUP BY device_id, COALESCE(NULLIF(platform_type, ''), '(null)')
  ) x
  WHERE rn = 1
),
dev_os AS (
  SELECT device_id, os_name
  FROM (
    SELECT
      device_id,
      COALESCE(NULLIF(os_name, ''), '(null)') AS os_name,
      ROW_NUMBER() OVER (
        PARTITION BY device_id
        ORDER BY COUNT(*) DESC, COALESCE(NULLIF(os_name, ''), '(null)')
      ) AS rn
    FROM beh
    GROUP BY device_id, COALESCE(NULLIF(os_name, ''), '(null)')
  ) x
  WHERE rn = 1
)
SELECT 'active_devices' AS section, CAST(COUNT(*) AS STRING) AS k, NULL AS v1, NULL AS v2
FROM active
UNION ALL
SELECT 'biz', biz_code, CAST(devices AS STRING), CAST(events AS STRING)
FROM biz_uv
UNION ALL
SELECT 'platform', platform_type, CAST(COUNT(*) AS STRING), NULL
FROM dev_plat
GROUP BY platform_type
UNION ALL
SELECT 'os', os_name, CAST(COUNT(*) AS STRING), NULL
FROM dev_os
GROUP BY os_name
ORDER BY section, v1 DESC NULLS LAST, k
;
