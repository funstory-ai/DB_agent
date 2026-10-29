# -*- coding: utf-8 -*-
"""T052: C/D also dropped on 7d — same decomp as B (within-arm tags + ver)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

SQL = r"""
WITH act AS (
  SELECT device_id, created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    lower(trim(ab_tag)) AS tag,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i','j') THEN 'D'
    END AS exp_group,
    CASE
      WHEN version LIKE '1.32.%' THEN '1.32'
      WHEN version LIKE '1.33.1%' THEN '1.33.1'
      WHEN version LIKE '1.33.3%' THEN '1.33.3'
      WHEN version LIKE '1.33.%' THEN '1.33.other'
      ELSE 'other'
    END AS ver_b,
    CASE
      WHEN lower(trim(os_name)) IN ('android','ios','ipados') THEN 'mobile'
      WHEN lower(trim(os_name)) IN ('windows','macos','linux','chromeos') THEN 'desktop'
      ELSE 'other'
    END AS plat
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, version, os_name,
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
wk AS (
  SELECT *, CASE WHEN install_day < '2026-09-21' THEN '0914' ELSE '0921' END AS week
  FROM act
),
di AS (
  SELECT device_id, userid, installtime FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-09-13 16:00:00'
              AND d.installtime < '2026-09-30 16:00:00' THEN 0
             WHEN d.userid IS NOT NULL THEN 1 ELSE 2 END, d.installtime) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM wk) c ON c.device_id=d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime>'1970-01-02'
  ) x WHERE rn=1
),
base0 AS (
  SELECT w.*, d.userid,
    COALESCE(
      CASE WHEN d.installtime >= '2026-09-13 16:00:00'
            AND d.installtime < '2026-09-30 16:00:00' THEN d.installtime END,
      w.act_ts) AS anchor_ts
  FROM wk w LEFT JOIN di d ON d.device_id=w.device_id
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
  SELECT b.device_id,
    min(o.createtime) AS pay_ts
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
  SELECT b.week, b.exp_group, b.tag, b.ver_b, b.plat, b.install_day,
    CASE WHEN b.userid IS NOT NULL THEN 1 ELSE 0 END AS is_reg,
    CASE WHEN p.device_id IS NOT NULL THEN 1 ELSE 0 END AS paid_7d,
    CASE WHEN p.pay_ts IS NOT NULL AND p.pay_ts < add_days(b.anchor_ts,3) THEN 1 ELSE 0 END AS paid_3d
  FROM base b LEFT JOIN pay p ON p.device_id=b.device_id
)
SELECT 'grp' AS q, week, exp_group AS dim, count(*) AS n,
  sum(paid_3d) AS p3, sum(paid_7d) AS p7,
  round(sum(paid_3d)*100.0/count(*),3) AS r3,
  round(sum(paid_7d)*100.0/count(*),3) AS r7
FROM lab GROUP BY week, exp_group
UNION ALL
SELECT 'tag', week, concat(exp_group,':',tag), count(*), sum(paid_3d), sum(paid_7d),
  round(sum(paid_3d)*100.0/count(*),3), round(sum(paid_7d)*100.0/count(*),3)
FROM lab GROUP BY week, exp_group, tag
UNION ALL
SELECT 'ver', week, concat(exp_group,':',ver_b), count(*), sum(paid_3d), sum(paid_7d),
  round(sum(paid_3d)*100.0/count(*),3), round(sum(paid_7d)*100.0/count(*),3)
FROM lab GROUP BY week, exp_group, ver_b
UNION ALL
SELECT 'plat', week, concat(exp_group,':',plat), count(*), sum(paid_3d), sum(paid_7d),
  round(sum(paid_3d)*100.0/count(*),3), round(sum(paid_7d)*100.0/count(*),3)
FROM lab GROUP BY week, exp_group, plat
ORDER BY q, dim, week
"""


def main() -> None:
    print("querying A/B/C/D decomp...", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]
    by = {(d["q"], d["week"], d["dim"]): d for d in data}

    print("\n=== GROUP 7d/3d ===", flush=True)
    print(f"{'g':2} {'w':4} {'n':>7} {'p3':>4} {'r3%':>7} {'p7':>4} {'r7%':>7}", flush=True)
    for g in "ABCD":
        for w in ("0914", "0921"):
            d = by[("grp", w, g)]
            print(
                f"{g:2} {w:4} {int(d['n']):7d} {int(d['p3']):4d} {float(d['r3']):6.3f}% "
                f"{int(d['p7']):4d} {float(d['r7']):6.3f}%",
                flush=True,
            )
        a, b = by[("grp", "0914", g)], by[("grp", "0921", g)]
        print(
            f"   Δp7={int(b['p7'])-int(a['p7']):+d}  Δr7={float(b['r7'])-float(a['r7']):+.3f}pp  "
            f"Δp3={int(b['p3'])-int(a['p3']):+d}  Δr3={float(b['r3'])-float(a['r3']):+.3f}pp",
            flush=True,
        )

    print("\n=== WITHIN-ARM TAG (same config) p7 bridge ===", flush=True)
    for g, tags in [("A", "abc"), ("B", "def"), ("C", "gh"), ("D", "ij")]:
        print(f" -- {g}", flush=True)
        for t in tags:
            dim = f"{g}:{t}"
            a, b = by.get(("tag", "0914", dim)), by.get(("tag", "0921", dim))
            if not a or not b:
                continue
            dlt = int(b["p7"]) - int(a["p7"])
            print(
                f"   {t}: p7 {int(a['p7'])}->{int(b['p7'])} (Δ{dlt:+d})  "
                f"n {int(a['n'])}->{int(b['n'])}  "
                f"rate {float(a['r7']):.3f}->{float(b['r7']):.3f}%",
                flush=True,
            )

    print("\n=== VER bridge p7 (BCD focus) ===", flush=True)
    for g in "BCD":
        print(f" -- {g}", flush=True)
        dims = sorted({k[2] for k in by if k[0] == "ver" and k[2].startswith(g + ":")})
        for dim in dims:
            a, b = by.get(("ver", "0914", dim)), by.get(("ver", "0921", dim))
            pa = int(a["p7"]) if a else 0
            pb = int(b["p7"]) if b else 0
            na = int(a["n"]) if a else 0
            nb = int(b["n"]) if b else 0
            ra = float(a["r7"]) / 100 if a and na else 0
            dlt = pb - pa
            rate_eff = pb - ra * nb
            vol_eff = ra * nb - pa
            if abs(dlt) >= 1 or pa >= 3 or pb >= 3:
                ver = dim.split(":", 1)[1]
                print(
                    f"   {ver:10} p7 {pa}->{pb} (Δ{dlt:+d}) n {na}->{nb} "
                    f"rateEff≈{rate_eff:+.1f} volEff≈{vol_eff:+.1f}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
