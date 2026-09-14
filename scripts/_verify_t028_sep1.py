# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def q(title, sql):
    print(f"\n=== {title} ===", flush=True)
    _, rows = query(sql)
    for x in rows:
        print(x, flush=True)
    return rows

q("Sep1 Safari", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS new_install,
  SUM(IF(event_name='translate_page', new_device_count, 0)) AS activation,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS act_rate,
  MAX(update_time) AS ut
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name='Safari' AND dates='2026-09-01'
GROUP BY dates
""")

q("Aug30-Sep1 Safari trend", """
SELECT dates,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS act_rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE browser_name='Safari' AND dates BETWEEN '2026-08-30' AND '2026-09-01'
GROUP BY dates ORDER BY dates
""")

q("Sep1 diff vs behaviour Safari", """
WITH base AS (
  SELECT DATE(add_hours(created_ts, 8)) AS d, device_id, event_name, is_new_user_today,
    MAX(CASE WHEN LOWER(TRIM(install_from)) = 'official_userscript' AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END)
      OVER (PARTITION BY device_id, DATE(add_hours(created_ts, 8))) AS embed
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-09-01'), 1), -32)
    AND created_ts < add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND TRIM(browser_name) = 'Safari'
    AND version <> '1.11.4'
)
SELECT
  COUNT(DISTINCT CASE WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' AND embed = 0 THEN device_id END) AS beh_ni,
  COUNT(DISTINCT CASE WHEN event_name = 'translate_page' AND is_new_user_today = '1' AND embed = 0 THEN device_id END) AS beh_act
FROM base
WHERE d = to_date('2026-09-01')
""")

_, tasks = query("SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'")
print("\n=== TASK ===", flush=True)
for r in tasks:
    name = r[1]
    if name in ("update_imm_event_device_count_by_utf8_day", "update_imm_event_device_count_by_utf8_day_M"):
        defn = str(r[8])
        print(f"{name}: state={r[7]} last_completed={r[14]} embed_ok={'embed_device_day' in defn}", flush=True)

q("max dates", """
SELECT 'main' t, MAX(dates) d FROM immdata.imm_event_device_count_by_utf8_day
UNION ALL SELECT '_M', MAX(dates) FROM immdata.imm_event_device_count_by_utf8_day_M
""")
