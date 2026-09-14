-- T022：新用户 N 日「首单付费」转化；验证 iOS 付费命名；量化老客二次付费虚高
-- 任务：docs/tasks/anomaly_new_user_cvr_renew_mix_20260831.md
-- 注意：iospay 付费单（含首单）均为 iospay_renew，不可用 renew 剔老客

-- §1 iOS 付费是否都叫 renew（近窗）
SELECT ordertype, count(*) AS orders, count(DISTINCT userid) AS users
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted, 0) = 0
  AND orderstatus = 'finished'
  AND COALESCE(amountpaid, 0) > 0
  AND createtime >= '2026-08-01' AND createtime < '2026-09-01'
  AND lower(COALESCE(ordertype, '')) LIKE 'iospay%'
GROUP BY 1
ORDER BY orders DESC;

-- §2 有过 iospay 现金的用户：第一笔是否也是 renew
WITH ios_cash AS (
  SELECT
    userid, ordertype,
    row_number() OVER (PARTITION BY userid ORDER BY createtime, id) AS rn
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) > 0
    AND lower(COALESCE(ordertype, '')) LIKE 'iospay%'
    AND createtime >= '2025-01-01'
)
SELECT
  count(*) AS users_with_ios_cash,
  count_if(lower(COALESCE(ordertype, '')) = 'iospay_renew') AS first_is_renew,
  round(count_if(lower(COALESCE(ordertype, '')) = 'iospay_renew') * 100.0 / count(*), 1) AS pct_first_renew
FROM ios_cash
WHERE rn = 1;

-- §3 首单付费 CVR vs 窗内任意付费（3 日）+ 虚高人数
WITH cohort AS (
  SELECT userid, min(installtime) AS first_install
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
lifetime_first_cash AS (
  SELECT userid, min(createtime) AS first_cash_ts
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) > 0
  GROUP BY 1
),
window_ranked AS (
  SELECT
    c.userid, c.first_install, o.createtime AS cash_ts, o.ordertype,
    row_number() OVER (PARTITION BY c.userid ORDER BY o.createtime, o.id) AS rn
  FROM cohort c
  JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0
   AND o.createtime >= c.first_install
   AND o.createtime < date_add(day, 3, c.first_install)
),
window_cash AS (
  SELECT * FROM window_ranked WHERE rn = 1
)
SELECT
  (SELECT count(*) FROM cohort) AS denom,
  count(*) AS naive_any_cash_in_3d,
  round(count(*) * 100.0 / (SELECT count(*) FROM cohort), 3) AS naive_cvr_pct,
  count_if(
    lf.first_cash_ts >= w.first_install
    AND lf.first_cash_ts < date_add(day, 3, w.first_install)
  ) AS true_firstpay_in_3d,
  round(count_if(
    lf.first_cash_ts >= w.first_install
    AND lf.first_cash_ts < date_add(day, 3, w.first_install)
  ) * 100.0 / (SELECT count(*) FROM cohort), 3) AS true_firstpay_cvr_pct,
  count_if(lf.first_cash_ts < w.first_install) AS inflated_prior_cash,
  round(count_if(lf.first_cash_ts < w.first_install) * 100.0 / nullif(count(*), 0), 1)
    AS inflated_pct_of_naive
FROM window_cash w
LEFT JOIN lifetime_first_cash lf ON lf.userid = w.userid;

-- §4 真首单渠道分布（说明并非「全是 iOS 问题」）
WITH cohort AS (
  SELECT userid, min(installtime) AS first_install
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
lifetime_ranked AS (
  SELECT userid, createtime, ordertype,
    row_number() OVER (PARTITION BY userid ORDER BY createtime, id) AS rn
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) > 0
),
lifetime_first_cash AS (
  SELECT userid, createtime AS first_cash_ts, ordertype AS first_otype
  FROM lifetime_ranked WHERE rn = 1
)
SELECT
  CASE
    WHEN lower(COALESCE(lf.first_otype, '')) LIKE 'iospay%' THEN 'iospay_*'
    WHEN lower(COALESCE(lf.first_otype, '')) = 'googleplay' THEN 'googleplay'
    WHEN lower(COALESCE(lf.first_otype, '')) = 'subscription' THEN 'subscription'
    WHEN lower(COALESCE(lf.first_otype, '')) = 'normal' THEN 'normal'
    ELSE coalesce(lf.first_otype, '(null)')
  END AS firstpay_channel,
  count(*) AS users
FROM cohort c
JOIN lifetime_first_cash lf ON lf.userid = c.userid
WHERE lf.first_cash_ts >= c.first_install
  AND lf.first_cash_ts < date_add(day, 3, c.first_install)
GROUP BY 1
ORDER BY users DESC;
