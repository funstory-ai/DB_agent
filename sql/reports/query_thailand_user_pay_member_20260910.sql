-- T036: 泰语账号总量 / 历史现金付费 / 当前有效会员
-- 泰语：账号母语 P020，LOWER(native_language)='th' 或 LIKE 'th-%'
-- 历史付费：finished 且 amountpaid>0（P013）
-- 有效会员：finished + subscriptionday>0 + (amountpaid>0 | onetime* | code)，MAX(cover_end)>=NOW()（同 T008）

WITH th_acct AS (
  SELECT CAST(userid AS BIGINT) AS userid
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
    AND (LOWER(native_language) = 'th' OR LOWER(native_language) LIKE 'th-%')
),
th_devices AS (
  SELECT COUNT(DISTINCT device_id) AS device_cnt
  FROM immdata.imm_device_native_language
  WHERE device_id IS NOT NULL AND CAST(device_id AS STRING) <> ''
    AND native_language IS NOT NULL AND native_language <> ''
    AND (LOWER(native_language) = 'th' OR LOWER(native_language) LIKE 'th-%')
),
paid_orders AS (
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND COALESCE(amountpaid, 0) > 0
),
member_cover AS (
  SELECT
    userid,
    MAX(DATEADD(day, COALESCE(subscriptionday, 0), createtime)) AS last_cover_end
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
  GROUP BY userid
)
SELECT
  (SELECT COUNT(*) FROM th_acct) AS thai_userid_cnt,
  (SELECT device_cnt FROM th_devices) AS thai_device_cnt,
  (SELECT COUNT(*) FROM th_acct a INNER JOIN paid_orders p ON a.userid = p.userid) AS thai_ever_paid_userid,
  (
    SELECT COUNT(*)
    FROM th_acct a
    INNER JOIN member_cover c ON a.userid = c.userid
    WHERE c.last_cover_end >= NOW()
  ) AS thai_active_member_userid
;
