# -*- coding: utf-8 -*-
"""T049: why A paid looks high on 09/21 week after basic_continue — dig absolute + mix."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Same knives as T048: semver >=1.32.6 + P039 excl old
# Compare weeks 0907 / 0914 / 0921 on: n, paid7, paid_asof, reg, version mix, daily paid

SQL = r"""
WITH weeks AS (
  SELECT '0907' AS wk, '2026-09-07' AS s, '2026-09-14' AS e, 1 AS ord
  UNION ALL SELECT '0914', '2026-09-14', '2026-09-21', 2
  UNION ALL SELECT '0921', '2026-09-21', '2026-09-28', 3
),
act AS (
  SELECT
    device_id,
    created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    version,
    CASE
      WHEN version LIKE '1.32.%' THEN '1.32'
      WHEN version LIKE '1.33.%' THEN concat('1.33.', coalesce(nullif(split_part(version,'.',3),''),'?'))
      WHEN version LIKE '1.34.%' THEN '1.34+'
      ELSE 'other'
    END AS ver_bucket,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i','j') THEN 'D'
    END AS exp_group,
    lower(trim(os_name)) AS os_name,
    lower(trim(install_from)) AS install_from
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, version, os_name, install_from,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-09-06 16:00:00' AND created_ts < '2026-09-28 16:00:00'
      AND event_name = 'translate_page' AND is_new_user_today = '1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        TRY_CAST(split_part(version, '.', 1) AS INT) > 1
        OR (
          TRY_CAST(split_part(version, '.', 1) AS INT) = 1
          AND (
            TRY_CAST(split_part(version, '.', 2) AS INT) > 32
            OR (
              TRY_CAST(split_part(version, '.', 2) AS INT) = 32
              AND TRY_CAST(split_part(version, '.', 3) AS INT) >= 6
            )
          )
        )
      )
  ) t
  WHERE rn = 1
    AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) >= '2026-09-07'
    AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) < '2026-09-28'
),
cohort AS (
  SELECT a.*, w.wk, w.ord
  FROM act a
  INNER JOIN weeks w ON a.install_day >= w.s AND a.install_day < w.e
),
di AS (
  SELECT device_id, userid, installtime FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-09-06 16:00:00'
              AND d.installtime < '2026-09-28 16:00:00' THEN 0
             WHEN d.userid IS NOT NULL THEN 1 ELSE 2 END, d.installtime) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort) c ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime > '1970-01-02'
  ) x WHERE rn = 1
),
base AS (
  SELECT c.*, d.userid,
    COALESCE(
      CASE WHEN d.installtime >= '2026-09-06 16:00:00'
            AND d.installtime < '2026-09-28 16:00:00' THEN d.installtime END,
      c.act_ts) AS anchor_ts
  FROM cohort c
  LEFT JOIN di d ON d.device_id = c.device_id
),
uid_cands AS (
  SELECT device_id, userid AS uid, act_ts FROM base WHERE userid IS NOT NULL
  UNION
  SELECT device_id, act_uid, act_ts FROM base WHERE act_uid IS NOT NULL
),
old_acct AS (
  SELECT DISTINCT u.device_id
  FROM uid_cands u
  INNER JOIN immdata.imt_userinfo ui ON ui.id = u.uid AND COALESCE(ui.isdeleted,0)=0
  WHERE ui.createtime < date_add(day, -1, u.act_ts)
),
clean AS (
  SELECT b.*
  FROM base b
  LEFT JOIN old_acct oa ON oa.device_id = b.device_id
  WHERE oa.device_id IS NULL
),
old_customer AS (
  SELECT DISTINCT c.device_id
  FROM clean c
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted,0)=0
   AND o.orderstatus = 'finished' AND o.createtime < c.anchor_ts
  WHERE c.userid IS NOT NULL
),
paid_flags AS (
  SELECT c.device_id,
    max(CASE
      WHEN o.orderstatus='finished'
       AND lower(COALESCE(o.ordertype,'')) <> 'iospay_renew'
       AND (COALESCE(o.amountpaid,0)>0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,''))='code')
       AND oc.device_id IS NULL
       AND o.createtime >= c.anchor_ts AND o.createtime < add_days(c.anchor_ts, 7)
      THEN 1 ELSE 0 END) AS paid_7d,
    max(CASE
      WHEN o.orderstatus='finished'
       AND lower(COALESCE(o.ordertype,'')) <> 'iospay_renew'
       AND (COALESCE(o.amountpaid,0)>0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,''))='code')
       AND oc.device_id IS NULL
       AND o.createtime >= c.anchor_ts AND o.createtime < '2026-09-28 16:00:00'
      THEN 1 ELSE 0 END) AS paid_asof,
    max(CASE
      WHEN o.orderstatus='finished'
       AND lower(COALESCE(o.ordertype,'')) <> 'iospay_renew'
       AND (COALESCE(o.amountpaid,0)>0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,''))='code')
       AND oc.device_id IS NULL
       AND o.createtime >= c.anchor_ts AND o.createtime < add_days(c.anchor_ts, 3)
      THEN 1 ELSE 0 END) AS paid_3d
  FROM clean c
  LEFT JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted,0)=0 AND c.userid IS NOT NULL
   AND o.createtime >= '2026-09-06 16:00:00' AND o.createtime < '2026-09-28 16:00:00'
  LEFT JOIN old_customer oc ON oc.device_id = c.device_id
  GROUP BY 1
),
labeled AS (
  SELECT
    c.wk, c.ord, c.exp_group, c.device_id, c.install_day, c.ver_bucket,
    c.os_name, c.install_from,
    CASE WHEN c.userid IS NOT NULL THEN 1 ELSE 0 END AS is_reg,
    COALESCE(p.paid_7d,0) AS paid_7d,
    COALESCE(p.paid_asof,0) AS paid_asof,
    COALESCE(p.paid_3d,0) AS paid_3d
  FROM clean c
  LEFT JOIN paid_flags p ON p.device_id = c.device_id
)
-- Q1: week x group headline
SELECT 'headline' AS q, wk, exp_group,
  cast(count(*) AS VARCHAR) AS c1,
  cast(sum(is_reg) AS VARCHAR) AS c2,
  cast(round(sum(is_reg)*100.0/count(*),2) AS VARCHAR) AS c3,
  cast(sum(paid_3d) AS VARCHAR) AS c4,
  cast(round(sum(paid_3d)*100.0/count(*),3) AS VARCHAR) AS c5,
  cast(sum(paid_7d) AS VARCHAR) AS c6,
  cast(round(sum(paid_7d)*100.0/count(*),3) AS VARCHAR) AS c7,
  cast(sum(paid_asof) AS VARCHAR) AS c8,
  cast(round(sum(paid_asof)*100.0/count(*),3) AS VARCHAR) AS c9,
  NULL AS c10
