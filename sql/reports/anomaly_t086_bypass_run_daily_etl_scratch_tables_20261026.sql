-- =============================================================================
-- T086 / OSS 403 绕过版 run_daily_etl（写仓执行；本仓只读勿跑）
--
-- 背景：
--   task_run_daily_etl → CALL PROCEDURE run_daily_etl()
--   2026-10-24 起 FAILED：实例临时/spill 存储桶 query-storage-aqua 被 bucket ACL 拒(403)
--   根因：CREATE TEMP TABLE 的数据块必须写 query-storage-aqua（Databend Cloud 平台代管，
--         不在任何用户阿里云账号下，见 docs/tasks/anomaly_ads_language_daily_overview_etl_failed_20261026.md）
--
-- 本脚本（与 T032 版语义完全等价，仅改落盘位置）：
--   A) 全部 CREATE TEMP TABLE → CREATE OR REPLACE TABLE immdata.etl_tmp_* / etl_stg_*
--      机理：普通表的块写主数据桶（10-24 后仍可读可写），不碰被 403 的桶；
--            物化一次、多处引用的语义不变，无 CTE 重算、无 spill 风险。
--      前提：过程 owner 对 immdata 需有 CREATE TABLE 权限。
--      残留：26 张 etl_* 常驻 immdata，每次运行 CREATE OR REPLACE 覆盖；
--            桶权限修复回滚 TEMP 版后可 DROP 清理。
--   B) CALL PROCEDURE 立即补近 14 日（含缺的 10-24/10-25）
--   C) 验收 SELECT + 与 10-23（最后一个好天）抽样对拍（P019）
--
-- 保留 T032 的历史修复：install_day 用 TRY_CAST，勿回退 TO_DATE。
-- =============================================================================

CREATE OR REPLACE PROCEDURE run_daily_etl()
RETURNS STRING
LANGUAGE SQL
COMMENT = 'T086: daily funnel/overview ETL; TEMP->real tables to bypass query-storage-aqua 403'
AS $$
BEGIN
-- =========================================================
-- 0) Common time boundaries
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_runtime AS
SELECT
    add_hours(date(add_hours(now(), 8)), -8)                                        AS day_end_ts,
    add_hours(add_days(date(add_hours(now(), 8)), -1), -8)                          AS day_1_start_ts,
    add_hours(add_days(date(add_hours(now(), 8)), -7), -8)                          AS day_7_start_ts,
    date(add_hours(now(), 8))                                                       AS biz_today,
    add_days(date(add_hours(now(), 8)), -14)                                        AS biz_d14,
    to_date(to_start_of_week(date(add_hours(now(), 8))))                            AS biz_this_week;

-- =========================================================
-- 1) Reusable filtered behaviour slices
--    Biggest win: scan user_behaviour once per window, not repeatedly.
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_ub_d1 AS
SELECT
    ub.created_ts,
    DATE(add_hours(ub.created_ts, 8)) AS dt,
    ub.device_id,
    ub.interface_language,
    ub.install_day,
    ub.event_name,
    ub.main_frame,
    ub.is_new_user_today,
    ub.page_type
FROM immdata.user_behaviour ub, immdata.etl_tmp_runtime r
WHERE ub.created_ts >= r.day_1_start_ts
  AND ub.created_ts <  r.day_end_ts
  AND ub.device_id IS NOT NULL
  AND ub.device_id <> '';

CREATE OR REPLACE TABLE immdata.etl_tmp_ub_d7 AS
SELECT
    ub.created_ts,
    DATE(add_hours(ub.created_ts, 8)) AS dt,
    ub.device_id,
    ub.interface_language,
    ub.install_day,
    ub.event_name,
    ub.main_frame,
    ub.is_new_user_today,
    ub.page_type
FROM immdata.user_behaviour ub, immdata.etl_tmp_runtime r
WHERE ub.created_ts >= r.day_7_start_ts
  AND ub.created_ts <  r.day_end_ts
  AND ub.version <> '1.11.4'
  AND ub.device_id IS NOT NULL
  AND ub.device_id <> '';

CREATE OR REPLACE TABLE immdata.etl_tmp_device_d1 AS
SELECT DISTINCT device_id
FROM immdata.etl_tmp_ub_d1;

-- =========================================================
-- 2) Small dimension helpers
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_deviceinfo_latest AS
SELECT
    z.deviceid,
    CAST(z.userid AS STRING) AS userid
