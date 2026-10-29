# -*- coding: utf-8 -*-
"""T050 light: BCD drop = truncated 7d window?"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Lean: one scan, compare 0914 vs 0921 under fair windows
SQL = r"""
WITH weeks AS (
  SELECT '0914' AS wk, '2026-09-14' AS s, '2026-09-21' AS e
  UNION ALL SELECT '0921', '2026-09-21', '2026-09-28'
),
act AS (
  SELECT device_id, created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i','j') THEN 'D'
    END AS exp_group
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-09-13 16:00:00' AND created_ts < '2026-09-28 16:00:00'
      AND event_name='translate_page' AND is_new_user_today='1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag))=1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        TRY_CAST(split_part(version,'.',1) AS INT) > 1
        OR (TRY_CAST(split_part(version,'.',1) AS INT)=1
            AND (TRY_CAST(split_part(version,'.',2) AS INT)>32
                 OR (TRY_CAST(split_part(version,'.',2) AS INT)=32
                     AND TRY_CAST(split_part(version,'.',3) AS INT)>=6)))
      )
  ) t
  WHERE rn=1
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) >= '2026-09-14'
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) < '2026-09-28'
),
cohort AS (
  SELECT a.*, w.wk FROM act a
  INNER JOIN weeks w ON a.install_day >= w.s AND a.install_day < w.e
),
di AS (
  SELECT device_id, userid, installtime FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-09-13 16:00:00'
              AND d.installtime < '2026-09-30 16:00:00' THEN 0
             WHEN d.userid IS NOT NULL THEN 1 ELSE 2 END, d.installtime) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort) c ON c.device_id=d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime>'1970-01-02'
  ) x WHERE rn=1
),
base0 AS (
  SELECT c.*, d.userid,
    COALESCE(
      CASE WHEN d.installtime >= '2026-09-13 16:00:00'
            AND d.installtime < '2026-09-30 16:00:00' THEN d.installtime END,
      c.act_ts) AS anchor_ts
  FROM cohort c LEFT JOIN di d ON d.device_id=c.device_id
),
uid_cands AS (
  SELECT device_id, userid AS uid, act_ts FROM base0 WHERE userid IS NOT NULL
  UNION SELECT device_id, act_uid, act_ts FROM base0 WHERE act_uid IS NOT NULL
),
old_acct AS (
  SELECT DISTINCT u.device_id FROM uid_cands u
  INNER JOIN immdata.imt_userinfo ui ON ui.id=u.uid AND COALESCE(ui.isdeleted,0)=0
  WHERE ui.createtime < date_add(day,-1,u.act_ts)
),
base AS (
  SELECT b.* FROM base0 b
  LEFT JOIN old_acct oa ON oa.device_id=b.device_id
  WHERE oa.device_id IS NULL
),
old_customer AS (
  SELECT DISTINCT b.device_id FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid=b.userid AND COALESCE(o.isdeleted,0)=0
   AND o.orderstatus='finished' AND o.createtime < b.anchor_ts
  WHERE b.userid IS NOT NULL
),
pay AS (
  SELECT b.device_id, b.wk, b.exp_group, b.install_day, b.anchor_ts,
    min(o.createtime) AS pay_ts
  FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid=b.userid AND COALESCE(o.isdeleted,0)=0 AND b.userid IS NOT NULL
   AND o.orderstatus='finished'
   AND lower(COALESCE(o.ordertype,''))<>'iospay_renew'
   AND (COALESCE(o.amountpaid,0)>0
        OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
        OR lower(COALESCE(o.ordertype,''))='code')
   AND o.createtime >= b.anchor_ts
   AND o.createtime < '2026-09-30 16:00:00'
  LEFT JOIN old_customer oc ON oc.device_id=b.device_id
  WHERE oc.device_id IS NULL
  GROUP BY 1,2,3,4,5
),
lab AS (
  SELECT b.wk, b.exp_group, b.install_day, b.device_id, b.anchor_ts,
    p.pay_ts,
    CASE WHEN p.pay_ts IS NOT NULL AND p.pay_ts < add_days(b.anchor_ts,1) THEN 1 ELSE 0 END AS p1,
    CASE WHEN p.pay_ts IS NOT NULL AND p.pay_ts < add_days(b.anchor_ts,3) THEN 1 ELSE 0 END AS p3,
    CASE WHEN p.pay_ts IS NOT NULL AND p.pay_ts < add_days(b.anchor_ts,7)
          AND p.pay_ts < '2026-09-28 16:00:00' THEN 1 ELSE 0 END AS p7_old,
    CASE WHEN p.pay_ts IS NOT NULL AND p.pay_ts < add_days(b.anchor_ts,7) THEN 1 ELSE 0 END AS p7_long,
    CASE WHEN add_days(b.anchor_ts,7) <= '2026-09-30 16:00:00' THEN 1 ELSE 0 END AS m7,
    CASE WHEN add_days(b.anchor_ts,3) <= '2026-09-30 16:00:00' THEN 1 ELSE 0 END AS m3
  FROM base b
  LEFT JOIN pay p ON p.device_id=b.device_id
)
SELECT 'all' AS scope, wk, exp_group,
  count(*) AS n,
  sum(p1) AS p1, round(sum(p1)*100.0/count(*),3) AS p1_pct,
  sum(p3) AS p3, round(sum(p3)*100.0/count(*),3) AS p3_pct,
  sum(p7_old) AS p7_old, round(sum(p7_old)*100.0/count(*),3) AS p7_old_pct,
  sum(p7_long) AS p7_long, round(sum(p7_long)*100.0/count(*),3) AS p7_long_pct
