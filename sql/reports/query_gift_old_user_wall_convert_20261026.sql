-- T085 扩量前已在用的用户：北京 2026-10-10 00:00 之前注册，扩量后到订单水位有翻译
-- 对照上一版含会员表（query_gift_old_user_wall_convert_20261023）。两边字母都出现的人排除。
-- asof：订单 createtime < 2026-10-25 17:04:36（北京 2026-10-26 01:04）

WITH ev AS (
  SELECT
    TRY_CAST(ex_int_arg1 AS BIGINT) AS uid,
    lower(trim(ab_tag)) AS ab,
    created_ts,
    event_name,
    trigger
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-10-09 16:00:00'
    AND created_ts < '2026-10-25 17:04:36'
    AND ex_int_arg1 IS NOT NULL
    AND ab_tag IS NOT NULL
    AND length(trim(ab_tag)) = 1
    AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
    AND (
      event_name = 'translate_page'
      OR (event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal')
      OR event_name = 'login_ai_quota_gift_exhausted_modal_show'
    )
    AND (
      TRY_CAST(split_part(version, '.', 1) AS INT) > 1
      OR (
        TRY_CAST(split_part(version, '.', 1) AS INT) = 1
        AND (
          TRY_CAST(split_part(version, '.', 2) AS INT) > 33
          OR (
            TRY_CAST(split_part(version, '.', 2) AS INT) = 33
            AND TRY_CAST(split_part(version, '.', 3) AS INT) >= 2
          )
        )
      )
    )
),
tagged AS (
  SELECT
    uid,
    max(CASE WHEN event_name = 'translate_page' AND ab BETWEEN 'a' AND 'e' THEN 1 ELSE 0 END) AS old_tr,
    max(CASE WHEN event_name = 'translate_page' AND ab BETWEEN 'f' AND 'j' THEN 1 ELSE 0 END) AS new_tr,
    min(CASE
          WHEN event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal'
           AND ab BETWEEN 'a' AND 'e' THEN created_ts
        END) AS old_wall_ts,
    min(CASE
          WHEN event_name = 'login_ai_quota_gift_exhausted_modal_show'
           AND ab BETWEEN 'f' AND 'j' THEN created_ts
        END) AS new_wall_ts
  FROM ev
  WHERE uid IS NOT NULL
  GROUP BY uid
),
users AS (
  SELECT
    t.uid,
    CASE WHEN t.old_tr = 1 THEN '老墙 a–e' ELSE '新墙 f–j' END AS grp,
    CASE WHEN t.old_tr = 1 THEN t.old_wall_ts ELSE t.new_wall_ts END AS wall_ts
  FROM tagged t
  INNER JOIN immdata.imt_userinfo ui
    ON ui.id = t.uid
   AND COALESCE(ui.isdeleted, 0) = 0
  WHERE ui.createtime < '2026-10-09 16:00:00'
    AND (t.old_tr = 1 OR t.new_tr = 1)
    AND NOT (t.old_tr = 1 AND t.new_tr = 1)
),
ord AS (
  SELECT o.userid, o.createtime
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.orderstatus = 'finished'
    AND o.userid IS NOT NULL
    AND o.createtime >= '2026-10-09 16:00:00'
    AND o.createtime < '2026-10-25 17:04:36'
    AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
    AND (
      COALESCE(o.amountpaid, 0) > 0
      OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
      OR lower(COALESCE(o.ordertype, '')) = 'code'
    )
)
SELECT
  u.grp,
  count(*) AS translated,
  count(CASE WHEN u.wall_ts IS NOT NULL THEN 1 END) AS hit,
  count(CASE WHEN u.wall_ts IS NOT NULL AND p.wall_paid = 1 THEN 1 END) AS wall_paid,
  count(CASE WHEN p.any_paid = 1 THEN 1 END) AS any_paid
FROM users u
LEFT JOIN (
  SELECT
    u2.uid,
    max(CASE WHEN o.createtime >= u2.wall_ts THEN 1 ELSE 0 END) AS wall_paid,
    1 AS any_paid
  FROM users u2
  INNER JOIN ord o ON o.userid = u2.uid
  GROUP BY u2.uid
) p ON p.uid = u.uid
GROUP BY u.grp
ORDER BY u.grp;
