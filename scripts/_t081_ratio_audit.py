# -*- coding: utf-8 -*-
"""T081 补充：luna 输入输出比例异常归因 —— 我们库 vs 供应商账单 横向对比
核心问题：8月(及相邻月) luna 的 output/input 比例，到底是我们少记了，还是供应商多记了？
判定思路：
  1) 我们库里 luna 与其同代模型(terra/mini)的比例是否一致 -> 一致则说明我们库内部自洽
  2) 供应商账单里 luna 与其同代模型的比例是否一致 -> 若 luna 明显偏高而 terra/mini 正常，则账单内部不自洽 => 账单侧异常
"""
import sys, os, re, glob
sys.path.insert(0, "H:/databend_sql/scripts")
from db import query
from openpyxl import load_workbook

DL = "C:/Users/86933/Downloads"

# ---------- 1) 解析供应商账单（订单汇总 sheet） ----------
def classify(unit):
    u = str(unit).lower()
    if "output" in u: return "output"
    if "cache" in u: return "cache"
    if "input" in u: return "input"
    return "other"

def map_model(raw):
    r = str(raw).lower()
    for k in ["gpt-5-mini","gpt-5.4","gpt-5.6-luna","gpt-5.6-terra","kimi-k2.5","kimi-k2.6","kimi-k3","qwen3.5-plus","gpt-6"]:
        if k in r: return k
    return raw

files = [os.path.join(DL,f) for f in os.listdir(DL) if "账单" in f and f.endswith(".xlsx")]
bill = {}  # (month, model) -> {input, output}
for f in sorted(files):
    m = re.search(r"(\d)月份账单", f)
    mon = int(m.group(1))
    wb = load_workbook(f, read_only=True, data_only=True)
    ws = wb["订单汇总"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]
    ci_model = hdr.index("模型名称"); ci_unit = hdr.index("计费单元"); ci_usage = hdr.index("用量")
    for r in rows[1:]:
        if r[ci_model] is None: continue
        typ = classify(r[ci_unit])
        if typ == "other": continue
        model = map_model(r[ci_model])
        agg = bill.setdefault((mon, model), {"input":0.0,"output":0.0,"cache":0.0})
        agg[typ] += float(r[ci_usage] or 0)
    wb.close()

# ---------- 2) 我们库里 6/7/8 月 UCloud 逐模型量 ----------
SQL = """
SELECT to_char(date_add(hour, 8, timestamp), 'YYYY-MM') AS ym,
       actualresourceid AS model,
       SUM(inputusage) AS inp,
       SUM(outputusage) AS outp
FROM immdata.token_used_aw
WHERE recordtype = 'capture'
  AND providername = 'UCloud'
  AND timestamp >= '2026-06-01 00:00:00'::TIMESTAMP
  AND timestamp <  '2026-09-01 00:00:00'::TIMESTAMP
GROUP BY ym, model
"""
cols, rows = query(SQL)
db = {}
for r in rows:
    ym, model, inp, outp = r[0], r[1], float(r[2] or 0), float(r[3] or 0)
    month = int(ym.split("-")[1])
    db[(month, model)] = {"input": inp, "output": outp}

# ---------- 3) 输出对比表 ----------
print("="*100)
print("逐模型 output/input 比例对比（比例=output÷input，越低说明 output 占比越小）")
print("="*100)
models_order = ["gpt-5-mini","gpt-5.4","gpt-5.6-terra","gpt-5.6-luna","kimi-k2.5","kimi-k2.6","qwen3.5-plus","gpt-6"]
for mon in [6,7,8]:
    print(f"\n##### {mon}月（账单窗 20260{mon}01~20260{mon+1 if mon<8 else 9}01）#####")
    print(f"{'模型':16s} | {'账单 in(B)':>11s} {'账单 out(B)':>11s} {'账单比例':>9s} || {'库内 in(B)':>11s} {'库内 out(B)':>11s} {'库内比例':>9s} | 比例差(账单-库)")
    for model in models_order:
        b = bill.get((mon,model)); d = db.get((mon,model))
        if not b and not d: continue
        bi = b['input']/1e9 if b else 0; bo = b['output']/1e9 if b else 0
        di = d['input']/1e9 if d else 0; do = d['output']/1e9 if d else 0
        br = (bo/bi) if bi else float('nan')
        dr = (do/di) if di else float('nan')
        diff = (br-dr) if (bi and di) else float('nan')
        bs = f"{br:.3f}" if bi else "  -  "
        ds = f"{dr:.3f}" if di else "  -  "
        dfs = f"{diff:+.3f}" if (bi and di) else "  -  "
        print(f"{model:16s} | {bi:11.3f} {bo:11.3f} {bs:>9s} || {di:11.3f} {do:11.3f} {ds:>9s} | {dfs}")

# ---------- 4) 同代模型横向比例（关键归因） ----------
print("\n" + "="*100)
print("关键归因：同一张账单/同一个库内，luna 与同代模型(terra/mini)的比例是否一致？")
print("="*100)
for mon in [6,7,8]:
    b_luna = bill.get((mon,"gpt-5.6-luna")); b_terra = bill.get((mon,"gpt-5.6-terra")); b_mini = bill.get((mon,"gpt-5-mini"))
    d_luna = db.get((mon,"gpt-5.6-luna")); d_terra = db.get((mon,"gpt-5.6-terra")); d_mini = db.get((mon,"gpt-5-mini"))
    def r(x):
        return (x['output']/x['input']) if x and x['input'] else None
    def f(x):
        return f"{x:.3f}" if x is not None else "  -  "
    print(f"\n{mon}月:")
    if (b_luna or b_terra or b_mini):
        print(f"  供应商账单  比例: luna={f(r(b_luna))}  terra={f(r(b_terra))}  mini={f(r(b_mini))}")
    if (d_luna or d_terra or d_mini):
        print(f"  我们库内    比例: luna={f(r(d_luna))}  terra={f(r(d_terra))}  mini={f(r(d_mini))}")
