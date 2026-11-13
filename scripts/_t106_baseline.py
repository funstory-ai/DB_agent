#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T106: 全模型（不限 luna）× 供应商 × 北京月 的 input/output 基线。

用于验证用户口径「我们平均输入输出比 0.2~0.25」，并计算 luna 在总量中的份额。
"""
import sys, time, csv
sys.path.insert(0, "scripts")
import db

SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       coalesce(providername,'(NULL)')              AS provider,
       count(*)                                    AS n_rows,
       SUM(inputusage)                             AS inp,
       SUM(outputusage)                            AS outp
FROM immdata.token_used_aw
WHERE timestamp >= '2025-12-31 16:00:00'
  AND timestamp  < '2026-11-10 16:00:00'
  AND recordtype = 'capture'
GROUP BY bj_month, provider
ORDER BY bj_month, provider
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
    t0 = time.time()
    cols, rows = q(SQL)
    print("cols:", cols, "rows:", len(rows), "elapsed:", round(time.time() - t0, 1), flush=True)
    with open("output/_t106_baseline_by_provider.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
    for r in rows:
        m, p, n, inp, outp = r
        inp, outp = float(inp or 0), float(outp or 0)
        print(f"{m} {p:<20} rows={n:>13,} in={inp:>17,.0f} out={outp:>16,.0f} out/in={outp/inp if inp else 0:.4f}", flush=True)
    print("[saved] output/_t106_baseline_by_provider.csv", flush=True)
