# -*- coding: utf-8 -*-
"""T055: deeper field dig on orders+behaviour for BCD p7 0831 vs 0907."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

SQL = r"""
WITH weeks AS (
  SELECT '0831' AS wk, '2026-08-31' AS s, '2026-09-07' AS e
  UNION ALL SELECT '0907', '2026-09-07', '2026-09-14'
),
act AS (
  SELECT device_id, created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i','j') THEN 'D'
    END AS exp_group,
    lower(trim(COALESCE(campaign,''))) AS campaign,
    lower(trim(COALESCE(browser_name,''))) AS browser_name,
    lower(trim(COALESCE(target_language,''))) AS to_lan,
    lower(trim(COALESCE(interface_language,''))) AS ui_lang,
    lower(trim(COALESCE(real_geo,''))) AS geo,
    version
  FROM (
    SELECT device_id, created_ts, ex_int_arg1, ab_tag, campaign, browser_name,
      target_language, interface_language, real_geo, version,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-30 16:00:00' AND created_ts < '2026-09-14 16:00:00'
      AND event_name='translate_page' AND is_new_user_today='1'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag))=1
      AND lower(trim(ab_tag)) BETWEEN 'd' AND 'j'
      AND (
        TRY_CAST(split_part(version,'.',1) AS INT) > 1
        OR (TRY_CAST(split_part(version,'.',1) AS INT)=1
            AND (TRY_CAST(split_part(version,'.',2) AS INT)>32
                 OR (TRY_CAST(split_part(version,'.',2) AS INT)=32
                     AND TRY_CAST(split_part(version,'.',3) AS INT)>=6)))
      )
  ) t WHERE rn=1
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) >= '2026-08-31'
    AND CAST(to_date(add_hours(created_ts,8)) AS VARCHAR) < '2026-09-14'
),
cohort AS (
  SELECT a.*, w.wk FROM act a
  INNER JOIN weeks w ON a.install_day >= w.s AND a.install_day < w.e
  WHERE a.exp_group IS NOT NULL
),
di AS (
  SELECT device_id, userid, installtime FROM (
    SELECT d.deviceid AS device_id, d.userid, d.installtime,
      row_number() OVER (PARTITION BY d.deviceid ORDER BY
        CASE WHEN d.userid IS NOT NULL AND d.installtime >= '2026-08-30 16:00:00'
              AND d.installtime < '2026-09-14 16:00:00' THEN 0
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
            AND d.installtime < '2026-09-14 16:00:00' THEN d.installtime END,
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
-- first paid order in 7d (T018 is_paid definition)
first_paid AS (
  SELECT * FROM (
    SELECT
      b.wk, b.exp_group, b.device_id, b.userid, b.anchor_ts,
      b.campaign, b.browser_name, b.to_lan, b.ui_lang, b.geo, b.version,
      o.id AS order_id,
      o.createtime AS pay_ts,
      lower(trim(COALESCE(o.ordertype,''))) AS ordertype,
      lower(trim(COALESCE(o.membership,''))) AS membership,
      lower(trim(COALESCE(o.membertype,''))) AS membertype,
      lower(trim(COALESCE(o.subscriptiontype,''))) AS subscriptiontype,
      lower(trim(COALESCE(o.currency,''))) AS currency,
      lower(trim(COALESCE(o.operator,''))) AS operator,
      lower(trim(COALESCE(o.couponname,''))) AS couponname,
      lower(trim(COALESCE(o.promotioncodeid,''))) AS promo,
      lower(trim(COALESCE(o.dateperiod,''))) AS dateperiod,
      o.amountpaid,
      o.amount,
      o.subscriptionday,
      o.subscriptiongoodsid,
      o.priceid,
      CASE WHEN COALESCE(o.amountpaid,0)>0 THEN 'cash'
           WHEN lower(COALESCE(o.ordertype,''))='code' THEN 'code'
           WHEN CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%' THEN 'onetime'
           ELSE 'other_paid'
      END AS pay_kind,
      row_number() OVER (PARTITION BY b.device_id ORDER BY o.createtime, o.id) AS rn
    FROM base b
    INNER JOIN immdata.imt_subscriptiongoodsorder o
      ON o.userid=b.userid AND COALESCE(o.isdeleted,0)=0 AND b.userid IS NOT NULL
     AND o.orderstatus='finished'
     AND lower(COALESCE(o.ordertype,''))<>'iospay_renew'
     AND (COALESCE(o.amountpaid,0)>0
          OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
          OR lower(COALESCE(o.ordertype,''))='code')
     AND o.createtime >= b.anchor_ts AND o.createtime < add_days(b.anchor_ts,7)
     AND o.createtime >= '2026-08-30 16:00:00'
     AND o.createtime < '2026-09-14 16:00:00'
    LEFT JOIN old_customer oc ON oc.device_id=b.device_id
    WHERE oc.device_id IS NULL
  ) x WHERE rn=1
)
SELECT 'ordertype' AS q, wk, ordertype AS dim, count(*) AS n FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'pay_kind', wk, pay_kind, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'membership', wk, nullif(membership,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'membertype', wk, nullif(membertype,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'subtype', wk, nullif(subscriptiontype,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'currency', wk, nullif(currency,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'operator', wk, nullif(operator,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'coupon', wk, CASE WHEN couponname IS NULL OR couponname='' THEN '(none)' ELSE couponname END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'promo', wk, CASE WHEN promo IS NULL OR promo='' THEN '(none)' ELSE substr(promo,1,40) END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'dateperiod', wk, nullif(dateperiod,''), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'subday', wk, cast(subscriptionday AS VARCHAR), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'amt_bucket', wk,
  CASE
    WHEN amountpaid IS NULL OR amountpaid=0 THEN '0'
    WHEN amountpaid < 500 THEN '1_499'
    WHEN amountpaid < 2000 THEN '500_1999'
    WHEN amountpaid < 5000 THEN '2000_4999'
    WHEN amountpaid < 20000 THEN '5000_19999'
    ELSE '20000+'
  END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'goodsid', wk, cast(subscriptiongoodsid AS VARCHAR), count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'campaign', wk, CASE WHEN campaign IS NULL OR campaign='' THEN '(none)' ELSE substr(campaign,1,40) END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'browser', wk, CASE WHEN browser_name IS NULL OR browser_name='' THEN '(none)' ELSE substr(browser_name,1,30) END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'geo', wk, CASE WHEN geo IS NULL OR geo='' THEN '(none)' ELSE geo END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
SELECT 'to_lan', wk, CASE WHEN to_lan IS NULL OR to_lan='' THEN '(none)' ELSE to_lan END, count(*) FROM first_paid GROUP BY 1,2,3
UNION ALL
-- denom campaign share for context (BCD activate)
SELECT 'den_campaign' AS q, wk,
  CASE WHEN campaign IS NULL OR campaign='' THEN '(none)' ELSE substr(campaign,1,40) END,
  count(*)
FROM base GROUP BY 1,2,3
UNION ALL
SELECT 'grp_pay', wk, exp_group, count(*) FROM first_paid GROUP BY 1,2,3
ORDER BY q, wk, n DESC
"""


def main() -> None:
    print("querying deep fields 0831 vs 0907 BCD payers...", flush=True)
    cols, rows = query(SQL)
    data = [dict(zip(cols, r)) for r in rows]

    # build wk-dim maps per q
    from collections import defaultdict

    by = defaultdict(dict)  # (q,dim) -> {wk: n}
    for d in data:
        dim = str(d["dim"]) if d["dim"] is not None else "(null)"
        by[(d["q"], dim)][d["wk"]] = int(d["n"])

    focus = [
        "grp_pay", "pay_kind", "ordertype", "membership", "membertype", "subtype",
        "currency", "operator", "coupon", "promo", "dateperiod", "subday",
        "amt_bucket", "goodsid", "campaign", "browser", "geo", "to_lan",
    ]
    for q in focus:
        print(f"\n=== {q} (dim | 0831 | 0907 | Δ) ===", flush=True)
        dims = sorted({k[1] for k in by if k[0] == q})
        rows_out = []
        for dim in dims:
            n1 = by[(q, dim)].get("0831", 0)
            n2 = by[(q, dim)].get("0907", 0)
            if n1 + n2 >= 3:
                rows_out.append((n2 - n1, n2, n1, dim))
        rows_out.sort(reverse=True)
        for dlt, n2, n1, dim in rows_out[:25]:
            print(f"  {dim:40} {n1:4d} -> {n2:4d}  (Δ{dlt:+d})", flush=True)

    print("\n=== den_campaign top by Δ (denominator, not just payers) ===", flush=True)
    dims = sorted({k[1] for k in by if k[0] == "den_campaign"})
    rows_out = []
    for dim in dims:
        n1 = by[("den_campaign", dim)].get("0831", 0)
        n2 = by[("den_campaign", dim)].get("0907", 0)
        if n1 + n2 >= 500:
            rows_out.append((n2 - n1, n2, n1, dim))
    rows_out.sort(reverse=True)
    for dlt, n2, n1, dim in rows_out[:20]:
        print(f"  {dim:40} {n1:6d} -> {n2:6d}  (Δ{dlt:+d})", flush=True)


if __name__ == "__main__":
    main()
