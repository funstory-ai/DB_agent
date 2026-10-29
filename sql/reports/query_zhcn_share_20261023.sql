-- 简中(zh-CN) 占比：DAU 口径 + 网页翻译量口径（任务 T083）
-- 口径：母语 = imm_device_native_language（target 优先 / interface fallback）；简中代码 = 'zh-CN'
-- 数据水位：两表均北京日更；结果约截至前一日

-- (1) DAU 口径：近 30 个北京日 各母语 DAU 累计占比（DAU 加权≈日均占比）
SELECT
  native_language,
  SUM(dau)                                            AS sum_dau_30d,
  ROUND(SUM(dau) * 1.0 / SUM(SUM(dau)) OVER (), 4)    AS dau_share
FROM immdata.ads_language_daily_overview
WHERE dt >= DATE('2026-10-22') - INTERVAL 29 DAY
  AND dt <= DATE('2026-10-22')
  AND native_language IS NOT NULL AND native_language <> ''
GROUP BY native_language
ORDER BY sum_dau_30d DESC
LIMIT 10;

-- (2) 网页翻译量口径：近 14 天 translate_page 事件按母语占比
--     总事件≈71.3M/14d≈5.09M/天，与“网页翻译日均500W”锚点吻合
SELECT
  COALESCE(n.native_language, 'UNKNOWN')              AS lang,
  COUNT(*)                                            AS events,
  ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4)    AS event_share
FROM immdata.user_behaviour b
LEFT JOIN immdata.imm_device_native_language n
       ON n.device_id = b.device_id
WHERE b.created_ts >= TIMESTAMP '2026-10-09 00:00:00'
  AND b.created_ts <  TIMESTAMP '2026-10-23 00:00:00'
  AND b.event_name = 'translate_page'
GROUP BY lang
ORDER BY events DESC
LIMIT 10;
