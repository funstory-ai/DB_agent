# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def show(title, sql):
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols), flush=True)
    for r in rows:
        print("\t".join(str(x) for x in r), flush=True)

show("_M by browser midJun", """
SELECT TRIM(browser_name) AS b,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
GROUP BY 1
HAVING SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 3000
ORDER BY ni DESC
""")

show("_M by browser lateAug", """
SELECT TRIM(browser_name) AS b,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
GROUP BY 1
HAVING SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 3000
ORDER BY ni DESC
""")

show("_M by os both", """
SELECT 'midJun' AS period, LOWER(TRIM(os_name)) AS os,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
GROUP BY 1, 2
HAVING SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 2000
UNION ALL
SELECT 'lateAug', LOWER(TRIM(os_name)),
  SUM(IF(event_name='init_page_daily', new_device_count, 0)),
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2)
FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
GROUP BY 1, 2
HAVING SUM(IF(event_name='init_page_daily', new_device_count, 0)) >= 2000
""")

show("_M weekly already known; Electron share _M", """
SELECT period, b, ni, rate FROM (
  SELECT 'midJun' AS period, TRIM(browser_name) AS b,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
    AND TRIM(browser_name) IN ('Chrome','Electron','Microsoft Edge','Safari','ImtiOS_oversea')
  GROUP BY 1, 2
  UNION ALL
  SELECT 'lateAug', TRIM(browser_name),
    SUM(IF(event_name='init_page_daily', new_device_count, 0)),
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2)
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
    AND TRIM(browser_name) IN ('Chrome','Electron','Microsoft Edge','Safari','ImtiOS_oversea')
  GROUP BY 1, 2
) t
""")
