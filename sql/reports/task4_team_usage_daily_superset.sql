-- 任务：团队租户用量看板（Superset）
-- 留档：docs/tasks/dashboard_team_usage_superset_20260814.md
-- 表：imt_teamusagedaily + imt_teamtenant
--
-- 【硬口径】token = Input + Output。
-- imt_teamusagedaily 同一模型既有汇总行（如 Gemini）又有 GeminiInput/GeminiOutput，
-- 禁止 SUM(usage) 全表，否则日用量约 ×2。
-- 本文件统一：只汇总 modelname LIKE '%Input' OR '%Output'。

-- =============================================================================
-- 图1：日用量（租户 × 日）【可挂 Superset】
-- Superset：Bar/Line；X=usage_date；Metric=SUM(daily_usage)；Series=tenant_name
-- 时间窗可由 Superset Filter 覆盖；下面给近 90 天默认窗
-- =============================================================================
SELECT
  CAST(u.tenantdate AS DATE) AS usage_date,
  t.id AS tenant_id,
  COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING))) AS tenant_name,
  SUM(u.usage) AS daily_usage
FROM immdata.imt_teamusagedaily u
LEFT JOIN immdata.imt_teamtenant t
  ON u.tenantid = t.id
 AND COALESCE(t.isdeleted, 0) = 0
WHERE COALESCE(u.isdeleted, 0) = 0
  AND (u.modelname LIKE '%Input' OR u.modelname LIKE '%Output')
  AND u.tenantdate >= DATEADD(day, -90, NOW())
  AND u.tenantdate < NOW()
GROUP BY
  CAST(u.tenantdate AS DATE),
  t.id,
  COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING)))
ORDER BY usage_date, tenant_name;


-- =============================================================================
-- 图1b：日用量 — Superset 虚拟表包装版【可挂 Superset · 须滚动窗】
-- 【勿写死日期】须用滚动近 90 天；写死上界会导致看板停在某日（如 2026-08-25 修口径后卡 8/24）
-- =============================================================================
SELECT
  CAST(usage_date AS DATE) AS usage_date,
  tenant_name AS tenant_name,
  SUM(daily_usage) AS "SUM(daily_usage)"
FROM (
  SELECT
    CAST(u.tenantdate AS DATE) AS usage_date,
    t.id AS tenant_id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING))) AS tenant_name,
    SUM(u.usage) AS daily_usage
  FROM immdata.imt_teamusagedaily u
  LEFT JOIN immdata.imt_teamtenant t
    ON u.tenantid = t.id
   AND COALESCE(t.isdeleted, 0) = 0
  WHERE COALESCE(u.isdeleted, 0) = 0
    AND (u.modelname LIKE '%Input' OR u.modelname LIKE '%Output')
  GROUP BY
    CAST(u.tenantdate AS DATE),
    t.id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING)))
) AS virtual_table
WHERE usage_date >= DATEADD(day, -90, NOW())
  AND usage_date < NOW()
GROUP BY
  CAST(usage_date AS DATE),
  tenant_name
ORDER BY "SUM(daily_usage)" DESC
LIMIT 10000;


-- =============================================================================
-- 图2：日占比（租户当日 / 当日全部租户）
-- =============================================================================
WITH daily AS (
  SELECT
    CAST(u.tenantdate AS DATE) AS usage_date,
    t.id AS tenant_id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING))) AS tenant_name,
    SUM(u.usage) AS daily_usage
  FROM immdata.imt_teamusagedaily u
  LEFT JOIN immdata.imt_teamtenant t
    ON u.tenantid = t.id
   AND COALESCE(t.isdeleted, 0) = 0
  WHERE COALESCE(u.isdeleted, 0) = 0
    AND (u.modelname LIKE '%Input' OR u.modelname LIKE '%Output')
    AND u.tenantdate >= DATEADD(day, -90, NOW())
    AND u.tenantdate < NOW()
  GROUP BY
    CAST(u.tenantdate AS DATE),
    t.id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING)))
)
SELECT
  usage_date,
  tenant_id,
  tenant_name,
  daily_usage,
  SUM(daily_usage) OVER (PARTITION BY usage_date) AS day_total_usage,
  CASE
    WHEN SUM(daily_usage) OVER (PARTITION BY usage_date) > 0
    THEN daily_usage * 100.0 / SUM(daily_usage) OVER (PARTITION BY usage_date)
    ELSE NULL
  END AS share_pct
FROM daily
ORDER BY usage_date, tenant_name;


-- =============================================================================
-- 图3：周用量（租户 × 周一）— SQL 内先按周汇总；usage_date 为 DATE
-- Superset：X=usage_date；Time grain 选「原始值/Day」即可（勿再套 Week）
-- =============================================================================
SELECT
  CAST(to_monday(CAST(u.tenantdate AS DATE)) AS DATE) AS usage_date,
  t.id AS tenant_id,
  COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING))) AS tenant_name,
  SUM(u.usage) AS weekly_usage
FROM immdata.imt_teamusagedaily u
LEFT JOIN immdata.imt_teamtenant t
  ON u.tenantid = t.id
 AND COALESCE(t.isdeleted, 0) = 0
WHERE COALESCE(u.isdeleted, 0) = 0
  AND (u.modelname LIKE '%Input' OR u.modelname LIKE '%Output')
  AND u.tenantdate >= DATEADD(day, -90, NOW())
  AND u.tenantdate < NOW()
GROUP BY
  CAST(to_monday(CAST(u.tenantdate AS DATE)) AS DATE),
  t.id,
  COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING)))
ORDER BY usage_date, tenant_name;


-- =============================================================================
-- 图3b：周用量 — Superset 虚拟表包装版（CAST AS DATE；滚动近 90 天，勿写死日期）
-- =============================================================================
SELECT
  CAST(to_monday(CAST(usage_date AS DATE)) AS DATE) AS usage_date,
  tenant_name AS tenant_name,
  SUM(daily_usage) AS "SUM(daily_usage)"
FROM (
  SELECT
    CAST(u.tenantdate AS DATE) AS usage_date,
    t.id AS tenant_id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING))) AS tenant_name,
    SUM(u.usage) AS daily_usage
  FROM immdata.imt_teamusagedaily u
  LEFT JOIN immdata.imt_teamtenant t
    ON u.tenantid = t.id
   AND COALESCE(t.isdeleted, 0) = 0
  WHERE COALESCE(u.isdeleted, 0) = 0
    AND (u.modelname LIKE '%Input' OR u.modelname LIKE '%Output')
  GROUP BY
    CAST(u.tenantdate AS DATE),
    t.id,
    COALESCE(t.tenantname, CONCAT('tenant_', CAST(u.tenantid AS STRING)))
) AS virtual_table
WHERE usage_date >= DATEADD(day, -90, NOW())
  AND usage_date < NOW()
GROUP BY
  CAST(to_monday(CAST(usage_date AS DATE)) AS DATE),
  tenant_name
ORDER BY "SUM(daily_usage)" DESC
LIMIT 10000;


-- =============================================================================
-- 可选：只要大模型 token（排除 BabelDoc/Comics 等）时，在 WHERE 再加：
--   AND u.categoryname IN ('OpenAIPro', 'OpenAIMax')
-- =============================================================================
