# -*- coding: utf-8 -*-
"""T051: tag skew vs 3:3:2:2 + B missing pays decomp (no heavy wall join)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

SQL_TAGS = r"""
WITH act AS (
  SELECT device_id, created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    lower(trim(ab_tag)) AS tag,
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
wk AS (
  SELECT *, CASE WHEN install_day < '2026-09-21' THEN '0914' ELSE '0921' END AS week
  FROM act
),
di AS (
  SELECT device_id, userid FROM (
    SELECT d.deviceid AS device_id, d.userid,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END, d.installtime) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM wk) c ON c.device_id=d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime>'1970-01-02'
  ) x WHERE rn=1
),
base AS (
  SELECT w.*, d.userid FROM wk w LEFT JOIN di d ON d.device_id=w.device_id
),
uid_cands AS (
  SELECT device_id, userid AS uid, act_ts FROM base WHERE userid IS NOT NULL
  UNION SELECT device_id, act_uid, act_ts FROM base WHERE act_uid IS NOT NULL
),
old_acct AS (
  SELECT DISTINCT u.device_id FROM uid_cands u
  INNER JOIN immdata.imt_userinfo ui ON ui.id=u.uid AND COALESCE(ui.isdeleted,0)=0
  WHERE ui.createtime < date_add(day,-1,u.act_ts)
),
clean AS (
  SELECT b.*, CASE WHEN oa.device_id IS NOT NULL THEN 1 ELSE 0 END AS is_old
  FROM base b LEFT JOIN old_acct oa ON oa.device_id=b.device_id
)
SELECT week, tag, exp_group,
  count(*) AS n_raw,
  sum(CASE WHEN is_old=0 THEN 1 ELSE 0 END) AS n_clean
FROM clean
GROUP BY week, tag, exp_group
ORDER BY week, tag
"""

SQL_B = r"""
WITH act AS (
  SELECT device_id, created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    CASE
      WHEN version LIKE '1.32.%' THEN '1.32'
      WHEN version LIKE '1.33.1%' THEN '1.33.1'
      WHEN version LIKE '1.33.3%' THEN '1.33.3'
      WHEN version LIKE '1.33.%' THEN '1.33.other'
      ELSE 'other'
    END AS ver_b,
    lower(trim(install_from)) AS install_from,
    lower(trim(os_name)) AS os_name,
    lower(trim(ab_tag)) AS tag
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, version, install_from, os_name,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-09-13 16:00:00' AND created_ts < '2026-09-28 16:00:00'
      AND event_name='translate_page' AND is_new_user_today='1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag))=1
      AND lower(trim(ab_tag)) IN ('d','e','f')
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
  SELECT *, CASE WHEN install_day < '2026-09-21' THEN '0914' ELSE '0921' END AS week FROM act
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
  SELECT b.device_id FROM base b
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
  SELECT b.week, b.install_day, b.tag, b.ver_b,
    CASE WHEN b.userid IS NOT NULL THEN 1 ELSE 0 END AS is_reg,
    CASE WHEN p.device_id IS NOT NULL THEN 1 ELSE 0 END AS paid_7d,
    CASE WHEN b.os_name IN ('android','ios','ipados') THEN 'mobile'
         WHEN b.os_name IN ('windows','macos','linux','chromeos') THEN 'desktop'
         ELSE 'other' END AS plat,
    CASE WHEN b.install_from IN ('chrome','edge','firefox','safari','official_userscript')
         THEN b.install_from
         WHEN b.install_from IS NULL OR b.install_from='' THEN '(null)'
         ELSE 'other' END AS ch
  FROM base b LEFT JOIN pay p ON p.device_id=b.device_id
)
SELECT 'by_ch' AS q, week, ch AS dim, count(*) AS n, sum(paid_7d) AS pays,
  round(sum(paid_7d)*100.0/count(*),3) AS rate, sum(is_reg) AS regs
FROM lab GROUP BY week, ch
UNION ALL
SELECT 'by_plat', week, plat, count(*), sum(paid_7d),
  round(sum(paid_7d)*100.0/count(*),3), sum(is_reg) FROM lab GROUP BY week, plat
UNION ALL
SELECT 'by_ver', week, ver_b, count(*), sum(paid_7d),
  round(sum(paid_7d)*100.0/count(*),3), sum(is_reg) FROM lab GROUP BY week, ver_b
UNION ALL
SELECT 'by_tag', week, tag, count(*), sum(paid_7d),
  round(sum(paid_7d)*100.0/count(*),3), sum(is_reg) FROM lab GROUP BY week, tag
