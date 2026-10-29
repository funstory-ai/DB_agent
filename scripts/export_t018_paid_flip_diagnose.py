# -*- coding: utf-8 -*-
"""T018: why A paid rate flips after 09/07 basic_continue — diagnose."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Per week A/B paid under: raw P034 / excl old / excl RuleA / excl both
# Also absolute paid counts + RuleA share + old share of paid

SQL = r"""
WITH weeks AS (
  SELECT '0824_0830' AS wk, '2026-08-24' AS s, '2026-08-31' AS e, 1 AS ord
  UNION ALL SELECT '0831_0906', '2026-08-31', '2026-09-07', 2
  UNION ALL SELECT '0907_0913', '2026-09-07', '2026-09-14', 3
  UNION ALL SELECT '0914_0920', '2026-09-14', '2026-09-21', 4
  UNION ALL SELECT '0921_0927', '2026-09-21', '2026-09-28', 5
),
act AS (
  SELECT
    device_id,
    created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    lower(trim(ab_tag)) AS ab_tag,
    lower(trim(install_from)) AS install_from,
    lower(trim(os_name)) AS os_name,
    trim(browser_name) AS browser_name,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i','j') THEN 'D'
    END AS exp_group
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, install_from, os_name, browser_name,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-20 16:00:00' AND created_ts < '2026-09-28 16:00:00'
      AND event_name = 'translate_page' AND is_new_user_today = '1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (version >= '1.32.6' OR version LIKE '1.33.%' OR version LIKE '1.34.%'
           OR version LIKE '1.35.%' OR version LIKE '1.36.%')
  ) t
  WHERE rn = 1
    AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) >= '2026-08-24'
    AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) < '2026-09-28'
),
cohort AS (
  SELECT a.*, w.wk, w.ord,
    CASE
      WHEN a.install_from = 'official_userscript'
       AND (
         (a.os_name = 'ios' AND a.browser_name = 'Safari')
         OR (a.os_name = 'macos' AND a.browser_name = 'Maxthon')
       )
      THEN 1 ELSE 0
    END AS is_rule_a
  FROM act a
  INNER JOIN weeks w
    ON a.install_day >= w.s AND a.install_day < w.e
),
di AS (
  SELECT device_id, userid, installtime
  FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY
          CASE WHEN d.userid IS NOT NULL
                AND d.installtime >= '2026-08-20 16:00:00'
                AND d.installtime < '2026-09-28 16:00:00' THEN 0
               WHEN d.userid IS NOT NULL THEN 1 ELSE 2 END,
          d.installtime
      ) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort) c ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime > '1970-01-02'
  ) x WHERE rn = 1
),
base AS (
  SELECT
    c.*,
    d.userid,
    COALESCE(
      CASE WHEN d.installtime >= '2026-08-20 16:00:00'
            AND d.installtime < '2026-09-28 16:00:00' THEN d.installtime END,
      c.act_ts
    ) AS anchor_ts
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
old_customer AS (
  SELECT DISTINCT b.device_id
  FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = b.userid AND COALESCE(o.isdeleted,0)=0
   AND o.orderstatus = 'finished' AND o.createtime < b.anchor_ts
  WHERE b.userid IS NOT NULL
),
paid AS (
  SELECT b.device_id,
    max(CASE
      WHEN o.orderstatus = 'finished'
       AND lower(COALESCE(o.ordertype,'')) <> 'iospay_renew'
       AND (COALESCE(o.amountpaid,0) > 0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,'')) = 'code')
       AND oc.device_id IS NULL
       AND o.createtime >= b.anchor_ts
       AND o.createtime < add_days(b.anchor_ts, 7)
      THEN 1 ELSE 0 END) AS paid_7d,
    max(CASE
      WHEN o.orderstatus = 'finished'
       AND lower(COALESCE(o.ordertype,'')) <> 'iospay_renew'
       AND (COALESCE(o.amountpaid,0) > 0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,'')) = 'code')
       AND oc.device_id IS NULL
       AND o.createtime >= b.anchor_ts
       AND o.createtime < '2026-09-28 16:00:00'
      THEN 1 ELSE 0 END) AS paid_asof
  FROM base b
  LEFT JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = b.userid AND COALESCE(o.isdeleted,0)=0
   AND b.userid IS NOT NULL
   AND o.createtime >= '2026-08-20 16:00:00'
   AND o.createtime < '2026-09-28 16:00:00'
  LEFT JOIN old_customer oc ON oc.device_id = b.device_id
  GROUP BY 1
),
labeled AS (
  SELECT
    b.wk, b.ord, b.exp_group, b.device_id,
    b.is_rule_a,
    CASE WHEN oa.device_id IS NOT NULL THEN 1 ELSE 0 END AS is_old,
    COALESCE(p.paid_7d, 0) AS paid_7d,
    COALESCE(p.paid_asof, 0) AS paid_asof,
    CASE WHEN b.userid IS NOT NULL THEN 1 ELSE 0 END AS is_reg
  FROM base b
  LEFT JOIN old_acct oa ON oa.device_id = b.device_id
  LEFT JOIN paid p ON p.device_id = b.device_id
)
SELECT
  wk, exp_group,
  count(*) AS n,
  sum(is_rule_a) AS n_rule_a,
  round(sum(is_rule_a)*100.0/count(*), 2) AS rule_a_pct,
  sum(is_old) AS n_old,
  round(sum(is_old)*100.0/count(*), 2) AS old_pct,
  sum(is_reg) AS n_reg,
  round(sum(is_reg)*100.0/count(*), 2) AS reg_pct,
  -- raw
  sum(paid_7d) AS paid7_raw,
  round(sum(paid_7d)*100.0/count(*), 3) AS paid7_raw_pct,
  sum(paid_asof) AS paid_asof_raw,
  round(sum(paid_asof)*100.0/count(*), 3) AS paid_asof_raw_pct,
  -- excl old
  sum(CASE WHEN is_old=0 THEN 1 ELSE 0 END) AS n_ex_old,
  sum(CASE WHEN is_old=0 THEN paid_7d ELSE 0 END) AS paid7_ex_old,
  round(sum(CASE WHEN is_old=0 THEN paid_7d ELSE 0 END)*100.0
    / nullif(sum(CASE WHEN is_old=0 THEN 1 ELSE 0 END),0), 3) AS paid7_ex_old_pct,
  sum(CASE WHEN is_old=0 THEN paid_asof ELSE 0 END) AS paid_asof_ex_old,
  round(sum(CASE WHEN is_old=0 THEN paid_asof ELSE 0 END)*100.0
    / nullif(sum(CASE WHEN is_old=0 THEN 1 ELSE 0 END),0), 3) AS paid_asof_ex_old_pct,
  -- excl RuleA
  sum(CASE WHEN is_rule_a=0 THEN 1 ELSE 0 END) AS n_ex_ra,
  sum(CASE WHEN is_rule_a=0 THEN paid_7d ELSE 0 END) AS paid7_ex_ra,
  round(sum(CASE WHEN is_rule_a=0 THEN paid_7d ELSE 0 END)*100.0
    / nullif(sum(CASE WHEN is_rule_a=0 THEN 1 ELSE 0 END),0), 3) AS paid7_ex_ra_pct,
  -- excl old + RuleA
  sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN 1 ELSE 0 END) AS n_clean,
  sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN paid_7d ELSE 0 END) AS paid7_clean,
  round(sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN paid_7d ELSE 0 END)*100.0
    / nullif(sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN 1 ELSE 0 END),0), 3) AS paid7_clean_pct,
  sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN paid_asof ELSE 0 END) AS paid_asof_clean,
  round(sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN paid_asof ELSE 0 END)*100.0
    / nullif(sum(CASE WHEN is_old=0 AND is_rule_a=0 THEN 1 ELSE 0 END),0), 3) AS paid_asof_clean_pct,
  -- paid composition
  sum(CASE WHEN paid_asof=1 AND is_old=1 THEN 1 ELSE 0 END) AS paid_asof_from_old,
  sum(CASE WHEN paid_asof=1 AND is_rule_a=1 THEN 1 ELSE 0 END) AS paid_asof_from_ra
