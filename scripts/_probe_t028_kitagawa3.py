# -*- coding: utf-8 -*-
"""L4: interface_language Kitagawa on recent Win Chrome store (VPN-safer).
Also segment: en / zh-CN / other; and geo×lang for reference only.
"""
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
FILT = f"""
  LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'chrome_store'
  AND {RECENT}
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# Lang bucket: en / zh-CN / other
show("L4 lang bucket recent WinChromeStore", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN TRIM(interface_language) = 'en' THEN 'en'
      WHEN TRIM(interface_language) = 'zh-CN' THEN 'zh-CN'
      ELSE 'other_lang'
    END AS lang,
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
  SELECT period, lang, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (SELECT period, lang, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2),
j AS (
  SELECT COALESCE(a.lang,b.lang) lang,
    COALESCE(b.ni,0) jun_ni, COALESCE(b.act,0) jun_act,
    COALESCE(a.ni,0) aug_ni, COALESCE(a.act,0) aug_act
  FROM (SELECT * FROM agg WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM agg WHERE period='midJun') b ON a.lang=b.lang
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
SELECT r.lang,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) aug_share,
  ROUND(r.rj*100,2) jun_rate, ROUND(r.ra*100,2) aug_rate,
  ROUND(((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100,3) mix_pp,
  ROUND((r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100,3) rate_pp,
  ROUND(
    ((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100
    +(r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100
  ,3) total_pp,
  ROUND((t.r_aug-t.r_jun)*100,3) segment_drop_pp
FROM rates r CROSS JOIN t
ORDER BY 1
""")

# Geo is VPN-noisy: still compute US vs exUS kitagawa on recent for "how much if we trusted IP"
show("L4b geo US vs exUS recent (VPN-noisy)", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE WHEN UPPER(TRIM(real_geo))='US' THEN 'US_ip' ELSE 'exUS_ip' END AS g,
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
  SELECT period, g, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (SELECT period, g, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2),
j AS (
  SELECT COALESCE(a.g,b.g) g,
    COALESCE(b.ni,0) jun_ni, COALESCE(b.act,0) jun_act,
    COALESCE(a.ni,0) aug_ni, COALESCE(a.act,0) aug_act
  FROM (SELECT * FROM agg WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM agg WHERE period='midJun') b ON a.g=b.g
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
SELECT r.g,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) aug_share,
  ROUND(r.rj*100,2) jun_rate, ROUND(r.ra*100,2) aug_rate,
  ROUND(((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100,3) mix_pp,
  ROUND((r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100,3) rate_pp,
  ROUND(
    ((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100
    +(r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100
  ,3) total_pp,
  ROUND((t.r_aug-t.r_jun)*100,3) segment_drop_pp
FROM rates r CROSS JOIN t
ORDER BY 1
""")

# Cross: 4 cells US_ip×en / US_ip×non-en / exUS×en / exUS×non-en — for "US en" ask
show("L4c geo x lang 4-cell recent", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN UPPER(TRIM(real_geo))='US' AND TRIM(interface_language)='en' THEN 'US_ip_x_en'
      WHEN UPPER(TRIM(real_geo))='US' THEN 'US_ip_x_nonEn'
      WHEN TRIM(interface_language)='en' THEN 'exUS_ip_x_en'
      ELSE 'exUS_ip_x_nonEn'
    END AS cell,
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
  SELECT period, cell, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
),
agg AS (SELECT period, cell, SUM(ni) ni, SUM(act) act FROM dev GROUP BY 1,2),
j AS (
  SELECT COALESCE(a.cell,b.cell) cell,
    COALESCE(b.ni,0) jun_ni, COALESCE(b.act,0) jun_act,
    COALESCE(a.ni,0) aug_ni, COALESCE(a.act,0) aug_act
  FROM (SELECT * FROM agg WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM agg WHERE period='midJun') b ON a.cell=b.cell
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
SELECT r.cell,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) aug_share,
  ROUND(r.rj*100,2) jun_rate, ROUND(r.ra*100,2) aug_rate,
  ROUND(((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100,3) mix_pp,
  ROUND((r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100,3) rate_pp,
  ROUND(
    ((r.aug_ni*1.0/t.aug_tot)-(r.jun_ni*1.0/t.jun_tot))*COALESCE(r.rj,0)*100
    +(r.aug_ni*1.0/t.aug_tot)*(COALESCE(r.ra,0)-COALESCE(r.rj,0))*100
  ,3) total_pp,
  ROUND((t.r_aug-t.r_jun)*100,3) segment_drop_pp
FROM rates r CROSS JOIN t
ORDER BY 1
""")
