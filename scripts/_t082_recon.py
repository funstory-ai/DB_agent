# -*- coding: utf-8 -*-
"""T082: 供应商(星图)明细 vs 我方 token_used_aw(UCloud 专线) 对账
交付: output/ucloud_supplier_recon_20261006_20261105.xlsx + 控制台报告
口径(沿用 T081): 北京日 = timestamp+8h; 模型用 actualresourceid; 供应商账单对应 providername='UCloud' 这一路。
"""
import sys, os
sys.path.insert(0, "H:/databend_sql/scripts")
from db import query
from openpyxl import load_workbook, Workbook
from collections import defaultdict

XLSX = r"C:\Users\86933\Downloads\66837208_星图_已完成订单_2026-10-06_2026-11-05_1793938462.xlsx"
RAMP_START, WIN_START, WIN_END = "2026-11-02", "2026-10-06", "2026-11-05"
OUT = "H:/databend_sql/output/ucloud_supplier_recon_20261006_20261105.xlsx"

SUP2DB = {
    "openai/gpt-5-mini": "gpt-5-mini", "gpt-5.4": "gpt-5.4",
    "gpt-5.6-luna": "gpt-5.6-luna", "gpt-5.6-terra": "gpt-5.6-terra",
    "gpt-6-luna": "gpt-6-luna", "gpt-6-sol": "gpt-6-sol", "gpt-6.1-sol": "gpt-6.1-sol",
    "kimi-k2.6": "kimi-k2.6", "qwen3.5-plus": "qwen3.5-plus",
    "glm-5.3-flash": "glm-5.3-flash", "gemini-3-flash-preview": "gemini-3-flash-preview",
    "claude-haiku-4-5-20251001": "claude-haiku-5-5",
}

def classify(u):
    s = str(u).lower()
    if "cache" in s: return "cache"
    if "input" in s: return "input"
    if "output" in s: return "output"
    return "other"

# ---------- 1) 供应商 ----------
wb = load_workbook(XLSX, data_only=True)
ws = wb["已支付订单详单"]
rows = list(ws.iter_rows(values_only=True))
hdr = list(rows[0]); idx = {h: i for i, h in enumerate(hdr)}
sup = defaultdict(float)
for r in rows[1:]:
    mraw = r[idx["模型名称"]]
    if mraw is None: continue
    mdb = SUP2DB.get(str(mraw).strip(), str(mraw).strip())
    typ = classify(r[idx["计费单元"]])
    if typ == "other": continue
    d = str(r[idx["开始时间"]])[:10]
    try: q = float(r[idx["用量"]])
    except: q = 0.0
    sup[(mdb, typ, d)] += q

# ---------- 2) 我方 UCloud 专线 (按 北京日×模型) ----------
SQL = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') bj, actualresourceid model,
       SUM(inputusage) inp, SUM(cachedinputusage) cinp, SUM(outputusage) outp
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture'
  AND timestamp >= '2026-10-05 16:00:00' AND timestamp < '2026-11-06 16:00:00'
