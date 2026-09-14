# -*- coding: utf-8 -*-
"""Recent-version decline: same-version, geo hold, os, channel."""
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

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# A) Overall recent-only midJun vs lateAug
show("A recent-only overall", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2
)
SELECT period, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")

# B) By OS recent-only
show("B recent-only by OS", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    LOWER(TRIM(os_name)) AS os,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, os, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, os, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM dev GROUP BY 1,2
)
SELECT a.period, a.os, a.ni, a.act, a.rate,
  ROUND(a.ni*100.0/t.tot,1) share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) tot FROM agg GROUP BY 1) t ON a.period=t.period
WHERE a.ni >= 2000
ORDER BY a.period, a.ni DESC
""")

# C) Exact same patch versions present in BOTH periods — rate change
show("C same patch version both periods", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    TRIM(version) AS ver,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, ver, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, ver, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM dev GROUP BY 1,2
  HAVING SUM(ni) >= 1500
)
SELECT
  j.ver,
  j.ni AS jun_ni, j.rate AS jun_rate,
  a.ni AS aug_ni, a.rate AS aug_rate,
  ROUND(a.rate - j.rate, 2) AS d_rate
FROM agg j
INNER JOIN agg a ON j.ver = a.ver AND j.period='midJun' AND a.period='lateAug'
ORDER BY j.ni DESC
""")

# D) Win Chrome store recent: geo midJun vs lateAug
show("D Win Chrome store recent by geo", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(real_geo),''),'(blank)') AS geo,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name))='windows'
    AND TRIM(browser_name)='Chrome'
    AND LOWER(TRIM(install_from))='chrome_store'
    AND version <> '1.11.4' AND {RECENT}
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
SELECT a.period, a.geo, a.ni, a.act, a.rate,
  ROUND(a.ni*100.0/t.tot,1) share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) tot FROM agg GROUP BY 1) t ON a.period=t.period
WHERE a.ni >= 2000
ORDER BY a.period, a.ni DESC
""")

# E) Hold geo mix: apply midJun geo shares to lateAug geo rates (Win Chrome store recent)
# Manual from output later; also compute lateAug rate if use only geos stable
show("E Win Chrome recent overall + top geos rate delta", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(real_geo),''),'(blank)') AS geo,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name))='windows'
    AND TRIM(browser_name)='Chrome'
    AND LOWER(TRIM(install_from))='chrome_store'
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, geo, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, geo, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2
),
jun AS (SELECT geo, ni, act, act*1.0/NULLIF(ni,0) rate FROM agg WHERE period='midJun'),
aug AS (SELECT geo, ni, act, act*1.0/NULLIF(ni,0) rate FROM agg WHERE period='lateAug')
SELECT
  (SELECT ROUND(SUM(act)*100.0/SUM(ni),2) FROM agg WHERE period='midJun') AS jun_rate,
  (SELECT ROUND(SUM(act)*100.0/SUM(ni),2) FROM agg WHERE period='lateAug') AS aug_rate,
  -- counterfactual: lateAug rates × midJun geo weights
  ROUND(SUM(j.ni * a.rate)*100.0 / NULLIF(SUM(j.ni),0), 2) AS aug_rate_if_jun_geo_mix,
  -- counterfactual: midJun rates × lateAug geo weights  
  ROUND(SUM(a.ni * j.rate)*100.0 / NULLIF(SUM(a.ni),0), 2) AS jun_rate_if_aug_geo_mix
FROM jun j
INNER JOIN aug a ON j.geo = a.geo
""")
