"""T101 收尾：用户给出「当时真正用的 SQL」= browser_name <> 'Electron'。
与第一次贴的 Rule A 版对比，判定 931,096 是否只是另一套过滤口径下的正常值。

逐字复用用户 SQL 内层/外层，仅加 created_ts >= '2026-08-25' 提速。
结果同时写文件，避免后台输出丢失。
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
ELECTRON = "browser_name <> 'Electron'"

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output",
                   "t101_electron_vs_ruleA_20261104.txt")


def bucket_sql(extra, at=None, cohorts=("2026-09-01", "2026-10-01", "2026-08-01")):
    frm = "immdata.user_behaviour" if at is None else (
        f"immdata.user_behaviour AT (TIMESTAMP => '{at}'::TIMESTAMP)")
    sels = [f"COUNT(DISTINCT IF(install_month_start_day = '{c}', device_id, NULL)) AS \"{c[:7]}\""
            for c in cohorts]
    return f"""
SELECT {', '.join(sels)}
FROM (
  SELECT
    to_start_of_month(add_hours(created_ts, 8)) AS month_start_day,
    event_name,
    device_id,
    to_start_of_month(min(install_day)) AS install_month_start_day
  FROM {frm}
  WHERE event_name = 'translate_page'
    AND version <> '1.11.4'
    AND TRY_CAST(install_day AS DATE) IS NOT NULL
    AND {extra}
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
            print(f"  [retry {i+1}] {str(e)[:180]}", flush=True)
            if i < tries - 1:
                time.sleep(2 ** i * 3)
    raise last


def run(label, sql):
    print(f"\n=== {label} ===", flush=True)
    t0 = time.time()
    try:
        cols, rows = q(sql)
        print(" | ".join(cols), flush=True)
        print(" | ".join(f"{v:,}" for v in rows[0]), flush=True)
        print(f"elapsed {time.time()-t0:.1f}s", flush=True)
        return cols, rows[0]
    except Exception as e:
        print(f"FAILED {type(e).__name__}: {str(e)[:300]} | {time.time()-t0:.1f}s", flush=True)
        return None, None


lines = []


def rec(s):
    lines.append(s)


# 1) 当前数据：Electron 版
c, r = run("CURRENT / Electron 版 (用户这次贴的)", bucket_sql(ELECTRON))
if r:
    rec(f"CURRENT Electron : " + ", ".join(f"{k}={v:,}" for k, v in zip(c, r)))

# 2) 当前数据：Rule A 版（对照）
c, r = run("CURRENT / Rule A 版 (用户第一次贴的)", bucket_sql(RULE_A))
if r:
    rec(f"CURRENT RuleA    : " + ", ".join(f"{k}={v:,}" for k, v in zip(c, r)))

# 3) 当前数据：无任何 browser/install_from 过滤
c, r = run("CURRENT / 无 browser、install_from 过滤", bucket_sql("1 = 1"))
if r:
    rec(f"CURRENT nofilter : " + ", ".join(f"{k}={v:,}" for k, v in zip(c, r)))

# 4) browser_name 分布（9 月 install_day 的设备，看 Electron / NULL 规模）
print("\n=== browser_name 分布（install_day 在 2026-09）===", flush=True)
dist_sql = """
SELECT browser_name, count(*) AS rows, count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE event_name = 'translate_page'
  AND version <> '1.11.4'
  AND TRY_CAST(install_day AS DATE) IS NOT NULL
  AND install_day >= '2026-09-01' AND install_day < '2026-10-01'
  AND created_ts >= '2026-08-25 00:00:00'
GROUP BY browser_name
ORDER BY devices DESC
LIMIT 30
"""
try:
    cols, rows = q(dist_sql)
    print(" | ".join(cols), flush=True)
    for row in rows:
        print(" | ".join(str(x) for x in row), flush=True)
        rec("DIST " + " | ".join(str(x) for x in row))
except Exception as e:
    print(f"FAILED {type(e).__name__}: {str(e)[:300]}", flush=True)

# 5) 真实 2026-11-01 快照：Electron 版
c, r = run("AT 2026-11-01 / Electron 版", bucket_sql(ELECTRON, at="2026-11-01 00:00:00"))
if r:
    rec(f"AT1101 Electron  : " + ", ".join(f"{k}={v:,}" for k, v in zip(c, r)))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nWROTE {OUT}", flush=True)
print("DONE", flush=True)
