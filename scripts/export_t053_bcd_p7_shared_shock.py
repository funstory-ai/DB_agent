# -*- coding: utf-8 -*-
"""T053: BCD 7d paid sync surge@0907 then drop — shared-shock dig (not noise talk)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Fair 7d only for weeks with full maturity to asof930: 0824,0831,0907,0914
# 0921 separately flagged. Focus: why BCD p7 jumps 0831->0907 together.

SQL = r"""
WITH weeks AS (
  SELECT '0831' AS wk, '2026-08-31' AS s, '2026-09-07' AS e, 1 AS ord
  UNION ALL SELECT '0907', '2026-09-07', '2026-09-14', 2
  UNION ALL SELECT '0914', '2026-09-14', '2026-09-21', 3
  UNION ALL SELECT '0921', '2026-09-21', '2026-09-28', 4
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
    END AS exp_group,
    lower(trim(COALESCE(real_geo,''))) AS geo,
    CASE
      WHEN lower(trim(os_name)) IN ('android','ios','ipados') THEN 'mobile'
      WHEN lower(trim(os_name)) IN ('windows','macos','linux','chromeos') THEN 'desktop'
      ELSE 'other'
    END AS plat,
    CASE
      WHEN lower(trim(install_from)) IN ('chrome','edge','firefox','safari') THEN lower(trim(install_from))
      WHEN lower(trim(install_from)) = 'official_userscript' THEN 'userscript'
      ELSE 'other'
    END AS ch
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, os_name, install_from, real_geo,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-30 16:00:00' AND created_ts < '2026-09-28 16:00:00'
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
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) >= '2026-08-31'
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) < '2026-09-28'
),
cohort AS (
  SELECT a.*, w.wk, w.ord FROM act a
  INNER JOIN weeks w ON a.install_day >= w.s AND a.install_day < w.e
),
di AS (
  SELECT device_id, userid, installtime FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-08-30 16:00:00'
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
      CASE WHEN d.installtime >= '2026-08-30 16:00:00'
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
  SELECT b.* FROM base0 b LEFT JOIN old_acct oa ON oa.device_id=b.device_id
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
  SELECT b.device_id, min(o.createtime) AS pay_ts,
    max(COALESCE(o.amountpaid,0)) AS amt
  FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid=b.userid AND COALESCE(o.isdeleted,0)=0 AND b.userid IS NOT NULL
   AND o.orderstatus='finished'
   AND lower(COALESCE(o.ordertype,''))<>'iospay_renew'
   AND (COALESCE(o.amountpaid,0)>0
        OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
        OR lower(COALESCE(o.ordertype,''))='code')
   AND o.createtime >= b.anchor_ts AND o.createtime < add_days(b.anchor_ts,7)
   AND o.createtime < '2026-09-30 16:00:00'
  LEFT JOIN old_customer oc ON oc.device_id=b.device_id
  WHERE oc.device_id IS NULL
  GROUP BY 1
),
lab AS (
  SELECT b.wk, b.exp_group, b.plat, b.ch,
    CASE
      WHEN b.geo IN ('cn','us','jp','kr','tw','hk','mo','sg','th','vn','id','my','ph','in','br','de','fr','gb','ru')
        THEN b.geo ELSE 'other'
    END AS geo_b,
    CASE WHEN b.userid IS NOT NULL THEN 1 ELSE 0 END AS is_reg,
    CASE WHEN p.device_id IS NOT NULL THEN 1 ELSE 0 END AS paid_7d,
    CASE WHEN p.device_id IS NOT NULL AND p.amt <= 0 THEN 1 ELSE 0 END AS paid_zero_amt
  FROM base b LEFT JOIN pay p ON p.device_id=b.device_id
)
SELECT 'grp' AS q, wk, exp_group AS dim,
  count(*) AS n, sum(is_reg) AS regs, sum(paid_7d) AS pays,
  round(sum(is_reg)*100.0/count(*),2) AS reg_pct,
  round(sum(paid_7d)*100.0/count(*),3) AS pay_pct,
  sum(paid_zero_amt) AS zero_amt_pays
FROM lab GROUP BY wk, exp_group
UNION ALL
SELECT 'bcd_plat', wk, plat, count(*), sum(is_reg), sum(paid_7d),
  round(sum(is_reg)*100.0/count(*),2), round(sum(paid_7d)*100.0/count(*),3), sum(paid_zero_amt)
FROM lab WHERE exp_group IN ('B','C','D') GROUP BY wk, plat
UNION ALL
SELECT 'bcd_geo', wk, geo_b, count(*), sum(is_reg), sum(paid_7d),
  round(sum(is_reg)*100.0/count(*),2), round(sum(paid_7d)*100.0/count(*),3), sum(paid_zero_amt)
FROM lab WHERE exp_group IN ('B','C','D') GROUP BY wk, geo_b
UNION ALL
SELECT 'bcd_ch', wk, ch, count(*), sum(is_reg), sum(paid_7d),
  round(sum(is_reg)*100.0/count(*),2), round(sum(paid_7d)*100.0/count(*),3), sum(paid_zero_amt)
FROM lab WHERE exp_group IN ('B','C','D') GROUP BY wk, ch
ORDER BY q, dim, wk
"""

cols, rows = query(SQL)
data = [dict(zip(cols, r)) for r in rows]

print("=== FROM YOUR XLSX 7d付费列 (confirmed) ===")
print("week   A      B      C      D")
print("0831  0.17%  0.13%  0.13%  0.15%")
print("0907  0.15%  0.17%  0.20%  0.19%   <- BCD sync UP, A down")
print("0914  0.15%  0.17%  0.14%  0.15%")
print("0921  0.17%  0.12%  0.12%  0.12%   <- BCD sync DOWN, A up")

print("\n=== LIVE grp p7 (excl old, semver) ===")
for d in data:
    if d["q"] != "grp":
        continue
    print(
        f"{d['wk']} {d['dim']} n={int(d['n']):6d} reg={float(d['reg_pct']):5.2f}% "
        f"p7={int(d['pays']):3d} ({float(d['pay_pct']):.3f}%) zeroAmt={int(d['zero_amt_pays'])}"
    )

print("\n=== BCD pool: plat / top geo / ch share & p7 ===")
for q in ("bcd_plat", "bcd_geo", "bcd_ch"):
    print(f" -- {q}")
    rows_q = [d for d in data if d["q"] == q]
    # only dims with n>=500 in any week
    dims = sorted({d["dim"] for d in rows_q})
    for dim in dims:
        line = []
        keep = False
        for wk in ("0831", "0907", "0914", "0921"):
            d = next((x for x in rows_q if x["wk"] == wk and x["dim"] == dim), None)
            if not d:
                line.append(f"{wk}:-")
                continue
            n, p, r = int(d["n"]), int(d["pays"]), float(d["pay_pct"])
            if n >= 800:
                keep = True
            line.append(f"{wk}:n={n} p7={p}({r:.3f}%)")
        if keep:
            print(f"  {dim}: " + " | ".join(line))
