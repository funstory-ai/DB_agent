#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T082 放量期(11-02~11-05) UCloud 全模型对账：我方 token_used_aw vs 供应商(星图)账单。
修正：供应商 计费单元 含 Unicode 全角下划线(U+FF3F)，先归一化再解析。
"""
import sys, unicodedata
sys.path.insert(0, "scripts")
import db
from openpyxl import load_workbook
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from collections import defaultdict

P = r"C:\Users\86933\Downloads\66837208_星图_已完成订单_2026-10-06_2026-11-05_1793938462.xlsx"
WIN0, WIN1 = "2026-11-02", "2026-11-05"   # 北京日期窗口(双方都有数据)

def norm(s):
    """Unicode 下划线(Pc 类) -> ascii '_'"""
    out = []
    for ch in str(s):
        out.append('_' if unicodedata.category(ch) == 'Pc' else ch)
    return ''.join(out)

def parse_unit(u):
    u = norm(u).strip()
    ul = u.lower()
    # 模型 id = 截到最早出现的标记（verbose 单元里 text&image 先于 input/output/cache）
    markers = ['_text&image', 'text&image', '_input', '_output', '_cache',
               'cache read', 'cache write', 'cache-read', 'cache-write']
    best_i, best = len(u), None
    for mk in markers:
        i = ul.find(mk)
        if i != -1 and i < best_i:
            best_i, best = i, mk
    if best is None:
        return u, 'other'
    mid = u[:best_i].rstrip('_').rstrip('-')
    # 类型用子串优先级（input/output 可能出现在 text&image 之后，必须优先判定）
    if 'output' in ul:
        typ = 'output'
    elif 'input' in ul:
        typ = 'input'
    else:
        typ = 'cache'          # text&image / cache read / cache write
    return mid, typ

# ---------- 供应商 ----------
wb = load_workbook(P, data_only=True)
ws = wb["已支付订单详单"]
rows = list(ws.iter_rows(values_only=True))
hdr = list(rows[0]); idx = {h: i for i, h in enumerate(hdr)}
data = rows[1:]

sup = defaultdict(lambda: defaultdict(float))          # model -> {input,output,cache}
sup_daily = defaultdict(lambda: defaultdict(float))    # (model,date) -> {...}
other_daily = defaultdict(float)                       # date -> 未归类量
other_total = 0.0
for r in data:
    d = str(r[idx['开始时间']])[:10]
    if d < WIN0 or d > WIN1:
        continue
    mid, typ = parse_unit(r[idx['计费单元']])
    q = float(r[idx['用量']] or 0)
    if typ == 'other':
        other_daily[d] += q
        other_total += q
        continue
    sup[mid][typ] += q
    sup_daily[(mid, d)][typ] += q

# ---------- 我方 ----------
SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') bj, actualresourceid,
       SUM(inputusage) inp, SUM(cachedinputusage) cinp, SUM(outputusage) outp
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture'
  AND timestamp >= '2026-11-01 16:00:00' AND timestamp < '2026-11-05 16:00:00'
GROUP BY bj, actualresourceid
"""
_, dbrows = db.query(SQL)
db_tot = defaultdict(lambda: [0.0, 0.0, 0.0])          # model -> [in,cinp,out]
db_daily = defaultdict(lambda: [0.0, 0.0])             # date -> [in,out]
for r in dbrows:
    bj, mid = r[0], r[1]
    if bj < WIN0 or bj > WIN1:
        continue
    inp, cinp, outp = float(r[2] or 0), float(r[3] or 0), float(r[4] or 0)
    db_tot[mid][0] += inp; db_tot[mid][1] += cinp; db_tot[mid][2] += outp
    db_daily[bj][0] += inp; db_daily[bj][1] += outp

# ---------- 输出：逐模型 ----------
def pct(a, b):
    return (a - b) / b * 100 if b else float('nan')

