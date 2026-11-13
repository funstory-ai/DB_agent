# -*- coding: utf-8 -*-
"""T112 交付后追问：某个「按天 × 地区桶 × 币种」格子的逐笔订单明细（只读、只打印）。

P044：解释已交付格子必须与当时同一次查询、同一粒度、同一时间锚点。
本脚本直接复用 sql/reports/query_sg_my_daily_detail_20261106_20261112.sql 中
逐字复刻自 T112 定稿的公共 CTE，并从交付 Excel 读取该格原值做自动对拍。

用法（默认即 2026-11-06 / MY / CNY）：
  python scripts/query_sg_my_daily_detail_20261106.py
  python scripts/query_sg_my_daily_detail_20261106.py --day 2026-11-06 --bucket SG

本脚本不写任何文件，属 P044 核查而非新交付，故不触发 WF_TASK 交付门禁；
若要另出 Excel 明细，需按 HARD_WORKFLOW.md 另起 T### 或带 WF_TASK 走正式交付。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402
import openpyxl  # noqa: E402

SQL_FILE = ROOT / "sql" / "reports" / "query_sg_my_daily_detail_20261106_20261112.sql"
DELIVERY = ROOT / "output" / "sg_my_revenue" / "sg_my_daily_revenue_yoy_20261025_20261112.xlsx"


def q(sql: str, retries: int = 6):
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} ({d:.0f}s): {str(e)[:160]}", flush=True)
            time.sleep(d)
            d *= 2


def load_parts() -> dict:
    text = SQL_FILE.read_text(encoding="utf-8")
    parts, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^--\s+@([A-Za-z0-9_]+)\b", line)
        if m:
            if cur:
                parts[cur] = "\n".join(buf).strip().rstrip(";").strip()
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        parts[cur] = "\n".join(buf).strip().rstrip(";").strip()
    return parts


def utc_lo(d: date) -> str:
    return f"{d - timedelta(days=1)} 16:00:00"


def utc_hi(d: date) -> str:
    return f"{d} 16:00:00"


def delivery_row(day: str, bucket: str, currency: str):
    """从交付 Excel 读该格：原币金额 / 汇率 / 收入¥ / 现金单数。"""
    wb = openpyxl.load_workbook(DELIVERY, data_only=True)
    ws = wb["分币种_SG_MY"]
    for r in ws.iter_rows(values_only=True):
        if (r[0] and str(r[0]).startswith(day) and r[1] == "今年"
                and r[2] == bucket and str(r[3]) == currency):
            return {"amt_major": r[4], "rate": r[5], "amt_cny": r[6], "cash_orders": r[7]}
    return None


def fmt(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, (datetime, date)):
        return str(v)
    try:
        return f"{float(v):,.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def show(title, cols, rows, nd=2):
    print(f"\n== {title} ==")
    print("  " + " | ".join(cols))
    for r in rows:
        print("  " + " | ".join(fmt(v, nd) for v in r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-11-06")
    ap.add_argument("--bucket", default="MY", choices=["SG", "MY"])
    ap.add_argument("--currency", default="CNY")
    ap.add_argument("--start", default="2026-10-25", help="T112 今年窗口起（北京日）")
    ap.add_argument("--end", default="2026-11-12", help="T112 今年窗口止（北京日）")
    a = ap.parse_args()

    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    ly_start = start.replace(year=start.year - 1)
    ly_end = end.replace(year=end.year - 1)
    repl = {
        "TY_LO": utc_lo(start), "TY_HI": utc_hi(end),
        "LY_LO": utc_lo(ly_start), "LY_HI": utc_hi(ly_end),
        "DAY": a.day, "BUCKET": a.bucket,
    }
    print(f"窗口(UTC)：TY {repl['TY_LO']} ~ {repl['TY_HI']} | LY {repl['LY_LO']} ~ {repl['LY_HI']}")
    print(f"下钻：北京日 {a.day} / 桶 {a.bucket} / 对照币种 {a.currency}")

    P = load_parts()
    need = ("CTES", "Q_CHECK", "Q_DETAIL")
    missing = [k for k in need if k not in P]
    if missing:
        raise SystemExit(f"SQL 缺段：{missing}")

    def render(key):
        s = P["CTES"] + "\n" + P[key]
        for k, v in repl.items():
            s = s.replace("{{" + k + "}}", v)
        return s

    c1, check_rows = q(render("Q_CHECK"))
    c2, detail_rows = q(render("Q_DETAIL"))

    show("① 库内复算（T112 原 Q_REV 聚合逻辑，仅加日期+桶过滤）", c1, check_rows)
    show("② 该日该桶逐笔订单明细", c2, detail_rows)

    # 按币种小计（由明细独立加总，不依赖 Q_CHECK）
    from collections import defaultdict
    agg = defaultdict(lambda: [0, 0, 0.0, 0.0])
    idx = {c: i for i, c in enumerate(c2)}
    for r in detail_rows:
        cur = str(r[idx["currency"]])
        agg[cur][0] += 1
        agg[cur][1] += int(r[idx["is_cash"]] or 0)
        agg[cur][2] += float(r[idx["amt_major"]] or 0)
        agg[cur][3] += float(r[idx["amt_cny"]] or 0)
    show("③ 明细按币种小计", ["币种", "订单数", "现金单数", "原币金额", "折CNY"],
         [(k, *v) for k, v in sorted(agg.items())])

    # 与交付表逐格对拍（P044）
    exp = delivery_row(a.day, a.bucket, a.currency)
    got = next((r for r in check_rows if str(r[c1.index("currency")]) == a.currency), None)
    print("\n== ④ P044 对拍（复算 vs 交付 Excel）==")
    if exp is None:
        print("  交付表未找到该格（检查 --day / --bucket / --currency）")
    elif got is None:
        print(f"  库内复算未返回 {a.currency} 行 —— 明细与交付格子不一致，需追查")
    else:
        gi = {c: i for i, c in enumerate(c1)}
        pairs = [
            ("原币金额", exp["amt_major"], got[gi["amt_major"]]),
            ("收入¥", exp["amt_cny"], got[gi["amt_cny"]]),
            ("汇率", exp["rate"], got[gi["rate"]]),
        ]
        all_ok = True
        for label, e, g in pairs:
            ok = e is not None and g is not None and abs(float(e) - float(g)) < 0.011
            all_ok &= ok
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}: 交付 {fmt(e)} | 复算 {fmt(g, 4)}")
        print(f"  交付表「现金单数」= {exp['cash_orders']}（该桶当日全部现金订单数，"
              f"每个币种行重复填，不是 {a.currency} 这一行的单数）")
        print(f"  复算该桶现金单数合计 = {sum(int(r[gi['cash_orders']]) for r in check_rows)} "
              f"(各币种行重复计，仅供理解列含义)")
        print(f"  P044 结论：{'一致，明细可解释该格' if all_ok else '不一致，禁止用此明细解释该格'}")


if __name__ == "__main__":
    main()
