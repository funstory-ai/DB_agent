-- 近两周试用订单用户 × user_behaviour.ex_int_arg1 匹配率
-- 规范大类: query；口径 P013 试用；匹配仅走 ex_int_arg1（按需求，非 P016 双路径）
-- 行为：同窗 event_name='translate_page'（性能收窄；非全事件）
-- 窗口示例（跑数日）：[2026-07-31, 2026-08-15)

WITH trial_users AS (
  SELECT DISTINCT CAST(userid AS INT) AS userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) = 0
    AND createtime >= '2026-07-31 00:00:00'
    AND createtime < '2026-08-15 00:00:00'
    AND userid IS NOT NULL
    AND (
      subscriptiongoodssnap IS NULL
      OR CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
    )
),
matched AS (
  SELECT DISTINCT ub.ex_int_arg1 AS userid
  FROM immdata.user_behaviour AS ub
  INNER JOIN trial_users AS t ON ub.ex_int_arg1 = t.userid
  WHERE ub.created_ts >= '2026-07-31 00:00:00'
    AND ub.created_ts < '2026-08-15 00:00:00'
    AND ub.event_name = 'translate_page'
    AND ub.ex_int_arg1 IS NOT NULL
)
SELECT
  (SELECT COUNT(*) FROM trial_users) AS trial_users,
  (SELECT COUNT(*) FROM matched) AS matched_users,
  (SELECT COUNT(*) FROM trial_users) - (SELECT COUNT(*) FROM matched) AS unmatched_users,
  ROUND(
    100.0 * (
      (SELECT COUNT(*) FROM trial_users) - (SELECT COUNT(*) FROM matched)
    ) / NULLIF((SELECT COUNT(*) FROM trial_users), 0),
    2
  ) AS unmatched_pct;

-- 实跑说明：大 cohort 直连 JOIN 易超时；实践为对 trial_users 分批 IN(2000)
-- 碰同窗 translate_page，再合并 DISTINCT matched。见 docs/tasks/query_trial14d_ex_int_arg1_match_20260814.md
