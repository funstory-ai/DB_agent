# -*- coding: utf-8 -*-
"""Remain drop via summary table (Rule A already in Jul28+)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# midJun = 6/10-6/20, lateAug = 8/20-8/30 (full days in backfill)
show("1 by os midJun vs lateAug", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  LOWER(TRIM(os_name)) AS os,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate,
  ROUND(SUM(IF(event_name='init_page_daily', new_device_count, 0))*100.0
    / SUM(SUM(IF(event_name='init_page_daily', new_device_count, 0))) OVER (PARTITION BY
      CASE WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
           WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug' END), 1) AS share
FROM immdata.imm_event_device_count_by_utf8_day
WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
   OR (dates >= '2026-08-20' AND dates < '2026-08-31')
GROUP BY 1, 2
HAVING period IS NOT NULL
ORDER BY period, ni DESC
""")

show("2 by browser midJun vs lateAug top", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  TRIM(browser_name) AS browser,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate,
  ROUND(SUM(IF(event_name='init_page_daily', new_device_count, 0))*100.0
    / SUM(SUM(IF(event_name='init_page_daily', new_device_count, 0))) OVER (PARTITION BY
      CASE WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
           WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug' END), 1) AS share
FROM immdata.imm_event_device_count_by_utf8_day
WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
   OR (dates >= '2026-08-20' AND dates < '2026-08-31')
GROUP BY 1, 2
HAVING period IS NOT NULL
  AND SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 5000
ORDER BY period, ni DESC
""")

# 3) within same OS: did rate drop, or only mix shift?
show("3 os rate only (same periods)", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  LOWER(TRIM(os_name)) AS os,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
   OR (dates >= '2026-08-20' AND dates < '2026-08-31')
GROUP BY 1, 2
HAVING period IS NOT NULL AND SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 10000
ORDER BY os, period
""")

# 4) Chrome (likely userscript residual) by os
show("4 Chrome by os midJun vs lateAug", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  LOWER(TRIM(os_name)) AS os,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name = 'Chrome'
  AND ((dates >= '2026-06-10' AND dates < '2026-06-21')
    OR (dates >= '2026-08-20' AND dates < '2026-08-31'))
GROUP BY 1, 2
HAVING period IS NOT NULL
ORDER BY period, ni DESC
""")

# 5) Decomposition: overall rate if hold midJun OS mix
# Use lateAug rates with midJun shares (rough)
show("5 overall totals", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
   OR (dates >= '2026-08-20' AND dates < '2026-08-31')
GROUP BY 1
HAVING period IS NOT NULL
ORDER BY 1
""")

# 6) Edge / WeChat / other low quality browsers growth
show("6 low-rate browsers lateAug", """
SELECT TRIM(browser_name) AS browser,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
GROUP BY 1
HAVING SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 2000
ORDER BY rate ASC, ni DESC
LIMIT 25
""")
