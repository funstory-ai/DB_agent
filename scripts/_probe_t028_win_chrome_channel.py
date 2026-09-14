# -*- coding: utf-8 -*-
"""Windows Chrome install_from mix — remaining drop driver."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

sql = """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(LOWER(TRIM(install_from)), ''), '(blank)') AS install_from,
    device_id,
    event_name,
    is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name)) = 'windows'
    AND TRIM(browser_name) = 'Chrome'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT period, install_from, device_id,
    MAX(CASE WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name = 'translate_page' AND is_new_user_today = '1' THEN 1 ELSE 0 END) AS act
  FROM base
  WHERE period IS NOT NULL
  GROUP BY 1, 2, 3
)
SELECT period, install_from,
  SUM(ni) AS ni, SUM(act) AS act,
  ROUND(SUM(act) * 100.0 / NULLIF(SUM(ni), 0), 2) AS rate,
  ROUND(SUM(ni) * 100.0 / SUM(SUM(ni)) OVER (PARTITION BY period), 1) AS share
FROM dev
GROUP BY 1, 2
HAVING SUM(ni) >= 500
ORDER BY period, ni DESC
"""
cols, rows = query(sql)
print("\t".join(cols), flush=True)
for r in rows:
    print("\t".join(str(x) for x in r), flush=True)

# also Electron install_from briefly
sql2 = """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(LOWER(TRIM(install_from)), ''), '(blank)') AS install_from,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND TRIM(browser_name) = 'Electron'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT period, install_from, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
)
SELECT period, install_from, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate,
  ROUND(SUM(ni)*100.0/SUM(SUM(ni)) OVER (PARTITION BY period),1) share
FROM dev GROUP BY 1,2 HAVING SUM(ni)>=500
ORDER BY period, ni DESC
"""
print("\n=== Electron by install_from ===", flush=True)
cols, rows = query(sql2)
print("\t".join(cols), flush=True)
for r in rows:
    print("\t".join(str(x) for x in r), flush=True)
