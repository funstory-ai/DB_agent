"""T101：扫描 2026-09 / 2026-10 的逐日 as-of 队列月曲线，定位 931,096 落在哪个时点。
口径同用户 SQL（内层按 活动月/event_name/device_id 分组，队列月=to_start_of_month(min(install_day))）。
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import query

RULE_A = """NOT (
      LOWER(TRIM(install_from)) = 'official_userscript'
      AND (
        (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
        OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
      )
    )"""

# (标签, UTC 截点)  北京日 00:00 = 前一日 16:00 UTC
CUTS = [
    ("0910", "2026-09-09 16:00:00"),
    ("0915", "2026-09-14 16:00:00"),
    ("0920", "2026-09-19 16:00:00"),
    ("0923", "2026-09-22 16:00:00"),
    ("0925", "2026-09-24 16:00:00"),
    ("0927", "2026-09-26 16:00:00"),
    ("0928", "2026-09-27 16:00:00"),
    ("0929", "2026-09-28 16:00:00"),
    ("0930", "2026-09-29 16:00:00"),
    ("1001", "2026-09-30 16:00:00"),
    ("1015", "2026-10-14 16:00:00"),
    ("1022", "2026-10-21 16:00:00"),
    ("1025", "2026-10-24 16:00:00"),
    ("1028", "2026-10-27 16:00:00"),
    ("1030", "2026-10-29 16:00:00"),
    ("1101", "2026-10-31 16:00:00"),
]

mins = [f"to_start_of_month(min(IF(created_ts < '{c}', install_day, NULL))) AS k_{n}"
        for n, c in CUTS]
selects = []
for n, _ in CUTS:
    selects.append(f"COUNT(DISTINCT IF(k_{n} = '2026-09-01', device_id, NULL)) AS \"s_{n}\"")
    selects.append(f"COUNT(DISTINCT IF(k_{n} = '2026-10-01', device_id, NULL)) AS \"o_{n}\"")

SQL = f"""
SELECT {', '.join(selects)}
FROM (
  SELECT
    to_start_of_month(add_hours(created_ts, 8)) AS month_start_day,
    event_name,
    device_id,
    {', '.join(mins)}
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND version != '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND {RULE_A}
    AND created_ts >= '2026-08-25 00:00:00'
  GROUP BY
    to_start_of_month(add_hours(created_ts, 8)),
    event_name,
    device_id
) t
"""


def q(sql, tries=6):
    last = None
    for i in range(tries):
        try:
            return query(sql)
        except Exception as e:
            last = e
            print(f"[retry {i+1}] {str(e)[:180]}", flush=True)
            if i < tries - 1:
                time.sleep(2 ** i * 3)
    raise last


print("=== as-of daily curve (Sept / Oct cohort) ===", flush=True)
t0 = time.time()
cols, rows = q(SQL)
print(f"elapsed {time.time()-t0:.1f}s", flush=True)
v = dict(zip(cols, rows[0]))
print("date  | sept_bucket | oct_bucket", flush=True)
for n, _ in CUTS:
    print(f"{n} | {v['s_'+n]:>11,} | {v['o_'+n]:>10,}", flush=True)
print("\nTARGETS: 1,010,718 / 931,096", flush=True)
print("DONE", flush=True)