FROM lab GROUP BY wk, exp_group
UNION ALL
SELECT 'm3' AS scope, wk, exp_group,
  count(*), sum(p1), round(sum(p1)*100.0/count(*),3),
  sum(p3), round(sum(p3)*100.0/count(*),3),
  sum(p7_old), round(sum(p7_old)*100.0/count(*),3),
  sum(p7_long), round(sum(p7_long)*100.0/count(*),3)
FROM lab WHERE m3=1 GROUP BY wk, exp_group
UNION ALL
SELECT 'm7' AS scope, wk, exp_group,
  count(*), sum(p1), round(sum(p1)*100.0/count(*),3),
  sum(p3), round(sum(p3)*100.0/count(*),3),
  sum(p7_old), round(sum(p7_old)*100.0/count(*),3),
  sum(p7_long), round(sum(p7_long)*100.0/count(*),3)
FROM lab WHERE m7=1 GROUP BY wk, exp_group
ORDER BY scope, wk, exp_group
"""

cols, rows = query(SQL)
print(f"{'scope':4} {'wk':4} {'g':2} {'n':>7} {'p1%':>7} {'p3%':>7} {'p7old%':>8} {'p7long%':>8} | p1 p3 p7o p7l")
by = {}
for r in rows:
    d = dict(zip(cols, r))
    by[(d["scope"], d["wk"], d["exp_group"])] = d
    print(
        f"{d['scope']:4} {d['wk']:4} {d['exp_group']:2} {int(d['n']):7d} "
        f"{float(d['p1_pct']):6.3f}% {float(d['p3_pct']):6.3f}% "
        f"{float(d['p7_old_pct']):7.3f}% {float(d['p7_long_pct']):7.3f}% | "
        f"{int(d['p1']):3d} {int(d['p3']):3d} {int(d['p7_old']):3d} {int(d['p7_long']):3d}"
    )

print("\n=== WoW BCD on fair windows (0921 - 0914, pp) ===")
for scope in ("all", "m3", "m7"):
    print(f" -- {scope}")
    for g in "ABCD":
        a = by[(scope, "0914", g)]
        b = by[(scope, "0921", g)]
        for metric, key in [("p1", "p1_pct"), ("p3", "p3_pct"), ("p7old", "p7_old_pct"), ("p7long", "p7_long_pct")]:
            dlt = float(b[key]) - float(a[key])
            print(f"   {g} {metric}: {float(a[key]):.3f}->{float(b[key]):.3f} (Δ{dlt:+.3f}pp)")
