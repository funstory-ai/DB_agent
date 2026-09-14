# -*- coding: utf-8 -*-
"""T028 Kitagawa: each factor's pp contribution to act-rate drop.
VPN caveat: real_geo unreliable; prefer interface_language.
"""
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
    return {c: [row[i] for row in rows] for i, c in enumerate(cols)} if rows else {}

# ---------- L1: headline main table OS (Rule A already in table) ----------
show("L1 OS midJun vs lateAug main table", """
WITH base AS (
  SELECT
    CASE
      WHEN dates >= '2026-06-10' AND dates < '2026-06-21' THEN 'midJun'
      WHEN dates >= '2026-08-20' AND dates < '2026-08-31' THEN 'lateAug'
    END AS period,
    LOWER(TRIM(os_name)) AS os,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE (dates >= '2026-06-10' AND dates < '2026-06-21')
     OR (dates >= '2026-08-20' AND dates < '2026-08-31')
  GROUP BY 1,2
  HAVING period IS NOT NULL
),
tot AS (
  SELECT period, SUM(ni) ni, SUM(act) act FROM base GROUP BY 1
),
j AS (
  SELECT
    COALESCE(a.os, b.os) AS os,
    COALESCE(b.ni,0) AS jun_ni, COALESCE(b.act,0) AS jun_act,
    COALESCE(a.ni,0) AS aug_ni, COALESCE(a.act,0) AS aug_act
  FROM (SELECT * FROM base WHERE period='lateAug') a
  FULL OUTER JOIN (SELECT * FROM base WHERE period='midJun') b ON a.os=b.os
),
rates AS (
  SELECT os, jun_ni, jun_act, aug_ni, aug_act,
    jun_act*1.0/NULLIF(jun_ni,0) AS rj,
    aug_act*1.0/NULLIF(aug_ni,0) AS ra
  FROM j
),
t AS (
  SELECT
    MAX(CASE WHEN period='midJun' THEN ni END) AS jun_tot,
    MAX(CASE WHEN period='lateAug' THEN ni END) AS aug_tot,
    MAX(CASE WHEN period='midJun' THEN act END)*1.0
      /NULLIF(MAX(CASE WHEN period='midJun' THEN ni END),0) AS r_jun,
    MAX(CASE WHEN period='lateAug' THEN act END)*1.0
      /NULLIF(MAX(CASE WHEN period='lateAug' THEN ni END),0) AS r_aug
  FROM tot
)
SELECT r.os,
  ROUND(r.jun_ni*100.0/t.jun_tot,2) AS jun_share,
  ROUND(r.aug_ni*100.0/t.aug_tot,2) AS aug_share,
  ROUND(r.rj*100,2) AS jun_rate,
  ROUND(r.ra*100,2) AS aug_rate,
  -- Kitagawa: mix = (s_aug-s_jun)*rj ; rate = s_aug*(ra-rj)  (pp of overall)
  ROUND( ((r.aug_ni*1.0/t.aug_tot) - (r.jun_ni*1.0/t.jun_tot)) * r.rj * 100, 3) AS mix_pp,
  ROUND( (r.aug_ni*1.0/t.aug_tot) * (COALESCE(r.ra,0)-COALESCE(r.rj,0)) * 100, 3) AS rate_pp,
  ROUND(
    ((r.aug_ni*1.0/t.aug_tot) - (r.jun_ni*1.0/t.jun_tot)) * r.rj * 100
    + (r.aug_ni*1.0/t.aug_tot) * (COALESCE(r.ra,0)-COALESCE(r.rj,0)) * 100
  , 3) AS total_pp,
  ROUND((t.r_aug - t.r_jun)*100, 3) AS overall_drop_pp
FROM rates r CROSS JOIN t
WHERE r.jun_ni + r.aug_ni >= 1000
ORDER BY ABS(
  ((r.aug_ni*1.0/t.aug_tot) - (r.jun_ni*1.0/t.jun_tot)) * r.rj
  + (r.aug_ni*1.0/t.aug_tot) * (COALESCE(r.ra,0)-COALESCE(r.rj,0))
) DESC
""")
