"""Produce a simplified 5-column weekly table for LAST YEAR (2024-11~2025-11)
matching the user's screenshot format: 周(周一), SG, MY, 合计, 备注.
Reads the already-computed sheet in sg_my_weekly_revenue_yoy_202411_202511.xlsx
(sheet '去年同期周收入_SG_MY') and rewrites the clean 5-column layout.
"""
import openpyxl
from pathlib import Path
from openpyxl.styles import Font, PatternFill, Alignment

OUT = Path("output/sg_my_revenue")
src = OUT / "sg_my_weekly_revenue_yoy_202411_202511.xlsx"
dst = OUT / "sg_my_weekly_lastyear_simple_202411_202511.xlsx"

wb_src = openpyxl.load_workbook(src, data_only=True)
ws_src = wb_src["去年同期周收入_SG_MY"]

rows = []
for r in ws_src.iter_rows(values_only=True):
    if not r or not r[0] or not str(r[0]).startswith("20"):
        continue
    if not isinstance(r[3], (int, float)):
        continue
    wk = str(r[0])[:10]
    sg = round(float(r[1] or 0), 2)
    my = round(float(r[2] or 0), 2)
    comb = round(float(r[3] or 0), 2)
    note = str(r[11] or "") if len(r) > 11 else ""
    rows.append((wk, sg, my, comb, note))

# split complete vs incomplete (edges)
complete = [x for x in rows if x[4] == ""]
incomplete = [x for x in rows if x[4] != ""]

# build workbook: main sheet = full year (all weeks, edges flagged), plus a
# '最近14完整周' sheet mirroring the screenshot framing.
wb = openpyxl.Workbook()
hdr = ["周(周一)", "SG", "MY", "合计", "备注"]
hdr_fill = PatternFill("solid", fgColor="D9D9D9")

def style_header(ws):
    for c in range(1, len(hdr)+1):
        cell = ws.cell(1, c)
        cell.font = Font(bold=True)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")

# --- Sheet1: full last-year weekly table (image format) ---
ws1 = wb.active; ws1.title = "去年周收入_SG_MY"
ws1.append(hdr); style_header(ws1)
for wk, sg, my, comb, note in rows:
    ws1.append([wk, sg, my, comb, note])
# re-apply note for incomplete weeks (already in note)
ws1.append([])
ws1.append(["注: 起始/末尾不完整周已在备注标注，不参与趋势判断；金额单位为人民币¥，按用户主导 real_geo 归属（同今年周版口径）。"])

# --- Sheet2: last 14 COMPLETE weeks of last year (mirror the screenshot) ---
ws2 = wb.create_sheet("去年最近14完整周")
ws2.append(hdr); style_header(ws2)
last14 = complete[-14:]
for wk, sg, my, comb, note in last14:
    ws2.append([wk, sg, my, comb, note])

wb.save(dst)
print("SAVED:", dst)
print(f"total weeks: {len(rows)} (complete {len(complete)}, incomplete {len(incomplete)})")
print("\n=== 去年最近 14 个完整周（SG+MY 合计，¥）===")
print(" | ".join(hdr))
for wk, sg, my, comb, note in last14:
    print(f"{wk} | {sg:>10,.0f} | {my:>8,.0f} | {comb:>10,.0f} | {note}")
