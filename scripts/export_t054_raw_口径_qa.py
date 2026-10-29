# -*- coding: utf-8 -*-
"""T054: raw-data /口径 dig for BCD 7d paid sync anomaly."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Reproduce T048 knives; audit numerator composition + maturity truncation + dupes

SQL = r"""
WITH weeks AS (
  SELECT '0831' AS wk, '2026-08-31' AS s, '2026-09-07' AS e
  UNION ALL SELECT '0907', '2026-09-07', '2026-09-14'
  UNION ALL SELECT '0914', '2026-09-14', '2026-09-21'
  UNION ALL SELECT '0921', '2026-09-21', '2026-09-28'
),
act AS (
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
    version
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, version,
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
  ) t WHERE rn=1
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) >= '2026-08-31'
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
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-08-30 16:00:00'
              AND d.installtime < '2026-09-28 16:00:00' THEN 0
             WHEN d.userid IS NOT NULL THEN 1 ELSE 2 END, d.installtime) rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort) c ON c.device_id=d.deviceid
    WHERE COALESCE(d.isdeleted,0)=0 AND d.installtime>'1970-01-02'
  ) x WHERE rn=1
),
base0 AS (
  SELECT c.*, d.userid, d.installtime AS di_install,
    COALESCE(
      CASE WHEN d.installtime >= '2026-08-30 16:00:00'
            AND d.installtime < '2026-09-28 16:00:00' THEN d.installtime END,
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
  SELECT b.*,
    CASE WHEN oa.device_id IS NOT NULL THEN 1 ELSE 0 END AS is_old,
    date_diff('hour', b.act_ts, b.anchor_ts) AS anchor_lag_h
  FROM base0 b LEFT JOIN old_acct oa ON oa.device_id=b.device_id
),
-- all finished orders in window for these userids (for composition)
ord_raw AS (
  SELECT
    b.wk, b.exp_group, b.device_id, b.anchor_ts, b.act_ts, b.is_old, b.install_day,
    o.id AS order_id,
    o.createtime AS pay_ts,
    o.ordertype,
    o.amountpaid,
    o.orderstatus,
    CASE WHEN lower(COALESCE(o.ordertype,''))='iospay_renew' THEN 1 ELSE 0 END AS is_renew,
    CASE WHEN lower(COALESCE(o.ordertype,''))='code' THEN 1 ELSE 0 END AS is_code,
    CASE WHEN CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%' THEN 1 ELSE 0 END AS is_onetime,
    CASE WHEN COALESCE(o.amountpaid,0)>0 THEN 1 ELSE 0 END AS has_cash,
    CASE
      WHEN o.orderstatus='finished'
       AND lower(COALESCE(o.ordertype,''))<>'iospay_renew'
       AND (COALESCE(o.amountpaid,0)>0
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            OR lower(COALESCE(o.ordertype,''))='code')
      THEN 1 ELSE 0
    END AS is_paid_flag,
    date_diff('hour', b.anchor_ts, o.createtime) AS hours_after_anchor,
    CASE WHEN add_days(b.anchor_ts,7) <= '2026-09-28 16:00:00' THEN 1 ELSE 0 END AS mature7_at_asof928
  FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = b.userid AND COALESCE(o.isdeleted,0)=0 AND b.userid IS NOT NULL
   AND o.createtime >= b.anchor_ts
   AND o.createtime < add_days(b.anchor_ts, 7)
   AND o.createtime >= '2026-08-30 16:00:00'
   AND o.createtime < '2026-09-28 16:00:00'
  WHERE b.is_old = 0
),
old_customer AS (
  SELECT DISTINCT b.device_id FROM base b
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid=b.userid AND COALESCE(o.isdeleted,0)=0
   AND o.orderstatus='finished' AND o.createtime < b.anchor_ts
  WHERE b.userid IS NOT NULL AND b.is_old=0
),
paid_dev AS (
  SELECT r.wk, r.exp_group, r.device_id, r.install_day, r.mature7_at_asof928,
    min(r.pay_ts) AS first_pay_ts,
    max(r.has_cash) AS any_cash,
    max(r.is_code) AS any_code,
    max(r.is_onetime) AS any_onetime,
    max(r.is_renew) AS any_renew_in_window,
    count(*) AS n_orders_7d,
    count(DISTINCT r.order_id) AS n_order_ids,
    sum(CASE WHEN r.is_paid_flag=1 THEN 1 ELSE 0 END) AS n_paid_flag_orders,
    min(r.hours_after_anchor) AS hours_to_first_order
  FROM ord_raw r
  LEFT JOIN old_customer oc ON oc.device_id=r.device_id
  WHERE r.is_paid_flag=1 AND oc.device_id IS NULL
  GROUP BY 1,2,3,4,5
)
-- A1 pay mix
SELECT 'pay_mix' AS q, wk, exp_group AS dim,
  cast(count(*) AS VARCHAR) AS c1,
  cast(sum(any_cash) AS VARCHAR) AS c2,
  cast(sum(CASE WHEN any_cash=0 AND any_code=1 THEN 1 ELSE 0 END) AS VARCHAR) AS c3,
  cast(sum(CASE WHEN any_cash=0 AND any_code=0 AND any_onetime=1 THEN 1 ELSE 0 END) AS VARCHAR) AS c4,
  cast(sum(CASE WHEN n_paid_flag_orders>=2 THEN 1 ELSE 0 END) AS VARCHAR) AS c5,
  cast(round(avg(n_paid_flag_orders),2) AS VARCHAR) AS c6,
  cast(sum(CASE WHEN hours_to_first_order < 0 THEN 1 ELSE 0 END) AS VARCHAR) AS c7
FROM paid_dev GROUP BY wk, exp_group

UNION ALL
-- A2 denom
SELECT 'denom', wk, exp_group,
  cast(count(*) AS VARCHAR),
  cast(sum(is_old) AS VARCHAR),
  cast(sum(CASE WHEN userid IS NOT NULL THEN 1 ELSE 0 END) AS VARCHAR),
  cast(sum(CASE WHEN anchor_lag_h < 0 THEN 1 ELSE 0 END) AS VARCHAR),
  cast(sum(CASE WHEN anchor_lag_h > 24 THEN 1 ELSE 0 END) AS VARCHAR),
  cast(sum(CASE WHEN add_days(anchor_ts,7) > '2026-09-28 16:00:00' THEN 1 ELSE 0 END) AS VARCHAR),
  cast(round(avg(CASE WHEN is_old=0 THEN anchor_lag_h END),1) AS VARCHAR)
FROM base GROUP BY wk, exp_group

UNION ALL
-- A3 multi device
SELECT 'multi_dev', wk, exp_group,
  cast(count(*) AS VARCHAR),
  cast(count(DISTINCT userid) AS VARCHAR),
  cast(sum(CASE WHEN cnt_dev>=2 THEN 1 ELSE 0 END) AS VARCHAR),
  '0','0','0','0'
FROM (
  SELECT b.wk, b.exp_group, b.userid, count(DISTINCT b.device_id) AS cnt_dev
  FROM base b INNER JOIN paid_dev p ON p.device_id=b.device_id
  WHERE b.is_old=0 AND b.userid IS NOT NULL
  GROUP BY 1,2,3
) x GROUP BY wk, exp_group

UNION ALL
-- A4 mature cmp via paid_dev flags + base counts joined simply
SELECT 'mature_cmp', b.wk, b.exp_group,
  cast(count(*) AS VARCHAR),
  cast(sum(CASE WHEN add_days(b.anchor_ts,7)<='2026-09-28 16:00:00' THEN 1 ELSE 0 END) AS VARCHAR),
  cast(count(p.device_id) AS VARCHAR),
  cast(sum(CASE WHEN p.device_id IS NOT NULL AND p.mature7_at_asof928=1 THEN 1 ELSE 0 END) AS VARCHAR),
  '0','0','0'
FROM base b
LEFT JOIN paid_dev p ON p.device_id=b.device_id
WHERE b.is_old=0
GROUP BY b.wk, b.exp_group

UNION ALL
-- A5 cash vs all paid rates need denom — emit counts only; rate in python
SELECT 'cash_only', wk, exp_group,
  cast(count(*) AS VARCHAR),
  cast(sum(any_cash) AS VARCHAR),
  cast(sum(CASE WHEN any_cash=0 THEN 1 ELSE 0 END) AS VARCHAR),
  '0','0','0','0'
FROM paid_dev GROUP BY wk, exp_group

ORDER BY q, dim, wk
"""


def main() -> None:
    print("querying raw/口径 QA...", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]

    print("\n=== DENOM QA (n, old, reg, anchor<0, anchor>24h, immature7_n, avg_lag_h) ===", flush=True)
    for d in data:
        if d["q"] != "denom":
            continue
        print(
            f"{d['wk']} {d['dim']}: n={d['c1']} old={d['c2']} reg={d['c3']} "
            f"anchorNeg={d['c4']} lag>24h={d['c5']} immature7={d['c6']} avgLagH={d['c7']}",
            flush=True,
        )

    print("\n=== PAY MIX among 7d paid devices (n, cash, code-only, onetime-only, multiOrder, avgOrders, negHour) ===", flush=True)
    for d in data:
        if d["q"] != "pay_mix":
            continue
        print(
            f"{d['wk']} {d['dim']}: paidDev={d['c1']} cash={d['c2']} codeOnly={d['c3']} "
            f"onetimeOnly={d['c4']} multiOrdDev={d['c5']} avgOrd={d['c6']} negHour={d['c7']}",
            flush=True,
        )

    print("\n=== CASH vs NON-CASH among paid devices ===", flush=True)
    denom = {(d["wk"], d["dim"]): d for d in data if d["q"] == "denom"}
    for d in data:
        if d["q"] != "cash_only":
            continue
        n = int(denom[(d["wk"], d["dim"])]["c1"]) - int(denom[(d["wk"], d["dim"])]["c2"])  # rough: use clean
        # denom c1=all including old; better recompute from mature - use paid counts only
        paid, cash, noncash = int(d["c1"]), int(d["c2"]), int(d["c3"])
        print(
            f"{d['wk']} {d['dim']}: paidDev={paid} cash={cash} nonCash={noncash} "
            f"nonCashShare={noncash/paid*100 if paid else 0:.1f}%",
            flush=True,
        )

    print("\n=== MULTI DEVICE same userid credited ===", flush=True)
    for d in data:
        if d["q"] != "multi_dev":
            continue
        print(
            f"{d['wk']} {d['dim']}: paidUserRows={d['c1']} distinctUid={d['c2']} uidWith2+Dev={d['c3']}",
            flush=True,
        )

    print("\n=== MATURE7 subset vs all (asof928 truncation) ===", flush=True)
    for d in data:
        if d["q"] != "mature_cmp":
            continue
        n_all, n_m7 = int(d["c1"]), int(d["c2"])
        p_all, p_m7 = int(d["c3"]), int(d["c4"])
        r_all = p_all * 100 / n_all if n_all else 0
        r_m7 = p_m7 * 100 / n_m7 if n_m7 else 0
        print(
            f"{d['wk']} {d['dim']}: all n={n_all} p7={p_all} ({r_all:.3f}%) | "
            f"mature7 n={n_m7} p7={p_m7} ({r_m7:.3f}%) Δr={r_m7-r_all:+.3f}pp",
            flush=True,
        )


if __name__ == "__main__":
    main()
