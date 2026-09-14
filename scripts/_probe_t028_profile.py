# -*- coding: utf-8 -*-
"""T028: iOS surge attribute profiles (fixed order by)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def dim_sql(dim_expr, dim_name):
    return f"""
WITH installs AS (
  SELECT
    CASE
      WHEN created_ts >= '2026-07-01' AND created_ts < '2026-07-28' THEN 'pre'
      WHEN created_ts >= '2026-07-28' AND created_ts < '2026-08-11' THEN 'surge'
    END AS cohort,
    device_id,
    created_ts AS install_ts,
    {dim_expr} AS val
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-01' AND created_ts < '2026-08-11'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND LOWER(TRIM(os_name)) = 'ios'
),
dedup AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY cohort, device_id ORDER BY install_ts) AS rn
    FROM installs WHERE cohort IS NOT NULL
  ) t WHERE rn = 1
)
SELECT cohort, val, COUNT(*) AS devices,
  COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY cohort) AS share
FROM dedup
GROUP BY cohort, val
ORDER BY cohort, devices DESC
LIMIT 30
"""

DIMS = [
    ("COALESCE(NULLIF(TRIM(install_from), ''), '(blank)')", "install_from"),
    ("COALESCE(NULLIF(TRIM(version), ''), '(blank)')", "version"),
    ("COALESCE(NULLIF(TRIM(browser_name), ''), '(blank)')", "browser_name"),
    ("COALESCE(NULLIF(TRIM(campaign), ''), '(blank)')", "campaign"),
    ("COALESCE(NULLIF(TRIM(platform_type), ''), '(blank)')", "platform_type"),
    ("COALESCE(NULLIF(TRIM(userscript), ''), '(blank)')", "userscript"),
    ("COALESCE(NULLIF(TRIM(engine_name), ''), '(blank)')", "engine_name"),
    ("COALESCE(NULLIF(TRIM(real_geo), ''), '(blank)')", "real_geo"),
]


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===")
    print(cols)
    for r in rows:
        print(r)


if __name__ == "__main__":
    for expr, name in DIMS:
        show(name, query(dim_sql(expr, name)))
