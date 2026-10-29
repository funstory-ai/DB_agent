-- T046 旧版付费硬墙：P034 激活 + P039 剔老号 · 激活后 7 日触墙率
-- 墙：user_need_pro + trigger=freeUsageLimitModal（不算注册墙）
-- 分组：A/B/C/D（同 T018）；附带 I/J 拆行便于看 gift 对旧墙的影响
-- 周切片同 T018 asof=09-28；obs 右开至 2026-09-30 16:00 UTC
-- 任务：docs/tasks/query_old_paywall_new_user_hit_rate_20260930.md

WITH slice_specs AS (
  SELECT 'natural_week_0821_0823_partial' AS slice, 'weekly' AS slice_type, 1 AS cohort_no,
         '2026-08-21' AS install_start, '2026-08-24' AS install_end_excl,
         '首周不满（3天）' AS maturity_status, DATE '2026-08-17' AS cohort_week_start
  UNION ALL
  SELECT 'natural_week_0824_0830', 'weekly', 2,
         '2026-08-24', '2026-08-31', '完整自然周（7天）', DATE '2026-08-24'
  UNION ALL
  SELECT 'natural_week_0831_0906', 'weekly', 3,
         '2026-08-31', '2026-09-07', '完整自然周（7天）', DATE '2026-08-31'
  UNION ALL
  SELECT 'natural_week_0907_0913', 'weekly', 4,
         '2026-09-07', '2026-09-14', '完整自然周（7天）', DATE '2026-09-07'
  UNION ALL
  SELECT 'natural_week_0914_0920', 'weekly', 5,
         '2026-09-14', '2026-09-21', '完整自然周（7天）', DATE '2026-09-14'
  UNION ALL
  SELECT 'natural_week_0921_0927', 'weekly', 6,
         '2026-09-21', '2026-09-28', '完整自然周（7天）；末段7d未熟', DATE '2026-09-21'
  UNION ALL
  SELECT 'natural_week_0928_partial', 'weekly', 7,
         '2026-09-28', '2026-09-29', '本周不满（1天）；7d未熟', DATE '2026-09-28'
  UNION ALL
  SELECT 'aggregate_0821_0928', 'aggregate', 99,
         '2026-08-21', '2026-09-29', '混合成熟度', NULL
),
cohort_beh AS (
  SELECT
    device_id,
    ab_tag,
    first_ts,
    act_uid,
    install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i', 'j') THEN 'D'
    END AS exp_group,
    CASE
      WHEN lower(trim(ab_tag)) = 'i' THEN 'I'
      WHEN lower(trim(ab_tag)) = 'j' THEN 'J'
      ELSE NULL
    END AS d_half
  FROM (
    SELECT
      device_id,
      ab_tag,
      created_ts AS first_ts,
      TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
      CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-20 16:00:00'
      AND created_ts < '2026-09-28 16:00:00'
      AND event_name = 'translate_page'
      AND is_new_user_today = '1'
      AND ab_tag IS NOT NULL
      AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        version >= '1.32.6'
        OR version LIKE '1.33.%'
        OR version LIKE '1.34.%'
        OR version LIKE '1.35.%'
        OR version LIKE '1.36.%'
      )
  ) x
  WHERE rn = 1
    AND install_day >= '2026-08-21'
    AND install_day < '2026-09-29'
),
di AS (
  SELECT device_id, userid
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY
          CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END,
          d.installtime
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort_beh) c
      ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0
      AND d.installtime > '1970-01-02'
  ) t
  WHERE rn = 1
),
base_raw AS (
  SELECT
    b.device_id,
    b.exp_group,
    b.d_half,
    b.ab_tag,
    b.first_ts,
    b.act_uid,
    b.install_day,
    d.userid
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
uid_candidates AS (
  SELECT device_id, userid AS uid, first_ts
  FROM base_raw
  WHERE userid IS NOT NULL
  UNION
  SELECT device_id, act_uid AS uid, first_ts
  FROM base_raw
  WHERE act_uid IS NOT NULL
),
old_acct_device AS (
  SELECT DISTINCT u.device_id
  FROM uid_candidates u
  INNER JOIN immdata.imt_userinfo ui
    ON ui.id = u.uid
   AND COALESCE(ui.isdeleted, 0) = 0
  WHERE ui.createtime < date_add(day, -1, u.first_ts)
),
base_devices AS (
  SELECT b.*
  FROM base_raw b
  LEFT JOIN old_acct_device oa ON oa.device_id = b.device_id
  WHERE oa.device_id IS NULL
),
wall_hit AS (
  SELECT DISTINCT g.device_id
  FROM immdata.user_behaviour g
  INNER JOIN base_devices b ON b.device_id = g.device_id
  WHERE g.created_ts >= '2026-08-20 16:00:00'
    AND g.created_ts < '2026-09-30 16:00:00'
    AND g.event_name = 'user_need_pro'
    AND g.trigger = 'freeUsageLimitModal'
    AND g.created_ts >= b.first_ts
    AND g.created_ts < add_days(b.first_ts, 7)
),
cohort_slices AS (
  SELECT
    s.slice,
    s.slice_type,
    s.cohort_no,
    s.install_start,
    s.install_end_excl,
    s.maturity_status,
    s.cohort_week_start,
    c.device_id,
    c.exp_group,
    c.d_half,
    c.install_day,
    CASE WHEN w.device_id IS NOT NULL THEN 1 ELSE 0 END AS hit_7d,
    CASE
      WHEN add_days(c.first_ts, 7) <= CAST('2026-09-30 16:00:00' AS TIMESTAMP) THEN 1
      ELSE 0
    END AS mature_7d
  FROM base_devices c
  INNER JOIN slice_specs s
    ON c.install_day >= s.install_start
   AND c.install_day < s.install_end_excl
  LEFT JOIN wall_hit w ON w.device_id = c.device_id
)
-- A/B/C/D
SELECT
  c.slice,
  c.slice_type,
  c.cohort_no,
  c.install_start,
  c.install_end_excl,
  c.maturity_status,
  c.cohort_week_start,
  c.exp_group AS group_key,
  'ABCD' AS group_kind,
  count(DISTINCT c.device_id) AS activate_uv,
  count(DISTINCT CASE WHEN c.hit_7d = 1 THEN c.device_id END) AS wall_hit_7d_uv,
  round(
    count(DISTINCT CASE WHEN c.hit_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS wall_hit_7d_pct,
  count(DISTINCT CASE WHEN c.mature_7d = 1 THEN c.device_id END) AS activate_uv_mature7d,
  count(DISTINCT CASE WHEN c.mature_7d = 1 AND c.hit_7d = 1 THEN c.device_id END) AS wall_hit_7d_uv_mature,
  round(
    count(DISTINCT CASE WHEN c.mature_7d = 1 AND c.hit_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT CASE WHEN c.mature_7d = 1 THEN c.device_id END), 0), 2
  ) AS wall_hit_7d_pct_mature
FROM cohort_slices c
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9

UNION ALL

-- I / J（D 内拆分）
SELECT
  c.slice,
  c.slice_type,
  c.cohort_no,
  c.install_start,
  c.install_end_excl,
  c.maturity_status,
  c.cohort_week_start,
  c.d_half AS group_key,
  'IJ' AS group_kind,
  count(DISTINCT c.device_id) AS activate_uv,
  count(DISTINCT CASE WHEN c.hit_7d = 1 THEN c.device_id END) AS wall_hit_7d_uv,
  round(
    count(DISTINCT CASE WHEN c.hit_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS wall_hit_7d_pct,
  count(DISTINCT CASE WHEN c.mature_7d = 1 THEN c.device_id END) AS activate_uv_mature7d,
  count(DISTINCT CASE WHEN c.mature_7d = 1 AND c.hit_7d = 1 THEN c.device_id END) AS wall_hit_7d_uv_mature,
  round(
    count(DISTINCT CASE WHEN c.mature_7d = 1 AND c.hit_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT CASE WHEN c.mature_7d = 1 THEN c.device_id END), 0), 2
  ) AS wall_hit_7d_pct_mature
FROM cohort_slices c
WHERE c.d_half IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9

ORDER BY cohort_no, group_kind, group_key
;
