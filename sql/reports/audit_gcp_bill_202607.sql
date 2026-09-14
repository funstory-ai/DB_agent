-- GCP 2026-07 账单 vs immdata.token_used_aw（Google / Vertex Gemini）
-- 账单来源：桌面 Excel「沉浸式 2026.7.xlsx」（Billing Export 明细）
-- 只读

-- 1) 库内 7 月 Google token 汇总（capture；与历史 UCloud 对账同口径）
SELECT
  resourcename,
  SUM(coalesce(inputusage, 0)) AS input_tokens,
  SUM(coalesce(cachedinputusage, 0)) AS cached_input_tokens,
  SUM(coalesce(outputusage, 0)) AS output_tokens,
  COUNT(*) AS row_cnt
FROM immdata.token_used_aw
WHERE providername = 'Google'
  AND timestamp >= '2026-07-01'
  AND timestamp < '2026-08-01'
  AND recordtype = 'capture'
GROUP BY resourcename
ORDER BY resourcename;

-- 2) 按 Vertex 官方价（与 GCP SKU 标价一致）估算 USD
--    gemini -> gemini-3-flash-preview: 0.5 / 3.0 per 1M
--    gemini_25_pro_preview -> gemini-3.1-pro-preview: 2.0 / 12.0 per 1M
WITH u AS (
  SELECT
    resourcename,
    SUM(coalesce(inputusage, 0)) AS in_t,
    SUM(coalesce(outputusage, 0)) AS out_t
  FROM immdata.token_used_aw
  WHERE providername = 'Google'
    AND timestamp >= '2026-07-01'
    AND timestamp < '2026-08-01'
    AND recordtype = 'capture'
  GROUP BY resourcename
)
SELECT
  resourcename,
  in_t,
  out_t,
  ROUND(
    CASE resourcename
      WHEN 'gemini' THEN in_t / 1e6 * 0.5 + out_t / 1e6 * 3.0
      WHEN 'gemini_25_pro_preview' THEN in_t / 1e6 * 2.0 + out_t / 1e6 * 12.0
      ELSE 0
    END,
    2
  ) AS est_usd_list_price
FROM u
ORDER BY resourcename;

-- 3) 日级完整性（查缺失日；2026-07-08 Google 无数据）
SELECT
  to_date(timestamp) AS dt,
  SUM(coalesce(inputusage, 0) + coalesce(outputusage, 0)) AS total_tokens
FROM immdata.token_used_aw
WHERE providername = 'Google'
  AND timestamp >= '2026-07-01'
  AND timestamp < '2026-08-01'
GROUP BY 1
ORDER BY 1;

-- 4) 业务线拆分（Flash / gemini）
SELECT
  productline,
  SUM(coalesce(inputusage, 0) + coalesce(outputusage, 0)) AS total_tokens
FROM immdata.token_used_aw
WHERE providername = 'Google'
  AND resourcename = 'gemini'
  AND timestamp >= '2026-07-01'
  AND timestamp < '2026-08-01'
  AND recordtype = 'capture'
GROUP BY 1
ORDER BY total_tokens DESC
LIMIT 20;