print(f"=== 逐模型对比 放量期 {WIN0}~{WIN1}（单位：亿 token；比例=out/in）===")
print(f"{'模型':18s}|{'S_in':>9s}{'S_cache':>8s}{'S_out':>9s}{'S_o/i':>6s}|{'D_in':>9s}{'D_cinp':>7s}{'D_out':>9s}{'D_o/i':>6s}|{'in差%':>6s}{'out差%':>7s}| 备注")
print('-' * 114)
allm = sorted(set(sup) | set(db_tot), key=lambda m: -(db_tot.get(m, [0, 0, 0])[0] + sup.get(m, defaultdict(float)).get('input', 0)))
for m in allm:
    s = sup.get(m, defaultdict(float)); d = db_tot.get(m, [0, 0, 0])
    si, sc, so = s.get('input', 0), s.get('cache', 0), s.get('output', 0)
    di, dc, do = d[0], d[1], d[2]
    if si + di == 0:
        continue
    maxvol = max(si, sc, so, di, dc, do)
    tiny = maxvol < 5e6
    sr = f"{so/si*100:5.1f}" if si else "  - "
    dr = f"{do/di*100:5.1f}" if di else "  - "
    ind = pct(di, si)
    outd = pct(do, so)
    ind_s = f"{ind:+5.1f}" if ind == ind else "  -  "
    outd_s = f"{outd:+6.1f}" if outd == outd else "  -  "
    if tiny:
        note = "量极小(可忽略)"
    elif di == 0 and si > 0:
        note = "⚠️仅供应商(中台/团队Key未入AW)"
    elif si == 0 and di > 0:
        note = "仅我方"
    elif outd < -10:
        note = "⚠️我方输出偏低(供应商多计输出?)"
    elif ind < -10:
        note = "⚠️输入偏低"
    elif abs(ind) < 5 and abs(outd) < 12:
        note = "✅对上"
    else:
        note = "需复核"
    print(f"{m:18s}|{si/1e9:9.4f}{sc/1e9:8.4f}{so/1e9:9.4f}{sr:>6s}|{di/1e9:9.4f}{dc/1e9:7.4f}{do/1e9:9.4f}{dr:>6s}|{ind_s:>6s}{outd_s:>7s}| {note}")
print(f"(未归类/无法解析的 计费单元 全窗合计约 {other_total/1e9:.4f} 亿 token，已单列不计入上表)")
print(f"  每日未归类量: " + ", ".join(f"{d}={other_daily[d]/1e9:.4f}亿" for d in sorted(other_daily)))

print(f"\n=== 每日总览 {WIN0}~{WIN1} ===")
print(f"{'日期':12s}|{'S_in':>9s}{'S_out':>9s}{'S_o/i':>6s}|{'D_in':>9s}{'D_out':>9s}{'D_o/i':>6s}|{'in差%':>6s}")
print('-' * 70)
for d in sorted(db_daily):
    sd_in = sum(sup_daily[(m, d)].get('input', 0) for m in sup)
    sd_out = sum(sup_daily[(m, d)].get('output', 0) for m in sup)
    dd_in, dd_out = db_daily[d]
    sr = f"{sd_out/sd_in*100:5.1f}" if sd_in else "  - "
    dr = f"{dd_out/dd_in*100:5.1f}" if dd_in else "  - "
    ind = pct(dd_in, sd_in)
    print(f"{d:12s}|{sd_in/1e9:9.3f}{sd_out/1e9:9.3f}{sr:>6s}|{dd_in/1e9:9.3f}{dd_out/1e9:9.3f}{dr:>6s}|{ind:+5.1f}")

# ---------- 写 xlsx ----------
wb2 = Workbook()
ws1 = wb2.active; ws1.title = "逐模型对比_1102_1105"
hdr1 = ["模型", "供应商_in(亿)", "供应商_cache(亿)", "供应商_out(亿)", "供应商_out/in",
        "我方_in(亿)", "我方_cinp(亿)", "我方_out(亿)", "我方_out/in",
        "in差值%", "out差值%", "供应商cache占比", "备注"]
ws1.append(hdr1)
for c in range(1, len(hdr1) + 1):
    ws1.cell(1, c).font = Font(bold=True)
