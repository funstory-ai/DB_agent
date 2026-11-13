"""T105 探查：各月 UCloud 账单 / 星图订单的 sheet 结构与 luna 行样例。"""
import os
import polars as pl

DL = r"C:\Users\86933\Downloads"
FILES = [
    "Funstory.ai Limited 推文科技有限公司-6月份账单（20260601-20260701）.xlsx",
    "Funstory.ai Limited 推文科技有限公司-7月份账单（20260701-20260801）.xlsx",
    "Funstory.ai Limited 推文科技有限公司-8月份账单（20260801-20260901）.xlsx",
    "66837208_星图_已完成订单_2026-10-06_2026-11-05_1793938462.xlsx",
]

for f in FILES:
    p = os.path.join(DL, f)
    print("=" * 100)
    print("FILE:", f, os.path.getsize(p), "bytes")
    try:
        import fastexcel
        exc = fastexcel.read_excel(p)
        names = exc.sheet_names
    except Exception as e:
        print("  sheet_names err", e)
        names = []
    print("SHEETS:", names)
    for s in names:
        try:
            d = pl.read_excel(p, engine="calamine", sheet_name=s)
        except Exception as e:
            print("  read err", s, e)
            continue
        print("-" * 80)
        print(f"  [{s}] shape={d.shape}")
        print("  COLUMNS:", d.columns)
        with pl.Config(tbl_rows=8, tbl_cols=30, fmt_str_lengths=40):
            print(d.head(6))
        # 找 luna 行
        for c in d.columns:
            if d[c].dtype == pl.String:
                m = d.filter(pl.col(c).str.contains("(?i)luna"))
                if m.height:
                    print(f"  >>> luna rows by col[{c}]: {m.height}")
                    with pl.Config(tbl_rows=6, tbl_cols=30, fmt_str_lengths=40):
                        print(m.head(4))
                    break
