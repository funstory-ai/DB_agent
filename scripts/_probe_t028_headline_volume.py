# -*- coding: utf-8 -*-
"""Re-anchor: headline act-rate drop on MAIN table — who has the volume."""
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

# 1) Main table: overall + OS with share and contribution math inputs
show("1 main midJun vs lateAug by OS", """
SELECT period, os, ni, act, rate,
  ROUND(ni * 100.0 / SUM(ni) OVER (PARTITION BY period), 1) AS share
FROM (
  SELECT
    CASE
      WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
      WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
    END AS period,
    LOWER(TRIM(os_name)) AS os,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
     OR (dates >= '2026-08-20' AND dates < '2026-08-31')
  GROUP BY 1, 2
  HAVING period IS NOT NULL
) t
WHERE ni >= 1000
ORDER BY period, ni DESC
""")

show("1b main overall", """
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

# 2) Counterfactual on MAIN: hold each OS rate at midJun, lateAug volumes
show("2 counterfactual hold OS rates", """
WITH jun AS (
  SELECT LOWER(TRIM(os_name)) AS os,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
  GROUP BY 1
),
aug AS (
  SELECT LOWER(TRIM(os_name)) AS os,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
  GROUP BY 1
)
SELECT
  a.os,
  a.ni AS aug_ni,
  ROUND(a.ni*100.0/(SELECT SUM(ni) FROM aug),1) AS aug_share,
  ROUND(j.act*100.0/NULLIF(j.ni,0),2) AS jun_rate,
  ROUND(a.act*100.0/NULLIF(a.ni,0),2) AS aug_rate,
  ROUND((a.act*100.0/NULLIF(a.ni,0)) - (j.act*100.0/NULLIF(j.ni,0)),2) AS d_rate,
  -- pp contribution to overall: share_aug * d_rate
  ROUND(a.ni*1.0/(SELECT SUM(ni) FROM aug) * ((a.act*1.0/NULLIF(a.ni,0)) - (j.act*1.0/NULLIF(j.ni,0))) * 100, 2) AS approx_pp_to_overall
FROM aug a
LEFT JOIN jun j ON a.os = j.os
WHERE a.ni >= 1000
ORDER BY aug_ni DESC
""")

# 3) Within Windows on MAIN: browser breakdown
show("3 Windows browsers main", """
SELECT period, browser, ni, rate, share FROM (
  SELECT
    CASE
      WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
      WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
    END AS period,
    TRIM(browser_name) AS browser,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate,
    ROUND(SUM(IF(event_name='init_page_daily', new_device_count, 0))*100.0
      / SUM(SUM(IF(event_name='init_page_daily', new_device_count, 0))) OVER (
        PARTITION BY CASE
          WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
          WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
        END), 1) AS share
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE LOWER(TRIM(os_name)) = 'windows'
    AND ((dates >= '2026-06-10' AND dates < '2026-06-21')
      OR (dates >= '2026-08-20' AND dates < '2026-08-31'))
  GROUP BY 1, 2
  HAVING period IS NOT NULL
) t
WHERE ni >= 5000
ORDER BY period, ni DESC
""")
