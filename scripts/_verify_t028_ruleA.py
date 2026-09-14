# -*- coding: utf-8 -*-
"""Independent verify: other-channel embed surge + Rule A SQL correctness."""
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
    return rows

# 1) Top install_from × browser × os for new installs: pre vs post
show("1 top userscript combos PRE vs POST (new install)", """
WITH base AS (
  SELECT
    CASE WHEN created_ts < '2026-07-28' THEN 'pre' ELSE 'post' END AS seg,
    LOWER(TRIM(os_name)) AS os,
    TRIM(browser_name) AS browser,
    COUNT(DISTINCT device_id) AS ni
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(install_from)) = 'official_userscript'
  GROUP BY 1, 2, 3
)
SELECT seg, os, browser, ni,
  ROUND(ni * 100.0 / SUM(ni) OVER (PARTITION BY seg), 1) AS share_pct
FROM base
QUALIFY ROW_NUMBER() OVER (PARTITION BY seg ORDER BY ni DESC) <= 12
ORDER BY seg, ni DESC
""")

# 2) Same combos with activation rate (P034)
show("2 top userscript combos act rate POST", """
WITH dev AS (
  SELECT
    device_id,
    LOWER(TRIM(os_name)) AS os,
    TRIM(browser_name) AS browser,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-28' AND created_ts < '2026-09-01'
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND event_name IN ('init_page_daily','translate_page')
  GROUP BY 1, 2, 3
)
SELECT os, browser,
  SUM(ni) AS ni, SUM(act) AS act,
  ROUND(SUM(act)*100.0/NULLIF(SUM(ni),0), 1) AS act_rate
FROM dev
GROUP BY 1, 2
HAVING SUM(ni) >= 5000
ORDER BY ni DESC
LIMIT 20
""")

# 3) Maxthon daily (all + macos userscript) vs Safari pattern
show("3 Maxthon daily new/act (browser=Maxthon)", """
SELECT to_date(created_ts) AS d,
  COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
  COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
  AND TRIM(browser_name) = 'Maxthon'
GROUP BY 1 ORDER BY 1
""")

show("3b Maxthon×macos×userscript daily", """
SELECT to_date(created_ts) AS d,
  COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
  COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
  AND TRIM(browser_name) = 'Maxthon'
  AND LOWER(TRIM(os_name)) = 'macos'
  AND LOWER(TRIM(install_from)) = 'official_userscript'
GROUP BY 1 ORDER BY 1
""")

# 4) Compare kick scopes: old (all Safari×us) vs Rule A (ios Safari + macos Maxthon)
show("4 kick scope Aug: old vs RuleA vs RuleC", """
WITH flagged AS (
  SELECT device_id,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS kick_old,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND (
                (LOWER(TRIM(os_name))='ios' AND TRIM(browser_name)='Safari')
                OR (LOWER(TRIM(os_name))='macos' AND TRIM(browser_name)='Maxthon')
              ) THEN 1 ELSE 0 END) AS kick_a,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name) NOT LIKE 'Imt%'
              AND TRIM(browser_name) IN ('Safari','Maxthon','Chrome')
              AND NOT (TRIM(browser_name)='Chrome' AND LOWER(TRIM(os_name))<>'windows')
         THEN 1 ELSE 0 END) AS kick_c_approx,
    MAX(CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS ni,
    MAX(CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN 1 ELSE 0 END) AS act
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-01' AND created_ts < '2026-09-01'
  GROUP BY 1
)
SELECT
  SUM(ni) all_ni,
  SUM(CASE WHEN kick_old=1 THEN ni ELSE 0 END) old_kick_ni,
  SUM(CASE WHEN kick_a=1 THEN ni ELSE 0 END) a_kick_ni,
  SUM(CASE WHEN kick_old=1 AND kick_a=0 THEN ni ELSE 0 END) old_only_ni,
  SUM(CASE WHEN kick_a=1 AND kick_old=0 THEN ni ELSE 0 END) a_only_ni,
  ROUND(SUM(CASE WHEN kick_a=1 THEN act ELSE 0 END)*100.0
    / NULLIF(SUM(CASE WHEN kick_a=1 THEN ni ELSE 0 END),0), 1) a_kick_act_rate,
  ROUND(SUM(CASE WHEN kick_a=0 THEN act ELSE 0 END)*100.0
    / NULLIF(SUM(CASE WHEN kick_a=0 THEN ni ELSE 0 END),0), 1) a_remain_act_rate
FROM flagged
""")

# 5) What is old_only? (Safari non-iOS that Rule A keeps)
show("5 Safari×userscript by os Aug (what RuleA drops vs keeps)", """
SELECT LOWER(TRIM(os_name)) AS os,
  COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
  COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-01' AND created_ts < '2026-09-01'
  AND LOWER(TRIM(install_from)) = 'official_userscript'
  AND TRIM(browser_name) = 'Safari'
GROUP BY 1 ORDER BY ni DESC
""")

# 6) Windows Chrome × userscript?
show("6 Win Chrome×userscript daily sample", """
SELECT to_date(created_ts) AS d,
  COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
  COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
  AND LOWER(TRIM(os_name)) = 'windows'
  AND TRIM(browser_name) = 'Chrome'
  AND LOWER(TRIM(install_from)) = 'official_userscript'
GROUP BY 1 ORDER BY 1
""")

# 7) PRE false positive Rule A
show("7 RuleA PRE FP (7/1-7/27)", """
SELECT LOWER(TRIM(os_name)) os, TRIM(browser_name) browser,
  COUNT(DISTINCT device_id) ni
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-01' AND created_ts < '2026-07-28'
  AND event_name='init_page_daily' AND is_new_user_today='1'
  AND LOWER(TRIM(install_from))='official_userscript'
  AND (
    (LOWER(TRIM(os_name))='ios' AND TRIM(browser_name)='Safari')
    OR (LOWER(TRIM(os_name))='macos' AND TRIM(browser_name)='Maxthon')
  )
GROUP BY 1,2 ORDER BY ni DESC
""")

# 8) Current TASK still old rule?
show("8 TASK definition check", """
SELECT name, state
FROM (SELECT 1) t WHERE 1=0
""")
