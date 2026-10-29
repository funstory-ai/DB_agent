-- T043: 近 365 天曾经是 MAX 的用户 + 账号母语 + 仍在 MAX / 已退订
-- MAX 档位字段：membership='max'（不是 ordertype；ordertype=trial/subscription/code/…）
-- 含：现金付费 + 兑换码(code / onetime*)；不含试用(trial / iospay_trial / googleplay_trial)
-- 近一年：MAX 覆盖期与 [now-365d, now] 有交集
-- 仍在 MAX：MAX 覆盖 max(cover_end) >= NOW()；已退订：max(cover_end) < NOW()（未续费）

WITH max_orders AS (
  SELECT
    o.userid,
    o.createtime,
    o.subscriptionday,
    o.subscriptiontype,
    o.ordertype,
    o.amountpaid,
    DATEADD(day, COALESCE(o.subscriptionday, 0), o.createtime) AS cover_end
  FROM immdata.imt_subscriptiongoodsorder AS o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.orderstatus = 'finished'
    AND LOWER(COALESCE(o.membership, '')) = 'max'
    AND COALESCE(o.subscriptionday, 0) > 0
    AND LOWER(COALESCE(o.ordertype, '')) NOT IN ('trial', 'iospay_trial', 'googleplay_trial')
    AND (
      COALESCE(o.amountpaid, 0) > 0
      OR LOWER(COALESCE(o.ordertype, '')) = 'code'
      OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
    )
),
user_max AS (
  SELECT
    userid,
    MAX(cover_end) AS max_cover_end,
    MIN(createtime) AS first_max_ts,
    MAX(createtime) AS last_max_ts,
    COUNT(*) AS max_order_cnt,
    MAX(CASE WHEN COALESCE(amountpaid, 0) > 0 THEN 1 ELSE 0 END) AS has_paid_max,
    MAX(CASE
      WHEN LOWER(COALESCE(ordertype, '')) = 'code' THEN 1
      WHEN LOWER(COALESCE(subscriptiontype, '')) LIKE 'onetime%' THEN 1
      ELSE 0
    END) AS has_code_max
  FROM max_orders
  WHERE cover_end >= DATEADD(year, -1, NOW())
    AND createtime < NOW()
  GROUP BY userid
),
-- 最近一笔 MAX 单的类型（按 createtime）
last_type AS (
  SELECT userid, subscriptiontype AS last_max_subscriptiontype, ordertype AS last_max_ordertype
  FROM (
    SELECT
      userid,
      subscriptiontype,
      ordertype,
      ROW_NUMBER() OVER (PARTITION BY userid ORDER BY createtime DESC) AS rn
    FROM max_orders
    WHERE cover_end >= DATEADD(year, -1, NOW())
      AND createtime < NOW()
  ) t
  WHERE rn = 1
),
per_lang AS (
  SELECT
    CAST(userid AS BIGINT) AS userid,
    native_language,
    SUM(cnt) AS cnt_sum
  FROM immdata.imm_device_native_language
  WHERE userid IS NOT NULL
    AND native_language IS NOT NULL
    AND native_language <> ''
  GROUP BY CAST(userid AS BIGINT), native_language
),
user_lang AS (
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
    FROM per_lang
  ) r
  WHERE rn = 1
)
SELECT
  um.userid,
  ui.email,
  COALESCE(ul.native_language, 'unknown') AS native_language,
  CASE
    WHEN um.max_cover_end >= NOW() THEN '仍在MAX'
    ELSE '已退订'
  END AS max_status,
  CAST(um.max_cover_end AS STRING) AS max_cover_end,
  CAST(um.first_max_ts AS STRING) AS first_max_ts,
  CAST(um.last_max_ts AS STRING) AS last_max_ts,
  um.max_order_cnt,
  um.has_paid_max,
  um.has_code_max,
  lt.last_max_subscriptiontype,
  lt.last_max_ordertype
FROM user_max AS um
LEFT JOIN last_type AS lt ON lt.userid = um.userid
LEFT JOIN user_lang AS ul ON ul.userid = um.userid
LEFT JOIN immdata.imt_userinfo AS ui ON ui.id = um.userid
ORDER BY max_status, native_language, um.userid;
