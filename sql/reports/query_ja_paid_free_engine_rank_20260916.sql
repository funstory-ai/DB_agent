-- T040: 日语（账号母语）付费/免费用户 translate_page 引擎排序
-- 时间窗：近 30 天 [2026-08-17, 2026-09-17)
-- 日语：P020，LOWER(native_language)='ja' OR LIKE 'ja-%'
-- 付费=当前有效会员；免费=当前非会员（含过期）；会员口径同 T008/T036
-- 引擎：user_behaviour.translation_service；次数=translate_page 事件行数
-- 归属：P016 双路径；优先 ex_int_arg1（在日语 cohort 内）

WITH ja AS (
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
    AND (LOWER(native_language) = 'ja' OR LOWER(native_language) LIKE 'ja-%')
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
),
ja_flag AS (
  SELECT
    j.userid,
    CASE WHEN c.userid IS NOT NULL THEN 'paid' ELSE 'free' END AS pay_grp
  FROM ja j
  LEFT JOIN member_cover c
    ON j.userid = c.userid
   AND c.last_cover_end >= NOW()
),
dev_map AS (
  SELECT
    device_id,
    userid,
    pay_grp
  FROM (
    SELECT
      d.deviceid AS device_id,
      f.userid,
      f.pay_grp,
      ROW_NUMBER() OVER (
        PARTITION BY d.deviceid
        ORDER BY CASE WHEN f.pay_grp = 'paid' THEN 0 ELSE 1 END, f.userid
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN ja_flag f ON CAST(d.userid AS BIGINT) = f.userid
    WHERE COALESCE(d.isdeleted, 0) = 0
      AND d.deviceid IS NOT NULL
      AND CAST(d.deviceid AS STRING) <> ''
  ) t
  WHERE rn = 1
),
evt AS (
  SELECT
    COALESCE(jf_login.pay_grp, dm.pay_grp) AS pay_grp,
    COALESCE(b.translation_service, '(null)') AS translation_service
  FROM immdata.user_behaviour b
  LEFT JOIN ja_flag jf_login ON b.ex_int_arg1 = jf_login.userid
  LEFT JOIN dev_map dm ON b.device_id = dm.device_id
  WHERE b.created_ts >= '2026-08-17'
    AND b.created_ts < '2026-09-17'
    AND b.event_name = 'translate_page'
    AND (jf_login.userid IS NOT NULL OR dm.userid IS NOT NULL)
)
SELECT
  pay_grp,
  translation_service,
  COUNT(*) AS translate_cnt,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY pay_grp), 2) AS pct_within_grp
FROM evt
GROUP BY pay_grp, translation_service
ORDER BY pay_grp, translate_cnt DESC
;
