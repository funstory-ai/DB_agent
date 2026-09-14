-- 月末有效会员人数（与财务 MRR 截面同边界）
-- 会员单：finished + subscriptionday>0 + (amountpaid>0 | onetime* | ordertype=code)
-- 截面：createtime < as_of AND createtime+subscriptionday >= as_of；userid 去重
-- 范围：月末 2024-05 ～ 2026-06（as_of = 2024-06-01 … 2026-07-01）
-- 注意：cover 按单笔 createtime+day，不做跨单累加；到期前续费/code 堆叠可能导致与产品侧不一致
-- 交付：scripts/export_month_end_active_members.py → output/task7_month_end_active_members_*.xlsx

WITH bounds AS (
  SELECT DATEADD(month, n, CAST('2024-06-01' AS DATE)) AS as_of
  FROM (
    SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
    UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14
    UNION ALL SELECT 15 UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
    UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24
    UNION ALL SELECT 25
  ) t
),
member_orders AS (
  SELECT
    userid,
    createtime,
    DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND COALESCE(subscriptionday, 0) > 0
    AND (
      COALESCE(amountpaid, 0) > 0
      OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
      OR LOWER(COALESCE(ordertype, '')) = 'code'
    )
)
SELECT
  DATEADD(day, -1, b.as_of) AS month_end,
  b.as_of AS as_of_exclusive,
  COUNT(DISTINCT m.userid) AS active_member_userid_cnt
FROM bounds b
INNER JOIN member_orders m
  ON m.createtime < b.as_of
 AND m.cover_end >= b.as_of
GROUP BY b.as_of
ORDER BY b.as_of;
