-- T089 促销三类用户：高频免费 / 月费 / 年费到期
-- 留档：docs/tasks/query_promo_3cohorts_20261028.md
-- 口径：
--   翻译频次窗 = 滚动30天 [NOW()-30d, NOW())，event=translate_page，双路径归因(P016: deviceinfo + ex_int_arg1)
--   高频免费 = 免费用户(当前无在效付费订阅；含从未付费与已流失) 中 近30天翻译次数 前1%
--             （需求人确认取前1%；原述“前20%”≈40万过大。改比例见下方 PCT）
--   月费用户 = 当前在效，且最新有效订单 dateperiod='monthly'
--   年费到期 = 当前在效，且最新有效订单 dateperiod='yearly'，且 cover_end ∈ (NOW, 2026-11-13 23:59:59]
--   覆盖到期 = createtime + subscriptionday 天（沿用 T033 / T008）
--   会员类型列：免费 / 月费 / 年费
-- 调参：高频比例改下方 PCT 常量（0.01=前1%，0.20=前20%）

WITH member_cover AS (
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
  SELECT userid, MAX(cover_end) AS last_cover_end
  FROM member_cover GROUP BY userid
),
active_now AS (SELECT userid FROM user_cover WHERE last_cover_end >= NOW()),
active_monthly AS (
  SELECT uc.userid, uc.last_cover_end
  FROM user_cover uc
  JOIN member_cover m ON m.userid = uc.userid AND m.cover_end = uc.last_cover_end
  WHERE m.dateperiod = 'monthly' AND uc.last_cover_end >= NOW()
),
active_yearly_expiring AS (
  SELECT uc.userid, uc.last_cover_end
  FROM user_cover uc
  JOIN member_cover m ON m.userid = uc.userid AND m.cover_end = uc.last_cover_end
  WHERE m.dateperiod = 'yearly'
    AND uc.last_cover_end > NOW()
    AND uc.last_cover_end <= TIMESTAMP '2026-11-13 23:59:59'
),
beh_30d AS (
  SELECT device_id, created_ts, ex_int_arg1
  FROM immdata.user_behaviour
  WHERE created_ts >= DATEADD(day, -30, NOW()) AND created_ts < NOW()
    AND event_name = 'translate_page'
),
dev_userid AS (
  SELECT DISTINCT deviceid, userid FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0 AND userid IS NOT NULL AND deviceid IS NOT NULL AND deviceid <> ''
),
path_device AS (
  SELECT d.userid, b.device_id, b.created_ts
  FROM beh_30d b INNER JOIN dev_userid d ON b.device_id = d.deviceid
),
path_ex AS (
  SELECT CAST(b.ex_int_arg1 AS BIGINT) AS userid, b.device_id, b.created_ts
  FROM beh_30d b
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
  SELECT userid, COUNT(*) AS c30 FROM translate_hits GROUP BY userid
),
free_base AS (
  SELECT t.userid, t.c30
  FROM translate_cnt t
  LEFT JOIN active_now a ON t.userid = a.userid
  WHERE a.userid IS NULL
),
free_ranked AS (
  SELECT userid, c30,
         ROW_NUMBER() OVER (ORDER BY c30 DESC, userid) AS rn,
         COUNT(*) OVER () AS tot
  FROM free_base
),
free_high_freq AS (
  SELECT userid, c30 FROM free_ranked WHERE rn <= CEIL(tot * 0.01)
),
email AS (
  SELECT id AS userid, email
  FROM immdata.imt_userinfo
  WHERE COALESCE(isdeleted, 0) = 0
)
SELECT
  '高频免费用户' AS cohort_label,
  CAST(fh.userid AS BIGINT) AS userid,
  e.email,
  CAST(fh.c30 AS BIGINT) AS translate_cnt_30d,
  CAST(NULL AS STRING) AS expire_time,
  '免费' AS member_type
FROM free_high_freq fh
LEFT JOIN email e ON fh.userid = e.userid

UNION ALL

SELECT
  '月费用户' AS cohort_label,
  CAST(am.userid AS BIGINT) AS userid,
  e.email,
  COALESCE(tc.c30, 0) AS translate_cnt_30d,
  CAST(am.last_cover_end AS STRING) AS expire_time,
  '月费' AS member_type
FROM active_monthly am
LEFT JOIN email e ON am.userid = e.userid
LEFT JOIN translate_cnt tc ON am.userid = tc.userid

UNION ALL

SELECT
  '年费到期用户' AS cohort_label,
  CAST(ay.userid AS BIGINT) AS userid,
  e.email,
  COALESCE(tc.c30, 0) AS translate_cnt_30d,
  CAST(ay.last_cover_end AS STRING) AS expire_time,
  '年费' AS member_type
FROM active_yearly_expiring ay
LEFT JOIN email e ON ay.userid = e.userid
LEFT JOIN translate_cnt tc ON ay.userid = tc.userid
;