FROM (
    SELECT
        d.deviceid,
        d.userid,
        ROW_NUMBER() OVER (
            PARTITION BY d.deviceid
            ORDER BY d.updatetime DESC, d.createtime DESC
        ) AS rn
    FROM immdata.imt_deviceinfo d
    WHERE d.isdeleted = 0
      AND d.deviceid IS NOT NULL
      AND d.deviceid <> ''
) z
WHERE z.rn = 1;

CREATE OR REPLACE TABLE immdata.etl_tmp_pay_day AS
SELECT
    CAST(o.userid AS STRING) AS analyze_id,
    DATE(add_hours(o.createtime, 8)) AS pay_dt
FROM immdata.imt_subscriptiongoodsorder o
WHERE o.orderstatus = 'finished'
  AND o.amountpaid > 0
  AND o.userid IS NOT NULL
  AND CAST(o.userid AS STRING) <> ''
  AND (o.isdeleted = 0 OR o.isdeleted IS NULL)
GROUP BY CAST(o.userid AS STRING), DATE(add_hours(o.createtime, 8));

CREATE OR REPLACE TABLE immdata.etl_tmp_first_pay AS
SELECT
    CAST(o.userid AS STRING) AS analyze_id,
    MIN(DATE(add_hours(o.createtime, 8))) AS first_pay_dt
FROM immdata.imt_subscriptiongoodsorder o
WHERE o.orderstatus = 'finished'
  AND o.amountpaid > 0
  AND o.userid IS NOT NULL
  AND CAST(o.userid AS STRING) <> ''
  AND (o.isdeleted = 0 OR o.isdeleted IS NULL)
GROUP BY CAST(o.userid AS STRING);

CREATE OR REPLACE TABLE immdata.etl_tmp_exrate AS
SELECT
    UPPER(currency) AS currency,
    MAX(exchangeRate) AS exchangeRate
FROM immdata.exchangerates
GROUP BY UPPER(currency);

-- =========================================================
-- 3) imm_device_native_language staging
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_target_lang_top1 AS
SELECT
    t.device_id,
    t.target_language AS native_language,
    t.cnt
FROM (
    SELECT
        s.device_id,
        s.target_language,
        s.cnt,
        ROW_NUMBER() OVER (
            PARTITION BY s.device_id
            ORDER BY s.cnt DESC, s.update_time DESC, s.target_language
        ) AS rn
    FROM immdata.imm_user_target_lan_stats s
    INNER JOIN immdata.etl_tmp_device_d1 d
        ON s.device_id = d.device_id
    WHERE s.target_language IS NOT NULL
      AND s.target_language <> ''
) t
WHERE t.rn = 1;

CREATE OR REPLACE TABLE immdata.etl_tmp_interface_lang_top1 AS
SELECT
    t.device_id,
    t.interface_language AS native_language,
    t.cnt
FROM (
    SELECT
        ub.device_id,
        ub.interface_language,
        COUNT(*) AS cnt,
        MAX(ub.created_ts) AS last_ts,
        ROW_NUMBER() OVER (
            PARTITION BY ub.device_id
            ORDER BY COUNT(*) DESC, MAX(ub.created_ts) DESC, ub.interface_language
        ) AS rn
    FROM immdata.etl_tmp_ub_d1 ub
    WHERE ub.interface_language IS NOT NULL
      AND ub.interface_language <> ''
    GROUP BY ub.device_id, ub.interface_language
) t
WHERE t.rn = 1;

CREATE OR REPLACE TABLE immdata.etl_tmp_install_day_d1 AS
SELECT
    ub.device_id,
    MIN(TRY_CAST(ub.install_day AS DATE)) AS install_day
