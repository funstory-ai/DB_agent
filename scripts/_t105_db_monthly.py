#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105: 我方 token_used_aw 按北京自然月 × UCloud 模型聚合 input/output/cache/行数。

用途：与 UCloud 各月账单对照 luna 模型的输入输出比，估算账单侧 output 多计损失。
注意：WHERE 只用粗 UTC timestamp 保分区裁剪，北京月切分在 SELECT 表达式里。
"""
import sys, time, json, csv
sys.path.insert(0, "scripts")
import db

SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       actualresourceid AS model,
       count(*) AS n_rows,
       SUM(inputusage) AS inp,
       SUM(cachedinputusage) AS cinp,
       SUM(outputusage) AS outp
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture'
  AND timestamp >= '2026-05-31 16:00:00' AND timestamp < '2026-11-10 16:00:00'
GROUP BY bj_month, model
ORDER BY bj_month, model
"""


def q(sql):
    """OSS AccessDenied 瞬态，6 次指数退避。"""
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
    t0 = time.time()
    cols, rows = q(SQL)
    print("cols:", cols, "rows:", len(rows), "elapsed:", round(time.time() - t0, 1), flush=True)
    with open("output/_t105_db_monthly.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
    for r in rows:
        m, mod, n, inp, cinp, outp = r
        if "luna" in str(mod).lower() or "terra" in str(mod).lower() or "mini" in str(mod).lower():
            print(f"{m} {mod:<24} rows={n:>12,} in={int(inp or 0):>15,} out={int(outp or 0):>14,} "
                  f"out/in={(outp or 0)/(inp or 1):.4f}", flush=True)
    print("[saved] output/_t105_db_monthly.csv", flush=True)
