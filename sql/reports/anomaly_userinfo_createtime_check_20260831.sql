-- T023：检验 imt_userinfo.createtime 质量及与 installtime 关系
-- 任务：docs/tasks/anomaly_userinfo_createtime_check_20260831.md

-- §1 字段基本质量
SELECT
  count(*) AS users,
  count_if(createtime IS NULL) AS null_ctime,
  count_if(createtime <= '1970-01-02') AS epoch_ctime,
  min(createtime) AS min_ctime,
  max(createtime) AS max_ctime
FROM immdata.imt_userinfo
WHERE COALESCE(isdeleted, 0) = 0;

-- §2 8 月新注册：订单相对 createtime
WITH u AS (
  SELECT id AS userid, createtime AS acct_ctime
  FROM immdata.imt_userinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND createtime >= '2026-08-01' AND createtime < '2026-09-01'
),
first_any AS (
  SELECT u.userid, u.acct_ctime,
    min(o.createtime) AS first_finished_ts,
    min(CASE WHEN COALESCE(o.amountpaid, 0) > 0 THEN o.createtime END) AS first_cash_ts
  FROM u
  LEFT JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = u.userid AND COALESCE(o.isdeleted, 0) = 0 AND o.orderstatus = 'finished'
  GROUP BY 1, 2
)
SELECT
  count(*) AS aug_new_accounts,
  count_if(first_finished_ts IS NOT NULL) AS with_any_finished,
  count_if(first_cash_ts IS NOT NULL) AS with_cash,
  count_if(first_cash_ts IS NOT NULL AND first_cash_ts < date_add(minute, -5, acct_ctime))
    AS cash_5min_before_acct,
  count_if(first_finished_ts IS NOT NULL AND first_finished_ts >= acct_ctime
    AND date_diff('minute', acct_ctime, first_finished_ts) <= 60) AS finished_within_1h_after_acct
FROM first_any;

-- §3 8 月 min(install) 与账号创建的间隔分布（说明不能互相替代）
WITH cohort AS (
  SELECT userid, min(installtime) AS first_install
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
)
SELECT
  CASE
    WHEN ui.createtime IS NULL THEN '0_no_userinfo'
    WHEN abs(date_diff('minute', ui.createtime, c.first_install)) <= 60 THEN '1_within_1h'
    WHEN date_diff(day, date(ui.createtime), date(c.first_install)) = 0 THEN '2_same_day'
    WHEN c.first_install >= ui.createtime
     AND date_diff(day, date(ui.createtime), date(c.first_install)) <= 7 THEN '3_acct_then_install_1_7d'
    WHEN c.first_install >= ui.createtime
     AND date_diff(day, date(ui.createtime), date(c.first_install)) <= 30 THEN '4_acct_then_install_8_30d'
    WHEN c.first_install >= ui.createtime
     AND date_diff(day, date(ui.createtime), date(c.first_install)) <= 180 THEN '5_acct_then_install_31_180d'
    WHEN c.first_install >= ui.createtime THEN '6_acct_then_install_gt180d'
    WHEN ui.createtime > c.first_install
     AND date_diff(day, date(c.first_install), date(ui.createtime)) <= 1 THEN '7_install_then_acct_le1d'
    ELSE '8_install_long_before_acct'
  END AS bucket,
  count(*) AS users,
  round(count(*) * 100.0 / sum(count(*)) OVER (), 1) AS pct
FROM cohort c
LEFT JOIN immdata.imt_userinfo ui
  ON ui.id = c.userid AND COALESCE(ui.isdeleted, 0) = 0
GROUP BY 1
ORDER BY 1;
