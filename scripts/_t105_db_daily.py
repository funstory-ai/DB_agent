#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105: 我方 luna 逐北京日用量（用于与账单窗口精确对齐）。"""
import sys, time, csv
sys.path.insert(0, "scripts")
import db

SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') AS bj,
       actualresourceid AS model,
       count(*) AS n_rows,
       SUM(inputusage) AS inp,
       SUM(outputusage) AS outp
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture'
  AND timestamp >= '2026-07-31 16:00:00' AND timestamp < '2026-11-10 16:00:00'
  AND lower(actualresourceid) LIKE '%luna%'
GROUP BY bj, model
ORDER BY bj, model
"""


def q(sql):
    for i in range(6):
        try:
            return db.query(sql)
        except Exception as e:
            msg = str(e)
            if "AccessDenied" not in msg and "403" not in msg and i < 2:
                raise
            print(f"[retry {i+1}/6] {msg[:160]}", flush=True)
            time.sleep(2 ** i)
    raise RuntimeError("query failed after retries")


if __name__ == "__main__":
    cols, rows = q(SQL)
    print("rows:", len(rows), flush=True)
    with open("output/_t105_db_daily_luna.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
    for r in rows[:8]:
        print(r, flush=True)
    print("[saved] output/_t105_db_daily_luna.csv", flush=True)
