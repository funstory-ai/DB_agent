-- 用途：同 token 高频异常用户识别 + 月内累加 vs Pro 2000 万上限
-- 主表：immdata.token_used_aw（capture；必须限时）
-- 规范大类：anomaly
-- 时间窗：2026-05-01 ≤ timestamp < 2026-08-25（AW 至 8/24）
-- 已知坑：P010（勿引用 tmp_*）；behaviour 对账见任务文档（双路径 P016）

-- ========== 判定口径（可疑用户日）==========
-- 同一天、同一 userid、同一 resourcename + providername：
--   1) 当日 capture 请求 day_cnt >= 3000
--   2) 最常见 (inputusage, outputusage) 组合 pair_cnt >= 1000
--   3) pair_cnt / day_cnt >= 25%
--   4) 单笔 input+output >= 50（过滤极小噪声）
-- 注：chenghuili 类「多组相近 token」单组占比可 <25%，仍属同类形态，本口径偏保守。

-- ---------- A. 可疑用户日明细（可导出 Excel）----------
WITH pair AS (
  SELECT
    to_date(timestamp) AS dt,
    userid,
    resourcename,
    providername,
    coalesce(inputusage, 0) AS inn,
    coalesce(outputusage, 0) AS outt,
    COUNT(*) AS pair_cnt
  FROM immdata.token_used_aw
  WHERE timestamp >= '2026-05-01'
    AND timestamp < '2026-08-25'
    AND recordtype = 'capture'
    AND userid IS NOT NULL
    AND userid > 0
    AND coalesce(inputusage, 0) + coalesce(outputusage, 0) >= 50
  GROUP BY 1, 2, 3, 4, 5, 6
),
day_tot AS (
  SELECT dt, userid, resourcename, providername, SUM(pair_cnt) AS day_cnt
  FROM pair
  GROUP BY 1, 2, 3, 4
),
top_pair AS (
  SELECT
    p.*,
    d.day_cnt,
    ROW_NUMBER() OVER (
      PARTITION BY p.dt, p.userid, p.resourcename, p.providername
      ORDER BY p.pair_cnt DESC
    ) AS rn
  FROM pair p
  JOIN day_tot d
    ON p.dt = d.dt
   AND p.userid = d.userid
   AND p.resourcename = d.resourcename
   AND p.providername = d.providername
)
SELECT
  t.dt,
  t.userid,
  u.email,
  t.resourcename,
  t.providername,
  t.inn AS same_input,
  t.outt AS same_output,
  t.pair_cnt AS same_pair_cnt,
  t.day_cnt AS day_model_cnt,
  ROUND(t.pair_cnt * 100.0 / t.day_cnt, 1) AS same_share_pct
FROM top_pair t
LEFT JOIN immdata.imt_userinfo u
  ON u.id = t.userid
 AND COALESCE(u.isdeleted, 0) = 0
WHERE t.rn = 1
  AND t.day_cnt >= 3000
  AND t.pair_cnt >= 1000
  AND t.pair_cnt * 100.0 / t.day_cnt >= 25
ORDER BY t.pair_cnt DESC, t.dt;

-- ---------- B. 按月规模（用户日 / 去重用户）----------
-- WITH ... 同上 top_pair WHERE rn=1 AND 三条件
-- SELECT DATE_TRUNC('month', dt) ym, COUNT(*) user_days, COUNT(DISTINCT userid) users ...

-- ---------- C. 同月可疑天数 + 月 pro-token 是否贴 2000 万 ----------
-- 1) 从 A 取 DISTINCT (DATE_TRUNC month, userid, dt) 得 sus_day_n
-- 2) token_used_aw 按 (dt, userid) 汇总 categoryname='pro-token' 得 day_pro
-- 3) 按 (ym, userid) SUM(day_pro) = month_pro
-- 贴满阈值：>= 19_900_000（业务上限 20_000_000）
-- 关键结论（2026-05～08-24 实测）：
--   - 252 个「当月有可疑日」用户-月；>=19.9M 占 10.7%
--   - sus_day_n=1 → 贴满约 5%；>=6 天 → 约 55%
--   - 贴满者 2/3 为 >=2 可疑日；仅可疑日 >=19.9M 约 26%

-- ---------- D. 行为对账（高峰小时，双路径 P016）----------
-- deviceinfo.deviceid = user_behaviour.device_id
-- OR user_behaviour.ex_int_arg1 = userid
-- 高峰小时 AW 与 behaviour 数量级常差 3+ 个数量级；非 device_id 挂不上导致。
