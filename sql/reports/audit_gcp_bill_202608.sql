-- T039 GCP 2026-08 账单 vs immdata.token_used_aw（Google / Vertex Gemini）
-- 账单：Downloads「沉浸式--8月.xlsx」；口径同 T013
-- Flash=resourcename gemini @ 0.5/3.0 per 1M；Pro=gemini_25_pro_preview @ 2.0/12.0
-- 65折：Flash 0.33/1.95；Pro 1.3/7.8
-- 正式对账窗：发票使用起止含 7/31，应用 timestamp >= '2026-07-31' AND < '2026-09-01'
-- （仅日历 8 月会对不齐旧项目 7/31 行，表观误差虚高到 ~3%）

-- 1) 日历月资源汇总（8/1–8/31，对照用）
SELECT
  resourcename,
  SUM(COALESCE(inputusage, 0)) AS input_tokens,
  SUM(COALESCE(cachedinputusage, 0)) AS cached_input_tokens,
  SUM(COALESCE(outputusage, 0)) AS output_tokens,
  COUNT(*) AS row_cnt
FROM immdata.token_used_aw
WHERE providername = 'Google'
  AND timestamp >= '2026-08-01'
  AND timestamp < '2026-09-01'
  AND recordtype = 'capture'
GROUP BY resourcename
ORDER BY resourcename;

-- 2) 日历月标价 / 65折估算
WITH u AS (
  SELECT
    resourcename,
    SUM(COALESCE(inputusage, 0)) AS in_t,
    SUM(COALESCE(outputusage, 0)) AS out_t,
    SUM(COALESCE(cachedinputusage, 0)) AS cache_t
  FROM immdata.token_used_aw
  WHERE providername = 'Google'
    AND timestamp >= '2026-08-01'
    AND timestamp < '2026-09-01'
    AND recordtype = 'capture'
  GROUP BY resourcename
)
SELECT
  resourcename,
  in_t,
  out_t,
  cache_t,
  ROUND(
    CASE resourcename
      WHEN 'gemini' THEN in_t / 1e6 * 0.5 + out_t / 1e6 * 3.0
      WHEN 'gemini_25_pro_preview' THEN in_t / 1e6 * 2.0 + out_t / 1e6 * 12.0
      ELSE 0
    END,
    2
  ) AS est_usd_list,
  ROUND(
    CASE resourcename
      WHEN 'gemini' THEN in_t / 1e6 * 0.33 + out_t / 1e6 * 1.95
      WHEN 'gemini_25_pro_preview' THEN in_t / 1e6 * 1.3 + out_t / 1e6 * 7.8
      ELSE 0
    END,
    2
  ) AS est_usd_65pct
FROM u
ORDER BY resourcename;

-- 3) 对齐发票使用窗（7/31–8/31）标价 / 65折 —— 正式对账
WITH u AS (
  SELECT
    resourcename,
    SUM(COALESCE(inputusage, 0)) AS in_t,
    SUM(COALESCE(outputusage, 0)) AS out_t,
    SUM(COALESCE(cachedinputusage, 0)) AS cache_t
  FROM immdata.token_used_aw
  WHERE providername = 'Google'
    AND timestamp >= '2026-07-31'
    AND timestamp < '2026-09-01'
    AND recordtype = 'capture'
  GROUP BY resourcename
)
SELECT
  resourcename,
  in_t,
  out_t,
  cache_t,
  ROUND(
    CASE resourcename
      WHEN 'gemini' THEN in_t / 1e6 * 0.5 + out_t / 1e6 * 3.0
      WHEN 'gemini_25_pro_preview' THEN in_t / 1e6 * 2.0 + out_t / 1e6 * 12.0
      ELSE 0
    END,
    2
  ) AS est_usd_list,
  ROUND(
    CASE resourcename
      WHEN 'gemini' THEN in_t / 1e6 * 0.33 + out_t / 1e6 * 1.95
      WHEN 'gemini_25_pro_preview' THEN in_t / 1e6 * 1.3 + out_t / 1e6 * 7.8
      ELSE 0
    END,
    2
  ) AS est_usd_65pct
FROM u
ORDER BY resourcename;

-- 4) 日级完整性（含 7/31）
SELECT
  to_date(timestamp) AS dt,
  SUM(COALESCE(inputusage, 0) + COALESCE(outputusage, 0)) AS total_tokens
FROM immdata.token_used_aw
WHERE providername = 'Google'
  AND timestamp >= '2026-07-31'
  AND timestamp < '2026-09-01'
  AND recordtype = 'capture'
GROUP BY 1
ORDER BY 1;
