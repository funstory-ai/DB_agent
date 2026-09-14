# -*- coding: utf-8 -*-
"""T028 deep-dive: Windows Chrome chrome_store act-rate decline."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

WIN_CHROME = """
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND version <> '1.11.4'
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows[:40]:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)
    if len(rows) > 40:
        print(f"... ({len(rows)} rows)", flush=True)

# 1) Weekly trend Win Chrome store only
show("1 weekly Win Chrome store", f"""
WITH base AS (
  SELECT DATE(add_hours(created_ts,8)) d, device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-01'
    AND {WIN_CHROME}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT to_start_of_week(d,1) wk, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2
)
SELECT wk, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")