FROM immdata.etl_tmp_ub_d1 ub, immdata.etl_tmp_runtime r
WHERE ub.install_day IS NOT NULL
  AND REGEXP_LIKE(ub.install_day, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') = 1
  AND TRY_CAST(ub.install_day AS DATE) IS NOT NULL
  AND TRY_CAST(ub.install_day AS DATE) >= DATE '2020-01-01'
  AND TRY_CAST(ub.install_day AS DATE) <= add_days(r.biz_today, 30)
GROUP BY ub.device_id;

CREATE OR REPLACE TABLE immdata.etl_stg_device_native_language AS
SELECT
    x.device_id,
    x.native_language,
    x.cnt,
    NOW() AS update_time,
    CASE
        WHEN old.install_day IS NULL THEN inst.install_day
        WHEN inst.install_day IS NULL THEN old.install_day
        WHEN inst.install_day < old.install_day THEN inst.install_day
        ELSE old.install_day
    END AS install_day,
    CASE
        WHEN di.userid IS NOT NULL AND CAST(di.userid AS STRING) <> '' THEN CAST(di.userid AS STRING)
        ELSE CAST(old.userid AS STRING)
    END AS userid
FROM (
    SELECT
        d.device_id,
        COALESCE(tl.native_language, il.native_language) AS native_language,
        COALESCE(tl.cnt, il.cnt) AS cnt
    FROM immdata.etl_tmp_device_d1 d
    LEFT JOIN immdata.etl_tmp_target_lang_top1 tl
        ON d.device_id = tl.device_id
    LEFT JOIN immdata.etl_tmp_interface_lang_top1 il
        ON d.device_id = il.device_id
    WHERE COALESCE(tl.native_language, il.native_language) IS NOT NULL
      AND COALESCE(tl.native_language, il.native_language) <> ''
) x
LEFT JOIN immdata.imm_device_native_language old
    ON x.device_id = old.device_id
LEFT JOIN immdata.etl_tmp_deviceinfo_latest di
    ON x.device_id = di.deviceid
LEFT JOIN immdata.etl_tmp_install_day_d1 inst
    ON x.device_id = inst.device_id
WHERE old.install_day IS NULL
   OR (inst.install_day IS NOT NULL AND inst.install_day < old.install_day)
   OR (
       old.device_id IS NULL
       OR COALESCE(old.native_language, '') <> COALESCE(x.native_language, '')
       OR COALESCE(old.cnt, -1) <> COALESCE(x.cnt, -1)
       OR COALESCE(CAST(old.userid AS STRING), '') <> COALESCE(CAST(di.userid AS STRING), '')
   );

REPLACE INTO immdata.imm_device_native_language
ON (device_id)
SELECT *
FROM immdata.etl_stg_device_native_language;

-- =========================================================
-- 4) Reusable entity mapping for 7d jobs
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_entity_map_d7 AS
SELECT DISTINCT
    ub.device_id,
    CASE
        WHEN nl.userid IS NOT NULL AND CAST(nl.userid AS STRING) <> '' THEN CAST(nl.userid AS STRING)
        ELSE CONCAT('device_', ub.device_id)
    END AS analyze_id
FROM immdata.etl_tmp_ub_d7 ub
LEFT JOIN immdata.imm_device_native_language nl
    ON ub.device_id = nl.device_id;

CREATE OR REPLACE TABLE immdata.etl_tmp_entity_day_base AS
SELECT
    ub.dt,
    em.analyze_id,
    MAX(IF(ub.event_name = 'translate_page' AND ub.main_frame = '1', 1, 0)) AS is_dau,
    MAX(IF(ub.event_name = 'init_page_daily' AND ub.is_new_user_today = '1', 1, 0)) AS is_new_install,
    MAX(IF(ub.event_name = 'translate_page' AND ub.main_frame = '1' AND ub.is_new_user_today = '1', 1, 0)) AS is_new_activation,
    COUNT(IF(ub.event_name = 'translate_page' AND ub.main_frame = '1', 1, NULL)) AS translate_page_cnt,
    MIN(ub.created_ts) AS first_event_ts
FROM immdata.etl_tmp_ub_d7 ub
JOIN immdata.etl_tmp_entity_map_d7 em
  ON ub.device_id = em.device_id
GROUP BY ub.dt, em.analyze_id;

-- =========================================================
-- 5) imm_entity_current_profile staging
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_entity_profile_base AS
SELECT
    d.analyze_id,
    MAX(d.userid) AS userid,
    MIN(d.install_day) AS install_day,
    COUNT(DISTINCT d.device_id) AS device_count
FROM (
    SELECT DISTINCT
        ub.device_id,
        CAST(n.userid AS STRING) AS userid,
        n.install_day,
        em.analyze_id
    FROM immdata.etl_tmp_ub_d7 ub
    JOIN immdata.etl_tmp_entity_map_d7 em
      ON ub.device_id = em.device_id
    LEFT JOIN immdata.imm_device_native_language n
      ON ub.device_id = n.device_id
) d
GROUP BY d.analyze_id;

