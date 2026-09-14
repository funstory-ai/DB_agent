-- T026: 月末有效会员（task7）vs 按语言有效会员 对账
-- 截面：2026-06 月末；as_of = 2026-07-01；month_end = 2026-06-30
-- 只读。详见 docs/tasks/query_active_member_vs_lang_gap_20260901.md

WITH bounds AS (
  SELECT CAST('2026-07-01' AS DATE) AS as_of, CAST('2026-06-30' AS DATE) AS month_end
),
member_orders AS (
  SELECT
    userid,
    createtime,
    DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end,
    COALESCE(amountpaid, 0) AS amountpaid,
    CASE
      WHEN CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%' THEN 1
      WHEN LOWER(COALESCE(ordertype, '')) = 'code' THEN 1
      ELSE 0
    END AS is_ecom
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND COALESCE(subscriptionday, 0) > 0
),
task7_active AS (
  SELECT
    m.userid,
    max(CASE WHEN m.amountpaid > 0 OR m.is_ecom = 1 THEN 1 ELSE 0 END) AS is_member,
    max(CASE WHEN m.amountpaid > 0 THEN 1 ELSE 0 END) AS is_cash,
    max(m.is_ecom) AS has_ecom
  FROM member_orders m
  CROSS JOIN bounds b
  WHERE m.createtime < b.as_of
    AND m.cover_end >= b.as_of
    AND (m.amountpaid > 0 OR m.is_ecom = 1)
  GROUP BY m.userid
),
by_lang AS (
  SELECT DISTINCT t1.userid, t0.target_language
  FROM (
    SELECT device_id, target_language,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts DESC) AS rn
    FROM immdata.imt_device_regional_test
    WHERE target_language IN ('zh-CN','zh-TW','ko','en','ja','ar','fr','de','es')
  ) t0
  INNER JOIN immdata.imt_deviceinfo t1
    ON t0.device_id = t1.deviceid AND COALESCE(t1.isdeleted, 0) = 0
  INNER JOIN immdata.imt_subscriptiongoodsorder tt2
    ON t1.userid = tt2.userid
   AND COALESCE(tt2.isdeleted, 0) = 0
   AND tt2.orderstatus = 'finished'
   AND COALESCE(tt2.amountpaid, 0) > 0
  CROSS JOIN bounds b
  WHERE t0.rn = 1
    AND t1.userid IS NOT NULL
    AND DATEADD(day, COALESCE(tt2.subscriptionday, 0), tt2.createtime) >= b.month_end
    AND tt2.createtime <= b.as_of
)
SELECT
  (SELECT count(*) FROM task7_active) AS task7_total,
  (SELECT count(*) FROM task7_active WHERE is_cash = 1) AS task7_cash,
  (SELECT count(*) FROM task7_active WHERE is_cash = 0 AND has_ecom = 1) AS ecom_only,
  (SELECT count(DISTINCT userid) FROM by_lang) AS by_lang_distinct_userid,
  (SELECT sum(c) FROM (
      SELECT target_language, count(DISTINCT userid) AS c FROM by_lang GROUP BY 1
    ) s) AS by_lang_sum_group_by,
  (SELECT count(*) FROM task7_active t
    WHERE t.is_cash = 1
      AND NOT EXISTS (SELECT 1 FROM by_lang b WHERE b.userid = t.userid)
  ) AS cash_not_in_lang_path;
