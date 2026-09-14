-- T034: 近 30 天繁中(账号母语 zh-TW) translate_page：gemma 事件数与占比
-- 时间窗：滚动近 30 天（开查日 2026-09-10 → [2026-08-11, 2026-09-11)）
-- 繁中：P020 账号母语 LOWER(native_language)='zh-tw'
-- 行为归属：P016 双路径（deviceinfo.deviceid / ex_int_arg1）
-- gemma 识别：translation_service 含 gemma，或 = free-provider-translategemma
-- 说明：插件 TranslateGemma 为 free-model 子服务；绝大多数用量只落 translation_service='free-model'，
--       behaviour 无法拆出子 provider。本 SQL 仅统计可识别的 gemma 服务 ID；并附 free-model 对照。

WITH zh_tw AS (
  SELECT CAST(userid AS BIGINT) AS userid
  FROM (
    SELECT
      userid,
      native_language,
      SUM(COALESCE(cnt, 0)) AS cnt_sum,
      ROW_NUMBER() OVER (
        PARTITION BY userid
        ORDER BY SUM(COALESCE(cnt, 0)) DESC, native_language
      ) AS rn
    FROM immdata.imm_device_native_language
    WHERE userid IS NOT NULL
      AND CAST(userid AS STRING) <> ''
      AND native_language IS NOT NULL
      AND native_language <> ''
    GROUP BY userid, native_language
  ) t
  WHERE rn = 1
    AND LOWER(native_language) = 'zh-tw'
),
devices AS (
  SELECT DISTINCT d.deviceid AS device_id
  FROM immdata.imt_deviceinfo d
  INNER JOIN zh_tw z ON CAST(d.userid AS BIGINT) = z.userid
  WHERE COALESCE(d.isdeleted, 0) = 0
    AND d.deviceid IS NOT NULL
    AND CAST(d.deviceid AS STRING) <> ''
)
SELECT
  COUNT(*) AS translate_page_total,
  COUNT_IF(
    LOWER(COALESCE(b.translation_service, '')) LIKE '%gemma%'
    OR b.translation_service = 'free-provider-translategemma'
  ) AS gemma_events,
  ROUND(
    100.0 * COUNT_IF(
      LOWER(COALESCE(b.translation_service, '')) LIKE '%gemma%'
      OR b.translation_service = 'free-provider-translategemma'
    ) / NULLIF(COUNT(*), 0),
    4
  ) AS gemma_pct,
  COUNT_IF(b.translation_service = 'free-model') AS free_model_events,
  ROUND(
    100.0 * COUNT_IF(b.translation_service = 'free-model') / NULLIF(COUNT(*), 0),
    4
  ) AS free_model_pct
FROM immdata.user_behaviour b
WHERE b.created_ts >= '2026-08-11'
  AND b.created_ts < '2026-09-11'
  AND b.event_name = 'translate_page'
  AND (
    EXISTS (SELECT 1 FROM devices d WHERE d.device_id = b.device_id)
    OR EXISTS (SELECT 1 FROM zh_tw z WHERE z.userid = b.ex_int_arg1)
  )
;
