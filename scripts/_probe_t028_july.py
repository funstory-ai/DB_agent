# -*- coding: utf-8 -*-
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

sql = """
SELECT to_date(created_ts) AS d, LOWER(TRIM(os_name)) AS os, COUNT(DISTINCT device_id) AS device_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-01' AND created_ts < '2026-08-15'
  AND event_name = 'init_page_daily' AND is_new_user_today = '1'
  AND LOWER(TRIM(os_name)) IN ('ios', 'android', 'windows', 'macos')
GROUP BY 1, 2 ORDER BY 1, 2
"""
cols, rows = query(sql)
by = defaultdict(dict)
for d, os, cnt in rows:
    by[str(d)[:10]][os] = cnt
print("date\tios\tandroid\twindows\tmacos")
for d in sorted(by.keys()):
    print(
        f"{d}\t{by[d].get('ios',0)}\t{by[d].get('android',0)}\t{by[d].get('windows',0)}\t{by[d].get('macos',0)}"
    )

sql2 = """
SELECT
  CASE
    WHEN created_ts >= '2026-06-01' AND created_ts < '2026-07-01' THEN '2026-06'
    WHEN created_ts >= '2026-07-01' AND created_ts < '2026-08-01' THEN '2026-07'
    WHEN created_ts >= '2026-08-01' AND created_ts < '2026-09-01' THEN '2026-08'
  END AS ym,
  COUNT(DISTINCT CASE WHEN LOWER(TRIM(os_name))='ios' THEN device_id END) AS ios_d,
  COUNT(DISTINCT device_id) AS all_d
FROM immdata.user_behaviour
WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-01'
  AND event_name = 'init_page_daily' AND is_new_user_today = '1'
GROUP BY 1 ORDER BY 1
"""
print("\n=== share ===")
print(query(sql2))
