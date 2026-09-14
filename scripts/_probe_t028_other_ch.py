# -*- coding: utf-8 -*-
"""Compare chrome_store vs other Win Chrome channels; other browsers."""
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

show("WinChrome by install_from", """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(LOWER(TRIM(install_from)),''),'(blank)') AS ch,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name)) = 'windows'
    AND TRIM(browser_name) = 'Chrome'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, ch, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (SELECT period, ch, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2)
SELECT
  COALESCE(j.ch, a.ch) AS ch,
  COALESCE(j.ni,0) AS jun_ni,
  ROUND(COALESCE(j.act,0)*100.0/NULLIF(j.ni,0),2) AS jun_rate,
  COALESCE(a.ni,0) AS aug_ni,
  ROUND(COALESCE(a.act,0)*100.0/NULLIF(a.ni,0),2) AS aug_rate,
  ROUND(
    COALESCE(a.act,0)*100.0/NULLIF(a.ni,0)
    - COALESCE(j.act,0)*100.0/NULLIF(j.ni,0)
  ,2) AS d_pp
FROM (SELECT * FROM agg WHERE period='midJun') j
FULL OUTER JOIN (SELECT * FROM agg WHERE period='lateAug') a ON j.ch = a.ch
WHERE COALESCE(j.ni,0) + COALESCE(a.ni,0) >= 2000
ORDER BY COALESCE(a.ni, j.ni) DESC
""")

show("WinChrome store vs all_other", """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN LOWER(TRIM(install_from)) = 'chrome_store' THEN 'chrome_store'
      ELSE 'other_channels'
    END AS ch,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name)) = 'windows'
    AND TRIM(browser_name) = 'Chrome'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, ch, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
)
SELECT period, ch, SUM(ni) ni,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) AS rate
FROM dev GROUP BY 1,2 ORDER BY 1,2
""")

show("main table Win browsers (excl Chrome)", """
SELECT
  CASE
    WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
    WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
  END AS period,
  TRIM(browser_name) AS browser,
  SUM(IF(event_name='init_page_daily', new_device_count,0)) AS ni,
  ROUND(
    SUM(IF(event_name='translate_page', new_device_count,0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count,0)),0)
  ,2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE LOWER(TRIM(os_name))='windows'
  AND TRIM(browser_name) <> 'Chrome'
  AND ((dates >= '2026-06-10' AND dates < '2026-06-21')
    OR (dates >= '2026-08-20' AND dates < '2026-08-31'))
GROUP BY 1,2
HAVING period IS NOT NULL
  AND SUM(IF(event_name='init_page_daily', new_device_count,0)) >= 5000
ORDER BY 1, ni DESC
""")