CREATE OR REPLACE TABLE immdata.etl_tmp_entity_lang_pref AS
SELECT
    x.analyze_id,
    ARG_MAX(x.native_language, x.lang_cnt) AS native_language
FROM (
    SELECT
        em.analyze_id,
        n.native_language,
        COUNT(*) AS lang_cnt
    FROM immdata.etl_tmp_entity_map_d7 em
    JOIN immdata.imm_device_native_language n
      ON em.device_id = n.device_id
    WHERE n.native_language IS NOT NULL
      AND n.native_language <> ''
    GROUP BY em.analyze_id, n.native_language
) x
GROUP BY x.analyze_id;

CREATE OR REPLACE TABLE immdata.etl_stg_entity_current_profile AS
SELECT
    base.analyze_id,
    base.userid,
    lang.native_language,
    base.install_day,
    TO_DATE(TO_START_OF_WEEK(base.install_day)) AS install_week,
    base.device_count,
    NOW() AS update_time
FROM immdata.etl_tmp_entity_profile_base base
LEFT JOIN immdata.etl_tmp_entity_lang_pref lang
  ON base.analyze_id = lang.analyze_id;

REPLACE INTO immdata.imm_entity_current_profile
ON (analyze_id)
SELECT *
FROM immdata.etl_stg_entity_current_profile;

-- =========================================================
-- 6) imm_entity_daily_funnel staging
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_stg_entity_daily_funnel AS
SELECT
    b.dt,
    b.analyze_id,
    ep.userid,
    ep.native_language,
    ep.install_day,
    ep.install_week,
    b.is_dau,
    b.is_new_install,
    b.is_new_activation,
    IF(pt.analyze_id IS NOT NULL, 1, 0) AS pay_today,
    IF(fp.first_pay_dt IS NOT NULL AND fp.first_pay_dt <= b.dt, 1, 0) AS pay_ever,
    b.translate_page_cnt,
    b.first_event_ts,
    NOW() AS update_time
FROM immdata.etl_tmp_entity_day_base b
LEFT JOIN immdata.imm_entity_current_profile ep
  ON b.analyze_id = ep.analyze_id
LEFT JOIN immdata.etl_tmp_pay_day pt
  ON b.analyze_id = pt.analyze_id
 AND b.dt = pt.pay_dt
LEFT JOIN immdata.etl_tmp_first_pay fp
  ON b.analyze_id = fp.analyze_id;

REPLACE INTO immdata.imm_entity_daily_funnel
ON (dt, analyze_id)
SELECT *
FROM immdata.etl_stg_entity_daily_funnel;

-- =========================================================
-- 7) imm_entity_daily_feature_usage staging
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_feature_usage_raw AS
SELECT
    ub.dt,
    em.analyze_id,
    CASE
        WHEN ub.event_name = 'translate_video_subtitle' THEN 'translate_video_subtitle'
        WHEN ub.event_name = 'translate_manga' THEN 'translate_manga'
        WHEN ub.event_name = 'translate_input' THEN 'translate_input'
        WHEN ub.event_name = 'translate_image' THEN 'translate_image'
        WHEN ub.event_name = 'use_ai_subtitle' THEN 'use_ai_subtitle'
        WHEN ub.event_name = 'selection_translate' THEN 'selection_translate'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'pdfReader' THEN 'pdfReader'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'pdfProReader' THEN 'pdfProReader'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'ebookBuilder' THEN 'ebookBuilder'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'subtitleBuilder' THEN 'subtitleBuilder'
        ELSE NULL
    END AS feature_name,
    COUNT(*) AS use_cnt,
    MIN(ub.created_ts) AS first_use_ts
FROM immdata.etl_tmp_ub_d7 ub
JOIN immdata.etl_tmp_entity_map_d7 em
  ON ub.device_id = em.device_id
WHERE (
        ub.event_name IN ('translate_video_subtitle', 'translate_manga', 'translate_input', 'translate_image', 'use_ai_subtitle', 'selection_translate')
        OR (ub.event_name = 'translate_page' AND ub.page_type IN ('pdfReader', 'pdfProReader', 'ebookBuilder', 'subtitleBuilder'))
      )
