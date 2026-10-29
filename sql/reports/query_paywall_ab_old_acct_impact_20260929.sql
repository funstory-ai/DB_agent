-- T018 付费墙：老号剔除影响对照（与 T045 同刀：createtime < first_ts - 1 天）
-- 基线：P034 激活 · asof=2026-09-28（同 query_paywall_ab_longterm_20260928.sql）
-- 不替代正式周表；仅评估「剔老号」对注册/付费转化的影响
-- 任务：docs/tasks/query_paywall_ab_20260821.md

WITH cohort_beh AS (
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
    END AS exp_group
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
  SELECT device_id, userid, installtime
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      d.installtime,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY
          CASE
            WHEN d.userid IS NOT NULL
             AND d.installtime >= '2026-08-20 16:00:00'
             AND d.installtime < '2026-09-28 16:00:00'
            THEN 0
            WHEN d.userid IS NOT NULL THEN 1
            ELSE 2
          END,
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
base_devices AS (
  SELECT
    b.device_id,
    b.exp_group,
    b.first_ts,
    b.act_uid,
    b.install_day,
    d.userid,
    COALESCE(
      CASE
        WHEN d.installtime >= '2026-08-20 16:00:00'
         AND d.installtime < '2026-09-28 16:00:00'
        THEN d.installtime
      END,
      b.first_ts
    ) AS anchor_ts
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
uid_candidates AS (
  SELECT device_id, userid AS uid, first_ts
  FROM base_devices
  WHERE userid IS NOT NULL
  UNION
  SELECT device_id, act_uid AS uid, first_ts
  FROM base_devices
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
orders AS (
  SELECT
    o.userid,
    o.createtime,
    CASE
      WHEN o.orderstatus = 'finished'
       AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
       AND (
         COALESCE(o.amountpaid, 0) > 0
         OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
         OR lower(COALESCE(o.ordertype, '')) = 'code'
       )
      THEN 1 ELSE 0
    END AS is_paid
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.userid IS NOT NULL
    AND o.createtime >= '2026-08-20 16:00:00'
    AND o.createtime < '2026-09-28 16:00:00'
),
old_customer_device AS (
  SELECT DISTINCT c.device_id
  FROM base_devices c
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid
   AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished'
   AND o.createtime < c.anchor_ts
  WHERE c.userid IS NOT NULL
),
device_funnel AS (
  SELECT
    c.device_id,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS paid_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS paid_7d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < '2026-09-28 16:00:00' THEN 1 ELSE 0 END) AS paid_to_asof
  FROM base_devices c
  LEFT JOIN orders o ON o.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN old_customer_device old ON old.device_id = c.device_id
  GROUP BY 1
),
scoped AS (
  SELECT
    'A_all' AS metric_scope,
    c.device_id,
    c.exp_group,
    c.install_day,
    c.userid,
    CASE WHEN oa.device_id IS NOT NULL THEN 1 ELSE 0 END AS is_old_acct
  FROM base_devices c
  LEFT JOIN old_acct_device oa ON oa.device_id = c.device_id
  UNION ALL
  SELECT
    'B_excl_old_acct',
    c.device_id,
    c.exp_group,
    c.install_day,
    c.userid,
    0
  FROM base_devices c
  LEFT JOIN old_acct_device oa ON oa.device_id = c.device_id
  WHERE oa.device_id IS NULL
)
SELECT
  s.metric_scope,
  s.exp_group,
  count(DISTINCT s.device_id) AS new_devices,
  count(DISTINCT CASE WHEN s.userid IS NOT NULL THEN s.device_id END) AS registered_devices,
  round(
    count(DISTINCT CASE WHEN s.userid IS NOT NULL THEN s.device_id END) * 100.0
      / nullif(count(DISTINCT s.device_id), 0), 2
  ) AS register_rate_pct,
  count(DISTINCT CASE WHEN f.paid_3d = 1 THEN s.device_id END) AS paid_3d,
  round(
    count(DISTINCT CASE WHEN f.paid_3d = 1 THEN s.device_id END) * 100.0
      / nullif(count(DISTINCT s.device_id), 0), 2
  ) AS paid_3d_pct,
  count(DISTINCT CASE WHEN f.paid_7d = 1 THEN s.device_id END) AS paid_7d,
  round(
    count(DISTINCT CASE WHEN f.paid_7d = 1 THEN s.device_id END) * 100.0
      / nullif(count(DISTINCT s.device_id), 0), 2
  ) AS paid_7d_pct,
  count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN s.device_id END) AS paid_to_asof,
  round(
    count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN s.device_id END) * 100.0
      / nullif(count(DISTINCT s.device_id), 0), 2
  ) AS paid_to_asof_pct,
  -- 仅 A_all 有意义：老号占激活 / 占累计付费
  count(DISTINCT CASE WHEN s.metric_scope = 'A_all' AND s.is_old_acct = 1
                      THEN s.device_id END) AS old_acct_devices,
  count(DISTINCT CASE WHEN s.metric_scope = 'A_all' AND s.is_old_acct = 1
                           AND f.paid_to_asof = 1 THEN s.device_id END) AS old_acct_paid_to_asof
FROM scoped s
LEFT JOIN device_funnel f ON f.device_id = s.device_id
GROUP BY 1, 2
ORDER BY 1, 2
;
