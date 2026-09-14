# -*- coding: utf-8 -*-
"""T028: daily + monthly new-install by OS."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Daily Jul-Aug for ios/android/windows/macos only — use CASE day buckets via date ranges would be huge;
# use toYYYYMMDD or substring of cast — Databend: to_date in SELECT after filter is usually ok.

SQL_DAILY = """
SELECT
  to_date(created_ts) AS d,
  LOWER(TRIM(os_name)) AS os,
  COUNT(DISTINCT device_id) AS device_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-01'
  AND created_ts < '2026-09-02'
  AND event_name = 'init_page_daily'
  AND is_new_user_today = '1'
  AND LOWER(TRIM(os_name)) IN ('ios', 'android', 'windows', 'macos')
GROUP BY 1, 2
ORDER BY 1, 2
"""

SQL_MONTH = """
SELECT
  CASE
    WHEN created_ts >= '2026-06-01' AND created_ts < '2026-07-01' THEN '2026-06'
    WHEN created_ts >= '2026-07-01' AND created_ts < '2026-08-01' THEN '2026-07'
    WHEN created_ts >= '2026-08-01' AND created_ts < '2026-09-01' THEN '2026-08'
    ELSE NULL
  END AS ym,
  LOWER(TRIM(os_name)) AS os,
  COUNT(*) AS evt_cnt,
  COUNT(DISTINCT device_id) AS device_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-06-01'
  AND created_ts < '2026-09-01'
  AND event_name = 'init_page_daily'
  AND is_new_user_today = '1'
GROUP BY 1, 2
HAVING ym IS NOT NULL
ORDER BY 1, 4 DESC
"""

SQL_SPIKE_DAYS = """
WITH daily AS (
  SELECT
    to_date(created_ts) AS d,
    COUNT(DISTINCT device_id) AS device_cnt
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01'
    AND created_ts < '2026-09-02'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
  GROUP BY 1
)
SELECT d, device_cnt
FROM daily
ORDER BY device_cnt DESC
LIMIT 15
"""

SQL_IOS_DAILY_TOP = """
SELECT
  to_date(created_ts) AS d,
  COUNT(DISTINCT device_id) AS ios_devices,
  COUNT(*) AS ios_evts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-01'
  AND created_ts < '2026-09-02'
  AND event_name = 'init_page_daily'
  AND is_new_user_today = '1'
  AND LOWER(TRIM(os_name)) = 'ios'
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10
"""


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===")
    print(cols)
    for r in rows:
        print(r)


if __name__ == "__main__":
    show("month", query(SQL_MONTH))
    show("spike_days_all", query(SQL_SPIKE_DAYS))
    show("ios_top_days", query(SQL_IOS_DAILY_TOP))
    cols, rows = query(SQL_DAILY)
    # print last 20 days pivot-ish
    from collections import defaultdict
    by = defaultdict(dict)
    for d, os, cnt in rows:
        by[str(d)[:10]][os] = cnt
    print("\n=== daily_tail ===")
    print("date\tios\tandroid\twindows\tmacos\ttotal4")
    for d in sorted(by.keys())[-21:]:
        ios = by[d].get("ios", 0)
        andr = by[d].get("android", 0)
        win = by[d].get("windows", 0)
        mac = by[d].get("macos", 0)
        print(f"{d}\t{ios}\t{andr}\t{win}\t{mac}\t{ios+andr+win+mac}")
