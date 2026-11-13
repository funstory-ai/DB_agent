#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T106: 全供应商 luna 逐月用量与输入输出比（回答「其他供应商的 luna 是否也有 3 倍问题」）。

与 T105 区别：T105 只看 providername='UCloud'；本次不限供应商，按 provider × 北京月 × 模型 拆开。
"""
import sys, time, csv
sys.path.insert(0, "scripts")
import db

SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       coalesce(providername,'(NULL)')              AS provider,
       coalesce(actualresourceid,'(NULL)')          AS model,
       coalesce(recordtype,'(NULL)')                AS rtype,
       count(*)                                    AS n_rows,
       SUM(inputusage)                             AS inp,
       SUM(outputusage)                            AS outp
FROM immdata.token_used_aw
WHERE timestamp >= '2025-12-31 16:00:00'
  AND timestamp  < '2026-11-10 16:00:00'
  AND lower(actualresourceid) LIKE '%luna%'
GROUP BY bj_month, provider, model, rtype
ORDER BY bj_month, provider, model, rtype
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
    with open("output/_t106_luna_by_provider.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
    for r in rows:
        m, p, mod, rt, n, inp, outp = r
        inp, outp = float(inp or 0), float(outp or 0)
        print(f"{m} {p:<20} {mod:<20} {rt:<12} rows={n:>12,} in={inp:>15,.0f} "
              f"out={outp:>14,.0f} out/in={outp/inp if inp else 0:.4f}", flush=True)
    print("[saved] output/_t106_luna_by_provider.csv", flush=True)
