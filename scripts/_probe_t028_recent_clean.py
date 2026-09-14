# -*- coding: utf-8 -*-
"""iOS recent versions: who is the 25% act cohort? + clean recent excl RuleA."""
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

KICK = """
  NOT (
    LOWER(TRIM(install_from)) = 'official_userscript'
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
  )
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join(str(x) for x in r), flush=True)

show("iOS recent lateAug by install×browser", f"""
WITH base AS (
  SELECT
    COALESCE(NULLIF(LOWER(TRIM(install_from)),''),'(blank)') AS install_from,
    COALESCE(NULLIF(TRIM(browser_name),''),'(blank)') AS browser,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-20' AND created_ts < '2026-08-31'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT install_from, browser, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2,3
)
SELECT install_from, browser, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1,2
HAVING SUM(ni) >= 500
ORDER BY ni DESC
""")

show("recent+RuleA overall midJun vs lateAug", f"""
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
    AND {KICK}
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
SELECT * FROM (
  SELECT period, 'ALL' AS os, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM agg GROUP BY period
  UNION ALL
  SELECT period, os, ni, act, rate FROM agg WHERE ni >= 2000
) t
ORDER BY period, os
""")

# Fixed: 1.32.x only (the lateAug dominant recent) — rate by week for Win Chrome store
show("1.32.x Win Chrome store weekly", f"""
WITH base AS (
  SELECT DATE(add_hours(created_ts,8)) d, device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-15' AND created_ts < '2026-09-01'
    AND LOWER(TRIM(os_name))='windows'
    AND TRIM(browser_name)='Chrome'
    AND LOWER(TRIM(install_from))='chrome_store'
    AND TRIM(version) LIKE '1.32.%'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT to_start_of_week(d,1) wk, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2
)
SELECT wk, SUM(ni) ni, ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")

# US only Win Chrome store recent — removes geo mix
show("US-only Win Chrome store recent", f"""
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
    AND LOWER(TRIM(os_name))='windows'
    AND TRIM(browser_name)='Chrome'
    AND LOWER(TRIM(install_from))='chrome_store'
    AND TRIM(real_geo)='US'
    AND version <> '1.11.4' AND {RECENT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2
)
SELECT period, SUM(ni) ni, ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")
