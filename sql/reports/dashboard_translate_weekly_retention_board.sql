-- =============================================================================
-- 插件翻译业务分业务周留存 · Superset board
-- 任务：docs/tasks/dashboard_translate_weekly_retention_20260831.md
-- 源表：
--   imm_translate_biz_firstuse_weekly_retention（插件业务，device）
--   imm_babeldoc_firstuse_weekly_retention（BabelDoc，userid；不走 behaviour）
-- 口径：docs/norms/translate_biz.md
-- =============================================================================

-- 【可挂 Superset】ds_retention_by_biz
-- 推荐 Chart：Table（一业务一表）；Filter biz_code；Metric 一律 MAX
-- 列建议：cohort_week_start + cohort_devices + ret_w1..w4 + w1..w4_retention_rate
-- Metric 用 MAX（每周每业务一行）；留存率用百分比
SELECT
  biz_code,
  biz_name,
  event_name,
  cohort_week_start,
  cohort_devices,
  ret_w1_devices,
  ret_w2_devices,
  ret_w3_devices,
  ret_w4_devices,
  w1_retention_rate,
  w2_retention_rate,
  w3_retention_rate,
  w4_retention_rate
FROM immdata.imm_translate_biz_firstuse_weekly_retention
WHERE cohort_week_start >= date_add(week, -26, to_date(now()))
ORDER BY biz_code, cohort_week_start;

-- 【可挂 Superset】ds_retention_latest_by_biz
SELECT
  t.biz_code,
  t.biz_name,
  t.cohort_week_start,
  t.cohort_devices,
  t.w1_retention_rate,
  t.w4_retention_rate
FROM immdata.imm_translate_biz_firstuse_weekly_retention t
INNER JOIN (
  SELECT biz_code, max(cohort_week_start) AS max_w
  FROM immdata.imm_translate_biz_firstuse_weekly_retention
  GROUP BY 1
) m
  ON m.biz_code = t.biz_code
 AND m.max_w = t.cohort_week_start;

-- 【可挂 Superset】ds_babeldoc_retention
-- BabelDoc：首次使用周 + W1～W4；主体 userid；源 imm_babel_doc_record
-- Chart：Table；Metric MAX；列 cohort_week_start + cohort_users + 四率
SELECT
  biz_code,
  biz_name,
  cohort_week_start,
  cohort_users,
  ret_w1_users,
  ret_w2_users,
  ret_w3_users,
  ret_w4_users,
  w1_retention_rate,
  w2_retention_rate,
  w3_retention_rate,
  w4_retention_rate
FROM immdata.imm_babeldoc_firstuse_weekly_retention
WHERE cohort_week_start >= date_add(week, -26, to_date(now()))
ORDER BY cohort_week_start;

-- biz_code（插件）：web / video / ai_subtitle / image_pro / image_free / manga /
--   selection / input_space / side_panel / area_select / pdf / pdf_pro / hover / ebook
-- BabelDoc 用独立 Dataset，勿混进 device 业务 Filter
;
