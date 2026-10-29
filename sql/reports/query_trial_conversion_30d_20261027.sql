-- T088 近一个月「首次试用 → 累计付费」转化率（汇总数字交付）
-- 口径（已与用户确认）：
--   分母：近30天(NOW()-30d ~ NOW())内「首次」产生试用单的账号(userid)；此前无试用记录(MIN(createtime)在窗内即保证无更早试用)
--   分子：该账号在「首次试用单之后(asof当前)」任意一次付费单即算转化，累计、不限时
--   主体：userid 全量（含老用户）；匿名单(userid为空)剔除；不剔老号(P039 不适用)
--   试用(P013)：finished 且 amountpaid=0 且不是兑换码(排除 ordertype='code' 与 onetime* snap)
--   付费(P013)：finished 且 (amountpaid>0 或 兑换码：subscriptionday>0 且 onetime*/code)
-- 注：近期开启试用的 cohort 未到转化期，整体率会偏低；第 W* 周拆行暴露成熟度。
WITH trial_orders AS (
  SELECT userid, createtime
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) = 0
    AND NOT (
      LOWER(COALESCE(ordertype, '')) = 'code'
      OR CAST(COALESCE(subscriptiongoodssnap, '') AS STRING) LIKE '%"SubscriptionType":"onetime%'
    )
    AND userid IS NOT NULL
),
first_trial AS (
  SELECT userid, MIN(createtime) AS first_trial_ts
  FROM trial_orders
  GROUP BY userid
),
cohort AS (
  SELECT userid, first_trial_ts
  FROM first_trial
  WHERE first_trial_ts >= DATEADD(day, -30, NOW())
    AND first_trial_ts <  NOW()
),
paid_orders AS (
  SELECT DISTINCT userid, createtime
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND (
      COALESCE(amountpaid, 0) > 0
      OR (
        COALESCE(subscriptionday, 0) > 0
        AND (
          CAST(COALESCE(subscriptiongoodssnap, '') AS STRING) LIKE '%"SubscriptionType":"onetime%'
          OR LOWER(COALESCE(ordertype, '')) = 'code'
        )
      )
    )
    AND createtime >= DATEADD(day, -30, NOW())   -- 转化要求 paid>=首试>=win_start，故扫描窗足够
),
converted AS (
  SELECT DISTINCT c.userid
  FROM cohort c
  JOIN paid_orders p
    ON p.userid = c.userid
   AND p.createtime >= c.first_trial_ts
),
seg AS (
  SELECT
    c.userid,
    c.first_trial_ts,
    CASE WHEN conv.userid IS NOT NULL THEN 1 ELSE 0 END AS is_conv
  FROM cohort c
  LEFT JOIN converted conv ON c.userid = conv.userid
)
SELECT
  'ALL'                                             AS segment,
  COUNT(*)                                          AS trial_users,
  SUM(is_conv)                                      AS converted_users,
  ROUND(SUM(is_conv) * 1.0 / NULLIF(COUNT(*), 0), 4) AS conversion_rate
FROM seg

UNION ALL

SELECT
  'W' || CAST(FLOOR(DATEDIFF('day', DATEADD(day, -30, NOW()), first_trial_ts) / 7) AS STRING) AS segment,
  COUNT(*)                                          AS trial_users,
  SUM(is_conv)                                      AS converted_users,
  ROUND(SUM(is_conv) * 1.0 / NULLIF(COUNT(*), 0), 4) AS conversion_rate
FROM seg
GROUP BY 1
ORDER BY segment
;