GROUP BY
    ub.dt,
    em.analyze_id,
    CASE
        WHEN ub.event_name = 'translate_video_subtitle' THEN 'translate_video_subtitle'
        WHEN ub.event_name = 'translate_manga' THEN 'translate_manga'
        WHEN ub.event_name = 'translate_input' THEN 'translate_input'
        WHEN ub.event_name = 'translate_image' THEN 'translate_image'
        WHEN ub.event_name = 'use_ai_subtitle' THEN 'use_ai_subtitle'
        WHEN ub.event_name = 'selection_translate' THEN 'selection_translate'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'pdfReader' THEN 'pdfReader'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'pdfProReader' THEN 'pdfProReader'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'ebookBuilder' THEN 'ebookBuilder'
        WHEN ub.event_name = 'translate_page' AND ub.page_type = 'subtitleBuilder' THEN 'subtitleBuilder'
        ELSE NULL
    END;

CREATE OR REPLACE TABLE immdata.etl_stg_entity_daily_feature_usage AS
SELECT
    f.dt,
    f.analyze_id,
    ep.userid,
    ep.native_language,
    ep.install_day,
    ep.install_week,
    f.feature_name,
    1 AS used_flag,
    f.use_cnt,
    f.first_use_ts,
    NOW() AS update_time
FROM immdata.etl_tmp_feature_usage_raw f
LEFT JOIN immdata.imm_entity_current_profile ep
  ON f.analyze_id = ep.analyze_id
WHERE f.feature_name IS NOT NULL;

REPLACE INTO immdata.imm_entity_daily_feature_usage
ON (dt, analyze_id, feature_name)
SELECT *
FROM immdata.etl_stg_entity_daily_feature_usage;

-- =========================================================
-- 8) ads_language_daily_overview staging
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_pay_amount_by_lang AS
SELECT
    DATE(add_hours(o.createtime, 8)) AS dt,
    ep.native_language,
    COUNT(*) AS pay_today_order_cnt,
    CAST(SUM(o.amountpaid * ex.exchangeRate / 100) AS Float64) AS pay_today_amount
FROM immdata.imt_subscriptiongoodsorder o
JOIN immdata.imm_entity_current_profile ep
  ON CAST(o.userid AS STRING) = ep.analyze_id
LEFT JOIN immdata.etl_tmp_exrate ex
  ON UPPER(COALESCE(o.currency, 'CNY')) = ex.currency
JOIN immdata.etl_tmp_runtime r
  ON 1 = 1
WHERE o.orderstatus = 'finished'
  AND o.amountpaid > 0
  AND o.userid IS NOT NULL
  AND CAST(o.userid AS STRING) <> ''
  AND (o.isdeleted = 0 OR o.isdeleted IS NULL)
  AND DATE(add_hours(o.createtime, 8)) >= r.biz_d14
  AND DATE(add_hours(o.createtime, 8)) < r.biz_today
  AND ep.native_language IS NOT NULL
  AND ep.native_language <> ''
GROUP BY DATE(add_hours(o.createtime, 8)), ep.native_language;

CREATE OR REPLACE TABLE immdata.etl_stg_ads_language_daily_overview AS
SELECT
    f.dt,
    f.native_language,
    f.dau,
    f.new_install,
    f.new_activation,
    IF(f.new_install = 0, 0, f.new_activation / f.new_install) AS activation_rate,
    f.pay_today_user,
    COALESCE(o.pay_today_order_cnt, 0) AS pay_today_order_cnt,
    COALESCE(o.pay_today_amount, 0) AS pay_today_amount,
    IF(f.new_install = 0, 0, f.pay_today_user / f.new_install) AS pay_rate_by_install,
    IF(f.new_activation = 0, 0, f.pay_today_user / f.new_activation) AS pay_rate_by_activation,
    NOW() AS update_time
FROM (
    SELECT
        dt,
        native_language,
        SUM(is_dau) AS dau,
        SUM(is_new_install) AS new_install,
        SUM(is_new_activation) AS new_activation,
        SUM(pay_today) AS pay_today_user
    FROM immdata.imm_entity_daily_funnel, immdata.etl_tmp_runtime r
    WHERE dt >= r.biz_d14
      AND dt <  r.biz_today
      AND native_language IS NOT NULL
      AND native_language <> ''
    GROUP BY dt, native_language
) f
LEFT JOIN immdata.etl_tmp_pay_amount_by_lang o
  ON f.dt = o.dt
 AND f.native_language = o.native_language;

REPLACE INTO immdata.ads_language_daily_overview
ON (dt, native_language)
SELECT *
FROM immdata.etl_stg_ads_language_daily_overview;

