# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

sql = """
SELECT to_start_of_week(dates, 1) AS wk,
  SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS ni,
  SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS act,
  ROUND(
    SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 100.0
      / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0),
    2
  ) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-06-01' AND dates < '2026-09-02'
GROUP BY 1
ORDER BY 1
"""
cols, rows = query(sql)
print("\t".join(cols))
for r in rows:
    print("\t".join(str(x) for x in r))
