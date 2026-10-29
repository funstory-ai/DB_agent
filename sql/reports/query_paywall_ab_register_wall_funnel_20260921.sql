-- T018：激活 cohort 触注册墙后分流（A vs B，按激活自然周）
-- 观察：created_ts < 2026-09-21 16:00:00
-- 注册墙曝光：user_need_pro + trigger=unregisteredUsageLimitModal
-- 去登录主按钮：error_modal_primary_click + ex_char_arg1=translationUsageLimitHard + ex_char_arg2=not_login
-- 次按钮：error_modal_secondary_click + 同上（8/25 后文案多为「基础翻译继续」）
-- 基础翻译继续：usage_limit_basic_continue_click（埋点未落 wall_type；限定首次注册墙后 7 天内）
-- login_intent：login_intent_open + ex_char_arg1=translation_usage_limit_register

WITH cohort AS (
  SELECT
    device_id,
    first_ts,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
    END AS exp_group,
    CASE
      WHEN install_day >= '2026-08-24' AND install_day < '2026-08-31' THEN 'w0824'
      WHEN install_day >= '2026-08-31' AND install_day < '2026-09-07' THEN 'w0831'
      WHEN install_day >= '2026-09-07' AND install_day < '2026-09-14' THEN 'w0907'
      WHEN install_day >= '2026-09-14' AND install_day < '2026-09-21' THEN 'w0914'
    END AS week_slice
  FROM (
    SELECT
      device_id,
      ab_tag,
      created_ts AS first_ts,
      CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-23 16:00:00'
      AND created_ts < '2026-09-21 16:00:00'
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
    AND install_day >= '2026-08-24'
    AND install_day < '2026-09-21'
),
cohort_f AS (
  SELECT * FROM cohort
  WHERE exp_group IN ('A', 'B') AND week_slice IS NOT NULL
),
ev AS (
  SELECT
    c.device_id,
    c.exp_group,
    c.week_slice,
    c.first_ts,
    b.event_name,
    b.trigger,
    b.ex_char_arg1,
    b.ex_char_arg2,
    b.created_ts
  FROM immdata.user_behaviour b
  INNER JOIN cohort_f c ON c.device_id = b.device_id
  WHERE b.created_ts >= '2026-08-23 16:00:00'
    AND b.created_ts < '2026-09-21 16:00:00'
    AND b.created_ts >= c.first_ts
    AND (
      (b.event_name = 'user_need_pro' AND b.trigger = 'unregisteredUsageLimitModal')
      OR (
        b.event_name IN (
          'error_modal_primary_click',
          'error_modal_secondary_click'
        )
        AND b.ex_char_arg1 = 'translationUsageLimitHard'
        AND b.ex_char_arg2 = 'not_login'
      )
      OR b.event_name = 'usage_limit_basic_continue_click'
      OR (
        b.event_name = 'login_intent_open'
        AND b.ex_char_arg1 = 'translation_usage_limit_register'
      )
    )
),
first_wall AS (
  SELECT device_id, exp_group, week_slice, MIN(created_ts) AS wall_ts
  FROM ev
  WHERE event_name = 'user_need_pro'
  GROUP BY 1, 2, 3
),
flags AS (
  SELECT
    w.device_id,
    w.exp_group,
    w.week_slice,
    MAX(CASE
      WHEN e.event_name = 'error_modal_primary_click'
       AND e.created_ts >= w.wall_ts
       AND e.created_ts < DATEADD(day, 7, w.wall_ts)
      THEN 1 ELSE 0 END) AS hit_login_cta,
    MAX(CASE
      WHEN e.event_name = 'error_modal_secondary_click'
       AND e.created_ts >= w.wall_ts
       AND e.created_ts < DATEADD(day, 7, w.wall_ts)
      THEN 1 ELSE 0 END) AS hit_secondary,
    MAX(CASE
      WHEN e.event_name = 'usage_limit_basic_continue_click'
       AND e.created_ts >= w.wall_ts
       AND e.created_ts < DATEADD(day, 7, w.wall_ts)
      THEN 1 ELSE 0 END) AS hit_basic,
    MAX(CASE
      WHEN e.event_name = 'login_intent_open'
       AND e.created_ts >= w.wall_ts
       AND e.created_ts < DATEADD(day, 7, w.wall_ts)
      THEN 1 ELSE 0 END) AS hit_login_intent
  FROM first_wall w
  LEFT JOIN ev e
    ON e.device_id = w.device_id
   AND e.event_name <> 'user_need_pro'
  GROUP BY 1, 2, 3
),
di AS (
  SELECT device_id, userid
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END, d.installtime
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort_f) c ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0
  ) t
  WHERE rn = 1
),
base AS (
  SELECT
    c.week_slice,
    c.exp_group,
    COUNT(DISTINCT c.device_id) AS activate_uv,
    COUNT(DISTINCT CASE WHEN d.userid IS NOT NULL THEN c.device_id END) AS registered_uv
  FROM cohort_f c
  LEFT JOIN di d ON d.device_id = c.device_id
  GROUP BY 1, 2
),
wall_sum AS (
  SELECT
    f.week_slice,
    f.exp_group,
    COUNT(*) AS wall_uv,
    SUM(hit_login_cta) AS login_cta_uv,
    SUM(hit_secondary) AS secondary_uv,
    SUM(hit_basic) AS basic_uv,
    SUM(hit_login_intent) AS login_intent_uv,
    SUM(CASE WHEN hit_basic = 1 OR hit_secondary = 1 THEN 1 ELSE 0 END) AS bypass_path_uv,
    COUNT(DISTINCT CASE WHEN d.userid IS NOT NULL THEN f.device_id END) AS wall_then_registered_uv
  FROM flags f
  LEFT JOIN di d ON d.device_id = f.device_id
  GROUP BY 1, 2
)
SELECT
  b.week_slice,
  b.exp_group,
  b.activate_uv,
  b.registered_uv,
  ROUND(100.0 * b.registered_uv / NULLIF(b.activate_uv, 0), 2) AS register_rate_pct,
  COALESCE(w.wall_uv, 0) AS wall_uv,
  ROUND(100.0 * COALESCE(w.wall_uv, 0) / NULLIF(b.activate_uv, 0), 2) AS wall_rate_pct,
  COALESCE(w.login_cta_uv, 0) AS login_cta_uv,
  ROUND(100.0 * COALESCE(w.login_cta_uv, 0) / NULLIF(w.wall_uv, 0), 2) AS login_cta_among_wall_pct,
  COALESCE(w.login_intent_uv, 0) AS login_intent_uv,
  COALESCE(w.secondary_uv, 0) AS secondary_uv,
  ROUND(100.0 * COALESCE(w.secondary_uv, 0) / NULLIF(w.wall_uv, 0), 2) AS secondary_among_wall_pct,
  COALESCE(w.basic_uv, 0) AS basic_uv,
  ROUND(100.0 * COALESCE(w.basic_uv, 0) / NULLIF(w.wall_uv, 0), 2) AS basic_among_wall_pct,
  COALESCE(w.bypass_path_uv, 0) AS bypass_path_uv,
  ROUND(100.0 * COALESCE(w.bypass_path_uv, 0) / NULLIF(w.wall_uv, 0), 2) AS bypass_among_wall_pct,
  COALESCE(w.wall_then_registered_uv, 0) AS wall_then_registered_uv,
  ROUND(100.0 * COALESCE(w.wall_then_registered_uv, 0) / NULLIF(w.wall_uv, 0), 2) AS wall_to_registered_pct
FROM base b
LEFT JOIN wall_sum w
  ON w.week_slice = b.week_slice AND w.exp_group = b.exp_group
ORDER BY b.week_slice, b.exp_group
;
