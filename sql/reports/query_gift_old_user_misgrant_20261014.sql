-- T069 登录赠 5 万 token 错发老用户
-- 领取：imt_novicetaskrecord.taskkey='user_login_1'，isdeleted=0，userid 取最早一条
-- 老用户：imt_userinfo.id = record.userid，且 createtime < 领取时间 − 1 天（P039）
-- 本次放量：北京领取日 >= 2026-10-10
-- 用量：token_used_aw，recordtype=capture，timestamp >= 领取时间，input+output，每人封顶 5 万
-- 不用 imm_token_used
-- 触墙：login_ai_quota_gift_exhausted_modal_show
-- 任务：docs/tasks/query_gift_old_user_misgrant_20261014.md

WITH claims AS (
  SELECT userid, min(createtime) AS claim_ts
  FROM immdata.imt_novicetaskrecord
  WHERE taskkey = 'user_login_1'
    AND coalesce(isdeleted, 0) = 0
  GROUP BY userid
),
old AS (
  SELECT
    c.userid,
    c.claim_ts,
    CASE
      WHEN to_date(date_add(hour, 8, c.claim_ts)) >= '2026-10-10' THEN 'from_1010'
      ELSE 'before_1010'
    END AS wave
  FROM claims c
  JOIN immdata.imt_userinfo u ON c.userid = u.id
  WHERE u.createtime < date_add(day, -1, c.claim_ts)
),
used AS (
  SELECT
    o.userid,
    sum(coalesce(a.inputusage, 0) + coalesce(a.outputusage, 0)) AS raw_used,
    sum(CASE
      WHEN a.resourcename = 'auto' AND a.actualresourceid = 'babelfast'
      THEN coalesce(a.inputusage, 0) + coalesce(a.outputusage, 0) ELSE 0
    END) AS babel_used
  FROM old o
  JOIN immdata.token_used_aw a
    ON a.userid = o.userid
   AND a.timestamp >= o.claim_ts
   AND a.timestamp >= '2026-09-20 16:00:00'
   AND a.timestamp < '2026-10-14 16:00:00'
   AND a.recordtype = 'capture'
  GROUP BY o.userid
),
wall AS (
  SELECT DISTINCT ex_int_arg1 AS userid
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-09-20 16:00:00'
    AND created_ts < '2026-10-14 16:00:00'
    AND event_name = 'login_ai_quota_gift_exhausted_modal_show'
    AND ex_int_arg1 IS NOT NULL
    AND ex_int_arg1 <> 0
)
SELECT
  o.wave,
  count(*) AS old_users,
  count(*) * 50000 AS granted_tokens,
  sum(CASE WHEN coalesce(u.raw_used, 0) > 0 THEN 1 ELSE 0 END) AS used_any,
  sum(CASE WHEN coalesce(u.raw_used, 0) >= 40000 THEN 1 ELSE 0 END) AS ge_40k,
  sum(CASE WHEN coalesce(u.raw_used, 0) >= 50000 THEN 1 ELSE 0 END) AS ge_50k,
  sum(least(coalesce(u.raw_used, 0), 50000)) AS consumed_cap,
  sum(least(coalesce(u.babel_used, 0), 50000)) AS babel_cap,
  sum(CASE WHEN w.userid IS NOT NULL THEN 1 ELSE 0 END) AS wall_n,
  sum(CASE WHEN w.userid IS NOT NULL AND coalesce(u.raw_used, 0) >= 40000 THEN 1 ELSE 0 END) AS wall_and_40k,
  sum(CASE WHEN w.userid IS NOT NULL AND coalesce(u.raw_used, 0) < 40000 THEN 1 ELSE 0 END) AS wall_under_40k
FROM old o
LEFT JOIN used u ON o.userid = u.userid
LEFT JOIN wall w ON o.userid = w.userid
GROUP BY o.wave
ORDER BY o.wave;