GROUP BY bj, model"""
_, dbrows = query(SQL)
db = defaultdict(float)
for r in dbrows:
    bj, model, inp, cinp, outp = r[0], r[1], float(r[2] or 0), float(r[3] or 0), float(r[4] or 0)
    if not (WIN_START <= bj <= WIN_END): continue
    db[(model, "input", bj)] += inp
    db[(model, "cache", bj)] += cinp
    db[(model, "output", bj)] += outp

def pct(a, b):
    return (a - b) / b * 100.0 if b else float('nan')

def model_tot(m, side, typ, ramp=False):
    src = sup if side == "S" else db
    s = 0.0
    for (mm, t, d), q in src.items():
        if mm != m or t != typ: continue
        if ramp and not (RAMP_START <= d <= WIN_END): continue
        s += q
    return s

models = sorted(set(k[0] for k in sup))
models = [m for m in models if model_tot(m, "S", "input") + model_tot(m, "S", "output") > 0]

# ---------- 3) 输出报告 + 收集表格 ----------
lines = []
def L(x=""): lines.append(x)

L("="*100)
L("T082 对账: 供应商(星图 已支付订单) vs 我方 token_used_aw(UCloud 专线)  | 窗口 2026-10-06~11-05")
L("="*100)
L("重要前提: 供应商账单只覆盖 providername='UCloud' 这一路流量; 我方全 provider 还含 OneRouter/OpenAI 等(不在此账单内)。")
L("")

# 表A: 逐模型全窗
L("【表A】逐模型全窗对账 (单位 亿).  S=供应商 D=UCloud专线  差%=(D-S)/S")
L("%-20s | %8s %8s %6s | %8s %8s %6s | %8s %8s %6s | %s" %
  ("模型","S_in","D_in","in%","S_out","D_out","out%","S_cache","D_cache","cac%","备注"))
A_rows = []
for m in models:
    si, di = model_tot(m,"S","input"), model_tot(m,"D","input")
    so, do = model_tot(m,"S","output"), model_tot(m,"D","output")
    sc, dc = model_tot(m,"S","cache"), model_tot(m,"D","cache")
    note = ""
    if di == 0 and do == 0: note = "我方UCloud无此模型(或中台/团队Key未入AW账本 T017)"
    L("%-20s | %8.3f %8.3f %6s | %8.3f %8.3f %6s | %8.3f %8.3f %6s | %s" %
      (m, si/1e9, di/1e9, ("%+.1f"%pct(di,si)) if si else "  - ",
          so/1e9, do/1e9, ("%+.1f"%pct(do,so)) if so else "  - ",
          sc/1e9, dc/1e9, ("%+.1f"%pct(dc,sc)) if sc else "  - ", note))
    A_rows.append((m, si, di, so, do, sc, dc, note))
L("")

# 表A2: input+cache 合并口径
L("【表A2】输入侧合并口径: 供应商把 input 与 cache 拆开计, 我方 inputusage 已含 cache(见下'cache=0'根因)")
L("%-20s | %10s %10s %7s" % ("模型","S(in+cache)","D(input)","差%"))
A2_rows = []
for m in models:
    si, sc = model_tot(m,"S","input"), model_tot(m,"S","cache")
    di = model_tot(m,"D","input")
    comb = si + sc
    L("%-20s | %10.3f %10.3f %7s" % (m, comb/1e9, di/1e9, ("%+.1f"%pct(di,comb)) if comb else "  - "))
    A2_rows.append((m, comb, di))
L("")

# 表B: 放量期
L("【表B】放量期 11-02~11-05 逐模型 (单位 亿)")
L("%-20s | %8s %8s %6s | %8s %8s %6s | %s" %
  ("模型","S_in","D_in","in%","S_out","D_out","out%","备注"))
B_rows = []
for m in models:
    si = model_tot(m,"S","input",True); di = model_tot(m,"D","input",True)
    so = model_tot(m,"S","output",True); do = model_tot(m,"D","output",True)
    note = ""
    if di == 0 and do == 0: note = "我方UCloud无此模型"
    L("%-20s | %8.3f %8.3f %6s | %8.3f %8.3f %6s | %s" %
      (m, si/1e9, di/1e9, ("%+.1f"%pct(di,si)) if si else "  - ",
          so/1e9, do/1e9, ("%+.1f"%pct(do,so)) if so else "  - ", note))
    B_rows.append((m, si, di, so, do, note))
L("")

# 表C: 输出/输入 比例(延续 T081 luna 关注点)
L("【表C】输出/输入 比例 (越低 output 占比越小) —— 看供应商是否仍多计 luna/kimi 输出")
L("%-18s | %8s %8s | 判定" % ("模型","供应商","我方"))
C_rows = []
for m in ["gpt-5-mini","gpt-5.6-terra","gpt-5.6-luna","gpt-6-luna","kimi-k2.6"]:
    si, so = model_tot(m,"S","input"), model_tot(m,"S","output")
    di, do = model_tot(m,"D","input"), model_tot(m,"D","output")
    sr = so/si if si else float('nan'); dr = do/di if di else float('nan')
    jud = ""
    if sr == sr and dr == dr and sr - dr > 0.05: jud = "供应商输出占比偏高"
    L("%-18s | %8.3f %8.3f | %s" % (m, sr, dr, jud))
    C_rows.append((m, sr, dr, jud))
L("")

# 表D: request_id 修复验证
def fill(w1, w2):
    sql = f"""SELECT COUNT(*) n,
      SUM(CASE WHEN routeattemptid IS NOT NULL AND routeattemptid<>'' THEN 1 ELSE 0 END),
      SUM(CASE WHEN traceid IS NOT NULL AND traceid<>'' THEN 1 ELSE 0 END),
      SUM(CASE WHEN businessid IS NOT NULL AND businessid<>'' THEN 1 ELSE 0 END),
      SUM(CASE WHEN actionid IS NOT NULL AND actionid<>'' THEN 1 ELSE 0 END)
    FROM immdata.token_used_aw
    WHERE providername='UCloud' AND recordtype='capture' AND timestamp>='{w1}' AND timestamp<'{w2}'"""
    _, r = query(sql); row = r[0]; n = row[0]
    return n, [(row[i]/n*100 if n else 0) for i in range(1,5)]
L("【表D】关联ID(=request_id 等价物)填充率: 修复前(10-20~10-27) vs 放量后(11-02~11-06)")
L("%-18s | %10s | %8s %8s %8s %8s" % ("窗口","行数","routeatt%","trace%","biz%","act%"))
D_rows = []
for label,(a,b) in [("修复前10-20~10-27",("2026-10-20 00:00:00","2026-10-27 00:00:00")),
                     ("放量后11-02~11-06",("2026-11-02 00:00:00","2026-11-06 00:00:00"))]:
    n, f = fill(a,b)
    L("%-18s | %10d | %7.2f %7.2f %7.2f %7.2f" % (label, n, f[0], f[1], f[2], f[3]))
    D_rows.append((label, n, f))
L("")

# 表E: gpt-6-luna 每日(叙事核心)
L("【表E】gpt-6-luna 每日: 供应商 vs UCloud专线 (单位 亿) —— 看 10-20~11-01 缺口与放量对齐")
L("%-11s | %8s %8s %6s | %8s %8s %6s | %8s" % ("日期","S_in","D_in","in%","S_out","D_out","out%","S_cache"))
E_rows = []
SQL_E = """
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') bj,
       SUM(inputusage) inp, SUM(outputusage) outp
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture' AND actualresourceid='gpt-6-luna'
  AND timestamp >= '2026-10-05 16:00:00' AND timestamp < '2026-11-06 16:00:00'
