# -*- coding: utf-8 -*-
"""T125 检验 part3：验证付费留存表507处"公式→硬编码"转换的数值正确性。
对每个 base 是 =Qx/Px 公式、NEW 是硬编码值的单元格，重算 Q/P 对比。
"""
from openpyxl import load_workbook
from pathlib import Path
import re

ROOT = Path(r"H:\databend_sql")
NEW = ROOT / "output" / "推文datapack-2026Q3_T125.xlsx"
BASE = ROOT / "output" / "推文datapack-202607_T027.xlsx"
wb = load_workbook(NEW, data_only=True)
base = load_workbook(BASE, data_only=False)  # 读公式原文

ws_n = wb["付费用户留存率"]
bs_f = base["付费用户留存率"]

def norm(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return round(float(v), 6)
    return str(v)

bad = []
converted = 0
for r in range(1, bs_f.max_row + 1):
    nr = r + 3 if r >= 2 else r
    for c in range(1, bs_f.max_column + 1):
        bv = bs_f.cell(r, c).value
        nv = norm(ws_n.cell(nr, c).value)
        if isinstance(bv, str) and bv.startswith("=") and nv is not None and not (isinstance(nv, str) and nv.startswith("=")):
            # base 是公式，NEW 是硬编码值 → 需验证
            converted += 1
            # 解析 =Q14/P14 形式
            m = re.match(r"^=([A-Z]+)(\d+)/([A-Z]+)(\d+)$", bv)
            if m:
                col1, row1, col2, row2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
                from openpyxl.utils import column_index_from_string
                # 公式引用的是 base 表的行；但 base 表公式缓存已丢，用 base 的 Q/P 原值重算
                qv = bs_f.cell(row1, column_index_from_string(col1)).value
                pv = bs_f.cell(row2, column_index_from_string(col2)).value
                if isinstance(qv, (int, float)) and isinstance(pv, (int, float)) and pv:
                    calc = qv / pv
                    if abs(calc - nv) > 0.001:
                        bad.append((f"base r{r}c{c}", bv, f"{qv}/{pv}={round(calc,4)}", nv))

print(f"公式→硬编码 转换单元格数: {converted}")
print(f"数值不符(误差>0.001)的: {len(bad)}")
for x in bad[:30]:
    print("  ❌", x)

# 另外：检查 NEW 里是否还残留公式（应该都转硬编码了）
residual = []
for r in range(2, ws_n.max_row + 1):
    for c in range(1, ws_n.max_column + 1):
        v = ws_n.cell(r, c).value
        if isinstance(v, str) and v.startswith("="):
            residual.append((r, c, v))
print(f"NEW 表残留公式数: {len(residual)}")
for x in residual[:20]:
    print("  残留:", x)
