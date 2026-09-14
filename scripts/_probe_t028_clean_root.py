# -*- coding: utf-8 -*-
"""T028: residual drop AFTER zombies — recent Win Chrome store only. No zombie rehash."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Only recent builds — zombies already out by construction
RECENT = """(
  TRIM(version) LIKE '1.30.%'
  OR TRIM(version) LIKE '1.31.%'
  OR TRIM(version) LIKE '1.32.%'
)"""
FILT = f"""
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND {RECENT}
"""
ACT_EVENTS = (
    "translate_page",
    "selection_translate",
    "mouse_hover_translate",
    "translate_input",
    "translate_video_subtitle",
    "translateTextInSidePanel",
    "assistant_translate_page",
)

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)
    return rows

# 1) Baseline: recent-only Win Chrome store headline
show("1 recent WinChromeStore midJun vs lateAug", f"""
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
    AND {FILT}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2
)
SELECT period, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")

# 2) Same patch version in BOTH windows (true product/quality within version)
show("2 same-version both periods (ni>=800 each)", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    TRIM(version) AS ver,
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
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, ver, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
  FROM dev GROUP BY 1,2
)
SELECT j.ver, j.ni AS jun_ni, j.rate AS jun_rate, a.ni AS aug_ni, a.rate AS aug_rate,
  ROUND(a.rate - j.rate, 2) AS d_pp
FROM agg j
INNER JOIN agg a ON j.ver = a.ver AND j.period='midJun' AND a.period='lateAug'
WHERE j.ni >= 800 AND a.ni >= 800
ORDER BY j.ni DESC
""")

# 3) P034 vs broader same-day translate-family activation
ev_list = ",".join(f"'{e}'" for e in ACT_EVENTS)
show("3 P034 vs any-translate-family same-day", f"""
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
    AND {FILT}
    AND event_name IN ('init_page_daily', {ev_list})
),
dev AS (
  SELECT period, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act_p034,
    MAX(CASE WHEN event_name IN ({ev_list}) AND is_new_user_today='1' THEN 1 ELSE 0 END) act_any
  FROM base WHERE period IS NOT NULL GROUP BY 1,2
)
SELECT period, SUM(ni) ni,
  ROUND(SUM(act_p034)*100.0/NULLIF(SUM(ni),0),2) p034,
  ROUND(SUM(act_any)*100.0/NULLIF(SUM(ni),0),2) any_tr,
  ROUND((SUM(act_any)-SUM(act_p034))*100.0/NULLIF(SUM(ni),0),2) gap_pp
FROM dev GROUP BY 1 ORDER BY 1
""")

# 4) US-only recent trend by week (Aug) — within-geo product/quality
show("4 US recent weekly Aug", f"""
WITH base AS (
  SELECT
    to_date(DATE_TRUNC('week', created_ts)) AS wk,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-01'
    AND {FILT}
    AND UPPER(TRIM(real_geo)) = 'US'
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT wk, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base GROUP BY 1,2
)
SELECT wk, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0),2) rate
FROM dev GROUP BY 1 HAVING SUM(ni) >= 500
ORDER BY 1
""")
