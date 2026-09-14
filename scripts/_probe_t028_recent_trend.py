# -*- coding: utf-8 -*-
"""Deep-dive: recent-version-only act-rate decline (product vs mix)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# recent = 1.30 / 1.31 / 1.32 minors (matches _M top3 often)
RECENT = """(
  TRIM(version) LIKE '1.30.%'
  OR TRIM(version) LIKE '1.31.%'
  OR TRIM(version) LIKE '1.32.%'
)"""

FILT_BASE = """
  version <> '1.11.4'
  AND version IS NOT NULL
  AND version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+$'
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# 1) Weekly: recent-only overall (behaviour, all platform) — shorter: two periods + weekly via summary impossible for version
# Use weekly windows of 7d for recent-only Win+all
show("1 weekly recent-only ALL platform", f"""
WITH base AS (
  SELECT DATE(add_hours(created_ts,8)) AS d, device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-01'
    AND {FILT_BASE}
    AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT to_start_of_week(d,1) AS wk, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base GROUP BY 1,2
)
SELECT wk, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")
