# -*- coding: utf-8 -*-
"""T028: US x 1.32.7; patch x geo; day1 walls/events sample."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

FILT = """
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# H) 1.32.7 US vs ex-US lateAug
show("H 1.32.7 US vs exUS lateAug", f"""
WITH base AS (
  SELECT
    CASE WHEN UPPER(TRIM(real_geo))='US' THEN 'US' ELSE 'exUS' END AS g,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-20' AND created_ts < '2026-08-31'
    AND {FILT}
    AND TRIM(version) = '1.32.7'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT g, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2
)
SELECT g, SUM(ni) ni, ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")

# I) each 1.32 patch × US share and US rate
show("I 1.32 patch x US lateAug", f"""
WITH base AS (
  SELECT TRIM(version) AS ver,
    CASE WHEN UPPER(TRIM(real_geo))='US' THEN 1 ELSE 0 END AS is_us,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-20' AND created_ts < '2026-08-31'
    AND {FILT}
    AND TRIM(version) LIKE '1.32.%'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT ver, is_us, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2,3
)
SELECT ver, is_us, SUM(ni) ni,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1,2 HAVING SUM(ni)>=1500
ORDER BY ver, is_us
""")

# J) US lateAug non-activators: top other events same Beijing day (20% sample, 5-day window)
show("J US non-act day1 other events (sample)", f"""
WITH installs AS (
  SELECT device_id, MIN(created_ts) AS install_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-25' AND created_ts < '2026-08-30'
    AND {FILT}
    AND (
      TRIM(version) LIKE '1.30.%' OR TRIM(version) LIKE '1.31.%' OR TRIM(version) LIKE '1.32.%'
    )
    AND UPPER(TRIM(real_geo)) = 'US'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND ABS(xxhash64(device_id)) % 5 = 0
  GROUP BY 1
),
labeled AS (
  SELECT i.device_id, i.install_ts,
    MAX(CASE WHEN b.event_name='translate_page' THEN 1 ELSE 0 END) AS acted
  FROM installs i
  LEFT JOIN immdata.user_behaviour b
    ON b.device_id = i.device_id
   AND b.created_ts >= i.install_ts
   AND b.created_ts < DATEADD(day, 1, i.install_ts)
   AND ABS(xxhash64(b.device_id)) % 5 = 0
  GROUP BY 1,2
),
nonact AS (SELECT device_id, install_ts FROM labeled WHERE acted = 0),
ev AS (
  SELECT b.event_name, COUNT(DISTINCT n.device_id) AS devices
  FROM nonact n
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = n.device_id
   AND b.created_ts >= n.install_ts
   AND b.created_ts < DATEADD(day, 1, n.install_ts)
   AND ABS(xxhash64(b.device_id)) % 5 = 0
  GROUP BY 1
)
SELECT event_name, devices
FROM ev
ORDER BY devices DESC
LIMIT 25
""")

show("J2 nonact vs act cohort size", f"""
WITH installs AS (
  SELECT device_id, MIN(created_ts) AS install_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-25' AND created_ts < '2026-08-30'
    AND {FILT}
    AND (
      TRIM(version) LIKE '1.30.%' OR TRIM(version) LIKE '1.31.%' OR TRIM(version) LIKE '1.32.%'
    )
    AND UPPER(TRIM(real_geo)) = 'US'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND ABS(xxhash64(device_id)) % 5 = 0
  GROUP BY 1
),
labeled AS (
  SELECT i.device_id,
    MAX(CASE WHEN b.event_name='translate_page' THEN 1 ELSE 0 END) AS acted
  FROM installs i
  LEFT JOIN immdata.user_behaviour b
    ON b.device_id = i.device_id
   AND b.created_ts >= i.install_ts
   AND b.created_ts < DATEADD(day, 1, i.install_ts)
   AND ABS(xxhash64(b.device_id)) % 5 = 0
  GROUP BY 1
)
SELECT
  COUNT(*) AS sample_ni,
  SUM(acted) AS acted,
  SUM(1-acted) AS nonact,
  ROUND(AVG(acted)*100,2) AS rate
FROM labeled
""")
