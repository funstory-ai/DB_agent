# -*- coding: utf-8 -*-
"""Verify T028 ETL patch: data + TASK status."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def show(title, sql):
    print(f"\n{'='*60}\n{title}\n{'='*60}", flush=True)
    try:
        cols, rows = query(sql)
        print(cols, flush=True)
        for r in rows:
            print(r, flush=True)
        return cols, rows
    except Exception as e:
        print("ERR:", e, flush=True)
        return None, None

# 1) TASK status + definition keywords
show("1 TASK status", """
SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'
""")

_, task_rows = show("1b TASK embed keyword check", """
SELECT
  name,
  state,
  schedule,
  CASE
    WHEN definition ILIKE '%embed_device_day%' THEN 'yes'
    ELSE 'NO'
  END AS has_embed_cte,
  CASE
    WHEN definition ILIKE '%official_userscript%' THEN 'yes'
    ELSE 'NO'
  END AS has_kick_rule,
  last_completed_on
FROM (
  SELECT
    t[2] AS name,
    t[8] AS state,
    t[7] AS schedule,
    t[9] AS definition,
    t[15] AS last_completed_on
  FROM (
    SELECT array(
      name, task_name, created_on, owner, comment, warehouse, schedule_expr,
      status, definition, error_message, timeout, suspend_task_after_num_failures,
      next_scheduled_at, last_suspended_on, last_completed_on, created_on_extra
    ) AS t
    FROM (SELECT 1)
  ) x
) y
WHERE 1=0
""")

# Simpler: parse from SHOW TASKS in python
cols, rows = query("SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'")
print("\n=== 1c TASK summary ===", flush=True)
for r in rows:
    name = r[1]
    state = r[7]
    sched = r[6]
    defn = r[8] if len(r) > 8 else ''
    last_run = r[14] if len(r) > 14 else None
    has_embed = 'embed_device_day' in str(defn)
    has_kick = 'official_userscript' in str(defn)
    print(f"name={name} state={state} schedule={sched}", flush=True)
    print(f"  embed_cte={has_embed} kick_rule={has_kick} last_completed={last_run}", flush=True)

# 2) Table freshness
show("2 table max dates", """
SELECT 'main' AS tbl, MAX(dates) AS max_date, COUNT(*) AS total_rows
FROM immdata.imm_event_device_count_by_utf8_day
UNION ALL
SELECT '_M', MAX(dates), COUNT(*)
FROM immdata.imm_event_device_count_by_utf8_day_M
""")

# 3) Safari new install / activation / rate (post-patch expectation)
show("3 Safari daily (summary table)", """
SELECT dates,
  SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
  SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation,
  SUM(IF(event_name = 'translate_page', device_count, 0)) AS dau,
  ROUND(
    SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 100.0
      / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0),
    2
  ) AS act_rate_pct
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name = 'Safari'
  AND dates BETWEEN '2026-07-24' AND '2026-09-02'
GROUP BY dates
ORDER BY dates
""")

# 4) Compare summary vs behaviour direct (ex embed) for key dates
show("4 cross-check behaviour vs summary (ex embed)", """
WITH beh AS (
  SELECT
    to_date(created_ts) AS d,
    COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
    COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act
  FROM (
    SELECT created_ts, device_id, event_name, is_new_user_today,
      MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript' AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END)
        OVER (PARTITION BY device_id, to_date(created_ts)) AS embed
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-07-24' AND created_ts < '2026-09-03'
      AND TRIM(browser_name) = 'Safari'
  ) x
  WHERE embed = 0
  GROUP BY 1
),
summ AS (
  SELECT dates AS d,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE browser_name = 'Safari'
    AND dates BETWEEN '2026-07-24' AND '2026-09-02'
  GROUP BY 1
)
SELECT
  COALESCE(b.d, s.d) AS d,
  b.ni AS beh_ni, s.ni AS sum_ni,
  b.act AS beh_act, s.act AS sum_act,
  ABS(COALESCE(b.ni,0) - COALESCE(s.ni,0)) AS ni_diff,
  ABS(COALESCE(b.act,0) - COALESCE(s.act,0)) AS act_diff
FROM beh b
FULL OUTER JOIN summ s ON b.d = s.d
WHERE COALESCE(b.d, s.d) IN ('2026-07-27','2026-07-28','2026-07-30','2026-08-03','2026-08-31')
ORDER BY 1
""")

# 5) grain duplicate check in backfill window
show("5 grain dup check backfill window", """
SELECT dates, COUNT(*) AS rows, COUNT(DISTINCT (dates, event_name, os_name, platform_type, browser_name)) AS grains
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates BETWEEN '2026-07-28' AND '2026-08-31'
GROUP BY dates
HAVING rows <> grains
LIMIT 10
""")

# 6) Sep dates after patch - should also be clean if task ran
show("6 recent Safari (Sep if task ran)", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS new_install,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0)) * 100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)), 0), 2) AS act_rate_pct
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name = 'Safari' AND dates >= '2026-09-01'
GROUP BY 1 ORDER BY 1
""")
