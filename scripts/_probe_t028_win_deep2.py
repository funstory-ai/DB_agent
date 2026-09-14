# -*- coding: utf-8 -*-
"""Win Chrome store: version / geo / delayed act."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

FILT = """
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND version <> '1.11.4'
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

show("2 version mix + rate", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(version),''),'(blank)') AS ver,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, ver, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
),
agg AS (
  SELECT period, ver, SUM(ni) AS ni, SUM(act) AS act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) AS rate
  FROM dev GROUP BY 1,2
)
SELECT a.period, a.ver, a.ni, a.act, a.rate,
  ROUND(a.ni * 100.0 / t.tot, 1) AS share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) AS tot FROM agg GROUP BY 1) t ON a.period = t.period
WHERE a.ni >= 2000
ORDER BY a.period, a.ni DESC
""")

show("3 geo mix + rate", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(real_geo),''),'(blank)') AS geo,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, geo, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
),
agg AS (
  SELECT period, geo, SUM(ni) AS ni, SUM(act) AS act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) AS rate
  FROM dev GROUP BY 1,2
)
SELECT a.period, a.geo, a.ni, a.act, a.rate,
  ROUND(a.ni * 100.0 / t.tot, 1) AS share_pct
FROM agg a
INNER JOIN (SELECT period, SUM(ni) AS tot FROM agg GROUP BY 1) t ON a.period = t.period
WHERE a.ni >= 3000
ORDER BY a.period, a.ni DESC
""")
