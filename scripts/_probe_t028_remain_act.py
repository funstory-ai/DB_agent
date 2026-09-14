# -*- coding: utf-8 -*-
"""Remain-only weekly 3d act; EXISTS to avoid join blowup."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Two windows only: pre last week vs surge first week + mid Aug — remain only, 5% sample
SQL = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-21' AND created_ts < '2026-07-28' THEN 'pre_last'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-04' THEN 'post_w1'
      WHEN created_ts >= '2026-08-18' AND created_ts < '2026-08-25' THEN 'post_w8'
    END AS wk,
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-21' AND created_ts < '2026-08-25'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 20 = 0
  GROUP BY 1, 2
  HAVING wk IS NOT NULL AND kick = 0
)
SELECT
  wk,
  COUNT(*) AS n_sample,
  SUM(CASE WHEN EXISTS (
    SELECT 1
    FROM immdata.user_behaviour b
    WHERE b.device_id = i.device_id
      AND b.created_ts >= i.install_ts
      AND b.created_ts < DATEADD(day, 3, i.install_ts)
      AND b.event_name IN (
        'translate_page', 'translate_video_subtitle', 'use_ai_subtitle',
        'translate_image', 'translate_manga', 'selection_translate',
        'translate_input', 'translateTextInSidePanel'
      )
  ) THEN 1 ELSE 0 END) AS act_3d
FROM installs i
GROUP BY 1
ORDER BY 1
"""

cols, rows = query(SQL)
print(cols, flush=True)
for r in rows:
    n, a = r[1], r[2]
    rate = (a / n) if n else 0
    print(r, f"rate={rate:.4f}", flush=True)
