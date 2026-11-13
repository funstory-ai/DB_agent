"""T101 决定性验证：在历史快照上直接重跑用户月留存 SQL 的 9 月桶。

AT (TIMESTAMP => ...) 让 Databend 读「当时物理存在的数据」。
- 若 AT 11/1 的 9 月桶 ≈ 931,096  => 数据在 10→11 月间确实变过（删行/改值），可继续逐设备比对。
- 若 AT 11/1 ≈ 当前快照 as-of 回放值 1,028,658 => 数据没变，11 月那次执行口径/取数不同。
只加 created_ts >= 2026-08-25 窗口提速；其余 WHERE / GROUP BY 与用户 SQL 逐字一致。
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

POINTS = [
    ("nov01", "2026-11-01 00:00:00"),
    ("oct05", "2026-10-05 00:00:00"),
    ("oct01", "2026-10-01 00:00:00"),
    ("now",   None),
]


def sql_for(at):
    frm = "immdata.user_behaviour" if at is None else (
        f"immdata.user_behaviour AT (TIMESTAMP => '{at}'::TIMESTAMP)"
    )
    return f"""
SELECT
  COUNT(DISTINCT IF(install_month_start_day = '2026-09-01', device_id, NULL)) AS sept_bucket,
  COUNT(DISTINCT IF(install_month_start_day = '2026-10-01', device_id, NULL)) AS oct_bucket,
  COUNT(DISTINCT IF(install_month_start_day = '2026-08-01', device_id, NULL)) AS aug_bucket
FROM (
  SELECT
    to_start_of_month(add_hours(created_ts, 8)) AS month_start_day,
    event_name,
    device_id,
    to_start_of_month(min(install_day)) AS install_month_start_day
  FROM {frm}
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


def q(sql, tries=4):
    last = None
    for i in range(tries):
        try:
            return query(sql)
        except Exception as e:
            last = e
            print(f"  [retry {i+1}] {str(e)[:200]}", flush=True)
            if i < tries - 1:
                time.sleep(2 ** i * 3)
    raise last


for name, at in POINTS:
    print(f"\n=== AT {name} ({at}) ===", flush=True)
    t0 = time.time()
    try:
        cols, rows = q(sql_for(at))
        print(f"{' | '.join(cols)}", flush=True)
        print(" | ".join(f"{v:,}" for v in rows[0]), flush=True)
        print(f"elapsed {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"FAILED {type(e).__name__}: {str(e)[:300]} | {time.time()-t0:.1f}s", flush=True)

print("\nDONE", flush=True)
