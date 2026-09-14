# -*- coding: utf-8 -*-
"""T027: datapack retention/ARPU patch (final).

- Max share renormalized to m+y+x total; ARPU recalculated
- Monthly Y2/Y3 = Y1 * (8.1/5.7) / (9.3/5.7); yearly PIT r1 + 65% second renew
- Delete cohort stripe last 3 cols; 44.9% note; monthly （万） headers
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

BACKUP = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\推文datapack-202607_before_T027.xlsx")
OUT = Path(r"H:\databend_sql\output") / "推文datapack-202607_T027.xlsx"
DESK = Path(r"C:\Users\86933\Desktop\沉浸式翻译月报\推文datapack-202607.xlsx")

R2 = 0.65
M_ANCHOR_Y1, M_ANCHOR_Y2, M_ANCHOR_Y3 = 5.7, 8.1, 9.3
M2_RATIO = M_ANCHOR_Y2 / M_ANCHOR_Y1
M3_RATIO = M_ANCHOR_Y3 / M_ANCHOR_Y1
EPS = 0.051

MON = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
# (header_row, has_max)
QUARTERS = [
    (1, "2026Q2", datetime(2026, 6, 1), True),
    (19, "2026Q1", datetime(2026, 3, 1), True),
    (37, "2025Q4", datetime(2025, 12, 1), True),
    (55, "2025Q3", datetime(2025, 9, 1), True),
    (73, "2025Q2", datetime(2025, 6, 1), False),
    (89, "2025Q1", datetime(2025, 3, 1), False),
    (105, "2024Q4", datetime(2024, 12, 1), False),
]


def parse_mon(s: str) -> datetime:
    a, b = s.split("-")
    return datetime(2000 + int(b), MON[a], 1)


def load_cohorts(ws):
    yearly, monthly = [], []
    for r in range(2, 40):
        bm, n, y1 = ws.cell(r, 15).value, ws.cell(r, 16).value, ws.cell(r, 17).value
        if bm and isinstance(bm, str) and "-" in str(bm) and n and y1 not in (None, ""):
            yearly.append((parse_mon(str(bm)), str(bm), float(n), float(y1)))
    for r in range(2, 32):
        m, nu = ws.cell(r, 1).value, ws.cell(r, 2).value
        if not m or not nu:
            continue
        counts = [ws.cell(r + 32, c).value for c in range(3, 14)]
        if any(v is None for v in counts):
            continue
        rets = [float(v) / float(nu) for v in counts]
        monthly.append((parse_mon(str(m)), str(m), float(nu), rets))
    return yearly, monthly


def roll_yearly(yearly, asof):
    mature = [x for x in yearly if x[0] <= asof - relativedelta(years=1)]
    mature = sorted(mature, key=lambda x: x[0], reverse=True)[:6]
    if not mature:
        return None
    w = sum(x[2] for x in mature)
    return sum(x[3] for x in mature) / w


def roll_monthly(monthly, asof):
    mature = []
    for dt, lab, nu, rets in monthly:
        if len(rets) < 11 or rets[10] is None:
            continue
        if dt + relativedelta(months=11) > asof:
            continue
        mature.append((dt, lab, nu, 1.0 + sum(rets[:11])))
    mature = sorted(mature, key=lambda x: x[0], reverse=True)[:6]
    if not mature:
        return None
    w = sum(x[2] for x in mature)
    return sum(x[2] * x[3] for x in mature) / w


def arpu_with_max(wm, wy, wx, pm, py, px, m, y):
    return wm * pm * m + wy * py * y + wx * px * y


def arpu_no_max(wm, wy, pm, py, m, y):
    return wm * pm * m + wy * py * y


def fix_shares_and_arpu(arpu, ws_ret):
    yearly, monthly = load_cohorts(ws_ret)
    print("=== shares + ARPU ===")
    for start, qname, asof, has_max in QUARTERS:
        shares_r = start + 2
        m_r = start + 5
        y_r = start + 8
        x_r = start + 11 if has_max else None
        a_r = start + 15 if has_max else start + 13

        r1 = roll_yearly(yearly, asof)
        m1_raw = roll_monthly(monthly, asof)
        if r1 is None or m1_raw is None:
            raise RuntimeError(f"missing window {qname}")

        y1, y2, y3 = 1.0, 1.0 + r1, 1.0 + r1 + r1 * R2
        m1 = round(m1_raw, 1)
        m2 = round(m1 * M2_RATIO, 1)
        m3 = round(m1 * M3_RATIO, 1)
        mm, yy = (m1, m2, m3), (y1, y2, y3)

        if has_max:
            cnt_m = float(arpu.cell(shares_r, 1).value)
            cnt_y = float(arpu.cell(shares_r, 2).value)
            cnt_x = float(arpu.cell(shares_r, 3).value)
            total = cnt_m + cnt_y + cnt_x
            wm, wy, wx = cnt_m / total, cnt_y / total, cnt_x / total
            # write shares rounded to 2 decimals; adjust max so sum≈1
            wm_r, wy_r = round(wm, 2), round(wy, 2)
            wx_r = round(1.0 - wm_r - wy_r, 2)
            old = [arpu.cell(shares_r, c).value for c in range(4, 7)]
            arpu.cell(shares_r, 4).value = wm_r
            arpu.cell(shares_r, 5).value = wy_r
            arpu.cell(shares_r, 6).value = wx_r
            print(
                f"{qname} counts {cnt_m:.0f}/{cnt_y:.0f}/{cnt_x:.0f} "
                f"shares {old} -> {[wm_r, wy_r, wx_r]} "
                f"(exact max={wx:.4f})"
            )
            # use exact shares for ARPU to avoid rounding drift
            wm, wy, wx = wm, wy, wx
        else:
            wm = float(arpu.cell(shares_r, 3).value)
            wy = float(arpu.cell(shares_r, 4).value)
            wx = 0.0
            print(f"{qname} two-tier shares wm={wm} wy={wy}")

        price_m = float(arpu.cell(m_r, 1).value)
        price_y = float(arpu.cell(y_r, 1).value)
        for i, val in enumerate(mm):
            arpu.cell(m_r, 2 + i).value = val
        for i, val in enumerate(yy):
            arpu.cell(y_r, 2 + i).value = round(val, 2)

        if has_max and x_r:
            price_x = float(arpu.cell(x_r, 1).value)
            for i, val in enumerate(yy):
                arpu.cell(x_r, 2 + i).value = round(val, 2)
            aa = [
                arpu_with_max(wm, wy, wx, price_m, price_y, price_x, mm[i], yy[i])
                for i in range(3)
            ]
        else:
            aa = [arpu_no_max(wm, wy, price_m, price_y, mm[i], yy[i]) for i in range(3)]

        for i, val in enumerate(aa):
            arpu.cell(a_r, 1 + i).value = round(val, 1)
        arpu.cell(a_r, 5).value = None
        print(f"  months {mm} years {[round(v,2) for v in yy]} ARPU {[round(v,1) for v in aa]}")

        # spot-check user numbers
        if qname == "2026Q2":
            assert abs(aa[0] - 470.4) < 1.0, aa[0]
        if qname == "2025Q4":
            assert abs(aa[0] - 543.8) < 1.5, aa[0]


def delete_cohort_stripe_cols(ws):
    """Delete last three data columns: 有效订阅用户 / MRR / 销售净收入 (stripe)."""
    # find by header
    headers = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}
    targets = ["有效订阅用户", "MRR（港币）", "销售净收入（港币）"]
    cols = sorted([headers[t] for t in targets if t in headers], reverse=True)
    if len(cols) != 3:
        print("WARN cohort stripe cols:", {t: headers.get(t) for t in targets})
    for c in cols:
        print(f"delete cohort col {get_column_letter(c)} {ws.cell(1,c).value}")
        ws.delete_cols(c, 1)
    # clear trailing empties already gone
    print("cohort max_col now", ws.max_column, "last headers",
          [ws.cell(1, c).value for c in range(max(1, ws.max_column - 2), ws.max_column + 1)])


def add_retention_notes(ws):
    """44.9% sensitivity note by S column + table footer."""
    # Find Jun-25 yearly row
    jun_row = None
    for r in range(2, 40):
        if ws.cell(r, 15).value == "Jun-25":
            jun_row = r
            break
    if jun_row:
        # R col is one_year rate formula; put comment on R and S
        rate = None
        p, q = ws.cell(jun_row, 16).value, ws.cell(jun_row, 17).value
        if p and q:
            rate = float(q) / float(p)
        note = (
            f"敏感值：Jun-25 一年留存 {rate:.1%}（{int(q)}/{int(p)}）。"
            "该批为最新满一年单批，末周期可能尚有未续费；"
            "不作基准，建议用滚动6个月人数加权（约51.7%）。"
            if rate
            else "敏感值：Jun-25 一年留存约44.9%；末周期或有未续费，不作基准。"
        )
        for col in (18, 19):  # R, S
            cell = ws.cell(jun_row, col)
            cell.comment = Comment(note, "T027", width=300, height=120)
        # also value hint in U (right of T) without breaking O-T block — use column V
        ws.cell(jun_row, 22).value = "←敏感值44.9%，见批注"
        ws.cell(jun_row, 22).font = Font(color="C00000", size=9)

    # footer below table
    last = max(
        r
        for r in range(1, ws.max_row + 1)
        if any(ws.cell(r, c).value is not None for c in range(1, 21))
    )
    # clear old T027 notes then rewrite clean block
    for r in range(last + 1, last + 12):
        for c in range(1, 8):
            if ws.cell(r, c).value and str(ws.cell(r, c).value).startswith("【说明】"):
                pass
    # append after existing content
    start = last + 2
    # if notes already exist, find and replace from first 【说明】
    for r in range(60, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, str) and v.startswith("【说明】"):
            start = r
            for rr in range(r, r + 10):
                for c in range(1, 8):
                    ws.cell(rr, c).value = None
            break

    lines = [
        "【说明】续费基准与敏感值（表内仅改结果）",
        "1. 年费：该季末已满一年近最多6批人数加权得r1；年数=1 / 1+r1 / 1+r1+r1×65%。",
        "2. 月费：1年=首月1+SUM(1～11月留存)滚动加权；2年=1年×(8.1/5.7)；3年=1年×(9.3/5.7)。",
        "3. 敏感值：Jun-25 一年留存 44.9%（1443/3211）。最新单批、末周期可能尚未续费完毕，"
        "不能单独作基准；披露用，基准用滚动6月加权（约51.7%）。详见 Jun-25 行 S 列旁批注。",
        "4. Aug-25 月费缺第11月留存，不计入滚动。一年变了，二/三年按比例跟随。",
    ]
    for i, text in enumerate(lines):
        cell = ws.cell(start + i, 1, text)
        cell.alignment = Alignment(wrap_text=True)
        if i == 0:
            cell.font = Font(bold=True)


def fix_monthly_wan_headers(ws):
    """网页/视频/PDF/EPUB 与翻译事件数同为单位（万），表头补回（万）。"""
    mapping = {
        "网页翻译数": "网页翻译数(万)",
        "视频翻译数": "视频翻译数(万)",
        "PDF翻译数": "PDF翻译数(万)",
        "EPUB电子书翻译数": "EPUB电子书翻译数(万)",
        # already ok:
        # 累计激活用户(万), 翻译事件数(万)
    }
    for c in range(1, 15):
        v = ws.cell(1, c).value
        if v in mapping:
            print(f"header {get_column_letter(c)}: {v} -> {mapping[v]}")
            ws.cell(1, c).value = mapping[v]
        elif isinstance(v, str) and v.endswith("(万)"):
            print(f"header keep {v}")


def rewrite_arpu_footer(arpu):
    ar_last = max(
        r
        for r in range(1, arpu.max_row + 1)
        if any(arpu.cell(r, c).value is not None for c in range(1, 7))
    )
    for r in range(ar_last + 1, min(ar_last + 20, arpu.max_row + 5)):
        for c in range(1, 7):
            arpu.cell(r, c).value = None
    ns = ar_last + 2
    lines = [
        "【说明】占比与续费假设（表内仅保留结果）",
        "新增用户占比：月费/年费/Max 均以三者人数之和为分母（归一化后加总=1）。"
        "此前 Max 误用年费人数作分母导致约偏高一倍、三档加总>1；已改正并重算 ARPU。",
        "年费/Max 年数：按季 PIT，r1 近6批加权；1 / 1+r1 / 1+r1+r1×65%。",
        "月费月数：1年=1+留存滚动；2/3年按锚点比例 ×(8.1/5.7)/(9.3/5.7) 浮动传递。",
    ]
    for i, text in enumerate(lines):
        cell = arpu.cell(ns + i, 1, text)
        cell.alignment = Alignment(wrap_text=True)
        if i == 0:
            cell.font = Font(bold=True)


def main():
    if not BACKUP.exists():
        raise FileNotFoundError(BACKUP)
    shutil.copy2(BACKUP, OUT)
    wb = load_workbook(OUT)

    fix_shares_and_arpu(wb["ARPU值"], wb["付费用户留存率"])
    delete_cohort_stripe_cols(wb["同期群"])
    add_retention_notes(wb["付费用户留存率"])
    fix_monthly_wan_headers(wb["月度数据"])
    rewrite_arpu_footer(wb["ARPU值"])

    # N12 empty / N32 keep from prior if present
    ws = wb["付费用户留存率"]
    if ws["A12"].value == "Aug-25":
        ws["N12"] = None

    wb.save(OUT)
    print("wrote", OUT)
    try:
        shutil.copy2(OUT, DESK)
        print("desktop updated")
    except Exception as e:
        print("desktop copy failed:", e)


if __name__ == "__main__":
    main()