FROM labeled
WHERE exp_group IN ('A','B')
GROUP BY wk, exp_group, ord
ORDER BY ord, exp_group
"""


def se_pct(p: float, n: int) -> float:
    """percentage-point SE for proportion p in percent."""
    if n <= 0:
        return float("nan")
    q = p / 100.0
    return 100.0 * math.sqrt(q * (1 - q) / n)


def main() -> None:
    print("querying weekly A/B paid under filters...", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]
    by = {(d["wk"], d["exp_group"]): d for d in data}

    print(
        f"{'wk':10} {'g':2} {'n':>7} {'ra%':>5} {'old%':>5} {'reg%':>6} "
        f"{'p7':>5} {'p7%':>7} {'pA':>5} {'pA%':>7} "
        f"{'p7xo%':>7} {'p7xr%':>7} {'p7cl%':>7} {'pAcl%':>7} "
        f"{'pA_old':>6} {'pA_ra':>5}",
        flush=True,
    )
    for wk in ["0824_0830", "0831_0906", "0907_0913", "0914_0920", "0921_0927"]:
        for g in ("A", "B"):
            d = by[(wk, g)]
            print(
                f"{wk:10} {g:2} {int(d['n']):7d} {float(d['rule_a_pct']):5.1f} "
                f"{float(d['old_pct']):5.1f} {float(d['reg_pct']):5.1f}% "
                f"{int(d['paid7_raw']):5d} {float(d['paid7_raw_pct']):6.3f}% "
                f"{int(d['paid_asof_raw']):5d} {float(d['paid_asof_raw_pct']):6.3f}% "
                f"{float(d['paid7_ex_old_pct']):6.3f}% {float(d['paid7_ex_ra_pct']):6.3f}% "
                f"{float(d['paid7_clean_pct']):6.3f}% {float(d['paid_asof_clean_pct']):6.3f}% "
                f"{int(d['paid_asof_from_old']):6d} {int(d['paid_asof_from_ra']):5d}",
                flush=True,
            )

    print("\n=== A−B paid_asof_pct (pp) & rough 1.96*SE of difference ===", flush=True)
    print(f"{'wk':10} {'rawΔ':>7} {'~95%±':>7} {'xoΔ':>7} {'xrΔ':>7} {'clΔ':>7} {'winner':>8}", flush=True)
    for wk in ["0824_0830", "0831_0906", "0907_0913", "0914_0920", "0921_0927"]:
        a, b = by[(wk, "A")], by[(wk, "B")]
        def delta(ka, kb, na, nb):
            pa, pb = float(a[ka]), float(b[kb])
            na, nb = int(a[na]), int(b[nb])
            dlt = pa - pb
            se = math.sqrt(se_pct(pa, na) ** 2 + se_pct(pb, nb) ** 2)
            return dlt, 1.96 * se

        d_raw, ci_raw = delta("paid_asof_raw_pct", "paid_asof_raw_pct", "n", "n")
        d_xo, _ = delta("paid_asof_ex_old_pct", "paid_asof_ex_old_pct", "n_ex_old", "n_ex_old")
        # ex_ra uses paid7 for speed having paid_asof_ex_ra - we only have paid7_ex_ra and paid_asof_clean
        d_cl, ci_cl = delta("paid_asof_clean_pct", "paid_asof_clean_pct", "n_clean", "n_clean")
        # approximate xr using paid7
        d_xr = float(a["paid7_ex_ra_pct"]) - float(b["paid7_ex_ra_pct"])
        win = "A" if d_raw > 0 else ("B" if d_raw < 0 else "=")
        sig = "ns" if abs(d_raw) < ci_raw else "sig?"
        print(
            f"{wk:10} {d_raw:+6.3f} {ci_raw:6.3f} {d_xo:+6.3f} {d_xr:+6.3f} {d_cl:+6.3f} "
            f"{win}/{sig}",
            flush=True,
        )


if __name__ == "__main__":
    main()
