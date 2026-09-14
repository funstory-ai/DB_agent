# -*- coding: utf-8 -*-
"""Verify _M top3 minor filter vs zombie versions."""
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

show("2a weekly main", """
SELECT to_start_of_week(dates, 1) AS wk,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-06-01' AND dates < '2026-09-02'
GROUP BY 1 ORDER BY 1
""")

show("2b weekly _M", """
SELECT to_start_of_week(dates, 1) AS wk,
  SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
  ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
    / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-06-01' AND dates < '2026-09-02'
GROUP BY 1 ORDER BY 1
""")

show("3 Win Chrome rates", """
SELECT period, src, ni, act, rate FROM (
  SELECT 'midJun' AS period, 'main' AS src,
    SUM(IF(event_name='init_page_daily', new_device_count, 0)) AS ni,
    SUM(IF(event_name='translate_page', new_device_count, 0)) AS act,
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2) AS rate
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
    AND dates >= '2026-06-10' AND dates < '2026-06-21'
  UNION ALL
  SELECT 'midJun', '_M',
    SUM(IF(event_name='init_page_daily', new_device_count, 0)),
    SUM(IF(event_name='translate_page', new_device_count, 0)),
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2)
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
    AND dates >= '2026-06-10' AND dates < '2026-06-21'
  UNION ALL
  SELECT 'lateAug', 'main',
    SUM(IF(event_name='init_page_daily', new_device_count, 0)),
    SUM(IF(event_name='translate_page', new_device_count, 0)),
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2)
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
    AND dates >= '2026-08-20' AND dates < '2026-08-31'
  UNION ALL
  SELECT 'lateAug', '_M',
    SUM(IF(event_name='init_page_daily', new_device_count, 0)),
    SUM(IF(event_name='translate_page', new_device_count, 0)),
    ROUND(SUM(IF(event_name='translate_page', new_device_count, 0))*100.0
      / NULLIF(SUM(IF(event_name='init_page_daily', new_device_count, 0)),0), 2)
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE LOWER(TRIM(os_name))='windows' AND TRIM(browser_name)='Chrome'
    AND dates >= '2026-08-20' AND dates < '2026-08-31'
) t
""")

show("4 NI main vs _M", """
SELECT period, src, ni FROM (
  SELECT 'midJun' AS period, 'main' AS src,
    SUM(IF(event_name='init_page_daily', new_device_count,0)) AS ni
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
  UNION ALL
  SELECT 'midJun', '_M',
    SUM(IF(event_name='init_page_daily', new_device_count,0))
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE dates >= '2026-06-10' AND dates < '2026-06-21'
  UNION ALL
  SELECT 'lateAug', 'main',
    SUM(IF(event_name='init_page_daily', new_device_count,0))
  FROM immdata.imm_event_device_count_by_utf8_day
  WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
  UNION ALL
  SELECT 'lateAug', '_M',
    SUM(IF(event_name='init_page_daily', new_device_count,0))
  FROM immdata.imm_event_device_count_by_utf8_day_M
  WHERE dates >= '2026-08-20' AND dates < '2026-08-31'
) t
""")

show("5 Aug25 top minors from translate_page", """
WITH day_data AS (
  SELECT
    concat(split_part(version, '.', 1), '.', split_part(version, '.', 2)) AS version_minor,
    to_int32(split_part(version, '.', 1)) AS v1,
    to_int32(split_part(version, '.', 2)) AS v2
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-25' AND created_ts < '2026-08-26'
    AND ex_char_arg10 = 'com'
    AND version IS NOT NULL
    AND version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+$'
    AND event_name = 'translate_page'
),
ranked AS (
  SELECT version_minor, v1, v2,
    row_number() OVER (ORDER BY v1 DESC, v2 DESC) AS rn
  FROM (SELECT version_minor, v1, v2 FROM day_data GROUP BY 1,2,3) t
)
SELECT version_minor, v1, v2, rn FROM ranked WHERE rn <= 5 ORDER BY rn
""")

show("6 Aug25 zombie vs top3", """
WITH day_data AS (
  SELECT
    device_id, event_name, is_new_user_today, version,
    concat(split_part(version, '.', 1), '.', split_part(version, '.', 2)) AS version_minor,
    to_int32(split_part(version, '.', 1)) AS v1,
    to_int32(split_part(version, '.', 2)) AS v2
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-25' AND created_ts < '2026-08-26'
    AND ex_char_arg10 = 'com'
    AND version IS NOT NULL
    AND version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+$'
),
latest_minor AS (
  SELECT version_minor FROM (
    SELECT version_minor, v1, v2,
      row_number() OVER (ORDER BY v1 DESC, v2 DESC) AS rn
    FROM (
      SELECT version_minor, v1, v2 FROM day_data
      WHERE event_name = 'translate_page' GROUP BY 1,2,3
    ) t
  ) s WHERE rn <= 3
),
ni AS (
  SELECT DISTINCT device_id, version_minor, version
  FROM day_data
  WHERE event_name = 'init_page_daily' AND is_new_user_today = '1'
)
SELECT
  COUNT(*) AS ni_devices,
  SUM(CASE WHEN version_minor IN (SELECT version_minor FROM latest_minor) THEN 1 ELSE 0 END) AS in_top3,
  SUM(CASE WHEN version_minor NOT IN (SELECT version_minor FROM latest_minor) THEN 1 ELSE 0 END) AS out_top3,
  ROUND(SUM(CASE WHEN version_minor NOT IN (SELECT version_minor FROM latest_minor) THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS out_pct,
  SUM(CASE WHEN version IN ('1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7') THEN 1 ELSE 0 END) AS zombie_ni,
  SUM(CASE WHEN version IN ('1.15.10','1.16.5','1.20.13','1.23.9','1.23.10','1.11.7')
            AND version_minor IN (SELECT version_minor FROM latest_minor) THEN 1 ELSE 0 END) AS zombie_kept_in_top3
FROM ni
""")