FROM labeled
GROUP BY wk, exp_group, ord
UNION ALL
-- Q2: version mix share + paid7 within version for A/B
SELECT 'vermix' AS q, wk, exp_group,
  ver_bucket AS c1,
  cast(count(*) AS VARCHAR) AS c2,
  cast(round(count(*)*100.0/sum(count(*)) OVER (PARTITION BY wk, exp_group),1) AS VARCHAR) AS c3,
  cast(sum(paid_7d) AS VARCHAR) AS c4,
  cast(round(sum(paid_7d)*100.0/nullif(count(*),0),3) AS VARCHAR) AS c5,
  NULL, NULL, NULL, NULL, NULL
FROM labeled
WHERE exp_group IN ('A','B')
GROUP BY wk, exp_group, ver_bucket, ord
UNION ALL
-- Q3: install_day daily paid7 for A vs B in 0921 only + 0914 for compare
SELECT 'daily' AS q, wk, exp_group,
  install_day AS c1,
  cast(count(*) AS VARCHAR) AS c2,
  cast(sum(paid_7d) AS VARCHAR) AS c3,
  cast(round(sum(paid_7d)*100.0/count(*),3) AS VARCHAR) AS c4,
  cast(sum(is_reg) AS VARCHAR) AS c5,
  cast(round(sum(is_reg)*100.0/count(*),1) AS VARCHAR) AS c6,
  NULL, NULL, NULL, NULL