-- =========================================================
-- 9) ads_language_install_week_feature_funnel staging
--    IMPORTANT:
--    1. Recompute recent cohorts, default 12 weeks.
--    2. Denominator must come from full cohort users.
--    3. Feature usage must be LEFT JOINed, not INNER JOINed.
-- =========================================================

CREATE OR REPLACE TABLE immdata.etl_tmp_recent_weeks AS
SELECT
    add_days(biz_this_week, -84) AS recent_week_start,
    biz_this_week
FROM immdata.etl_tmp_runtime;

-- Full cohort users by install_week + native_language.
-- This is the denominator base.
CREATE OR REPLACE TABLE immdata.etl_tmp_cohort_recent AS
SELECT
    install_week,
    native_language,
    analyze_id,
    MAX(is_new_activation) AS activated_flag
FROM immdata.imm_entity_daily_funnel, immdata.etl_tmp_recent_weeks w
WHERE install_week >= w.recent_week_start
  AND install_week <= w.biz_this_week
  AND native_language IS NOT NULL
  AND native_language <> ''
GROUP BY
    install_week,
    native_language,
    analyze_id;

-- Feature dimension.
-- Use this to generate one row per cohort-language-week-feature,
-- so features without usage will still have a correct zero numerator.
CREATE OR REPLACE TABLE immdata.etl_tmp_feature_dim AS
SELECT 'translate_video_subtitle' AS feature_name UNION ALL
SELECT 'translate_manga' UNION ALL
SELECT 'translate_input' UNION ALL
SELECT 'translate_image' UNION ALL
SELECT 'use_ai_subtitle' UNION ALL
SELECT 'selection_translate' UNION ALL
SELECT 'pdfReader' UNION ALL
SELECT 'pdfProReader' UNION ALL
SELECT 'ebookBuilder' UNION ALL
SELECT 'subtitleBuilder';

-- Actual feature usage users.
-- This table only contains users who used the feature.
-- It must not be used as the denominator source.
CREATE OR REPLACE TABLE immdata.etl_tmp_feature_recent AS
SELECT
    install_week,
    native_language,
    analyze_id,
    feature_name,
    1 AS feature_used_flag,
    MIN(first_use_ts) AS feature_first_use_ts
FROM immdata.imm_entity_daily_feature_usage, immdata.etl_tmp_recent_weeks w
WHERE feature_name IN (
        'translate_video_subtitle', 'translate_manga', 'translate_input', 'translate_image',
        'use_ai_subtitle', 'selection_translate', 'pdfReader', 'pdfProReader',
        'ebookBuilder', 'subtitleBuilder'
      )
  AND install_week >= w.recent_week_start
  AND install_week <= w.biz_this_week
  AND native_language IS NOT NULL
  AND native_language <> ''
GROUP BY
    install_week,
    native_language,
    analyze_id,
    feature_name;

-- Paid within 7 days after first feature usage.
CREATE OR REPLACE TABLE immdata.etl_tmp_paid_in_7d AS
SELECT
    fr.install_week,
    fr.native_language,
    fr.analyze_id,
    fr.feature_name,
    1 AS paid_in_7d_flag
FROM immdata.etl_tmp_feature_recent fr
JOIN (
    SELECT
        CAST(userid AS STRING) AS analyze_id,
        add_hours(createtime, 8) AS pay_ts
    FROM immdata.imt_subscriptiongoodsorder
    WHERE orderstatus = 'finished'
      AND amountpaid > 0
      AND userid IS NOT NULL
      AND CAST(userid AS STRING) <> ''
      AND (isdeleted = 0 OR isdeleted IS NULL)
) ord
  ON fr.analyze_id = ord.analyze_id
 AND ord.pay_ts >= fr.feature_first_use_ts
 AND ord.pay_ts <  add_days(fr.feature_first_use_ts, 7)
GROUP BY
    fr.install_week,
    fr.native_language,
    fr.analyze_id,
    fr.feature_name;

