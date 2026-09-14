# -*- coding: utf-8 -*-
"""T028 full contribution ladder. Prefer interface_language over geo (VPN)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ZOMBIE = """TRIM(version) IN (
  '1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7'
)"""
RECENT = """(
  TRIM(version) LIKE '1.30.%'
  OR TRIM(version) LIKE '1.31.%'
  OR TRIM(version) LIKE '1.32.%'
)"""
WIN_CHROME_STORE = """
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

# L2: Windows browser on main table → contribution to OVERALL (need OS share)
# First get Windows-only browser kitagawa, then scale by Win NI share of overall later in print

show("L2 Win browser midJun vs lateAug", """
WITH base AS (
  SELECT
    CASE
      WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
      WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(TRIM(browser_name),''),'(blank)') AS browser,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE LOWER(TRIM(os_name)) = 'windows'
    AND ((dates >= '2026-06-10' AND dates < '2026-06-21')
      OR (dates >= '2026-08-20' AND dates < '2026-08-31'))
  GROUP BY 1,2 HAVING period IS NOT NULL
),
tot AS (SELECT period, SUM(ni) ni, SUM(act) act FROM base GROUP BY 1),
j AS (
  SELECT COALESCE(a.browser,b.browser) AS browser,
    COALESCE(b.ni,0) jun_ni, COALESCE(b.act,0) jun_act,
    COALESCE(a.ni,0) aug_ni, COALESCE(a.act,0) aug_act
  FROM (SELECT * FROM base WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM base WHERE period='midJun') b ON a.browser=b.browser
),
rates AS (
  SELECT *, jun_act*1.0/NULLIF(jun_ni,0) rj, aug_act*1.0/NULLIF(aug_ni,0) ra FROM j
),
t AS (
  SELECT
    MAX(CASE WHEN period='midJun' THEN ni END) jun_tot,
    MAX(CASE WHEN period='lateAug' THEN ni END) aug_tot,
    MAX(CASE WHEN period='midJun' THEN act END)*1.0
      /NULLIF(MAX(CASE WHEN period='midJun' THEN ni END),0) r_jun,
    MAX(CASE WHEN period='lateAug' THEN act END)*1.0
      /NULLIF(MAX(CASE WHEN period='lateAug' THEN ni END),0) r_aug
  FROM tot
)
SELECT r.browser,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) aug_share,
  ROUND(r.rj*100,2) jun_rate, ROUND(r.ra*100,2) aug_rate,
  ROUND(((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100,3) mix_pp_of_win,
  ROUND((r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100,3) rate_pp_of_win,
  ROUND((t.r_aug-t.r_jun)*100,3) win_drop_pp
FROM rates r CROSS JOIN t
WHERE r.jun_ni+r.aug_ni >= 5000
ORDER BY ABS(
  ((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)
  +(r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))
) DESC
""")

# L3: Win Chrome store — zombie vs other vs recent (3 buckets) via behaviour
show("L3 WinChromeStore zombie/recent/other", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN {ZOMBIE} THEN 'zombie'
      WHEN {RECENT} THEN 'recent'
      ELSE 'other_ver'
    END AS bucket,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND {WIN_CHROME_STORE}
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, bucket, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (
  SELECT period, bucket, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2
),
j AS (
  SELECT COALESCE(a.bucket,b.bucket) bucket,
    COALESCE(b.ni,0) jun_ni, COALESCE(b.act,0) jun_act,
    COALESCE(a.ni,0) aug_ni, COALESCE(a.act,0) aug_act
  FROM (SELECT * FROM agg WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM agg WHERE period='midJun') b ON a.bucket=b.bucket
),
rates AS (
  SELECT *, jun_act*1.0/NULLIF(jun_ni,0) rj, aug_act*1.0/NULLIF(aug_ni,0) ra FROM j
),
t AS (
  SELECT
    SUM(CASE WHEN period='midJun' THEN ni END) jun_tot,
    SUM(CASE WHEN period='lateAug' THEN ni END) aug_tot,
    SUM(CASE WHEN period='midJun' THEN act END)*1.0
      /NULLIF(SUM(CASE WHEN period='midJun' THEN ni END),0) r_jun,
    SUM(CASE WHEN period='lateAug' THEN act END)*1.0
      /NULLIF(SUM(CASE WHEN period='lateAug' THEN ni END),0) r_aug
  FROM agg
)
SELECT r.bucket,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) aug_share,
  ROUND(r.rj*100,2) jun_rate, ROUND(r.ra*100,2) aug_rate,
  ROUND(((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100,3) mix_pp,
  ROUND((r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100,3) rate_pp,
  ROUND(
    ((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100
    +(r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100
  ,3) total_pp_of_channel,
  ROUND((t.r_aug-t.r_jun)*100,3) channel_drop_pp
FROM rates r CROSS JOIN t
ORDER BY 1
""")
