# -*- coding: utf-8 -*-
"""T028: new install surge by OS — init_page_daily + is_new_user_today=1."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Recent ~3 weeks vs prior 3 weeks (informal anomaly window)
# Use Beijing-ish calendar constants; no DATE() on created_ts

SQL_DAILY = """
SELECT
  to_date(created_ts) AS d,
  COALESCE(NULLIF(TRIM(LOWER(os_name)), ''), '(blank)') AS os,
  COUNT(*) AS evt_cnt,
  COUNT(DISTINCT device_id) AS device_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-01'
  AND created_ts < '2026-09-02'
  AND event_name = 'init_page_daily'
  AND is_new_user_today = '1'
GROUP BY 1, 2
ORDER BY 1, 4 DESC
"""

# Note: to_date in SELECT is OK; WHERE uses raw range. Databend may still prefer no to_date in SELECT for perf - use date trunc via range bins if needed.

SQL_WEEKLY = """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-08-11' AND created_ts < '2026-08-18' THEN 'W1_0811_0817'
      WHEN created_ts >= '2026-08-18' AND created_ts < '2026-08-25' THEN 'W2_0818_0824'
      WHEN created_ts >= '2026-08-25' AND created_ts < '2026-09-01' THEN 'W3_0825_0831'
      WHEN created_ts >= '2026-09-01' AND created_ts < '2026-09-02' THEN 'D_0901'
      ELSE NULL
    END AS wk,
    COALESCE(NULLIF(TRIM(LOWER(os_name)), ''), '(blank)') AS os,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-11'
    AND created_ts < '2026-09-02'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
)
SELECT wk, os, COUNT(*) AS evt_cnt, COUNT(DISTINCT device_id) AS device_cnt
FROM base
WHERE wk IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 4 DESC
"""

SQL_OS_COMPARE = """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-08-04' AND created_ts < '2026-08-18' THEN 'prev_14d'
      WHEN created_ts >= '2026-08-18' AND created_ts < '2026-09-01' THEN 'recent_14d'
      ELSE NULL
    END AS period,
    CASE
      WHEN LOWER(COALESCE(os_name, '')) LIKE '%ios%'
        OR LOWER(COALESCE(os_name, '')) LIKE '%iphone%'
        OR LOWER(COALESCE(os_name, '')) LIKE '%ipad%'
        THEN 'ios_family'
      WHEN LOWER(COALESCE(os_name, '')) LIKE '%android%' THEN 'android'
      WHEN LOWER(COALESCE(os_name, '')) IN ('mac', 'macos', 'darwin')
        OR LOWER(COALESCE(os_name, '')) LIKE 'mac%' THEN 'mac'
      WHEN LOWER(COALESCE(os_name, '')) LIKE '%win%' THEN 'windows'
      WHEN LOWER(COALESCE(os_name, '')) LIKE '%chrome%' THEN 'chrome_os_or_ext'
      ELSE CONCAT('other:', COALESCE(NULLIF(TRIM(LOWER(os_name)), ''), '(blank)'))
    END AS os_grp,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-04'
    AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
)
SELECT period, os_grp,
  COUNT(*) AS evt_cnt,
  COUNT(DISTINCT device_id) AS device_cnt
FROM base
WHERE period IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 4 DESC
"""


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===")
    print(cols)
    for r in rows[:80]:
        print(r)
    if len(rows) > 80:
        print(f"... ({len(rows)} rows)")


if __name__ == "__main__":
    show("os_compare_14d", query(SQL_OS_COMPARE))
    show("weekly", query(SQL_WEEKLY))
