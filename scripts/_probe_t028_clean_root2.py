# -*- coding: utf-8 -*-
"""T028 residual: recent Win Chrome store — version/geo/ab/walls (no zombies)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

RECENT = """(
  TRIM(version) LIKE '1.30.%'
  OR TRIM(version) LIKE '1.31.%'
  OR TRIM(version) LIKE '1.32.%'
)"""
FILT = f"""
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND {RECENT}
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)
    return rows

# A) version_minor mix + rate (recent only)
show("A version_minor midJun vs lateAug", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    concat(split_part(TRIM(version),'.',1),'.',split_part(TRIM(version),'.',2)) AS vm,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, vm, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, vm, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM dev GROUP BY 1,2
)
SELECT a.period, a.vm, a.ni, a.rate,
  ROUND(a.ni*100.0/t.tot,1) share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) tot FROM agg GROUP BY 1) t ON a.period=t.period
WHERE a.ni >= 1000
ORDER BY a.period, a.ni DESC
""")

# B) top geos both periods + rate (recent only)
show("B top geo midJun vs lateAug", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(UPPER(TRIM(real_geo)),''),'(blank)') AS geo,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, geo, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, geo, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM dev GROUP BY 1,2
)
SELECT a.period, a.geo, a.ni, a.rate,
  ROUND(a.ni*100.0/t.tot,1) share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) tot FROM agg GROUP BY 1) t ON a.period=t.period
WHERE a.ni >= 2500
ORDER BY a.period, a.ni DESC
""")

# C) geo holdout: midJun geo rates × lateAug shares
show("C geo counterfactual (recent)", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(UPPER(TRIM(real_geo)),''),'(blank)') AS geo,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, geo, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, geo, SUM(ni) ni, SUM(act) act
  FROM dev GROUP BY 1,2
),
jun AS (SELECT geo, act*1.0/NULLIF(ni,0) AS r, ni FROM agg WHERE period='midJun'),
aug AS (SELECT geo, ni, act FROM agg WHERE period='lateAug'),
joined AS (
  SELECT a.geo, a.ni AS aug_ni, a.act AS aug_act, COALESCE(j.r, 0.5) AS jun_r
  FROM aug a LEFT JOIN jun j ON a.geo = j.geo
)
SELECT
  ROUND(SUM(aug_act)*100.0/NULLIF(SUM(aug_ni),0),2) AS late_actual,
  ROUND(SUM(aug_ni * jun_r)*100.0/NULLIF(SUM(aug_ni),0),2) AS if_jun_geo_rates,
  ROUND(SUM(aug_act)*100.0/NULLIF(SUM(aug_ni),0),2)
    - ROUND(SUM(aug_ni * jun_r)*100.0/NULLIF(SUM(aug_ni),0),2) AS within_geo_pp
FROM joined
""")
