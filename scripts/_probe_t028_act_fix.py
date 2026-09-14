# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

SQL = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-08' THEN 'W01'
      WHEN created_ts >= '2026-07-08' AND created_ts < '2026-07-15' THEN 'W02'
      WHEN created_ts >= '2026-07-15' AND created_ts < '2026-07-22' THEN 'W03'
      WHEN created_ts >= '2026-07-22' AND created_ts < '2026-07-28' THEN 'W04'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-04' THEN 'W05'
      WHEN created_ts >= '2026-08-04' AND created_ts < '2026-08-11' THEN 'W06'
      WHEN created_ts >= '2026-08-11' AND created_ts < '2026-08-18' THEN 'W07'
      WHEN created_ts >= '2026-08-18' AND created_ts < '2026-08-25' THEN 'W08'
      WHEN created_ts >= '2026-08-25' AND created_ts < '2026-09-01' THEN 'W09'
    END AS wk,
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 50 = 0
  GROUP BY 1, 2
  HAVING wk IS NOT NULL
),
seg AS (
  SELECT wk, device_id, install_ts,
    CASE WHEN kick=1 THEN 'kick' ELSE 'remain' END AS seg
  FROM installs
),
activated AS (
  SELECT DISTINCT s.device_id
  FROM seg s
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = s.device_id
   AND b.created_ts >= s.install_ts
   AND b.created_ts < DATEADD(day, 3, s.install_ts)
   AND b.event_name IN (
     'translate_page', 'translate_video_subtitle', 'use_ai_subtitle',
     'translate_image', 'translate_manga', 'selection_translate',
     'translate_input', 'translateTextInSidePanel'
   )
   AND ABS(xxhash64(b.device_id)) % 50 = 0
)
SELECT
  s.wk, s.seg,
  COUNT(*) AS n_sample,
  COUNT(a.device_id) AS act_3d,
  COUNT(a.device_id) * 1.0 / COUNT(*) AS act_rate
FROM seg s
LEFT JOIN activated a ON a.device_id = s.device_id
GROUP BY 1, 2
ORDER BY 1, 2
"""

cols, rows = query(SQL)
print(cols, flush=True)
for r in rows:
    print(r, flush=True)
