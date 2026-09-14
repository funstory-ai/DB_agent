-- T018 付费墙 A/B/C/D：按自然周（周一至周日）切同期群，同时保留总体汇总
-- 主表：immdata.user_behaviour / imt_deviceinfo / imt_checkoutsession / imt_subscriptiongoodsorder
-- 口径：
--   1) 分母为埋点侧新装 device；deviceinfo 仅 LEFT JOIN 补 userid（P031）
--   2) anchor_ts 优先采用观察窗内 installtime，否则采用首条 translate_page
--   3) 付费沿用 T018 v3：finished，排除 iospay_renew；现金/onetime/code 计付费
--   4) anchor 前已有 finished 订单的 device 视为老客，其付费不计
--   5) paid_to_asof = [anchor_ts, 观察截止) 内累计付费，不限制 3d/7d
--   6) 北京 2026-09-04 当日右开边界 = UTC 2026-09-04 16:00:00
-- 已知坑：P002/P003/P004/P013/P017/P031/P032/P033

WITH slice_specs AS (
  SELECT
    'natural_week_0821_0823_partial' AS slice,
    'weekly' AS slice_type,
    1 AS cohort_no,
    '2026-08-21' AS install_start,
    '2026-08-24' AS install_end_excl,
    '首周不满（3天）' AS maturity_status
  UNION ALL
  SELECT
    'natural_week_0824_0830' AS slice,
    'weekly' AS slice_type,
    2 AS cohort_no,
    '2026-08-24' AS install_start,
    '2026-08-31' AS install_end_excl,
    '完整自然周（7天）' AS maturity_status
  UNION ALL
  SELECT
    'natural_week_0831_0904_partial' AS slice,
    'weekly' AS slice_type,
    3 AS cohort_no,
    '2026-08-31' AS install_start,
    '2026-09-05' AS install_end_excl,
    '本周不满（5天）' AS maturity_status
  UNION ALL
  SELECT
    'aggregate_0821_0904' AS slice,
    'aggregate' AS slice_type,
    99 AS cohort_no,
    '2026-08-21' AS install_start,
    '2026-09-05' AS install_end_excl,
    '混合成熟度' AS maturity_status
),
cohort_beh AS (
  SELECT
    device_id,
    ab_tag,
    first_ts,
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
      install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-20 16:00:00'
      AND created_ts < '2026-09-04 16:00:00'
      AND event_name = 'translate_page'
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
      AND install_day >= '2026-08-21'
      AND install_day < '2026-09-05'
  ) x
  WHERE rn = 1
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
             AND d.installtime < '2026-09-04 16:00:00'
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
    b.ab_tag,
    b.first_ts,
    b.install_day,
    d.userid,
    COALESCE(
      CASE
        WHEN d.installtime >= '2026-08-20 16:00:00'
         AND d.installtime < '2026-09-04 16:00:00'
        THEN d.installtime
      END,
      b.first_ts
    ) AS anchor_ts
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= '2026-08-20 16:00:00'
    AND createtime < '2026-09-04 16:00:00'
),
orders AS (
  SELECT
    o.userid,
    o.createtime,
    CASE
      WHEN o.orderstatus = 'finished'
       AND COALESCE(o.amountpaid, 0) = 0
       AND COALESCE(CAST(o.subscriptiongoodssnap AS STRING), '')
           NOT LIKE '%"SubscriptionType":"onetime%'
       AND lower(COALESCE(o.ordertype, '')) <> 'code'
      THEN 1 ELSE 0
    END AS is_trial,
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
    AND o.createtime < '2026-09-04 16:00:00'
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
    max(CASE WHEN ck.createtime >= c.anchor_ts
              AND ck.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS checkout_3d,
    max(CASE WHEN o.is_trial = 1
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS trial_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS paid_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS paid_7d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < '2026-09-04 16:00:00' THEN 1 ELSE 0 END) AS paid_to_asof
  FROM base_devices c
  LEFT JOIN checkout ck ON ck.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN orders o ON o.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN old_customer_device old ON old.device_id = c.device_id
  GROUP BY 1
),
cohort_slices AS (
  SELECT
    s.slice,
    s.slice_type,
    s.cohort_no,
    s.install_start,
    s.install_end_excl,
    s.maturity_status,
    c.device_id,
    c.userid,
    c.exp_group
  FROM base_devices c
  INNER JOIN slice_specs s
    ON c.install_day >= s.install_start
   AND c.install_day < s.install_end_excl
)
SELECT
  c.slice,
  c.slice_type,
  c.cohort_no,
  c.install_start,
  c.install_end_excl,
  c.maturity_status,
  c.exp_group,
  count(DISTINCT c.device_id) AS new_devices,
  count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) AS registered_devices,
  round(
    count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS register_rate_pct,
  count(DISTINCT CASE WHEN f.checkout_3d = 1 THEN c.device_id END) AS checkout_3d,
  round(
    count(DISTINCT CASE WHEN f.checkout_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS checkout_3d_pct,
  count(DISTINCT CASE WHEN f.trial_3d = 1 THEN c.device_id END) AS trial_3d,
  round(
    count(DISTINCT CASE WHEN f.trial_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS trial_3d_pct,
  count(DISTINCT CASE WHEN f.paid_3d = 1 THEN c.device_id END) AS paid_3d,
  round(
    count(DISTINCT CASE WHEN f.paid_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_3d_pct,
  count(DISTINCT CASE WHEN f.paid_7d = 1 THEN c.device_id END) AS paid_7d,
  round(
    count(DISTINCT CASE WHEN f.paid_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_7d_pct,
  count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN c.device_id END) AS paid_to_asof,
  round(
    count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_to_asof_pct
FROM cohort_slices c
LEFT JOIN device_funnel f ON f.device_id = c.device_id
GROUP BY 1, 2, 3, 4, 5, 6, 7
ORDER BY c.cohort_no, c.exp_group;
