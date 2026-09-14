-- T021：安装前现金 gap≥30 天（29 人）根因：碰撞 / 刷新 / bug
-- 任务：docs/tasks/anomaly_order_before_install_20260831.md

-- §1 互斥根因
WITH cohort AS (
  SELECT userid, min(installtime) AS first_install
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
prior AS (
  SELECT c.userid, c.first_install, min(o.createtime) AS earliest_cash_ts,
    date_diff(day, date(min(o.createtime)), date(c.first_install)) AS gap_day
  FROM cohort c
  JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0
   AND o.createtime < c.first_install
  GROUP BY 1, 2
),
u29 AS (
  SELECT p.*, ui.createtime AS acct_ctime,
    date_diff(day, date(ui.createtime), date(p.first_install)) AS acct_age_days,
    CASE WHEN ui.createtime IS NOT NULL AND p.earliest_cash_ts < ui.createtime
      THEN 1 ELSE 0 END AS cash_before_account
  FROM prior p
  LEFT JOIN immdata.imt_userinfo ui
    ON ui.id = p.userid AND COALESCE(ui.isdeleted, 0) = 0
  WHERE p.gap_day >= 30
),
del_dev AS (
  SELECT u.userid, min(d.installtime) AS min_del_install, count(*) AS del_device_rows
  FROM u29 u
  JOIN immdata.imt_deviceinfo d
    ON d.userid = u.userid AND COALESCE(d.isdeleted, 0) = 1
   AND d.installtime > '1970-01-02'
  GROUP BY 1
),
live AS (
  SELECT u.userid,
    max(CASE WHEN d.installtime > d.createtime
      AND date_diff(day, date(d.createtime), date(d.installtime)) >= 30
      THEN 1 ELSE 0 END) AS refresh_30d
  FROM u29 u
  JOIN immdata.imt_deviceinfo d
    ON d.userid = u.userid AND COALESCE(d.isdeleted, 0) = 0
   AND d.installtime > '1970-01-02'
  GROUP BY 1
),
dev_share AS (
  SELECT u.userid,
    max(CASE WHEN oth.userid IS NOT NULL THEN 1 ELSE 0 END) AS shared_deviceid
  FROM u29 u
  JOIN immdata.imt_deviceinfo d
    ON d.userid = u.userid AND COALESCE(d.isdeleted, 0) = 0
  LEFT JOIN immdata.imt_deviceinfo oth
    ON oth.deviceid = d.deviceid AND oth.userid <> u.userid
   AND COALESCE(oth.isdeleted, 0) = 0
  GROUP BY 1
),
ord_share AS (
  SELECT u.userid,
    max(CASE WHEN o2.userid IS NOT NULL THEN 1 ELSE 0 END) AS order_key_shared
  FROM u29 u
  JOIN immdata.imt_subscriptiongoodsorder o1
    ON o1.userid = u.userid AND COALESCE(o1.isdeleted, 0) = 0
   AND o1.orderstatus = 'finished' AND COALESCE(o1.amountpaid, 0) > 0
   AND o1.createtime = u.earliest_cash_ts
  LEFT JOIN immdata.imt_subscriptiongoodsorder o2
    ON o2.userid <> u.userid AND COALESCE(o2.isdeleted, 0) = 0
   AND o2.orderstatus = 'finished'
   AND (
     (o1.apptransactionid IS NOT NULL AND o1.apptransactionid <> ''
      AND o2.apptransactionid = o1.apptransactionid)
     OR (o1.subscriptionid IS NOT NULL AND o1.subscriptionid <> ''
      AND o2.subscriptionid = o1.subscriptionid)
   )
  GROUP BY 1
),
labeled AS (
  SELECT
    CASE
      WHEN u.cash_before_account = 1 THEN 'A_cash_before_account'
      WHEN COALESCE(dd.del_device_rows, 0) > 0
       AND dd.min_del_install IS NOT NULL AND dd.min_del_install < u.first_install
        THEN 'B_soft_deleted_older_device'
      WHEN COALESCE(l.refresh_30d, 0) = 1 THEN 'C_install_refreshed'
      WHEN COALESCE(ds.shared_deviceid, 0) = 1 THEN 'D_deviceid_collision'
      WHEN COALESCE(os.order_key_shared, 0) = 1 THEN 'E_order_key_shared'
      WHEN COALESCE(u.acct_age_days, -1) >= 30 THEN 'F_old_acct_late_device'
      ELSE 'G_other'
    END AS root_cause
  FROM u29 u
  LEFT JOIN del_dev dd ON dd.userid = u.userid
  LEFT JOIN live l ON l.userid = u.userid
  LEFT JOIN dev_share ds ON ds.userid = u.userid
  LEFT JOIN ord_share os ON os.userid = u.userid
)
SELECT root_cause, count(*) AS users,
  round(count(*) * 100.0 / sum(count(*)) OVER (), 1) AS pct
FROM labeled
GROUP BY 1
ORDER BY 1;

-- §2 刷新/软删计数（应为 0）
WITH cohort AS (
  SELECT userid, min(installtime) AS first_install
  FROM immdata.imt_deviceinfo
  WHERE installtime > '1970-01-02' AND COALESCE(isdeleted, 0) = 0
  GROUP BY userid
  HAVING min(installtime) >= '2026-08-01' AND min(installtime) < '2026-09-01'
),
prior AS (
  SELECT c.userid, c.first_install, min(o.createtime) AS earliest_cash_ts,
    date_diff(day, date(min(o.createtime)), date(c.first_install)) AS gap_day
  FROM cohort c
  JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0
   AND o.createtime < c.first_install
  GROUP BY 1, 2
),
u29 AS (SELECT * FROM prior WHERE gap_day >= 30)
SELECT
  count(*) AS n29,
  count_if(cash_before_account = 1) AS cash_before_account,
  (SELECT count(DISTINCT u.userid) FROM u29 u
    JOIN immdata.imt_deviceinfo d ON d.userid = u.userid AND COALESCE(d.isdeleted,0)=1
    AND d.installtime > '1970-01-02' AND d.installtime < u.first_install
  ) AS earlier_soft_deleted_install,
  (SELECT count(DISTINCT u.userid) FROM u29 u
    JOIN immdata.imt_deviceinfo d ON d.userid = u.userid AND COALESCE(d.isdeleted,0)=0
    AND d.installtime > d.createtime
    AND date_diff(day, date(d.createtime), date(d.installtime)) >= 30
  ) AS install_refreshed_30d
FROM (
  SELECT u.*, CASE WHEN ui.createtime IS NOT NULL AND u.earliest_cash_ts < ui.createtime
    THEN 1 ELSE 0 END AS cash_before_account
  FROM u29 u
  LEFT JOIN immdata.imt_userinfo ui ON ui.id = u.userid AND COALESCE(ui.isdeleted,0)=0
) s;
