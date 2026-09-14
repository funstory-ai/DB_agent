# -*- coding: utf-8 -*-
"""T028: Safari 新装激活 — user definition, match dashboard screenshot."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# Match chart "Safari新装激活日活":
# 新装 = init_page_daily + is_new_user_today=1
# 激活 = translate_page + is_new_user_today=1
# 日活 = translate_page device UV (any is_new_user)
# Filter: browser_name = Safari (iOS typical for this chart)

SQL_DAILY = """
SELECT
  to_date(created_ts) AS d,
  COUNT(DISTINCT CASE
    WHEN event_name = 'init_page_daily' AND is_new_user_today = '1'
    THEN device_id END) AS new_install,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_new_user_today = '1'
    THEN device_id END) AS activation,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page'
    THEN device_id END) AS dau
FROM immdata.user_behaviour
WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
  AND LOWER(TRIM(os_name)) = 'ios'
  AND TRIM(browser_name) = 'Safari'
GROUP BY 1
ORDER BY 1
"""

# Same + exclude integration segment
SQL_DAILY_EX = """
WITH ev AS (
  SELECT
    to_date(created_ts) AS d,
    device_id,
    event_name,
    is_new_user_today,
    MAX(CASE
      WHEN LOWER(TRIM(install_from)) = 'official_userscript'
       AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END)
      OVER (PARTITION BY device_id, to_date(created_ts)) AS is_embed
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
    AND LOWER(TRIM(os_name)) = 'ios'
    AND TRIM(browser_name) = 'Safari'
)
SELECT
  d,
  COUNT(DISTINCT CASE
    WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' AND is_embed = 0
    THEN device_id END) AS new_install_ex,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_new_user_today = '1' AND is_embed = 0
    THEN device_id END) AS activation_ex,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_embed = 0
    THEN device_id END) AS dau_ex
FROM ev
GROUP BY 1
ORDER BY 1
"""

# Try summary table if exists
SQL_SUM = """
SELECT
  dates AS d,
  SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
  SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation,
  SUM(IF(event_name = 'translate_page', device_count, 0)) AS dau
FROM immdata.imm_app_new_event_device_count_by_utf8_day
WHERE dates >= '2026-07-24' AND dates < '2026-08-04'
  AND LOWER(TRIM(os_name)) = 'ios'
  AND TRIM(browser_name) = 'Safari'
GROUP BY 1
ORDER BY 1
"""


def show(title, result):
    cols, rows = result
    print(f"\n=== {title} ===", flush=True)
    print(cols, flush=True)
    for r in rows:
        d, ni, act, dau = r[0], r[1], r[2], r[3]
        rate = (act / ni * 100) if ni else 0
        print(f"{d}  新装={ni}  激活={act}  日活={dau}  激活率={rate:.2f}%", flush=True)


if __name__ == "__main__":
    try:
        show("summary_table", query(SQL_SUM))
    except Exception as e:
        print("summary_table failed:", e, flush=True)
    show("behaviour_raw", query(SQL_DAILY))
    show("behaviour_ex_embed", query(SQL_DAILY_EX))
