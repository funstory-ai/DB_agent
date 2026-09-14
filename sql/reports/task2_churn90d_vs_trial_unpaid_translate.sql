-- 任务二定稿 SQL（与 scripts/export_task2_churn_vs_trial.py 一致）
-- 留档：docs/tasks/query_churn30d_vs_trial_unpaid_20260814.md
-- 口径：流失A（会员覆盖含 onetime*，P024）+ 试用未付费；P013/P016–P020/P024

WITH trial_90d AS (
  SELECT userid,
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
      OR CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%\"SubscriptionType\":\"onetime%'
    )
  GROUP BY userid
),
paid_ever AS (
  -- 历史上有过现金付费 或 onetime* 兑换码 → 不算「试用未付费」
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND (
      COALESCE(amountpaid, 0) > 0
      OR (
        COALESCE(subscriptionday, 0) > 0
        AND CAST(subscriptiongoodssnap AS STRING) LIKE '%\"SubscriptionType\":\"onetime%'
      )
    )
),
trial_unpaid AS (
  SELECT t.*
  FROM trial_90d t
  LEFT JOIN paid_ever p ON t.userid = p.userid
  WHERE p.userid IS NULL
),
-- 会员时长覆盖：含现金付费与 onetime* 兑换码（P024）；排除额度包与真试用
member_cover AS (
  SELECT
    userid,
    createtime,
    DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end,
    CASE WHEN COALESCE(amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_cash_paid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND COALESCE(subscriptionday, 0) > 0
    AND (
      COALESCE(amountpaid, 0) > 0
      OR CAST(subscriptiongoodssnap AS STRING) LIKE '%\"SubscriptionType\":\"onetime%'
    )
),
user_cover AS (
  SELECT
    userid,
    MAX(cover_end) AS last_cover_end,
    MAX(createtime) AS last_member_order_ts,
    SUM(is_cash_paid) AS paid_time_orders
  FROM member_cover
  GROUP BY userid
),
churn_90d AS (
  SELECT
    userid,
    last_cover_end,
    last_member_order_ts,
    paid_time_orders,
    DATEDIFF(day, last_cover_end, NOW()) AS days_unpaid_since_expiry
  FROM user_cover
  WHERE last_cover_end < NOW()
    AND last_cover_end >= DATEADD(day, -90, NOW())
),
cohort AS (
  SELECT
    '流失会员' AS cohort_label,
    c.userid,
    c.last_cover_end,
    c.last_member_order_ts,
    c.paid_time_orders,
    c.days_unpaid_since_expiry,
    CAST(NULL AS TIMESTAMP) AS first_trial_ts_90d,
    CAST(NULL AS TIMESTAMP) AS last_trial_ts_90d,
    CAST(NULL AS BIGINT) AS trial_orders_90d
  FROM churn_90d c
  UNION ALL
  SELECT
    '试用未付费' AS cohort_label,
    t.userid,
    CAST(NULL AS TIMESTAMP) AS last_cover_end,
    CAST(NULL AS TIMESTAMP) AS last_member_order_ts,
    CAST(NULL AS BIGINT) AS paid_time_orders,
    CAST(NULL AS INT) AS days_unpaid_since_expiry,
    t.first_trial_ts_90d,
    t.last_trial_ts_90d,
    t.trial_orders_90d
  FROM trial_unpaid t
),
device_user_cnt AS (
  SELECT deviceid, COUNT(DISTINCT userid) AS users_on_device
  FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND deviceid IS NOT NULL
    AND deviceid <> ''
  GROUP BY deviceid
),
user_devices AS (
  SELECT DISTINCT c.userid, d.deviceid
  FROM cohort c
  INNER JOIN immdata.imt_deviceinfo d
    ON c.userid = d.userid
   AND COALESCE(d.isdeleted, 0) = 0
   AND d.deviceid IS NOT NULL
   AND d.deviceid <> ''
),
user_device_stats AS (
  SELECT
    ud.userid,
    COUNT(DISTINCT ud.deviceid) AS device_cnt,
    COUNT(DISTINCT CASE WHEN duc.users_on_device > 1 THEN ud.deviceid END) AS shared_device_cnt,
    MAX(duc.users_on_device) AS max_users_on_any_device,
    MAX(CASE WHEN ud.deviceid = 'LK8j8qPLDa3gUgujz9Yt7RtmltkXP0bD' THEN 1 ELSE 0 END) AS has_device_LK8
  FROM user_devices ud
  INNER JOIN device_user_cnt duc ON ud.deviceid = duc.deviceid
  GROUP BY ud.userid
),
devices AS (
  SELECT DISTINCT deviceid FROM user_devices
),
beh AS (
  SELECT
    b.device_id,
    SUM(CASE WHEN b.event_name = 'translate_page' AND b.page_type = 'html' THEN 1 ELSE 0 END) AS web_cnt,
    SUM(CASE WHEN b.event_name = 'translate_video_subtitle' THEN 1 ELSE 0 END) AS video_cnt,
    SUM(CASE WHEN b.event_name IN ('translate_image', 'translate_image_client') THEN 1 ELSE 0 END) AS image_cnt,
    SUM(CASE WHEN b.event_name = 'translate_manga' THEN 1 ELSE 0 END) AS manga_cnt,
    SUM(CASE WHEN b.event_name = 'translate_page' AND b.page_type IN ('pdfReader', 'pdfProReader') THEN 1 ELSE 0 END) AS pdf_cnt
  FROM immdata.user_behaviour b
  INNER JOIN devices d ON b.device_id = d.deviceid
  WHERE b.created_ts >= DATEADD(day, -90, NOW())
    AND b.created_ts < NOW()
    AND (
      (b.event_name = 'translate_page' AND b.page_type IN ('html', 'pdfReader', 'pdfProReader'))
      OR b.event_name IN (
        'translate_video_subtitle',
        'translate_image',
        'translate_image_client',
        'translate_manga'
      )
    )
  GROUP BY b.device_id
),
user_agg AS (
  SELECT
    ud.userid,
    SUM(COALESCE(beh.web_cnt, 0)) AS web_translate_cnt,
    SUM(COALESCE(beh.video_cnt, 0)) AS video_translate_cnt,
    SUM(COALESCE(beh.image_cnt, 0)) AS image_translate_cnt,
    SUM(COALESCE(beh.manga_cnt, 0)) AS manga_translate_cnt,
    SUM(COALESCE(beh.pdf_cnt, 0)) AS pdf_translate_cnt
  FROM user_devices ud
  LEFT JOIN beh ON ud.deviceid = beh.device_id
  GROUP BY ud.userid
),
user_native_lang AS (
  SELECT
    ud.userid,
    nl.native_language,
    SUM(COALESCE(nl.cnt, 0)) AS cnt_sum
  FROM user_devices ud
  INNER JOIN immdata.imm_device_native_language nl
    ON ud.deviceid = nl.device_id
  WHERE nl.native_language IS NOT NULL
    AND nl.native_language <> ''
  GROUP BY ud.userid, nl.native_language
),
user_native_top AS (
  SELECT userid, native_language, cnt_sum
  FROM (
    SELECT
      userid,
      native_language,
      cnt_sum,
      ROW_NUMBER() OVER (
        PARTITION BY userid
        ORDER BY cnt_sum DESC, native_language
      ) AS rn
    FROM user_native_lang
  ) t
  WHERE rn = 1
)
SELECT
  c.cohort_label,
  c.userid,
  u.email,
  nt.native_language AS account_native_language,
  COALESCE(nt.cnt_sum, 0) AS native_language_cnt_sum,
  c.last_cover_end,
  c.last_member_order_ts,
  c.paid_time_orders,
  c.days_unpaid_since_expiry,
  c.first_trial_ts_90d,
  c.last_trial_ts_90d,
  c.trial_orders_90d,
  COALESCE(ds.device_cnt, 0) AS device_cnt,
  COALESCE(ds.shared_device_cnt, 0) AS shared_device_cnt,
  COALESCE(ds.max_users_on_any_device, 0) AS max_users_on_any_device,
  COALESCE(ds.has_device_LK8, 0) AS has_device_LK8,
  CASE WHEN ds.userid IS NULL THEN 0 ELSE 1 END AS has_deviceinfo,
  COALESCE(ua.web_translate_cnt, 0) AS web_translate_cnt,
  COALESCE(ua.video_translate_cnt, 0) AS video_translate_cnt,
  COALESCE(ua.image_translate_cnt, 0) AS image_translate_cnt,
  COALESCE(ua.manga_translate_cnt, 0) AS manga_translate_cnt,
  COALESCE(ua.pdf_translate_cnt, 0) AS pdf_translate_cnt,
  COALESCE(ua.web_translate_cnt, 0)
    + COALESCE(ua.video_translate_cnt, 0)
    + COALESCE(ua.image_translate_cnt, 0)
    + COALESCE(ua.manga_translate_cnt, 0)
    + COALESCE(ua.pdf_translate_cnt, 0) AS translate_total_cnt
FROM cohort c
LEFT JOIN immdata.imt_userinfo u
  ON c.userid = u.id AND COALESCE(u.isdeleted, 0) = 0
LEFT JOIN user_native_top nt ON c.userid = nt.userid
LEFT JOIN user_device_stats ds ON c.userid = ds.userid
LEFT JOIN user_agg ua ON c.userid = ua.userid
ORDER BY c.cohort_label, translate_total_cnt DESC, c.userid;
