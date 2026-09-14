-- T033 繁中高频 / 即将到期月费（四类分列）
-- 留档：docs/tasks/query_zh_hant_high_freq_user_20260910.md
-- 高频窗：近90天 translate_page >300（付费/人群窗仍为90天退订·试用 / 当前免费 / 月费7天到期）
-- 性能：高频三类先扫近90天 translate_page 再挂母语/订单；月费到期单独小集合

WITH
user_native AS (
  SELECT CAST(userid AS BIGINT) AS userid, native_language, cnt_sum
  FROM (
    SELECT
      userid,
      native_language,
      SUM(COALESCE(cnt, 0)) AS cnt_sum,
      ROW_NUMBER() OVER (
        PARTITION BY userid
        ORDER BY SUM(COALESCE(cnt, 0)) DESC, native_language
      ) AS rn
    FROM immdata.imm_device_native_language
    WHERE userid IS NOT NULL
      AND CAST(userid AS STRING) <> ''
      AND native_language IS NOT NULL
      AND native_language <> ''
    GROUP BY userid, native_language
  ) t
  WHERE rn = 1
    AND LOWER(native_language) = 'zh-tw'
),
member_cover AS (
  SELECT
    userid,
    createtime,
    DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end,
    LOWER(COALESCE(dateperiod, '')) AS dateperiod
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
),
user_cover AS (
  SELECT userid, MAX(cover_end) AS last_cover_end, MAX(createtime) AS last_member_order_ts
  FROM member_cover
  GROUP BY userid
),
active_now AS (
  SELECT userid FROM user_cover WHERE last_cover_end >= NOW()
),
churn_90d AS (
  SELECT
    userid,
    last_cover_end,
    DATEDIFF(day, last_cover_end, NOW()) AS days_since_expiry
  FROM user_cover
  WHERE last_cover_end < NOW()
    AND last_cover_end >= DATEADD(day, -90, NOW())
),
trial_90d AS (
  SELECT
    userid,
    MIN(createtime) AS first_trial_ts_90d,
    MAX(createtime) AS last_trial_ts_90d,
    COUNT(*) AS trial_orders_90d
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) = 0
    AND createtime >= DATEADD(day, -90, NOW())
    AND userid IS NOT NULL
    AND (
      subscriptiongoodssnap IS NULL
      OR CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
    )
  GROUP BY userid
),
paid_or_code_ever AS (
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND (
      COALESCE(amountpaid, 0) > 0
      OR (
        COALESCE(subscriptionday, 0) > 0
        AND (
          CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
          OR LOWER(COALESCE(ordertype, '')) = 'code'
        )
      )
    )
),
trial_unpaid AS (
  SELECT t.userid, t.first_trial_ts_90d, t.last_trial_ts_90d, t.trial_orders_90d
  FROM trial_90d t
  LEFT JOIN paid_or_code_ever p ON t.userid = p.userid
  WHERE p.userid IS NULL
),
expiring_monthly_7d AS (
  SELECT
    uc.userid,
    uc.last_cover_end,
    DATEDIFF(day, NOW(), uc.last_cover_end) AS days_to_expiry
  FROM user_cover uc
  WHERE uc.last_cover_end > NOW()
    AND uc.last_cover_end <= DATEADD(day, 7, NOW())
    AND EXISTS (
      SELECT 1 FROM member_cover m
      WHERE m.userid = uc.userid
        AND m.cover_end = uc.last_cover_end
        AND m.dateperiod = 'monthly'
    )
),
-- 近90天 translate_page：设备路径 + ex_int_arg1（P016）
beh_90d AS (
  SELECT device_id, created_ts, ex_int_arg1
  FROM immdata.user_behaviour
  WHERE created_ts >= DATEADD(day, -90, NOW())
    AND created_ts < NOW()
    AND event_name = 'translate_page'
),
dev_userid AS (
  SELECT DISTINCT
    deviceid,
    userid
  FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND deviceid IS NOT NULL
    AND deviceid <> ''
),
path_device AS (
  SELECT
    d.userid,
    b.device_id,
    b.created_ts
  FROM beh_90d b
  INNER JOIN dev_userid d ON b.device_id = d.deviceid
),
path_ex AS (
  SELECT
    CAST(b.ex_int_arg1 AS BIGINT) AS userid,
    b.device_id,
    b.created_ts
  FROM beh_90d b
  WHERE b.ex_int_arg1 IS NOT NULL
    AND CAST(b.ex_int_arg1 AS STRING) <> ''
    AND CAST(b.ex_int_arg1 AS STRING) <> '0'
),
translate_hits AS (
  SELECT userid, device_id, created_ts FROM path_device
  UNION
  SELECT userid, device_id, created_ts FROM path_ex
),
translate_cnt AS (
  SELECT userid, COUNT(*) AS translate_page_90d
  FROM translate_hits
  GROUP BY userid
  HAVING COUNT(*) > 300
),
hf_zh AS (
  SELECT t.userid, t.translate_page_90d
  FROM translate_cnt t
  INNER JOIN user_native n ON t.userid = n.userid
),
email AS (
  SELECT id AS userid, email
  FROM immdata.imt_userinfo
  WHERE COALESCE(isdeleted, 0) = 0
)
SELECT
  '退订' AS cohort_label,
  h.userid,
  e.email,
  h.translate_page_90d,
  CAST(c.last_cover_end AS STRING) AS last_cover_end,
  c.days_since_expiry,
  CAST(NULL AS STRING) AS first_trial_ts_90d,
  CAST(NULL AS INT) AS days_to_expiry
FROM hf_zh h
INNER JOIN churn_90d c ON h.userid = c.userid
LEFT JOIN email e ON h.userid = e.userid

UNION ALL

SELECT
  '试用未付费',
  h.userid,
  e.email,
  h.translate_page_90d,
  CAST(NULL AS STRING),
  CAST(NULL AS INT),
  CAST(t.first_trial_ts_90d AS STRING),
  CAST(NULL AS INT)
FROM hf_zh h
INNER JOIN trial_unpaid t ON h.userid = t.userid
LEFT JOIN churn_90d c ON h.userid = c.userid
LEFT JOIN email e ON h.userid = e.userid
WHERE c.userid IS NULL

UNION ALL

SELECT
  '免费',
  h.userid,
  e.email,
  h.translate_page_90d,
  CAST(NULL AS STRING),
  CAST(NULL AS INT),
  CAST(NULL AS STRING),
  CAST(NULL AS INT)
FROM hf_zh h
LEFT JOIN active_now a ON h.userid = a.userid
LEFT JOIN churn_90d c ON h.userid = c.userid
LEFT JOIN trial_unpaid t ON h.userid = t.userid
LEFT JOIN email e ON h.userid = e.userid
WHERE a.userid IS NULL
  AND c.userid IS NULL
  AND t.userid IS NULL

UNION ALL

SELECT
  '即将到期月费',
  x.userid,
  e.email,
  CAST(NULL AS BIGINT),
  CAST(x.last_cover_end AS STRING),
  CAST(NULL AS INT),
  CAST(NULL AS STRING),
  x.days_to_expiry
FROM expiring_monthly_7d x
INNER JOIN user_native n ON x.userid = n.userid
LEFT JOIN email e ON x.userid = e.userid
;