GROUP BY bj ORDER BY bj"""
_, er = query(SQL_E)
uc = {r[0]:(float(r[1]or 0),float(r[2]or 0)) for r in er}
for d in sorted(set(uc) | set(k[2] for k in sup if k[0]=='gpt-6-luna')):
    si = model_tot('gpt-6-luna','S','input') and sum(q for (mm,t,dd),q in sup.items() if mm=='gpt-6-luna' and t=='input' and dd==d)
    so = sum(q for (mm,t,dd),q in sup.items() if mm=='gpt-6-luna' and t=='output' and dd==d)
    sc = sum(q for (mm,t,dd),q in sup.items() if mm=='gpt-6-luna' and t=='cache' and dd==d)
    di, dop = uc.get(d, (0,0))
    L("%-11s | %8.3f %8.3f %6s | %8.3f %8.3f %6s | %8.3f" %
      (d, si/1e9, di/1e9, ("%+.1f"%pct(di,si)) if si else "  - ",
          so/1e9, dop/1e9, ("%+.1f"%pct(dop,so)) if so else "  - ", sc/1e9))
    E_rows.append((d, si, di, so, dop, sc))
L("")
L("说明: 10-20~11-01 供应商/UCloud专线均为0, 但全provider仍~0.6B/天 -> 此期流量切到其它上游, UCloud不计费;")
L("      11-02起 UCloud专线恢复并与供应商对齐(输入+4%), 输出仍低~15-25%(供应商多计, 见T081/T042)。")

print("\n".join(lines))

# ---------- 4) 导出 xlsx ----------
wb2 = Workbook()
def sheet(name, header, data, widths=None):
    s = wb2.create_sheet(name)
    s.append(header)
    for row in data: s.append(row)
    if widths:
        for i, w in enumerate(widths, 1): s.column_dimensions[chr(64+i)].width = w
    return s
sheet("逐模型全窗", ["模型","供应商_in","UCloud_in","in差%","供应商_out","UCloud_out","out差%","供应商_cache","UCloud_cache","cache差%","备注"],
      [(m, round(si,3), round(di,3), (round(pct(di,si),1) if si else None), round(so,3), round(do,3),
        (round(pct(do,so),1) if so else None), round(sc,3), round(dc,3), (round(pct(dc,sc),1) if sc else None), note)
       for (m,si,di,so,do,sc,dc,note) in A_rows])
sheet("输入含cache合并", ["模型","供应商_in+cache","UCloud_input","差%"],
      [(m, round(comb,3), round(di,3), (round(pct(di,comb),1) if comb else None)) for (m,comb,di) in A2_rows])
sheet("放量期11-02起", ["模型","供应商_in","UCloud_in","in差%","供应商_out","UCloud_out","out差%","备注"],
      [(m, round(si,3), round(di,3), (round(pct(di,si),1) if si else None), round(so,3), round(do,3),
        (round(pct(do,so),1) if so else None), note) for (m,si,di,so,do,note) in B_rows])
sheet("输出输入比例", ["模型","供应商比例","我方比例","判定"],
      [(m, (round(sr,3) if sr==sr else None), (round(dr,3) if dr==dr else None), jud) for (m,sr,dr,jud) in C_rows])
sheet("关联ID填充", ["窗口","行数","routeattemptid%","traceid%","businessid%","actionid%"],
      [(label, n, round(f[0],2), round(f[1],2), round(f[2],2), round(f[3],2)) for (label,n,f) in D_rows])
sheet("gpt6luna每日", ["日期","供应商_in","UCloud_in","供应商_out","UCloud_out","供应商_cache"],
      [(d, round(si,3), round(di,3), round(so,3), round(dop,3), round(sc,3)) for (d,si,di,so,dop,sc) in E_rows])
sheet("说明", ["结论与口径"],
      [["1. 供应商(星图)账单只对应我方 providername='UCloud' 这一路; 全provider含OneRouter/OpenAI等不在该账单内。"],
       ["2. 输入: UCloud专线 vs 供应商对齐良好(+4%); 供应商拆 input/cache, 我方 inputusage 已含cache, 合并后差~1.5%。"],
       ["3. 输出: 我方系统性低~15%(放量期~25%)。延续T081/T042结论: 供应商多计luna/kimi输出, 非我方少记(我方luna输出占比0.258与同代mini/terra≈0.24自洽, 供应商luna 0.318偏高)。"],
       ["4. cache: 我方 cachedinputusage 全窗=0, 供应商单独计cache(gpt-6-luna 0.224B)。根因: imt-api 各Controller硬编码 CachedInputUsage=0, 未记录缓存token。"],
       ["5. 10-20~11-01 供应商/UCloud专线均0, 但全provider~0.6B/天 -> 此期gpt-6-luna流量切到其它上游, UCloud不计费; 11-02起UCloud恢复放量并与供应商对齐。"],
       ["6. request_id修复已落地: routeattemptid/traceid 填充率从修复前0% -> 放量后100%; UCloud量从~1920行/周 增至53.5万行/4天。"]])
if "Sheet" in wb2.sheetnames: del wb2["Sheet"]
wb2.save(OUT)
print("\n已导出:", OUT)
