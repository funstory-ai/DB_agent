# -*- coding: utf-8 -*-
"""T028: fast activation + kick FP (hash sample / short window)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# 2% hash sample; install Jul21-27 (pre) vs Jul28-Aug3 (surge_w1)
# activate = any translate-like event within 3d after install
SQL_ACT = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-21' AND created_ts < '2026-07-28' THEN 'pre_w'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-04' THEN 'surge_w1'
    END AS cohort,
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from)) = 'official_userscript'
              AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END) AS is_kick,
    MAX(CASE WHEN TRIM(browser_name) LIKE 'ImtiOS%' THEN 1 ELSE 0 END) AS is_imt
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-21'
    AND created_ts < '2026-08-04'
    AND event_name = 'init_page_daily'
    AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 50 = 0
  GROUP BY 1, 2
  HAVING cohort IS NOT NULL
),
seg AS (
  SELECT
    cohort,
    device_id,
    install_ts,
    CASE
      WHEN is_kick = 1 THEN 'kick_ous_safari'
      WHEN is_imt = 1 THEN 'imt_ios_app'
      ELSE 'other'
    END AS seg
  FROM installs
),
acts AS (
  SELECT device_id, created_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-21'
    AND created_ts < '2026-08-07'
    AND event_name IN (
      'translate_page', 'translate_video_subtitle', 'use_ai_subtitle',
      'translate_image', 'translate_manga', 'selection_translate',
      'translate_input', 'translateTextInSidePanel'
    )
    AND ABS(xxhash64(device_id)) % 50 = 0
    AND LOWER(TRIM(os_name)) = 'ios'
)
SELECT
  s.cohort,
  s.seg,
  COUNT(*) AS devices_sample,
  COUNT(DISTINCT CASE
    WHEN a.device_id IS NOT NULL
     AND a.created_ts >= s.install_ts
     AND a.created_ts < DATEADD(day, 3, s.install_ts)
    THEN s.device_id END) AS act_3d,
  COUNT(DISTINCT CASE
    WHEN a.device_id IS NOT NULL
     AND a.created_ts >= s.install_ts
     AND a.created_ts < DATEADD(day, 3, s.install_ts)
    THEN s.device_id END) * 1.0 / COUNT(*) AS act_rate_3d
FROM seg s
LEFT JOIN acts a ON a.device_id = s.device_id
GROUP BY 1, 2
ORDER BY 1, 2
"""

# Kick rule FP on pre full (not sample): share of iOS that would be kicked
SQL_FP = """
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-28' THEN 'pre'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-11' THEN 'surge'
    END AS cohort,
    device_id,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS kick
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-08-11'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
  GROUP BY 1, 2
  HAVING cohort IS NOT NULL
)
SELECT
  cohort,
  COUNT(*) AS ios_devices,
  SUM(kick) AS kick_devices,
  SUM(kick) * 1.0 / COUNT(*) AS kick_share
FROM installs
GROUP BY 1
ORDER BY 1
"""

# Same-day translate proxy on install event itself? check if init co-occurs with translate same day — too weak
# Instead: among kick devices, share with ANY later init (retention proxy) vs imt — optional light
SQL_RETURN_D1 = """
WITH installs AS (
  SELECT
    device_id,
    MIN(created_ts) AS install_ts,
    MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript'
              AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END) AS is_kick,
    MAX(CASE WHEN TRIM(browser_name) LIKE 'ImtiOS%' THEN 1 ELSE 0 END) AS is_imt
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-28' AND created_ts < '2026-08-01'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND ABS(xxhash64(device_id)) % 20 = 0
  GROUP BY 1
),
seg AS (
  SELECT device_id, install_ts,
    CASE WHEN is_kick=1 THEN 'kick' WHEN is_imt=1 THEN 'imt' ELSE 'other' END AS seg
  FROM installs
),
d1 AS (
  SELECT DISTINCT s.device_id
  FROM seg s
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = s.device_id
   AND b.created_ts >= DATEADD(day, 1, s.install_ts)
   AND b.created_ts < DATEADD(day, 2, s.install_ts)
   AND b.event_name = 'init_page_daily'
   AND ABS(xxhash64(b.device_id)) % 20 = 0
)
SELECT
  s.seg,
  COUNT(*) AS devices_sample,
  COUNT(d.device_id) AS d1_return,
  COUNT(d.device_id) * 1.0 / COUNT(*) AS d1_rate
FROM seg s
LEFT JOIN d1 d ON d.device_id = s.device_id
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
    # FP already printed in prior run; skip unless --all
    import sys as _sys
    if "--all" in _sys.argv:
        show("kick_fp_pre_vs_surge", query(SQL_FP))
    show("act_3d_2pct_sample", query(SQL_ACT))
    show("d1_return_5pct_sample", query(SQL_RETURN_D1))
