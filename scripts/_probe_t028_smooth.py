# -*- coding: utf-8 -*-
"""T028: after-kick smoothness — daily installs + weekly act rate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Daily iOS new installs: total / kick / remain (Jul–Aug)
SQL_DAILY = """
WITH installs AS (
  SELECT
    to_date(created_ts) AS d,
    device_id,
    MAX(CASE
      WHEN LOWER(TRIM(install_from)) = 'official_userscript'
       AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
  GROUP BY 1, 2
)
SELECT
  d,
  COUNT(*) AS ios_all,
  SUM(kick) AS kick_n,
  COUNT(*) - SUM(kick) AS remain_n
FROM installs
GROUP BY 1
ORDER BY 1
"""

# Weekly 3d activation: remain vs kick (2% sample for speed)
# Week buckets by install date
SQL_ACT_W = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-08' THEN 'W01_0701'
      WHEN created_ts >= '2026-07-08' AND created_ts < '2026-07-15' THEN 'W02_0708'
      WHEN created_ts >= '2026-07-15' AND created_ts < '2026-07-22' THEN 'W03_0715'
      WHEN created_ts >= '2026-07-22' AND created_ts < '2026-07-28' THEN 'W04_0722'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-04' THEN 'W05_0728'
      WHEN created_ts >= '2026-08-04' AND created_ts < '2026-08-11' THEN 'W06_0804'
      WHEN created_ts >= '2026-08-11' AND created_ts < '2026-08-18' THEN 'W07_0811'
      WHEN created_ts >= '2026-08-18' AND created_ts < '2026-08-25' THEN 'W08_0818'
      WHEN created_ts >= '2026-08-25' AND created_ts < '2026-09-01' THEN 'W09_0825'
    END AS wk,
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE
      WHEN LOWER(TRIM(install_from)) = 'official_userscript'
       AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 50 = 0
  GROUP BY 1, 2
  HAVING wk IS NOT NULL
),
seg AS (
  SELECT wk, device_id, install_ts,
    CASE WHEN kick = 1 THEN 'kick' ELSE 'remain' END AS seg
  FROM installs
),
acts AS (
  SELECT device_id, created_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-04'
    AND event_name IN (
      'translate_page', 'translate_video_subtitle', 'use_ai_subtitle',
      'translate_image', 'translate_manga', 'selection_translate',
      'translate_input', 'translateTextInSidePanel'
    )
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 50 = 0
)
SELECT
  s.wk,
  s.seg,
  COUNT(*) AS n_sample,
  COUNT(DISTINCT CASE
    WHEN a.device_id IS NOT NULL
     AND a.created_ts >= s.install_ts
     AND a.created_ts < DATEADD(day, 3, s.install_ts)
    THEN s.device_id END) AS act_3d,
  COUNT(DISTINCT CASE
    WHEN a.device_id IS NOT NULL
     AND a.created_ts >= s.install_ts
     AND a.created_ts < DATEADD(day, 3, s.install_ts)
    THEN s.device_id END) * 1.0 / COUNT(*) AS act_rate
FROM seg s
LEFT JOIN acts a ON a.device_id = s.device_id
GROUP BY 1, 2
ORDER BY 1, 2
"""

# Period summary: pre vs post jump for remain
SQL_PERIOD = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-28' THEN 'pre'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-09-01' THEN 'post'
    END AS period,
    device_id,
    MAX(CASE
      WHEN LOWER(TRIM(install_from)) = 'official_userscript'
       AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
  GROUP BY 1, 2
  HAVING period IS NOT NULL
)
SELECT
  period,
  COUNT(*) AS ios_all,
  SUM(kick) AS kick_n,
  COUNT(*) - SUM(kick) AS remain_n,
  (COUNT(*) - SUM(kick)) * 1.0 / CASE WHEN period = 'pre' THEN 27 ELSE 35 END AS remain_per_day
FROM installs
GROUP BY 1
ORDER BY 1
"""


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===", flush=True)
    print(cols, flush=True)
    for r in rows:
        print(r, flush=True)


if __name__ == "__main__":
    show("period_remain", query(SQL_PERIOD))
    show("daily", query(SQL_DAILY))
    show("act_weekly_2pct", query(SQL_ACT_W))
