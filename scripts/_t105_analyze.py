#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105 主分析：逐月 luna 输入输出比 + 账单侧 output 多计损失。

对照口径
  我方: immdata.token_used_aw, UCloud 专线, recordtype=capture, 北京自然日
  账单: 6/7/8 月账单「订单汇总」(自然月) / 8月「订单明细」小时桶(逐日) / 星图详单(逐日, 10-06~11-05)
  类型: 计费单元归一化后按 output > input > cache 判定
  金额: 实收折后 USD（订单金额），单价 = 金额 / 用量 * 1e6
"""
import csv
from collections import defaultdict

YI = 1e8
M = 1e6
FX = 7.1  # ¥/USD, 与 T082 8 月折算一致


def read_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


sup = read_csv("output/_t105_supplier_rows.csv")
dbday = read_csv("output/_t105_db_daily_luna.csv")
dbmon = read_csv("output/_t105_db_monthly.csv")

# ---------- 账单侧聚合 ----------
def is_luna(m):
    return "luna" in m.lower()

# 自然月（6/7/8 汇总 + 星图按开始时间归月）
mon_sup = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # month -> typ -> [qty, usd]
day_sup = defaultdict(lambda: [0.0, 0.0])  # (date, typ) -> [qty, usd]
for r in sup:
    if not is_luna(r["model"]) or r["src"] == "bill08_detail":
        continue
    t = r["typ"]
    q, a = float(r["qty"]), float(r["amount_usd"])
    mon_sup[r["month"]][t][0] += q
    mon_sup[r["month"]][t][1] += a
for r in sup:
    if not is_luna(r["model"]):
        continue
    if r["src"] == "bill08_detail" or r["src"] == "star":
        t = r["typ"]
        d = r["date"]
        if not d:
            continue
        day_sup[(d, t)][0] += float(r["qty"])
        day_sup[(d, t)][1] += float(r["amount_usd"])

# ---------- 我方侧聚合 ----------
mon_db = defaultdict(lambda: [0.0, 0.0, 0])  # month -> [inp, outp, rows]
for r in dbmon:
    if not is_luna(r["model"]):
        continue
    mon_db[r["bj_month"]][0] += float(r["inp"] or 0)
    mon_db[r["bj_month"]][1] += float(r["outp"] or 0)
    mon_db[r["bj_month"]][2] += int(r["n_rows"])

day_db = defaultdict(lambda: [0.0, 0.0, 0])
for r in dbday:
    day_db[r["bj"]][0] += float(r["inp"] or 0)
    day_db[r["bj"]][1] += float(r["outp"] or 0)
    day_db[r["bj"]][2] += int(r["n_rows"])


def price(month_or_window, typ="output"):
    """加权折后单价 USD/百万 token"""
    if isinstance(month_or_window, tuple):
        dates = month_or_window
        q = sum(day_sup[(d, typ)][0] for d in dates if (d, typ) in day_sup)
        a = sum(day_sup[(d, typ)][1] for d in dates if (d, typ) in day_sup)
    else:
        q, a = mon_sup[month_or_window][typ]
    return a / (q / M) if q else 0.0


print("=" * 110)
print("【A】自然月对照：账单侧(有账单的月份) vs 我方")
print(f"{'月份':<9}{'账单input(亿)':>14}{'我方input(亿)':>14}{'账单output(亿)':>15}{'我方output(亿)':>15}"
      f"{'账单out/in':>12}{'我方out/in':>12}{'倍数':>8}{'差额(亿)':>11}{'单价$/M':>10}{'多计USD':>11}")
monthly = []
for m in sorted(set(list(mon_sup.keys()) + list(mon_db.keys()))):
    si, sa = mon_sup[m].get("input", [0.0, 0.0])
    so, so_amt = mon_sup[m].get("output", [0.0, 0.0])
    di, do, _ = mon_db[m]
    has_bill = si > 0
    r_bill = so / si if si else 0
    r_db = do / di if di else 0
    mult = r_bill / r_db if r_db else 0
    gap = so - do
    p = price(m)
    loss = gap / M * p if has_bill else 0
    print(f"{m:<9}{si/YI:>14.2f}{di/YI:>14.2f}{so/YI:>15.2f}{do/YI:>15.2f}"
          f"{r_bill:>12.4f}{r_db:>12.4f}{mult:>8.2f}{gap/YI:>11.2f}{p:>10.4f}{loss:>11.2f}"
          + ("" if has_bill else "   <- 无账单"))
    monthly.append(dict(month=m, has_bill=has_bill, sup_in=si, db_in=di, sup_out=so, db_out=do,
                        ratio_sup=r_bill, ratio_db=r_db, mult=mult, gap=gap, price=p, loss=loss,
                        sup_out_usd=so_amt))

print()
print("=" * 110)
print("【B】8 月逐日对照（账单订单明细小时桶 vs 我方逐日）")
print(f"{'日期':<12}{'账单in(亿)':>12}{'我方in(亿)':>12}{'账单out(亿)':>13}{'我方out(亿)':>13}"
      f"{'账单比':>9}{'我方比':>9}{'倍数':>8}")
aug_daily = []
for d in sorted({k[0] for k in day_sup if k[0].startswith("2026-08")}):
    si = day_sup[(d, "input")][0]
    so = day_sup[(d, "output")][0]
    di, do, _ = day_db[d]
    if si == 0 and di == 0:
        continue
    rs, rd = so / si if si else 0, do / di if di else 0
    mult = rs / rd if rd else 0
    print(f"{d:<12}{si/YI:>12.2f}{di/YI:>12.2f}{so/YI:>13.2f}{do/YI:>13.2f}{rs:>9.3f}{rd:>9.3f}{mult:>8.2f}")
    aug_daily.append(dict(date=d, sup_in=si, db_in=di, sup_out=so, db_out=do,
                          ratio_sup=rs, ratio_db=rd, mult=mult))

print()
print("=" * 110)
print("【C】星图 10-06~11-05 逐日对照（luna 合计, 账单 vs 我方）")
print(f"{'日期':<12}{'账单in(亿)':>12}{'我方in(亿)':>12}{'账单out(亿)':>13}{'我方out(亿)':>13}"
      f"{'账单比':>9}{'我方比':>9}{'倍数':>8}{'差额(亿)':>11}")
star_daily = []
for d in sorted({k[0] for k in day_sup if k[0] >= "2026-10-06"}):
    si = day_sup[(d, "input")][0]
    so = day_sup[(d, "output")][0]
    di, do, _ = day_db[d]
    if si == 0 and di == 0:
        continue
    rs, rd = so / si if si else 0, do / di if di else 0
    mult = rs / rd if rd else 0
    print(f"{d:<12}{si/YI:>12.2f}{di/YI:>12.2f}{so/YI:>13.2f}{do/YI:>13.2f}"
          f"{rs:>9.3f}{rd:>9.3f}{mult:>8.2f}{(so-do)/YI:>11.2f}")
    star_daily.append(dict(date=d, sup_in=si, db_in=di, sup_out=so, db_out=do,
                           ratio_sup=rs, ratio_db=rd, mult=mult, gap=so - do))

print()
print("=" * 110)
print("【D】窗口汇总（同日期窗，避免自然月/账期错配）")
WINDOWS = [
    ("2026-08 全月", [d for d in day_sup if d[0].startswith("2026-08")], "2026-08", "bill08_detail"),
    ("2026-10-06~10-31", [d for d in day_sup if "2026-10-06" <= d[0] <= "2026-10-31"], None, "star"),
    ("2026-11-01~11-05", [d for d in day_sup if "2026-11-01" <= d[0] <= "2026-11-05"], None, "star"),
    ("星图全窗 10-06~11-05", [d for d in day_sup if "2026-10-06" <= d[0] <= "2026-11-05"], None, "star"),
]
for label, dates, mkey, src in WINDOWS:
    si = sum(day_sup[(d, "input")][0] for d in dates if (d, "input") in day_sup)
    so = sum(day_sup[(d, "output")][0] for d in dates if (d, "output") in day_sup)
    sa = sum(day_sup[(d, "output")][1] for d in dates if (d, "output") in day_sup)
    di = sum(day_db[d][0] for d in dates)
    do = sum(day_db[d][1] for d in dates)
    p = sa / (so / M) if so else 0
    print(f"{label:<24} 账单 in={si/YI:>7.2f}亿 out={so/YI:>7.2f}亿 (out/in={so/si if si else 0:.4f}) | "
          f"我方 in={di/YI:>7.2f}亿 out={do/YI:>7.2f}亿 (out/in={do/di if di else 0:.4f}) | "
          f"倍数={(so/si)/(do/di) if si and di and do else 0:.2f} | 差额={(so-do)/YI:>7.2f}亿 | "
          f"单价=${p:.4f}/M | 多计=${(so-do)/M*p:,.2f}")
