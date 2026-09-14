-- 异常复核：webdata document feature DAU 2026-08 第一周飙升
-- 对照：feature_dau vs file active vs 官网 popup_document
-- 只读；窗口可按需改

-- 1) 看板同口径：document 日 DAU
SELECT stat_date,
       dau AS document_feature_dau
FROM webdata.ads_webapp_feature_dau
WHERE feature = 'document'
  AND stat_date >= '2026-07-20'
  AND stat_date < '2026-08-18'
ORDER BY stat_date;

-- 2) 周对比：feature vs 全站 file active vs 官网 popup
WITH fd AS (
  SELECT
    CASE
      WHEN stat_date >= '2026-07-27' AND stat_date < '2026-08-03' THEN 'W_jul27'
      WHEN stat_date >= '2026-08-03' AND stat_date < '2026-08-10' THEN 'W_aug03'
    END AS wk,
    AVG(dau) AS avg_feature_dau
  FROM webdata.ads_webapp_feature_dau
  WHERE feature = 'document'
    AND stat_date >= '2026-07-27'
    AND stat_date < '2026-08-10'
  GROUP BY 1
),
act AS (
  SELECT
    CASE
      WHEN dt >= '2026-07-27' AND dt < '2026-08-03' THEN 'W_jul27'
      WHEN dt >= '2026-08-03' AND dt < '2026-08-10' THEN 'W_aug03'
    END AS wk,
    AVG(dau) AS avg_file_active
  FROM webdata.ads_webapp_active
  WHERE function_type = 'file'
    AND version_type = 'all'
    AND interface_language_group = 'all'
    AND dt >= '2026-07-27'
    AND dt < '2026-08-10'
  GROUP BY 1
),
pop AS (
  SELECT
    CASE
      WHEN dt >= '2026-07-27' AND dt < '2026-08-03' THEN 'W_jul27'
      WHEN dt >= '2026-08-03' AND dt < '2026-08-10' THEN 'W_aug03'
    END AS wk,
    COUNT(DISTINCT web_user_id) AS popup_document_week_uv
  FROM webdata.dws_webapp_user_day
  WHERE function_type = 'file'
    AND site_host = 'immersivetranslate.com'
    AND campaign = 'popup_document'
    AND dt >= '2026-07-27'
    AND dt < '2026-08-10'
  GROUP BY 1
)
SELECT f.wk,
       ROUND(f.avg_feature_dau, 0) AS avg_document_feature_dau,
       ROUND(a.avg_file_active, 0) AS avg_file_active_all,
       p.popup_document_week_uv
FROM fd f
LEFT JOIN act a ON f.wk = a.wk
LEFT JOIN pop p ON f.wk = p.wk
WHERE f.wk IS NOT NULL
ORDER BY f.wk;

-- 3) 日级：popup_document 与 feature_dau 对齐
SELECT d.dt,
       COUNT(DISTINCT d.web_user_id) AS popup_document_uv,
       f.dau AS document_feature_dau,
       ROUND(f.dau * 1.0 / NULLIF(COUNT(DISTINCT d.web_user_id), 0), 3) AS feat_over_popup
FROM webdata.dws_webapp_user_day d
JOIN webdata.ads_webapp_feature_dau f
  ON f.stat_date = d.dt
 AND f.feature = 'document'
WHERE d.function_type = 'file'
  AND d.site_host = 'immersivetranslate.com'
  AND d.campaign = 'popup_document'
  AND d.dt >= '2026-07-20'
  AND d.dt < '2026-08-18'
GROUP BY d.dt, f.dau
ORDER BY d.dt;

-- 4) 宿主拆分：官网涨、app 子域跌（解释总 file 略降）
SELECT dt,
       site_host,
       COUNT(DISTINCT web_user_id) AS uv
FROM webdata.dws_webapp_user_day
WHERE function_type = 'file'
  AND site_host IN ('immersivetranslate.com', 'app.immersivetranslate.com')
  AND dt IN ('2026-07-28', '2026-07-29', '2026-08-03', '2026-08-04', '2026-08-05')
GROUP BY 1, 2
ORDER BY 1, 2;

-- 5) 真实文档 Web App 总活 + Popup 双 campaign 合计（周对比）
WITH weeks AS (
  SELECT dt,
         CASE
           WHEN dt >= '2026-07-27' AND dt < '2026-08-03' THEN 'W_jul27'
           WHEN dt >= '2026-08-03' AND dt < '2026-08-10' THEN 'W_aug03'
         END AS wk
  FROM webdata.ads_webapp_active
  WHERE function_type = 'file'
    AND version_type = 'all'
    AND interface_language_group = 'all'
    AND dt >= '2026-07-27'
    AND dt < '2026-08-10'
),
file_active AS (
  SELECT w.wk, AVG(a.dau) AS avg_file_dau
  FROM weeks w
  JOIN webdata.ads_webapp_active a ON a.dt = w.dt
  WHERE a.function_type = 'file'
    AND a.version_type = 'all'
    AND a.interface_language_group = 'all'
  GROUP BY w.wk
),
popup_both AS (
  SELECT
    CASE
      WHEN dt >= '2026-07-27' AND dt < '2026-08-03' THEN 'W_jul27'
      WHEN dt >= '2026-08-03' AND dt < '2026-08-10' THEN 'W_aug03'
    END AS wk,
    AVG(uv) AS avg_popup_doc_uv
  FROM (
    SELECT dt, COUNT(DISTINCT web_user_id) AS uv
    FROM webdata.dws_webapp_user_day
    WHERE function_type = 'file'
      AND campaign IN ('popup_document', 'popup_btn_document')
      AND dt >= '2026-07-27'
      AND dt < '2026-08-10'
    GROUP BY dt
  ) t
  GROUP BY 1
)
SELECT f.wk,
       ROUND(f.avg_file_dau, 0) AS avg_file_active_real,
       ROUND(p.avg_popup_doc_uv, 0) AS avg_popup_document_both_campaigns
FROM file_active f
LEFT JOIN popup_both p ON f.wk = p.wk
WHERE f.wk IS NOT NULL
ORDER BY f.wk;
