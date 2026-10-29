# -*- coding: utf-8 -*-
"""T018 old-acct exclusion impact (1d buffer), asof=2026-09-28 baseline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql/reports/query_paywall_ab_old_acct_impact_20260929.sql").read_text(
    encoding="utf-8"
)

# 完整自然周切片（影响是否改组间排序）
SQL_WEEK = r"""
WITH cohort_beh AS (
  SELECT
    device_id,
    first_ts,
    act_uid,
    install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i', 'j') THEN 'D'
    END AS exp_group
  FROM (
    SELECT
      device_id, ab_tag, created_ts AS first_ts,
      TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
      CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-20 16:00:00' AND created_ts < '2026-09-28 16:00:00'
      AND event_name = 'translate_page' AND is_new_user_today = '1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (version >= '1.32.6' OR version LIKE '1.33.%' OR version LIKE '1.34.%'
           OR version LIKE '1.35.%' OR version LIKE '1.36.%')
  ) x
  WHERE rn = 1 AND install_day >= '2026-08-21' AND install_day < '2026-09-29'
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
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort_beh) c ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0 AND d.installtime > '1970-01-02'
  ) t WHERE rn = 1
),
base_devices AS (
  SELECT b.device_id, b.exp_group, b.first_ts, b.act_uid, b.install_day, d.userid,
    COALESCE(
      CASE WHEN d.installtime >= '2026-08-20 16:00:00'
            AND d.installtime < '2026-09-28 16:00:00' THEN d.installtime END,
      b.first_ts
    ) AS anchor_ts
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
uid_candidates AS (
  SELECT device_id, userid AS uid, first_ts FROM base_devices WHERE userid IS NOT NULL
  UNION
  SELECT device_id, act_uid, first_ts FROM base_devices WHERE act_uid IS NOT NULL
),
old_acct_device AS (
  SELECT DISTINCT u.device_id
  FROM uid_candidates u
  INNER JOIN immdata.imt_userinfo ui ON ui.id = u.uid AND COALESCE(ui.isdeleted,0)=0
  WHERE ui.createtime < date_add(day, -1, u.first_ts)
),
orders AS (
  SELECT o.userid, o.createtime,
    CASE WHEN o.orderstatus = 'finished'
          AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
          AND (COALESCE(o.amountpaid,0)>0
               OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
               OR lower(COALESCE(o.ordertype,''))='code')
         THEN 1 ELSE 0 END AS is_paid
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted,0)=0 AND o.userid IS NOT NULL
    AND o.createtime >= '2026-08-20 16:00:00' AND o.createtime < '2026-09-28 16:00:00'
),
old_customer_device AS (
  SELECT DISTINCT c.device_id
  FROM base_devices c
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid AND COALESCE(o.isdeleted,0)=0
   AND o.orderstatus='finished' AND o.createtime < c.anchor_ts
  WHERE c.userid IS NOT NULL
),
device_funnel AS (
  SELECT c.device_id,
    max(CASE WHEN o.is_paid=1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS paid_7d
  FROM base_devices c
  LEFT JOIN orders o ON o.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN old_customer_device old ON old.device_id = c.device_id
  GROUP BY 1
),
weeks AS (
  SELECT '0824_0830' AS wk, '2026-08-24' AS s, '2026-08-31' AS e
  UNION ALL SELECT '0831_0906', '2026-08-31', '2026-09-07'
  UNION ALL SELECT '0907_0913', '2026-09-07', '2026-09-14'
  UNION ALL SELECT '0914_0920', '2026-09-14', '2026-09-21'
  UNION ALL SELECT '0921_0927', '2026-09-21', '2026-09-28'
),
scoped AS (
  SELECT 'A_all' AS metric_scope, c.*, w.wk
  FROM base_devices c
  INNER JOIN weeks w ON c.install_day >= w.s AND c.install_day < w.e
  UNION ALL
  SELECT 'B_excl_old_acct', c.*, w.wk
  FROM base_devices c
  INNER JOIN weeks w ON c.install_day >= w.s AND c.install_day < w.e
  LEFT JOIN old_acct_device oa ON oa.device_id = c.device_id
  WHERE oa.device_id IS NULL
)
SELECT
  s.wk, s.metric_scope, s.exp_group,
  count(DISTINCT s.device_id) AS n,
  round(count(DISTINCT CASE WHEN s.userid IS NOT NULL THEN s.device_id END)*100.0
    / nullif(count(DISTINCT s.device_id),0), 2) AS reg_pct,
  round(count(DISTINCT CASE WHEN f.paid_7d=1 THEN s.device_id END)*100.0
    / nullif(count(DISTINCT s.device_id),0), 2) AS paid_7d_pct
FROM scoped s
LEFT JOIN device_funnel f ON f.device_id = s.device_id
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
"""


def main() -> None:
    print("=== aggregate A vs B (asof 09-28) ===", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]
    by = {(d["metric_scope"], d["exp_group"]): d for d in data}
    groups = ["A", "B", "C", "D"]
    print(
        f"{'grp':>3} {'n_A':>8} {'n_B':>8} {'excl%':>7} "
        f"{'regA':>7} {'regB':>7} {'dReg':>7} "
        f"{'p7A':>7} {'p7B':>7} {'dP7':>7} "
        f"{'pcA':>7} {'pcB':>7} {'dPc':>7} "
        f"{'old%act':>8} {'old%pay':>8}",
        flush=True,
    )
    for g in groups:
        a = by[("A_all", g)]
        b = by[("B_excl_old_acct", g)]
        n_a, n_b = int(a["new_devices"]), int(b["new_devices"])
        excl = (n_a - n_b) * 100.0 / n_a if n_a else 0
        old_n = int(a["old_acct_devices"] or 0)
        old_pay = int(a["old_acct_paid_to_asof"] or 0)
        pay_a = int(a["paid_to_asof"] or 0)
        d_reg = float(b["register_rate_pct"]) - float(a["register_rate_pct"])
        d_p7 = float(b["paid_7d_pct"]) - float(a["paid_7d_pct"])
        d_pc = float(b["paid_to_asof_pct"]) - float(a["paid_to_asof_pct"])
        print(
            f"{g:>3} {n_a:8d} {n_b:8d} {excl:6.1f}% "
            f"{float(a['register_rate_pct']):6.2f}% {float(b['register_rate_pct']):6.2f}% {d_reg:+6.2f}pp "
            f"{float(a['paid_7d_pct']):6.2f}% {float(b['paid_7d_pct']):6.2f}% {d_p7:+6.2f}pp "
            f"{float(a['paid_to_asof_pct']):6.2f}% {float(b['paid_to_asof_pct']):6.2f}% {d_pc:+6.2f}pp "
            f"{old_n*100.0/n_a:7.1f}% {old_pay*100.0/pay_a if pay_a else 0:7.1f}%",
            flush=True,
        )

    # ranking check paid_to_asof
    def rank(scope: str, key: str) -> list[str]:
        return sorted(groups, key=lambda g: -float(by[(scope, g)][key]))

    print("\n累计付费排序 A:", rank("A_all", "paid_to_asof_pct"), flush=True)
    print("累计付费排序 B:", rank("B_excl_old_acct", "paid_to_asof_pct"), flush=True)
    print("注册率排序 A:", rank("A_all", "register_rate_pct"), flush=True)
    print("注册率排序 B:", rank("B_excl_old_acct", "register_rate_pct"), flush=True)

    print("\n=== closed weeks reg / paid_7d ===", flush=True)
    cols, rows = query(SQL_WEEK)
    wdata = [dict(zip(cols, r)) for r in rows]
    weeks = sorted({d["wk"] for d in wdata})
    for wk in weeks:
        print(f"\n-- {wk} --", flush=True)
        print(
            f"{'grp':>3} {'nA':>7} {'nB':>7} {'excl%':>6} "
            f"{'regA':>7} {'regB':>7} {'dReg':>7} "
            f"{'p7A':>7} {'p7B':>7} {'dP7':>7}",
            flush=True,
        )
        for g in groups:
            a = next(d for d in wdata if d["wk"] == wk and d["metric_scope"] == "A_all" and d["exp_group"] == g)
            b = next(d for d in wdata if d["wk"] == wk and d["metric_scope"] == "B_excl_old_acct" and d["exp_group"] == g)
            n_a, n_b = int(a["n"]), int(b["n"])
            excl = (n_a - n_b) * 100.0 / n_a if n_a else 0
            d_reg = float(b["reg_pct"]) - float(a["reg_pct"])
            d_p7 = float(b["paid_7d_pct"]) - float(a["paid_7d_pct"])
            print(
                f"{g:>3} {n_a:7d} {n_b:7d} {excl:5.1f}% "
                f"{float(a['reg_pct']):6.2f}% {float(b['reg_pct']):6.2f}% {d_reg:+6.2f}pp "
                f"{float(a['paid_7d_pct']):6.2f}% {float(b['paid_7d_pct']):6.2f}% {d_p7:+6.2f}pp",
                flush=True,
            )


if __name__ == "__main__":
    main()
