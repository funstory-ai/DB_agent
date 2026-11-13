# -*- coding: utf-8 -*-
"""T081 延伸：周一大放量(修复后) UCloud 数据 vs 修复前 是否一致
检查口径：input/output 比例(out/in) 在 修复前(以8月为准) 与 修复后(11-02~06, gpt-6-luna) 是否同处健康区间(~0.20-0.28)，
且 修复后日级比例是否稳定(无 spike/零值)。
"""
import sys
sys.path.insert(0, "H:/databend_sql/scripts")
from db import query

# ---------- A) 按月×模型 比例（2026-06 ~ 2026-11 部分） ----------
SQL_A = """
SELECT to_char(date_add(hour, 8, timestamp), 'YYYY-MM') AS ym,
       actualresourceid AS model,
       SUM(inputusage) AS inp,
       SUM(cachedinputusage) AS cinp,
       SUM(outputusage) AS outp,
       COUNT(*) AS n
FROM immdata.token_used_aw
WHERE recordtype = 'capture'
  AND providername = 'UCloud'
  AND timestamp >= '2026-06-01 00:00:00'::TIMESTAMP
  AND timestamp <  '2026-11-07 00:00:00'::TIMESTAMP
GROUP BY ym, model
ORDER BY ym, model
"""
cols, rows = query(SQL_A)
print("="*110)
print("A) UCloud 按月×模型 out/in 比例（修复前 8月 vs 修复后 11月 对照）")
print("="*110)
print(f"{'月份':8s} {'模型':16s} {'行数':>12s} {'in(B)':>11s} {'out(B)':>11s} {'out/in':>8s}")
cur_ym = None
for r in rows:
    ym, model, inp, cinp, outp, n = r[0], r[1], float(r[2] or 0), float(r[3] or 0), float(r[4] or 0), int(r[5] or 0)
    if ym != cur_ym:
        print(f"-- {ym} --"); cur_ym = ym
    ratio = (outp/inp) if inp else float('nan')
    print(f"{'':8s} {model:16s} {n:12,d} {inp/1e9:11.3f} {outp/1e9:11.3f} {ratio:8.3f}")

# ---------- B) 日级比例（10-28 ~ 11-06，看周一前后边界+稳定性） ----------
SQL_B = """
SELECT to_date(date_add(hour, 8, timestamp)) AS bj_date,
       actualresourceid AS model,
       SUM(inputusage) AS inp,
       SUM(outputusage) AS outp,
       COUNT(*) AS n
FROM immdata.token_used_aw
WHERE recordtype = 'capture'
  AND providername = 'UCloud'
  AND timestamp >= '2026-10-28 00:00:00'::TIMESTAMP
  AND timestamp <  '2026-11-07 00:00:00'::TIMESTAMP
GROUP BY bj_date, model
ORDER BY bj_date, model
"""
cols2, rows2 = query(SQL_B)
print("\n" + "="*110)
print("B) 日级 out/in（10-28~11-06，重点看 11-02 周一前后是否一致/稳定）")
print("="*110)
print(f"{'北京日':12s} {'模型':16s} {'行数':>12s} {'in(B)':>11s} {'out(B)':>11s} {'out/in':>8s}")
for r in rows2:
    d, model, inp, outp, n = r[0], r[1], float(r[2] or 0), float(r[3] or 0), int(r[4] or 0)
    ratio = (outp/inp) if inp else float('nan')
    flag = "  <== 周一" if str(d)=="2026-11-02" else ""
    print(f"{str(d):12s} {model:16s} {n:12,d} {inp/1e9:11.3f} {outp/1e9:11.3f} {ratio:8.3f}{flag}")
