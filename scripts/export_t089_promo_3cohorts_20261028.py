# -*- coding: utf-8 -*-
"""T089: 促销三类用户（高频免费 / 月费 / 年费到期）→ 三 sheet Excel。

口径见 sql/reports/query_promo_3cohorts_20261028.sql 头部注释。
输出列：userid, 邮箱, 近30天翻译次数, 到期时间, 会员类型。
免费用户 到期时间 留空；月费/年费 到期时间=当前有效订单的覆盖结束日。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query
from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "reports" / "query_promo_3cohorts_20261028.sql"
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)

SHEETS = {
    "高频免费用户": [
        ("userid", "userid"),
        ("email", "邮箱"),
        ("translate_cnt_30d", "近30天翻译次数"),
        ("member_type", "会员类型"),
    ],
    "月费用户": [
        ("userid", "userid"),
        ("email", "邮箱"),
        ("translate_cnt_30d", "近30天翻译次数"),
        ("expire_time", "到期时间"),
        ("member_type", "会员类型"),
    ],
    "年费到期用户": [
        ("userid", "userid"),
        ("email", "邮箱"),
        ("translate_cnt_30d", "近30天翻译次数"),
        ("expire_time", "到期时间"),
        ("member_type", "会员类型"),
    ],
}


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print("running T089 SQL ...", flush=True)
    cols, rows = query(sql)
    print("cols", cols, "nrows", len(rows), flush=True)

    col_idx = {c: i for i, c in enumerate(cols)}
    by = {k: [] for k in SHEETS}
    for r in rows:
        label = r[col_idx["cohort_label"]]
        if label in by:
            by[label].append(r)

    stamp = datetime.now().strftime("%Y%m%d")
    out = OUT_DIR / f"promo_3cohorts_{stamp}.xlsx"
    wb = Workbook()
    default = wb.active
    wb.remove(default)

    # 汇总 sheet
    summary = wb.create_sheet("汇总", 0)
    summary.append(["人群", "人数", "有邮箱人数", "备注"])
    for cell in summary[1]:
        cell.font = Font(bold=True)
    summary.append(["口径", "", "", "高频=免费用户近30天翻译次数前1%；月费=当前在效monthly；年费到期=当前在效yearly且11-13前到期"])
    hf_min = None
    for name, fields in SHEETS.items():
        data = by.get(name, [])
        with_email = sum(1 for r in data if r[col_idx["email"]] not in (None, ""))
        note = ""
        if name == "高频免费用户" and data:
            hf_min = min(r[col_idx["translate_cnt_30d"]] for r in data)
            note = f"前1%门槛≈≥{hf_min}次/30天"
        summary.append([name, len(data), with_email, note])
        print(f"sheet {name}: {len(data)} (email:{with_email})", flush=True)
    if hf_min is not None:
        print("高频免费用户 前1% 最低翻译次数 =", hf_min, flush=True)

    for name, fields in SHEETS.items():
        ws = wb.create_sheet(name)
        headers = [h for _, h in fields]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for r in by.get(name, []):
            ws.append([r[col_idx[k]] for k, _ in fields])

    wb.save(out)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
