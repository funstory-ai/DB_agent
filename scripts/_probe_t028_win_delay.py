# -*- coding: utf-8 -*-
"""Same-day vs 3d activation for Win Chrome store."""
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

def run(title, start, end):
    sql = f"""
    WITH installs AS (
      SELECT device_id, MIN(created_ts) AS install_ts
      FROM immdata.user_behaviour
      WHERE created_ts >= '{start}' AND created_ts < '{end}'
        AND {FILT}
        AND event_name = 'init_page_daily' AND is_new_user_today = '1'
        AND ABS(xxhash64(device_id)) % 10 = 0
      GROUP BY 1
    ),
    acts AS (
      SELECT device_id, created_ts
      FROM immdata.user_behaviour
      WHERE created_ts >= '{start}' AND created_ts < DATEADD(day, 3, to_date('{end}'))
        AND event_name = 'translate_page'
        AND LOWER(TRIM(os_name)) = 'windows'
        AND ABS(xxhash64(device_id)) % 10 = 0
    )
    SELECT
      COUNT(*) AS ni_sample,
      COUNT(DISTINCT CASE
        WHEN a.device_id IS NOT NULL
         AND a.created_ts >= i.install_ts
         AND a.created_ts < DATEADD(day, 1, i.install_ts)
        THEN i.device_id END) AS act_d0,
      COUNT(DISTINCT CASE
        WHEN a.device_id IS NOT NULL
         AND a.created_ts >= i.install_ts
         AND a.created_ts < DATEADD(day, 3, i.install_ts)
        THEN i.device_id END) AS act_d3
    FROM installs i
    LEFT JOIN acts a ON a.device_id = i.device_id
    """
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    # fix join blowup: recompute properly
    sql2 = f"""
    WITH installs AS (
      SELECT device_id, MIN(created_ts) AS install_ts
      FROM immdata.user_behaviour
      WHERE created_ts >= '{start}' AND created_ts < '{end}'
        AND {FILT}
        AND event_name = 'init_page_daily' AND is_new_user_today = '1'
        AND ABS(xxhash64(device_id)) % 10 = 0
      GROUP BY 1
    ),
    act_d0 AS (
      SELECT DISTINCT i.device_id
      FROM installs i
      INNER JOIN immdata.user_behaviour b
        ON b.device_id = i.device_id
       AND b.created_ts >= i.install_ts
       AND b.created_ts < DATEADD(day, 1, i.install_ts)
       AND b.event_name = 'translate_page'
       AND ABS(xxhash64(b.device_id)) % 10 = 0
    ),
    act_d3 AS (
      SELECT DISTINCT i.device_id
      FROM installs i
      INNER JOIN immdata.user_behaviour b
        ON b.device_id = i.device_id
       AND b.created_ts >= i.install_ts
       AND b.created_ts < DATEADD(day, 3, i.install_ts)
       AND b.event_name = 'translate_page'
       AND ABS(xxhash64(b.device_id)) % 10 = 0
    )
    SELECT
      (SELECT COUNT(*) FROM installs) AS ni,
      (SELECT COUNT(*) FROM act_d0) AS act_d0,
      (SELECT COUNT(*) FROM act_d3) AS act_d3
    """
    cols, rows = query(sql2)
    ni, d0, d3 = rows[0]
    print(f"ni={ni} act_d0={d0} ({d0/ni*100:.2f}%) act_d3={d3} ({d3/ni*100:.2f}%)", flush=True)

if __name__ == "__main__":
    run("midJun 6/10-6/17", "2026-06-10", "2026-06-18")
    run("lateAug 8/20-8/27", "2026-08-20", "2026-08-28")
