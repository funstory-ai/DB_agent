"""T101：一次扫描算出「各 as-of 截点 × 各队列月」的 new_user_count 网格。

目的：判定 1,010,718 / 931,096 到底是不是 9 月桶，还是别的格子
（例如 11 月初看到的其实是 10 月桶，或某个截点下的 9 月桶）。
口径：逐字复用用户 SQL 的内层分组 (活动月, event_name, device_id)，
      队列月 = to_start_of_month(min(install_day))，外层 COUNT(DISTINCT device_id)。
      只加 created_ts >= 2026-08-25 窗口做提速（用户原 SQL 无窗口）。
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

# UTC 截点；北京 = UTC+8，故北京 10/1 00:00 = 09/30 16:00 UTC
CUTS = [
    ("oct01", "2026-09-30 16:00:00"),
    ("oct03", "2026-10-02 16:00:00"),
    ("oct05", "2026-10-04 16:00:00"),
    ("oct08", "2026-10-07 16:00:00"),
    ("nov01", "2026-10-31 16:00:00"),
    ("now",   None),
]
COHORTS = ["2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01", "1970-01-01"]

mins = []
for name, cut in CUTS:
    if cut is None:
        mins.append(f"to_start_of_month(min(install_day)) AS {name}")
    else:
        mins.append(f"to_start_of_month(min(IF(created_ts < '{cut}', install_day, NULL))) AS {name}")

selects = []
for name, _ in CUTS:
    for c in COHORTS:
        key = f"{name}_{c[:7]}"
        selects.append(
            f"COUNT(DISTINCT IF({name} = '{c}', device_id, NULL)) AS \"{key}\""
        )
# 额外：9 月队列在 10 月活跃（M1）与 9 月活跃
selects.append(
    "COUNT(DISTINCT IF(nov01 = '2026-09-01' AND month_start_day = '2026-10-01', device_id, NULL)) AS \"sept_m1_at_nov01\""
)
selects.append(
    "COUNT(DISTINCT IF(nov01 = '2026-09-01' AND month_start_day = '2026-09-01', device_id, NULL)) AS \"sept_active_sept_at_nov01\""
)

SQL = f"""
SELECT
  {', '.join(selects)}
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


print("=== cutoff x cohort grid ===", flush=True)
t0 = time.time()
cols, rows = q(SQL)
print(f"elapsed {time.time()-t0:.1f}s", flush=True)
r = rows[0]
vals = dict(zip(cols, r))
for name, _ in CUTS:
    line = [f"{name:6s}"]
    for c in COHORTS:
        line.append(f"{c[:7]}={vals.get(f'{name}_{c[:7]}'):>10,}")
    print("  " + "  ".join(line), flush=True)
print(f"sept_m1_at_nov01            = {vals['sept_m1_at_nov01']:,}", flush=True)
print(f"sept_active_sept_at_nov01   = {vals['sept_active_sept_at_nov01']:,}", flush=True)
print("\nTARGETS: 1,010,718 / 931,096", flush=True)
print("DONE", flush=True)
