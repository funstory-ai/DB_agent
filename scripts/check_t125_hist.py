# -*- coding: utf-8 -*-
"""T125 检验 part2：历史行完整性（Q2及更早一个不动）+ 疑点深挖。
对比 NEW vs T027定稿 的历史行，逐格找差异。
"""
from openpyxl import load_workbook
from pathlib import Path
from datetime import datetime

ROOT = Path(r"H:\databend_sql")
NEW = ROOT / "output" / "推文datapack-2026Q3_T125.xlsx"
BASE = ROOT / "output" / "推文datapack-202607_T027.xlsx"
wb = load_workbook(NEW, data_only=False)
base = load_workbook(BASE, data_only=False)

def norm(v):
    """规范化值用于对比：None/空串归一；公式字符串保留；数值浮点归一。"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return round(float(v), 6)
    if isinstance(v, (datetime,)):
        return v
    return str(v)

def cmp_sheet(name, header_rows, row_map):
    """row_map: [(new_row, base_row, label)] 逐行对比"""
    ws, bs = wb[name], base[name]
    diffs = []
    for nr, br, label in row_map:
        maxc = max(ws.max_column, bs.max_column)
        for c in range(1, maxc + 1):
            nv, bv = norm(ws.cell(nr, c).value), norm(bs.cell(br, c).value)
            if nv != bv:
                diffs.append((label, nr, br, c, bv, nv))
    return diffs

print("=" * 70)
print("【历史完整性】NEW vs T027定稿，Q2及更早逐格对比")

# 封面/captable 应完全一致
for name in ["封面", "captable"]:
    ws, bs = wb[name], base[name]
    diffs = []
    for r in range(1, max(ws.max_row, bs.max_row) + 1):
        for c in range(1, max(ws.max_column, bs.max_column) + 1):
            if norm(ws.cell(r, c).value) != norm(bs.cell(r, c).value):
                diffs.append((r, c, norm(bs.cell(r, c).value), norm(ws.cell(r, c).value)))
    print(f"  {name}: {'✅ 完全一致' if not diffs else f'❌ {len(diffs)}处差异'}")
    for d in diffs[:5]:
        print("     ", d)

# 月度数据: 定稿 r2-9 (2024Q4..2026Q2) → NEW r2-9 (Q3加在r10)
d = cmp_sheet("月度数据", 1, [(r, r, f"r{r}") for r in range(1, 10)])
print(f"  月度数据(r1-9历史): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# MRR: 定稿 r1-27 → NEW r1-27
d = cmp_sheet("MRR", 1, [(r, r, f"r{r}") for r in range(1, 28)])
print(f"  MRR(r1-27历史): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# 月留存GA: NEW顶部插了3行(r2-4 Q3)，历史从NEW r5 = 定稿 r2 开始
ws_n, ws_b = wb["月留存（GA）"], base["月留存（GA）"]
d = []
for r in range(1, ws_b.max_row + 1):
    nr = r + 3 if r >= 2 else r
    for c in range(1, max(ws_n.max_column, ws_b.max_column) + 1):
        if norm(ws_n.cell(nr, c).value) != norm(ws_b.cell(r, c).value):
            d.append((f"base r{r}→new r{nr}", c, norm(ws_b.cell(r, c).value), norm(ws_n.cell(nr, c).value)))
print(f"  月留存GA(历史整体下移3行): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# 付费留存: 一次插行3行，历史整体下移3行
ws_n, ws_b = wb["付费用户留存率"], base["付费用户留存率"]
d = []
for r in range(1, ws_b.max_row + 1):
    nr = r + 3 if r >= 2 else r
    for c in range(1, max(ws_n.max_column, ws_b.max_column) + 1):
        if norm(ws_n.cell(nr, c).value) != norm(ws_b.cell(r, c).value):
            d.append((f"base r{r}→new r{nr}", c, norm(ws_b.cell(r, c).value), norm(ws_n.cell(nr, c).value)))
print(f"  付费留存(历史整体下移3行): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# ARPU: NEW顶部插了18行(Q3块)，历史从NEW r19 = 定稿 r1
ws_n, ws_b = wb["ARPU值"], base["ARPU值"]
d = []
for r in range(1, ws_b.max_row + 1):
    nr = r + 18
    for c in range(1, max(ws_n.max_column, ws_b.max_column) + 1):
        if norm(ws_n.cell(nr, c).value) != norm(ws_b.cell(r, c).value):
            d.append((f"base r{r}→new r{nr}", c, norm(ws_b.cell(r, c).value), norm(ws_n.cell(nr, c).value)))
print(f"  ARPU(历史整体下移18行): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# 同期群: Q3加在r28-30，历史r1-27不变
d = cmp_sheet("同期群", 1, [(r, r, f"r{r}") for r in range(1, 28)])
print(f"  同期群(r1-27历史): {'✅ 完全一致' if not d else f'❌ {len(d)}处差异'}")
for x in d[:10]: print("     ", x)

# 分语言: 这是单月快照表，主月从2026.06改成2026.09，整表值都会变（预期），不算破坏
print("  分语言转化: 单月快照表，主月06→09，值整体替换（预期行为，非破坏）")

# ============ 疑点1: 年费区历史留存率有没有值 ============
print("=" * 70)
print("【疑点1】付费留存 年费区(Q:O-R列) 历史 vs Q3 留存率")
ws = wb["付费用户留存率"]
print("  NEW 年费区 r2-12 (O base_month, P 年费用户, Q 1年率, R ...):")
for r in list(range(2, 8)) + list(range(18, 24)):
    print(f"    r{r}: O={ws.cell(r,15).value} P={ws.cell(r,16).value} Q={ws.cell(r,17).value} R={ws.cell(r,18).value}")
print("  T027定稿 年费区 r2-8:")
bs = base["付费用户留存率"]
for r in range(2, 9):
    print(f"    r{r}: O={bs.cell(r,15).value} P={bs.cell(r,16).value} Q={bs.cell(r,17).value} R={bs.cell(r,18).value}")

# ============ 疑点2: MRR B列与飞书订阅增长趋势 ============
print("=" * 70)
print("【疑点2】MRR B列(自建MRR÷汇率) 历史趋势")
ws = wb["MRR"]
for r in range(22, 31):
    print(f"    r{r}: {ws.cell(r,1).value} B={ws.cell(r,2).value} C={ws.cell(r,3).value} D={ws.cell(r,4).value}")