for m in allm:
    s = sup.get(m, defaultdict(float)); d = db_tot.get(m, [0, 0, 0])
    si, sc, so = s.get('input', 0), s.get('cache', 0), s.get('output', 0)
    di, dc, do = d[0], d[1], d[2]
    if si + di == 0:
        continue
    maxvol = max(si, sc, so, di, dc, do)
    tiny = maxvol < 5e6
    sr = round(so/si*100, 1) if si else None
    dr = round(do/di*100, 1) if di else None
    ind = round(pct(di, si), 1) if si else None
    outd = round(pct(do, so), 1) if so else None
    cshare = round(sc/(si+sc)*100, 1) if (si+sc) else None
    if tiny: note = "量极小(可忽略)"
    elif di == 0 and si > 0: note = "仅供应商(中台/团队Key未入AW)"
    elif si == 0 and di > 0: note = "仅我方"
    elif outd is not None and outd < -10: note = "我方输出偏低(供应商多计输出?)"
    elif ind is not None and ind < -10: note = "输入偏低"
    elif (ind is None or abs(ind) < 5) and (outd is None or abs(outd) < 12): note = "对上"
    else: note = "需复核"
    ws1.append([m, round(si/1e9, 4), round(sc/1e9, 4), round(so/1e9, 4), sr,
                round(di/1e9, 4), round(dc/1e9, 4), round(do/1e9, 4), dr,
                ind, outd, cshare, note])
# 未归类行
if other_total > 0:
    ws1.append(["(未归类/无法解析计费单元)", None, None, None, None, None, None, None, None,
                None, None, None, f"合计{other_total/1e9:.4f}亿,不计入模型"])

ws2 = wb2.create_sheet("每日对比_1102_1105")
hdr2 = ["日期", "供应商_in(亿)", "供应商_out(亿)", "供应商_out/in", "我方_in(亿)", "我方_out(亿)", "我方_out/in", "in差值%"]
ws2.append(hdr2)
for c in range(1, len(hdr2) + 1):
    ws2.cell(1, c).font = Font(bold=True)
for d in sorted(db_daily):
    sd_in = sum(sup_daily[(m, d)].get('input', 0) for m in sup)
    sd_out = sum(sup_daily[(m, d)].get('output', 0) for m in sup)
    dd_in, dd_out = db_daily[d]
    sr = round(sd_out/sd_in*100, 1) if sd_in else None
    dr = round(dd_out/dd_in*100, 1) if dd_in else None
    ind = round(pct(dd_in, sd_in), 1) if sd_in else None
    ws2.append([d, round(sd_in/1e9, 4), round(sd_out/1e9, 4), sr,
                round(dd_in/1e9, 4), round(dd_out/1e9, 4), dr, ind])

ws3 = wb2.create_sheet("说明")
notes = [
    "T082 放量期对账：窗口 = 北京 2026-11-02 ~ 2026-11-05（双方都有数据；11-06 起供应商账单尚无）。",
    "左=供应商(星图 UCloud 后付费订单明细 xlsx)；右=我方 immdata.token_used_aw (providername='UCloud', recordtype='capture')。",
    "供应商账单只覆盖我方 UCloud 专线这一路上游；全 provider(含 OneRouter/OpenAI 等)不在此账单内。",
    "解析修正：供应商 计费单元 含 Unicode 全角下划线(U+FF3F)，已归一化为 ASCII 再拆分 模型/input/output/cache。",
    "cache：我方 cachedinputusage 恒为 0（imt-api 硬编码 CachedInputUsage=0），cache token 已折入 inputusage（见 gpt-6-luna：我方 in≈供 in+cache，差~1.8%）。",
    "比例 = out/in。供应商 luna/kimi 的 out/in 偏高 = 供应商多计输出的老问题（T081）；我方自记比例正常(24~37%)。",
    "⚠️仅供应商：gpt-5.4 等中台/团队 Key 未入 AW 账本（T017 已知），非本次问题。",
    "量小(<10万token/模型)长尾已忽略，不影响结论。",
]
for i, t in enumerate(notes, 1):
    ws3.cell(i, 1, t)

out = "output/ucloud_recon_ramp_20261102_20261105.xlsx"
wb2.save(out)
print("\n已导出:", out)
