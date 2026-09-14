# -*- coding: utf-8 -*-
"""T028: activation rate for iOS surge segments."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Install window Jul28-Aug3 (one week surge start) to keep activation join smaller
# Observe translate within 3 days after install

SQL = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-28' THEN 'pre'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-04' THEN 'surge_w1'
    END AS cohort,
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from)) = 'official_userscript' THEN 1 ELSE 0 END) AS is_ous,
    MAX(CASE WHEN TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END) AS is_safari,
    MAX(CASE WHEN LOWER(TRIM(userscript)) = 'true' THEN 1 ELSE 0 END) AS is_us,
    MAX(CASE WHEN TRIM(browser_name) LIKE 'ImtiOS%' THEN 1 ELSE 0 END) AS is_imt_app
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01'
    AND created_ts < '2026-08-04'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
  GROUP BY 1, 2
  HAVING cohort IS NOT NULL
),
seg AS (
  SELECT
    cohort,
    device_id,
    install_ts,
    CASE
      WHEN is_ous = 1 AND is_safari = 1 THEN 'userscript_safari'
      WHEN is_imt_app = 1 THEN 'imt_ios_app'
      ELSE 'other'
    END AS seg
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
)
SELECT
  s.cohort,
  s.seg,
  COUNT(*) AS devices,
  COUNT(a.device_id) AS activated_3d,
  COUNT(a.device_id) * 1.0 / COUNT(*) AS act_rate_3d
FROM seg s
LEFT JOIN activated a ON a.device_id = s.device_id
GROUP BY 1, 2
ORDER BY 1, 2
"""

# Also: kick rule impact on August totals
SQL_KICK = """
WITH installs AS (
  SELECT
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript' AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-08-01' AND created_ts < '2026-09-01'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
  GROUP BY 1
)
SELECT
  COUNT(*) AS ios_devices,
  SUM(kick) AS kick_devices,
  SUM(kick) * 1.0 / COUNT(*) AS kick_share,
  COUNT(*) - SUM(kick) AS remain_devices
FROM installs
"""

SQL_CROSS = """
SELECT
  CASE
    WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-28' THEN 'pre'
    WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-11' THEN 'surge'
  END AS cohort,
  COALESCE(NULLIF(TRIM(install_from),''),'(blank)') AS install_from,
  COALESCE(NULLIF(TRIM(browser_name),''),'(blank)') AS browser_name,
  COUNT(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-01' AND created_ts < '2026-08-11'
  AND event_name = 'init_page_daily' AND is_new_user_today = '1'
  AND LOWER(TRIM(os_name)) = 'ios'
GROUP BY 1, 2, 3
HAVING cohort IS NOT NULL
ORDER BY cohort, devices DESC
LIMIT 40
"""

SQL_SURGE_VER = """
SELECT version, COUNT(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-28' AND created_ts < '2026-08-11'
  AND event_name = 'init_page_daily' AND is_new_user_today = '1'
  AND LOWER(TRIM(os_name)) = 'ios'
  AND LOWER(TRIM(install_from)) = 'official_userscript'
  AND TRIM(browser_name) = 'Safari'
GROUP BY 1
ORDER BY 2 DESC
LIMIT 15
"""


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===")
    print(cols)
    for r in rows:
        print(r)


if __name__ == "__main__":
    show("cross", query(SQL_CROSS))
    show("surge_userscript_safari_ver", query(SQL_SURGE_VER))
    show("kick_aug", query(SQL_KICK))
    show("activation", query(SQL))
