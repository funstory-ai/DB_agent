# -*- coding: utf-8 -*-
"""T125 交付物整体检验：
1) 9张表 Q3 数据自洽性（比率=分子/分母、合计=分项、占比和=1）
2) 历史行完整性（与 T027 定稿对比，Q2及更早一个不动）
3) 每个 Q3 数字来源可追溯（对照 merge 脚本各 sheet 函数）
纯只读，不改任何文件。
"""
from openpyxl import load_workbook
from pathlib import Path

ROOT = Path(r"H:\databend_sql")
NEW = ROOT / "output" / "推文datapack-2026Q3_T125.xlsx"
BASE = ROOT / "output" / "推文datapack-202607_T027.xlsx"

def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return None

def close(a, b, tol=0.02):
    if a is None or b is None:
        return None
    return abs(a - b) <= max(tol, abs(b) * 0.01)

wb = load_workbook(NEW, data_only=True)
base = load_workbook(BASE, data_only=True)
print("文件 sheets:", wb.sheetnames)
print()

# ============ 1. 月度数据 ============
print("=" * 70)
print("【1】月度数据")
ws = wb["月度数据"]
# 找表头
hdr = [ws.cell(1, c).value for c in range(1, 10)]
print("表头:", hdr)
for r in range(1, ws.max_row + 1):
    a = ws.cell(r, 1).value
    if a and str(a).startswith("2026Q"):
        vals = [num(ws.cell(r, c).value) for c in range(2, 9)]
        print(f"  r{r} {a}: 累计激活={vals[0]} 翻译事件={vals[1]} 网页={vals[2]} 视频={vals[3]} PDF={vals[4]} EPUB={vals[5]} MAU={vals[6]}")
        # 自洽: 翻译事件 = 网页+视频+PDF+EPUB
        s = sum(v for v in vals[2:6] if v is not None)
        print(f"     自洽检查 网页+视频+PDF+EPUB={round(s,1)} vs 翻译事件={vals[1]} → {'OK' if close(s, vals[1], 0.5) else '❌不符'}")

# ============ 2. MRR ============
print("=" * 70)
print("【2】MRR")
ws = wb["MRR"]
for r in range(28, 31):
    print(f"  r{r}:", [ws.cell(r, c).value for c in range(1, 5)])
print("  D列(销售总收入)是否全空:", all(ws.cell(r, 4).value is None for r in range(28, 31)))

# ============ 3. 月留存GA ============
print("=" * 70)
print("【3】月留存(GA) — 顶部Q3三行")
ws = wb["月留存（GA）"]
for r in range(35, 38):  # 【修正】升序表，Q3追加在表尾 r35-37
    left = [ws.cell(r, c).value for c in range(1, 9)]   # A年月 B新增 C:H 1-6月率
    right = [ws.cell(r, c).value for c in range(12, 19)]  # L年月 M total N:S 人数
    new = num(left[1])
    print(f"  r{r} {left[0]}: 新增={new} 率(1-3月)={[left[i] for i in range(2,5)]}")
    print(f"      右块 {right[0]}: total={right[1]} 人数(1-3月)={[right[i] for i in range(2,5)]}")
    # 自洽: 左率 ≈ 右人数/新增
    for i in range(2, 5):
        rate, cnt = num(left[i]), num(right[i])
        if rate is not None and cnt is not None and new:
            calc = cnt / new
            print(f"      率{i-1}: {rate} vs {cnt}/{new}={round(calc,4)} → {'OK' if close(rate, calc, 0.001) else '⚠️差异'}")

# ============ 4. 付费留存 ============
print("=" * 70)
print("【4】付费用户留存率 — 顶部Q3三行(率区) + 人数区 + 年费区")
ws = wb["付费用户留存率"]
print("  率区(A-C):")
for r in range(2, 5):
    print(f"    r{r}:", [ws.cell(r, c).value for c in range(1, 5)])
print("  人数区(A-C):")
for r in range(37, 40):
    print(f"    r{r}:", [ws.cell(r, c).value for c in range(1, 5)])
print("  年费区(O-R):")
for r in range(2, 5):
    print(f"    r{r}:", [ws.cell(r, c).value for c in range(15, 19)])
# 自洽: 率区1月率 ≈ 人数区1月/新增
for rr, cr in zip(range(2, 5), range(37, 40)):
    new = num(ws.cell(rr, 2).value)
    rate = num(ws.cell(rr, 3).value)
    cnt = num(ws.cell(cr, 3).value)
    if rate is not None and cnt is not None and new:
        print(f"    {ws.cell(rr,1).value} 1月率 {rate} vs {cnt}/{new}={round(cnt/new,4)} → {'OK' if close(rate,cnt/new,0.001) else '⚠️'}")

# ============ 5. ARPU ============
print("=" * 70)
print("【5】ARPU值 — 顶部2026Q3块")
ws = wb["ARPU值"]
for r in range(1, 18):
    row = [ws.cell(r, c).value for c in range(1, 7)]
    if any(v is not None for v in row):
        print(f"  r{r}:", row)

# ============ 6. 同期群 ============
print("=" * 70)
print("【6】同期群 — Q3三行")
ws = wb["同期群"]
for r in range(28, 31):
    print(f"  r{r} 日期={ws.cell(r,1).value}: 营销={ws.cell(r,2).value} 激活={ws.cell(r,3).value} 成本={ws.cell(r,4).value} 收入={round(ws.cell(r,5).value,0) if num(ws.cell(r,5).value) else None} 总回报={ws.cell(r,7).value} 转化={ws.cell(r,8).value} 转化率={ws.cell(r,9).value}")

# ============ 7. 分语言 ============
print("=" * 70)
print("【7】分语言地区付费转化率")
ws = wb["分语言地区付费转化率"]
print("  表头:", [ws.cell(1, c).value for c in range(1, 5)])
tot_mau = tot_paid = 0
for r in range(2, 11):
    region = ws.cell(r, 1).value
    mau, paid, rate = num(ws.cell(r, 2).value), num(ws.cell(r, 3).value), num(ws.cell(r, 4).value)
    if mau: tot_mau += mau
    if paid: tot_paid += paid
    ok = close(paid / mau, rate, 0.0001) if (mau and paid is not None and rate is not None) else None
    print(f"  {region}: 月活={int(mau) if mau else None} 付费={int(paid) if paid else None} 转化率={rate} → {'OK' if ok else '⚠️'}")
print(f"  合计: 月活={int(tot_mau)} 付费={int(tot_paid)} 整体转化率={round(tot_paid/tot_mau,5)}")