FROM labeled
WHERE wk IN ('0914','0921') AND exp_group IN ('A','B')
GROUP BY wk, exp_group, install_day, ord
UNION ALL
-- Q4: platform mix A/B
SELECT 'osmix' AS q, wk, exp_group,
  CASE
    WHEN os_name IN ('android','ios','ipados') THEN 'mobile'
    WHEN os_name IN ('windows','macos','linux','chromeos') THEN 'desktop'
    ELSE coalesce(os_name,'(null)')
  END AS c1,
  cast(count(*) AS VARCHAR) AS c2,
  cast(round(count(*)*100.0/sum(count(*)) OVER (PARTITION BY wk, exp_group),1) AS VARCHAR) AS c3,
  cast(sum(paid_7d) AS VARCHAR) AS c4,
  cast(round(sum(paid_7d)*100.0/nullif(count(*),0),3) AS VARCHAR) AS c5,
  NULL, NULL, NULL, NULL, NULL
FROM labeled
WHERE exp_group IN ('A','B')
GROUP BY 1,2,3,4, ord
ORDER BY q, wk, exp_group, c1
"""


def main() -> None:
    print("querying T049 dig...", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]

    print("\n=== HEADLINE (n, reg%, p3d n/%, p7d n/%, pasof n/%) ===", flush=True)
    print(f"{'wk':4} {'g':2} {'n':>7} {'reg%':>6} {'p3':>4} {'p3%':>7} {'p7':>4} {'p7%':>7} {'pA':>4} {'pA%':>7}", flush=True)
    for d in data:
        if d["q"] != "headline":
            continue
        print(
            f"{d['wk']:4} {d['exp_group']:2} {int(d['c1']):7d} {float(d['c3']):5.1f}% "
            f"{int(d['c4']):4d} {float(d['c5']):6.3f}% "
            f"{int(d['c6']):4d} {float(d['c7']):6.3f}% "
            f"{int(d['c8']):4d} {float(d['c9']):6.3f}%",
            flush=True,
        )

    # A-B deltas + SE
    print("\n=== A−B paid7% (pp) & ~95%CI ===", flush=True)
    by = {(d["wk"], d["exp_group"]): d for d in data if d["q"] == "headline"}
    for wk in ("0907", "0914", "0921"):
        a, b = by[(wk, "A")], by[(wk, "B")]
        na, nb = int(a["c1"]), int(b["c1"])
        pa, pb = float(a["c7"]) / 100, float(b["c7"]) / 100
        dlt = (pa - pb) * 100
        se = 100 * math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
        print(f"  {wk}: Δ={dlt:+.3f}pp  ±{1.96*se:.3f}  A_p7={int(a['c6'])} B_p7={int(b['c6'])}", flush=True)

    print("\n=== VER MIX A/B (share%, paid7 n/%) ===", flush=True)
    for d in data:
        if d["q"] != "vermix":
            continue
        print(
            f"{d['wk']:4} {d['exp_group']:2} {str(d['c1']):10} n={int(d['c2']):6d} "
            f"share={float(d['c3']):5.1f}% p7={int(d['c4']):3d} ({float(d['c5']):.3f}%)",
            flush=True,
        )

    print("\n=== DAILY A/B (0914+0921) ===", flush=True)
    for d in data:
        if d["q"] != "daily":
            continue
        print(
            f"{d['wk']:4} {d['exp_group']:2} {d['c1']} n={int(d['c2']):5d} "
            f"p7={int(d['c3']):3d} ({float(d['c4']):.3f}%) reg={float(d['c6']):.1f}%",
            flush=True,
        )

    print("\n=== OS MIX A/B ===", flush=True)
    for d in data:
        if d["q"] != "osmix":
            continue
        print(
            f"{d['wk']:4} {d['exp_group']:2} {str(d['c1']):8} n={int(d['c2']):6d} "
            f"share={float(d['c3']):5.1f}% p7={int(d['c4']):3d} ({float(d['c5']):.3f}%)",
            flush=True,
        )


if __name__ == "__main__":
    main()
