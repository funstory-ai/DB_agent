-- 账号级「新装用户」过滤（无 user_behaviour）
-- 锚点：userid 的 min(installtime)
-- 规则：
--   1) 无现金单早于 install_anchor - 5min
--   2) 无现金单早于 userinfo.createtime - 5min
--   3) 账龄（createtime→install_anchor）< 30 天
-- 任务：docs/tasks/query_new_install_user_filter_20260831.md
-- 验证：T021 安装前≥30天付费 29/29 剔除；≤5min 多数保留

-- 可复用：改窗口后取 clean 人群
WITH cohort AS (
  SELECT userid, min(installtime) AS install_anchor
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
feat AS (
  SELECT
    c.userid,
    c.install_anchor,
    ui.createtime AS acct_ctime,
    date_diff(day, date(ui.createtime), date(c.install_anchor)) AS acct_age_days,
    max(CASE
      WHEN o.createtime < date_add(minute, -5, c.install_anchor)
       AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0
    END) AS has_cash_before_anchor_5m,
    max(CASE
      WHEN ui.createtime IS NOT NULL
       AND o.createtime < date_add(minute, -5, ui.createtime)
       AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0
    END) AS has_cash_before_acct_5m
  FROM cohort c
  LEFT JOIN immdata.imt_userinfo ui
    ON ui.id = c.userid AND COALESCE(ui.isdeleted, 0) = 0
  LEFT JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid
   AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished'
  GROUP BY 1, 2, 3, 4
),
clean_new_install_users AS (
  SELECT userid, install_anchor, acct_ctime, acct_age_days
  FROM feat
  WHERE has_cash_before_anchor_5m = 0
    AND has_cash_before_acct_5m = 0
    AND COALESCE(acct_age_days, -1) < 30
)
-- §1 规模
SELECT
  (SELECT count(*) FROM cohort) AS raw_users,
  count(*) AS clean_users,
  round(count(*) * 100.0 / (SELECT count(*) FROM cohort), 2) AS pct_kept
FROM clean_new_install_users;

-- §2 T021：安装前现金按 gap，看是否被剔（应：≥30d 全剔，≤5min 多数留）
WITH cohort AS (
  SELECT userid, min(installtime) AS install_anchor
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
prior AS (
  SELECT
    c.userid, c.install_anchor,
    min(o.createtime) AS earliest_cash_ts,
    date_diff('minute', min(o.createtime), c.install_anchor) AS gap_min,
    date_diff(day, date(min(o.createtime)), date(c.install_anchor)) AS gap_day
  FROM cohort c
  JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0
   AND o.createtime < c.install_anchor
  GROUP BY 1, 2
),
feat AS (
  SELECT
    p.*,
    date_diff(day, date(ui.createtime), date(p.install_anchor)) AS acct_age_days,
    CASE WHEN p.earliest_cash_ts < date_add(minute, -5, p.install_anchor) THEN 1 ELSE 0 END AS drop_prior_cash,
    CASE WHEN COALESCE(date_diff(day, date(ui.createtime), date(p.install_anchor)), -1) >= 30
      THEN 1 ELSE 0 END AS drop_old_acct
  FROM prior p
  LEFT JOIN immdata.imt_userinfo ui
    ON ui.id = p.userid AND COALESCE(ui.isdeleted, 0) = 0
)
SELECT
  CASE
    WHEN gap_min <= 5 THEN '1_le_5min'
    WHEN gap_day < 30 THEN '2_6min_to_29d'
    ELSE '3_ge_30d'
  END AS gap_bucket,
  count(*) AS users,
  count_if(drop_prior_cash = 1 OR drop_old_acct = 1) AS dropped,
  count_if(NOT (drop_prior_cash = 1 OR drop_old_acct = 1)) AS kept
FROM feat
GROUP BY 1
ORDER BY 1;
