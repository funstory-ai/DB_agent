#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105: 解析 UCloud/星图供应商账单，产出逐月/逐日 × 模型 × 计费类型 的用量与实收金额(USD)。

数据源
  6/7/8 月账单: 「订单汇总」(月, 17列) + 「订单明细」(小时桶, 29列)
  星图: 「已支付订单详单」(10-06~11-05, 22列, 按「开始时间」归北京日)
口径
  计费单元含 Unicode 全角下划线(U+FF3F) -> norm() 归一化为 '_'
  类型优先级 output > input > cache（'text&image' 会早于 input 出现，不能按首次出现判定类型）
  金额一律取「订单金额」/「订单总额」实收(折后, USD)，不取「原价」
"""
import os, csv, unicodedata
import polars as pl

DL = r"C:\Users\86933\Downloads"
OUTDIR = "output"
MONTH_BILLS = [
    ("2026-06", "Funstory.ai Limited 推文科技有限公司-6月份账单（20260601-20260701）.xlsx"),
    ("2026-07", "Funstory.ai Limited 推文科技有限公司-7月份账单（20260701-20260801）.xlsx"),
    ("2026-08", "Funstory.ai Limited 推文科技有限公司-8月份账单（20260801-20260901）.xlsx"),
]
STAR = "66837208_星图_已完成订单_2026-10-06_2026-11-05_1793938462.xlsx"


def norm(s):
    return "".join("_" if unicodedata.category(ch) == "Pc" else ch for ch in str(s))


def num(x):
    if x is None:
        return 0.0
    s = str(x).replace("$", "").replace(",", "").strip()
    if s in ("", "-", "null", "None"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def typ_of(unit):
    ul = norm(unit).lower()
    if "output" in ul:
        return "output"
    if "input" in ul:
        return "input"
    return "cache"


def model_of(row, unit=None):
    m = row.get("模型名称")
    return str(m).strip() if m else "(unknown)"


def amount_col(d):
    for c in ["订单金额", "订单总额"]:
        if c in d.columns:
            return c
    raise KeyError("no amount col")


def collect(d, src, month, date_getter):
    ac = amount_col(d)
    out = []
    for row in d.iter_rows(named=True):
        unit = row.get("计费单元") or ""
        rec = {
            "src": src,
            "month": month,
            "date": date_getter(row),
            "model": model_of(row, unit),
            "unit": norm(unit),
            "typ": typ_of(unit),
            "qty": num(row.get("用量")),
            "amount_usd": num(row.get(ac)),
            "list_amount_usd": num(row.get("原价")),
            "disc_price": num(row.get("折后价")),
        }
        out.append(rec)
    return out


def main():
    recs = []
    # 1) 月度账单「订单汇总」
    for month, fn in MONTH_BILLS:
        p = os.path.join(DL, fn)
        d = pl.read_excel(p, engine="calamine", sheet_name="订单汇总")
        recs += collect(d, f"bill{month[5:7]}", month, lambda r: "")
        print(f"[汇总] {month}: {d.height} 行, luna={sum(1 for r in recs if r['month']==month and 'luna' in r['model'].lower())} 计费单元")
    # 2) 8 月账单「订单明细」(小时桶) -> 按日
    p8 = os.path.join(DL, MONTH_BILLS[2][1])
    d8 = pl.read_excel(p8, engine="calamine", sheet_name="订单明细")
    recs += collect(d8, "bill08_detail", "2026-08", lambda r: str(r.get("交易生效时间(UTC+8)") or "")[:10])
    print(f"[明细] 8月订单明细: {d8.height} 行")
    # 3) 星图详单 -> 按开始时间归日
    ps = os.path.join(DL, STAR)
    ds = pl.read_excel(ps, engine="calamine", sheet_name="已支付订单详单")
    recs += collect(ds, "star", "", lambda r: str(r.get("开始时间") or "")[:10])
    for r in recs:
        if r["src"] == "star":
            r["month"] = r["date"][:7]
    print(f"[星图] {ds.height} 行, 日期 {min(r['date'] for r in recs if r['src']=='star')} ~ {max(r['date'] for r in recs if r['src']=='star')}")

    with open(os.path.join(OUTDIR, "_t105_supplier_rows.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    print("[saved] output/_t105_supplier_rows.csv", len(recs), "rows")

    # 控制台摘要：按 src/month/model/typ
    from collections import defaultdict
    agg = defaultdict(lambda: [0.0, 0.0])
    for r in recs:
        if r["src"] == "bill08_detail":  # 与汇总重复, 只用于逐日
            continue
        k = (r["src"], r["month"], r["model"], r["typ"])
        agg[k][0] += r["qty"]
        agg[k][1] += r["amount_usd"]
    print("\n=== luna 账单侧摘要 (用量/实收USD) ===")
    for k in sorted(agg):
        if "luna" not in k[2].lower():
            continue
        q, a = agg[k]
        print(f"{k[0]:<12} {k[1]:<8} {k[2]:<16} {k[3]:<7} qty={q:>18,.0f}  usd={a:>12,.2f}  $/M={a/(q/1e6) if q else 0:.4f}")


if __name__ == "__main__":
    main()
