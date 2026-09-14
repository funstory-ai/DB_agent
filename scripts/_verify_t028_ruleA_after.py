# -*- coding: utf-8 -*-
"""Verify T028 Rule A after write-warehouse run."""
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

# 1 TASK
cols, rows = query("SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'")
print("\n=== 1 TASK Rule A ===", flush=True)
for r in rows:
    name = r[1]
    if name not in (
        "update_imm_event_device_count_by_utf8_day",
        "update_imm_event_device_count_by_utf8_day_M",
    ):
        continue
    d = str(r[8])
    print(f"NAME={name}", flush=True)
    print(f"  STATE={r[7]} last={r[14]} next={r[13]}", flush=True)
    has_embed = "embed_device_day" in d
    has_safari = "Safari" in d
    has_maxthon = "Maxthon" in d
    has_ios = "os_name" in d and "ios" in d
    has_macos = "macos" in d.lower()
    has_rule_a = has_maxthon and "official_userscript" in d and has_safari
    print(
        f"  embed={has_embed} Safari={has_safari} Maxthon={has_maxthon}",
        flush=True,
    )
    print(f"  ios_filter={has_ios} macos_filter={has_macos}", flush=True)
    print(f"  RULE_A_OK={has_rule_a}", flush=True)

# 2 freshness
show("2 max dates", """
SELECT 'main' AS t, MAX(dates) AS max_d, COUNT(*) AS rows
FROM immdata.imm_event_device_count_by_utf8_day
UNION ALL
SELECT '_M', MAX(dates), COUNT(*)
FROM immdata.imm_event_device_count_by_utf8_day_M
""")

# 3 Safari smooth (Rule A still kicks ios Safari)
show("3 Safari daily 7/24-9/01", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name='Safari'
  AND dates BETWEEN '2026-07-24' AND '2026-09-01'
GROUP BY dates ORDER BY dates
""")

# 4 Maxthon should be near empty after kick
show("4 Maxthon daily 7/24-9/01", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name='Maxthon'
  AND dates BETWEEN '2026-07-24' AND '2026-09-01'
GROUP BY dates ORDER BY dates
""")

# 5 macOS overall act rate recovery
show("5 macOS overall 7/24-8/10", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE LOWER(TRIM(os_name))='macos'
  AND dates BETWEEN '2026-07-24' AND '2026-08-10'
GROUP BY dates ORDER BY dates
""")

# 6 cross-check key days: summary vs behaviour Rule A
show("6 cross-check Safari/Maxthon vs behaviour RuleA", """
WITH beh AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS d,
    TRIM(browser_name) AS browser,
    COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
    COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
  FROM (
    SELECT created_ts, device_id, event_name, is_new_user_today, browser_name,
      MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
                AND (
                  (LOWER(TRIM(os_name))='ios' AND TRIM(browser_name)='Safari')
                  OR (LOWER(TRIM(os_name))='macos' AND TRIM(browser_name)='Maxthon')
                ) THEN 1 ELSE 0 END)
        OVER (PARTITION BY device_id, DATE(add_hours(created_ts, 8))) AS kick
    FROM immdata.user_behaviour
    WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
      AND created_ts < add_hours(add_days(to_date('2026-08-03'), 1), -8)
      AND version <> '1.11.4'
      AND TRIM(browser_name) IN ('Safari', 'Maxthon')
  ) x
  WHERE kick = 0
  GROUP BY 1, 2
),
summ AS (
  SELECT dates AS d, browser_name AS browser,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE browser_name IN ('Safari', 'Maxthon')
    AND dates BETWEEN '2026-07-28' AND '2026-08-03'
  GROUP BY 1, 2
)
SELECT COALESCE(b.d, s.d) AS d, COALESCE(b.browser, s.browser) AS browser,
  b.ni AS beh_ni, s.ni AS sum_ni, ABS(COALESCE(b.ni,0)-COALESCE(s.ni,0)) AS ni_diff,
  b.act AS beh_act, s.act AS sum_act
FROM beh b
FULL OUTER JOIN summ s ON b.d = s.d AND b.browser = s.browser
ORDER BY 1, 2
""")

# 7 grain dup
show("7 grain dup sample", """
SELECT dates, event_name, os_name, platform_type, browser_name, COUNT(*) AS c
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates BETWEEN '2026-07-28' AND '2026-09-01'
GROUP BY 1,2,3,4,5
HAVING COUNT(*) > 1
LIMIT 5
""")

# 8 update_time on backfill edge days
show("8 update_time edge", """
SELECT dates, browser_name, MAX(update_time) AS ut,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name IN ('Safari','Maxthon')
  AND dates IN ('2026-07-28','2026-08-31','2026-09-01')
GROUP BY 1, 2
ORDER BY 1, 2
""")
