# -*- coding: utf-8 -*-
"""T028 follow-up: remaining act-rate drop after Rule A."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

KICK = """
  MAX(CASE WHEN LOWER(TRIM(install_from)) = 'official_userscript'
            AND (
              (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
              OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
            ) THEN 1 ELSE 0 END)
    OVER (PARTITION BY device_id, DATE(add_hours(created_ts, 8)))
"""

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join("" if x is None else str(x) for x in r), flush=True)

# A) Weekly overall act rate WITH Rule A (fair across periods)
show("A weekly overall RuleA-ex (P034)", f"""
WITH base AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS d,
    device_id, event_name, is_new_user_today,
    {KICK} AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-02'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT
    to_start_of_week(d, 1) AS wk,
    device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) AS act
  FROM base
  GROUP BY 1, 2
)
SELECT wk,
  SUM(ni) AS ni, SUM(act) AS act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 2) AS rate
FROM dev
GROUP BY 1 ORDER BY 1
""")

# B) Same WITHOUT kick (to show how much Rule A recovered)
show("B weekly overall RAW (no kick)", """
WITH base AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS d,
    device_id, event_name, is_new_user_today
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-06-01' AND created_ts < '2026-09-02'
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT
    to_start_of_week(d, 1) AS wk,
    device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM base GROUP BY 1, 2
)
SELECT wk, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 2) rate
FROM dev GROUP BY 1 ORDER BY 1
""")

# C) By OS: mid-Jun vs late-Aug (Rule A)
show("C by OS midJun vs lateAug RuleA", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    LOWER(TRIM(os_name)) AS os,
    device_id, event_name, is_new_user_today,
    {KICK} AS kick
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT period, os, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
)
SELECT period, os, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 2) rate,
  ROUND(SUM(ni)*100.0/SUM(SUM(ni)) OVER (PARTITION BY period), 1) share_ni
FROM dev
GROUP BY 1,2
ORDER BY period, ni DESC
""")

# D) Top install_from × browser shifts (Rule A kept only)
show("D top install×browser midJun vs lateAug RuleA", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    COALESCE(NULLIF(LOWER(TRIM(install_from)),''),'(blank)') AS install_from,
    COALESCE(NULLIF(TRIM(browser_name),''),'(blank)') AS browser,
    device_id, event_name, is_new_user_today,
    {KICK} AS kick
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT period, install_from, browser, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3,4
),
agg AS (
  SELECT period, install_from, browser, SUM(ni) ni, SUM(act) act,
    ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 1) rate
  FROM dev GROUP BY 1,2,3
  HAVING SUM(ni) >= 3000
)
SELECT * FROM agg
ORDER BY period, ni DESC
""")

# E) Contribution: which segments explain rate drop (share×rate)
# Compare overall and show userscript-kept (non RuleA) vs others
show("E userscript KEEP vs non-userscript rates", f"""
WITH base AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-06-10' AND created_ts < '2026-06-21' THEN 'midJun'
      WHEN created_ts >= '2026-08-20' AND created_ts < '2026-08-31' THEN 'lateAug'
    END AS period,
    CASE
      WHEN LOWER(TRIM(install_from))='official_userscript' THEN 'userscript'
      ELSE 'other_install'
    END AS ch,
    device_id, event_name, is_new_user_today,
    {KICK} AS kick
  FROM immdata.user_behaviour
  WHERE (
      (created_ts >= '2026-06-10' AND created_ts < '2026-06-21')
      OR (created_ts >= '2026-08-20' AND created_ts < '2026-08-31')
    )
    AND version <> '1.11.4'
    AND event_name IN ('init_page_daily', 'translate_page')
),
dev AS (
  SELECT period, ch, device_id,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' AND kick=0 THEN 1 ELSE 0 END) act
  FROM base WHERE period IS NOT NULL
  GROUP BY 1,2,3
)
SELECT period, ch, SUM(ni) ni, SUM(act) act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 2) rate,
  ROUND(SUM(ni)*100.0/SUM(SUM(ni)) OVER (PARTITION BY period), 1) share
FROM dev GROUP BY 1,2 ORDER BY 1,2
""")