-- Correct final ADS aggregation.
-- Key fix:
--   immdata.etl_tmp_cohort_recent CROSS JOIN immdata.etl_tmp_feature_dim
--   LEFT JOIN immdata.etl_tmp_feature_recent
-- instead of:
--   immdata.etl_tmp_cohort_recent JOIN immdata.etl_tmp_feature_recent
CREATE OR REPLACE TABLE immdata.etl_stg_ads_language_install_week_feature_funnel AS
SELECT
    c.install_week,
    c.native_language,
    fd.feature_name,

    COUNT(DISTINCT c.analyze_id) AS cohort_size,

    COUNT(DISTINCT IF(
        c.activated_flag = 1,
        c.analyze_id,
        NULL
    )) AS activated_users,

    COUNT(DISTINCT IF(
        c.activated_flag = 1
        AND fr.feature_used_flag = 1,
        c.analyze_id,
        NULL
    )) AS activated_feature_users,

    COUNT(DISTINCT IF(
        c.activated_flag = 1
        AND fr.feature_used_flag = 1
        AND p7.paid_in_7d_flag = 1,
        c.analyze_id,
        NULL
    )) AS activated_feature_paid_users,

    IF(
        COUNT(DISTINCT c.analyze_id) = 0,
        0,
        COUNT(DISTINCT IF(c.activated_flag = 1, c.analyze_id, NULL))
        / COUNT(DISTINCT c.analyze_id)
    ) AS activation_rate,

    IF(
        COUNT(DISTINCT IF(c.activated_flag = 1, c.analyze_id, NULL)) = 0,
        0,
        COUNT(DISTINCT IF(
            c.activated_flag = 1
            AND fr.feature_used_flag = 1,
            c.analyze_id,
            NULL
        ))
        / COUNT(DISTINCT IF(c.activated_flag = 1, c.analyze_id, NULL))
    ) AS activation_to_feature_rate,

    IF(
        COUNT(DISTINCT IF(
            c.activated_flag = 1
            AND fr.feature_used_flag = 1,
            c.analyze_id,
            NULL
        )) = 0,
        0,
        COUNT(DISTINCT IF(
            c.activated_flag = 1
            AND fr.feature_used_flag = 1
            AND p7.paid_in_7d_flag = 1,
            c.analyze_id,
            NULL
        ))
        / COUNT(DISTINCT IF(
            c.activated_flag = 1
            AND fr.feature_used_flag = 1,
            c.analyze_id,
            NULL
        ))
    ) AS feature_to_pay_rate,

    IF(
        COUNT(DISTINCT c.analyze_id) = 0,
        0,
        COUNT(DISTINCT IF(
            c.activated_flag = 1
            AND fr.feature_used_flag = 1
            AND p7.paid_in_7d_flag = 1,
            c.analyze_id,
            NULL
        ))
        / COUNT(DISTINCT c.analyze_id)
    ) AS cohort_to_pay_rate,

    NOW() AS update_time
FROM immdata.etl_tmp_cohort_recent c
CROSS JOIN immdata.etl_tmp_feature_dim fd
LEFT JOIN immdata.etl_tmp_feature_recent fr
  ON c.install_week = fr.install_week
 AND c.native_language = fr.native_language
 AND c.analyze_id = fr.analyze_id
 AND fd.feature_name = fr.feature_name
LEFT JOIN immdata.etl_tmp_paid_in_7d p7
  ON c.install_week = p7.install_week
 AND c.native_language = p7.native_language
 AND c.analyze_id = p7.analyze_id
 AND fd.feature_name = p7.feature_name
GROUP BY
    c.install_week,
    c.native_language,
    fd.feature_name;

REPLACE INTO immdata.ads_language_install_week_feature_funnel
ON (install_week, native_language, feature_name)
SELECT *
FROM immdata.etl_stg_ads_language_install_week_feature_funnel;

  RETURN 'ok';
END;
$$;


-- =============================================================================
-- B) 立即补数（procedure 按北京「今天」重刷 [biz_today-14, biz_today)）
-- =============================================================================

CALL PROCEDURE run_daily_etl();

-- 可选（与上等价触发一次调度任务，一般不必同时跑）:
-- EXECUTE TASK task_run_daily_etl;

-- =============================================================================
-- C) 验收
-- =============================================================================

SELECT MAX(dt) AS max_dt, MAX(update_time) AS max_ut
FROM immdata.ads_language_daily_overview;

SELECT dt, COUNT(*) AS n, SUM(dau) AS dau_sum, MAX(update_time) AS max_ut
FROM immdata.ads_language_daily_overview
WHERE dt >= '2026-09-01'
GROUP BY dt
ORDER BY dt DESC;

SELECT MAX(dt) AS funnel_max_dt, MAX(update_time) AS funnel_max_ut
FROM immdata.imm_entity_daily_funnel
WHERE dt >= '2026-09-01';

-- 期望：max_dt >= 2026-09-06；若今日已过 BJ 日切，CALL 后应为「昨天」
