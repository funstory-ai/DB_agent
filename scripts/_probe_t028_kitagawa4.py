# -*- coding: utf-8 -*-
"""Shares + clean counterfactuals for contribution report."""
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
    return cols, rows

show("WinChrome install_from", """
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
    AND LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
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
SELECT period, ch, ni,
  ROUND(ni*100.0/SUM(ni) OVER (PARTITION BY period),2) share_pct,
  ROUND(act*100.0/NULLIF(ni,0),2) rate
FROM agg WHERE ni >= 3000
ORDER BY period, ni DESC
""")

# Recent 4-cell raw for local python kitagawa + CFs
cols, rows = show("recent 4cell raw", """
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN UPPER(TRIM(real_geo))='US' AND TRIM(interface_language)='en' THEN 'US_en'
      WHEN UPPER(TRIM(real_geo))='US' THEN 'US_nonEn'
      WHEN TRIM(interface_language)='en' THEN 'ex_en'
      ELSE 'ex_nonEn'
    END AS cell,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
    AND LOWER(TRIM(install_from))='chrome_store'
    AND (TRIM(version) LIKE '1.30.%' OR TRIM(version) LIKE '1.31.%' OR TRIM(version) LIKE '1.32.%')
    AND event_name IN ('init_page_daily','translate_page')
),
dev AS (
  SELECT period, cell, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL GROUP BY 1,2,3
)
SELECT period, cell, SUM(ni) ni, SUM(act) act
FROM dev GROUP BY 1,2 ORDER BY 1,2
""")

# Local counterfactuals
from collections import defaultdict
d = defaultdict(dict)
for period, cell, ni, act in rows:
    d[cell][period] = (int(ni), int(act))

cells = sorted(d.keys())
jun_tot = sum(d[c]['midJun'][0] for c in cells)
aug_tot = sum(d[c]['lateAug'][0] for c in cells)
jun_act = sum(d[c]['midJun'][1] for c in cells)
aug_act = sum(d[c]['lateAug'][1] for c in cells)
r_jun = jun_act / jun_tot
r_aug = aug_act / aug_tot
print(f"\n=== CF local ===", flush=True)
print(f"midJun {r_jun*100:.2f} lateAug {r_aug*100:.2f} drop {(r_aug-r_jun)*100:.2f}pp", flush=True)

# Kitagawa per cell
print("cell\tjun_s\taug_s\trj\tra\tmix\trate\ttotal", flush=True)
for c in cells:
    jn, ja = d[c]['midJun']
    an, aa = d[c]['lateAug']
    sj, sa = jn/jun_tot, an/aug_tot
    rj, ra = ja/jn, aa/an
    mix = (sa - sj) * rj * 100
    rate = sa * (ra - rj) * 100
    print(f"{c}\t{sj*100:.2f}\t{sa*100:.2f}\t{rj*100:.2f}\t{ra*100:.2f}\t{mix:.3f}\t{rate:.3f}\t{mix+rate:.3f}", flush=True)

# CF: freeze US_en rate at midJun, keep late shares
usen = 'US_en'
rj_u = d[usen]['midJun'][1] / d[usen]['midJun'][0]
cf1_act = sum(
    (d[c]['lateAug'][0] * (rj_u if c == usen else d[c]['lateAug'][1]/d[c]['lateAug'][0]))
    for c in cells
)
cf1 = cf1_act / aug_tot
print(f"CF freeze US_en rate: {cf1*100:.2f} recover {(cf1-r_aug)*100:.2f}pp of recent", flush=True)

# CF: freeze US_en share at midJun; late rates; redistribute extra US_en NI to others by late weights
sj_u = d[usen]['midJun'][0] / jun_tot
sa_u = d[usen]['lateAug'][0] / aug_tot
# Construct synthetic late shares: US_en = sj_u, others scaled
others = [c for c in cells if c != usen]
other_sa = sum(d[c]['lateAug'][0]/aug_tot for c in others)
synth = {usen: sj_u}
for c in others:
    synth[c] = (1 - sj_u) * (d[c]['lateAug'][0]/aug_tot) / other_sa
cf2 = sum(synth[c] * (d[c]['lateAug'][1]/d[c]['lateAug'][0]) for c in cells)
print(f"CF freeze US_en share (late rates): {cf2*100:.2f} recover {(cf2-r_aug)*100:.2f}pp", flush=True)

# CF: freeze both US_en share and rate at midJun
synth_r = {c: (d[c]['midJun'][1]/d[c]['midJun'][0] if c == usen else d[c]['lateAug'][1]/d[c]['lateAug'][0]) for c in cells}
cf3 = sum(synth[c] * synth_r[c] for c in cells)
print(f"CF freeze US_en share+rate: {cf3*100:.2f} recover {(cf3-r_aug)*100:.2f}pp", flush=True)

# CF: global en (not geo) freeze
# rebuild with en vs non-en
print("\n=== CF global interface_language=en ===", flush=True)
