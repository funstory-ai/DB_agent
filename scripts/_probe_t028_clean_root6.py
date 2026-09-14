# -*- coding: utf-8 -*-
"""Confirm: interface_language mix outside US; en-only US rates."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

FILT = """
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND (
    TRIM(version) LIKE '1.30.%'
    OR TRIM(version) LIKE '1.31.%'
    OR TRIM(version) LIKE '1.32.%'
  )
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

show("exUS lang mix", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(interface_language),''),'(blank)') AS lang,
    device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND UPPER(TRIM(COALESCE(real_geo,''))) <> 'US'
    AND event_name IN ('init_page_daily','translate_page')
  GROUP BY 1,2,3
)
SELECT period, lang, SUM(ni) ni,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate,
  ROUND(SUM(ni)*100.0/SUM(SUM(ni)) OVER (PARTITION BY period),1) share_pct
FROM base WHERE period IS NOT NULL
GROUP BY 1,2 HAVING SUM(ni) >= 2000
ORDER BY period, ni DESC
""")

show("US en-only overall recent", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND UPPER(TRIM(real_geo)) = 'US'
    AND TRIM(interface_language) = 'en'
    AND event_name IN ('init_page_daily','translate_page')
  GROUP BY 1,2
)
SELECT period, SUM(ni) ni,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM base WHERE period IS NOT NULL
GROUP BY 1 ORDER BY 1
""")
