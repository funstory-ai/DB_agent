# -*- coding: utf-8 -*-
"""Quantify low-version + HK contribution; cross geo×ver."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

FILT = """
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND version <> '1.11.4'
"""

# bucket: good = 1.30+ or 1.31+ or 1.32+; zombie = known low-rate olds
show_sql = f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN TRIM(version) IN ('1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7') THEN 'zombie_old'
      WHEN TRIM(version) LIKE '1.32.%' OR TRIM(version) LIKE '1.31.%' OR TRIM(version) LIKE '1.30.%' THEN 'recent_1_30plus'
      ELSE 'other'
    END AS ver_bucket,
    COALESCE(NULLIF(TRIM(real_geo),''),'(blank)') AS geo,
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
  SELECT period, ver_bucket, geo, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3,4
)
SELECT period, ver_bucket,
  SUM(ni) AS ni, SUM(act) AS act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) AS rate
FROM dev
GROUP BY 1,2
ORDER BY 1,2
"""

print("=== ver_bucket ===", flush=True)
cols, rows = query(show_sql)
print("\t".join(cols), flush=True)
for r in rows:
    print("\t".join(str(x) for x in r), flush=True)

# HK × ver_bucket lateAug
sql_hk = f"""
WITH base AS (
  SELECT
    CASE
      WHEN TRIM(version) IN ('1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7') THEN 'zombie_old'
      WHEN TRIM(version) LIKE '1.32.%' OR TRIM(version) LIKE '1.31.%' OR TRIM(version) LIKE '1.30.%' THEN 'recent_1_30plus'
      ELSE 'other'
    END AS ver_bucket,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-20' AND created_ts < '2026-08-31'
    AND {FILT}
    AND TRIM(real_geo) = 'HK'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT ver_bucket, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base GROUP BY 1,2
)
SELECT ver_bucket, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY ni DESC
"""
print("\n=== HK lateAug by ver_bucket ===", flush=True)
cols, rows = query(sql_hk)
print("\t".join(cols), flush=True)
for r in rows:
    print("\t".join(str(x) for x in r), flush=True)

# rate if exclude zombie_old
sql_ex = f"""
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
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, device_id, ver,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
),
flagged AS (
  SELECT period, device_id,
    MAX(ni) AS ni, MAX(act) AS act,
    MAX(CASE WHEN ver IN ('1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7') THEN 1 ELSE 0 END) AS zombie
  FROM dev GROUP BY 1,2
)
SELECT period,
  SUM(ni) all_ni, ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) all_rate,
  SUM(CASE WHEN zombie=0 THEN ni ELSE 0 END) clean_ni,
  ROUND(SUM(CASE WHEN zombie=0 THEN act ELSE 0 END)*100.0
    / NULLIF(SUM(CASE WHEN zombie=0 THEN ni ELSE 0 END),0),2) clean_rate,
  SUM(CASE WHEN zombie=1 THEN ni ELSE 0 END) zombie_ni,
  ROUND(SUM(CASE WHEN zombie=1 THEN ni ELSE 0 END)*100.0/NULLIF(SUM(ni),0),1) zombie_share
FROM flagged GROUP BY 1 ORDER BY 1
"""
print("\n=== exclude zombie versions ===", flush=True)
cols, rows = query(sql_ex)
print("\t".join(cols), flush=True)
for r in rows:
    print("\t".join(str(x) for x in r), flush=True)
