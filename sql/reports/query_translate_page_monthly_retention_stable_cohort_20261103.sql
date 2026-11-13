-- =============================================================================
-- translate_page 月留存 · 稳定队列修复版（对应 T101 / 原 query_translate_page_monthly_retention_ruleA.sql）
--
-- ⚠️ 2026-11-04 定案：下方「问题」前提已被时间旅行实测推翻，本修复草案不再有必要，
--    保留仅作历史参考，勿据此上线。
--    实测：user_behaviour 纯追加、已落库行不变；在真实历史快照上重跑原 SQL，
--    2026-09 桶 10/05=1,005,727 → 11/01=1,028,733 → 当前=1,030,035，单调递增；
--    用户所报 931,096 不是这条 SQL 在当时的表上能跑出的值。
--    T032 只改派生表 imm_device_native_language，不改 user_behaviour.install_day。
--
-- 【已撤回的历史问题描述，保留存档】
-- 问题（❌ 已证伪）：原 SQL 的队列月 = to_start_of_month(min(install_day)) 是查询时从
--       user_behaviour.install_day 现场重算的；曾推测 install_day 被 ETL 改小（T032），
--       导致同一月份重拉结果漂移（2026-09：1,010,718 → 931,096，−7.9%）。
-- 修复（❌ 前提不成立）：把每台设备的队列月【快照】到稳定表，月留存改 JOIN 快照。
--
-- ⚠️ 本仓只读：下方 (A) 快照 ETL 由数据团队执行，本会话不代跑；(B) 为只读 SELECT。
-- =============================================================================


-- =============================================================================
-- (A) 快照 ETL —— 数据团队在「回填稳定后」执行一次（建议每月 +14 天 asof）
--     构建 immdata.dim_device_install_cohort(device_id, cohort_month, source)
--     之后永不重算该表，月留存只 JOIN 它。
-- =============================================================================
-- CREATE TABLE IF NOT EXISTS immdata.dim_device_install_cohort (
--   device_id    String,
--   cohort_month Date,        -- to_start_of_month(首装月)
--   source       String       -- 'deviceinfo' = 取自 imt_deviceinfo.installtime（稳定）
--                             -- 'ub_install_day' = 取自 user_behaviour.min(install_day)（无锚点时的冻结值）
-- )
-- ;

-- INSERT INTO immdata.dim_device_install_cohort
-- WITH ub AS (                       -- 每台设备的 live min(install_day)（冻结于本次 asof）
--   SELECT device_id,
--          to_start_of_month(MIN(TRY_CAST(install_day AS DATE))) AS ub_cohort
--   FROM immdata.user_behaviour
--   WHERE event_name = 'translate_page'
--     AND version != '1.11.4'
--     AND TRY_CAST(install_day AS DATE) IS NOT NULL
--     AND install_day <> '1970-01-01'
--   GROUP BY device_id
-- )
-- SELECT
--   COALESCE(di.deviceid, ub.device_id) AS device_id,
--   to_start_of_month(COALESCE(di.installtime, ub.ub_cohort)) AS cohort_month,
--   CASE WHEN di.deviceid IS NOT NULL THEN 'deviceinfo' ELSE 'ub_install_day' END AS source
-- FROM ub
-- LEFT JOIN immdata.imt_deviceinfo di
--   ON di.deviceid = ub.device_id AND COALESCE(di.isdeleted,0) = 0
-- ;


-- =============================================================================
-- (B) 月留存（只读）· 改 JOIN 快照表
--     口径与原 SQL 对齐：Rule A 剔除；version != '1.11.4'；活动月以北京时区截断。
-- =============================================================================
SELECT
  c.cohort_month                                                       AS month_start_day,
  COUNT(DISTINCT c.device_id)                                         AS new_user_count,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 1) = m.month_start_day, c.device_id, NULL)) AS one_month_ret,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 2) = m.month_start_day, c.device_id, NULL)) AS two_month_ret,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 3) = m.month_start_day, c.device_id, NULL)) AS three_month_ret,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 4) = m.month_start_day, c.device_id, NULL)) AS four_month_ret,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 5) = m.month_start_day, c.device_id, NULL)) AS five_month_ret,
  COUNT(DISTINCT IF(add_months(c.cohort_month, 6) = m.month_start_day, c.device_id, NULL)) AS six_month_ret
FROM immdata.dim_device_install_cohort c
JOIN (
  SELECT
    device_id,
    to_start_of_month(add_hours(created_ts, 8)) AS month_start_day
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND version != '1.11.4'
    AND NOT (
      LOWER(TRIM(install_from)) = 'official_userscript'
      AND (
        (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
        OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
      )
    )
  GROUP BY device_id, to_start_of_month(add_hours(created_ts, 8))
) m
  ON m.device_id = c.device_id
GROUP BY c.cohort_month
ORDER BY c.cohort_month DESC
;