UNION ALL
SELECT 'by_day', week, install_day, count(*), sum(paid_7d),
  round(sum(paid_7d)*100.0/count(*),3), sum(is_reg) FROM lab GROUP BY week, install_day
UNION ALL
SELECT 'by_reg', week, cast(is_reg AS VARCHAR), count(*), sum(paid_7d),
  round(sum(paid_7d)*100.0/nullif(count(*),0),3), NULL FROM lab GROUP BY week, is_reg
ORDER BY q, week, dim
"""

# Expected hex-first-char bias (SHA256 hex id)
HEX_EXPECT = {
    "a": 2 / 16, "b": 2 / 16, "c": 2 / 16,  # 2,d / 3,e / 4,f
    "d": 1 / 16, "e": 1 / 16, "f": 1 / 16,  # 5,6,7
    "g": 1 / 16, "h": 2 / 16,  # 8 / 9,a
    "i": 1 / 16, "j": 1 / 16,  # b,c
}


def main() -> None:
    print("=== TAG COUNTS ===", flush=True)
    cols, rows = query(SQL_TAGS)
    data = [dict(zip(cols, r)) for r in rows]
    for week in ("0914", "0921"):
        subset = [d for d in data if d["week"] == week]
        total_c = sum(int(d["n_clean"]) for d in subset)
        total_r = sum(int(d["n_raw"]) for d in subset)
        print(f"\n-- {week} total_raw={total_r} total_clean={total_c}", flush=True)
        print(f"{'tag':3} {'grp':2} {'n_c':>7} {'share':>7} {'hexExp':>7} {'Δpp':>7}", flush=True)
        grp = {"A": 0, "B": 0, "C": 0, "D": 0}
        for d in sorted(subset, key=lambda x: x["tag"]):
            n = int(d["n_clean"])
            share = n / total_c * 100
            exp = HEX_EXPECT[d["tag"]] * 100
            grp[d["exp_group"]] += n
            print(
                f"{d['tag']:3} {d['exp_group']:2} {n:7d} {share:6.2f}% {exp:6.2f}% {share-exp:+6.2f}",
                flush=True,
            )
        print("groups vs theory 30/30/20/20 and hex-bias 37.5/18.75/18.75/12.5:", flush=True)
        theory = {"A": 30, "B": 30, "C": 20, "D": 20}
        hexb = {"A": 37.5, "B": 18.75, "C": 18.75, "D": 12.5}
        for g in "ABCD":
            share = grp[g] / total_c * 100
            print(
                f"  {g}: n={grp[g]} share={share:.2f}%  vs33={share-theory[g]:+.2f}pp  vsHex={share-hexb[g]:+.2f}pp",
                flush=True,
            )

    print("\n=== B DECOMP ===", flush=True)
    cols, rows = query(SQL_B)
    rows = [dict(zip(cols, r)) for r in rows]
    by = {}
    for d in rows:
        by[(d["q"], d["week"], str(d["dim"]))] = d
        print(
            f"{d['q']:7} {d['week']} {str(d['dim']):16} n={int(d['n']):6d} "
            f"pays={int(d['pays']):3d} rate={float(d['rate']):.3f}%",
            flush=True,
        )

    print("\n=== B pays bridge 0914->0921 (contribution) ===", flush=True)
    for q in ("by_ver", "by_plat", "by_ch", "by_tag", "by_day"):
        print(f" -- {q}", flush=True)
        dims = sorted({k[2] for k in by if k[0] == q})
        total_delta = 0
        for dim in dims:
            a = by.get((q, "0914", dim))
            b = by.get((q, "0921", dim))
            pa = int(a["pays"]) if a else 0
            pb = int(b["pays"]) if b else 0
            na = int(a["n"]) if a else 0
            nb = int(b["n"]) if b else 0
            ra = float(a["rate"]) / 100 if a and na else 0
            # mix: expected pays if rate held + volume change
            mix_vol = ra * nb - pa  # change from n shift at old rate
            rate_eff = pb - ra * nb  # change from rate at new n
            dlt = pb - pa
            total_delta += dlt
            if abs(dlt) >= 1 or abs(pa) >= 3 or abs(pb) >= 3:
                print(
                    f"   {dim:16} pays {pa}->{pb} (Δ{dlt:+d})  "
                    f"n {na}->{nb}  rateEff≈{rate_eff:+.1f} volEff≈{mix_vol:+.1f}",
                    flush=True,
                )
        print(f"   SUM Δpays={total_delta}", flush=True)


if __name__ == "__main__":
    main()
