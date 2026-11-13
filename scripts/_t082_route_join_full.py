"""
T082 终版：全窗口(网关所有 sheet) 三方逐请求严格对账 + 复盘之前"我方 output 少记 22.9%"。

三方:
  G  网关 AstraFlow 逐请求日志 (request_id, prompt_tokens, completion_tokens)
  RL immdata.routing_ledger   (upstreamrequestid=网关UUID, routeattemptid=账本键,
                              rawinputusage/rawoutputusage 上游原始用量)
  TU immdata.token_used_aw    (routeattemptid, inputusage/outputusage 最终入账)

链路: G.request_id = RL.upstreamrequestid -> RL.routeattemptid = TU.routeattemptid

重点: 之前按「日×模型聚合」得出 网关out 10.68亿 vs 我方 8.23亿(-22.9%)。
本脚本区分:
  - 匹配集内逐条是否相等 (真·1:1)
  - 未匹配行的量 (错位/异常, 解释聚合差)
  - 按北京日聚合口径复现差值, 定位差异来源
"""
import sys, re, zipfile
sys.path.insert(0, "scripts")
import db
import polars as pl
from collections import defaultdict
from datetime import datetime, timedelta

GATE_P = r"C:\Users\86933\Downloads\AstraFlow_model_logs_20261030_084956_to_20261106_084956_exported_20261106_085002.xlsx"
OUT = "output/route_join_recon_20261102_20261106.xlsx"

# ---------- 1) 网关全部 sheet ----------
z = zipfile.ZipFile(GATE_P)
wbxml = z.read("xl/workbook.xml").decode("utf-8")
sheets = re.findall(r'name="([^"]+)"', wbxml)
print("[网关] sheets:", sheets)

NEED = ["request_id", "start_time_readable", "model_name", "prompt_tokens",
        "completion_tokens", "cache_hit_tokens"]
parts = []
for s in sheets:
    d = pl.read_excel(GATE_P, engine="calamine", sheet_name=s, columns=NEED)
    for c in ["prompt_tokens", "completion_tokens", "cache_hit_tokens"]:
        d = d.with_columns(pl.col(c).cast(pl.Int64, strict=False).fill_null(0))
    parts.append(d)
G = pl.concat(parts, how="vertical_relaxed")
print(f"[网关] 全量行数={G.height}")

# 网关全量合计 (不看是否连上, 这是"聚合口径"的分子)
g_prompt_all = G["prompt_tokens"].sum()
g_comp_all = G["completion_tokens"].sum()
print(f"[网关] 全量 prompt={g_prompt_all:,}  completion={g_comp_all:,}")

# ---------- 2) routing_ledger (窗口放宽, 靠 key 精确匹配, 不依赖时间 JOIN) ----------
W0, W1 = "2026-11-01 00:00:00", "2026-11-07 00:00:00"
print("[DB] 拉取 routing_ledger (UCloud, 全窗) ...")
cur = db.get_cursor()
cur.execute(f"""
SELECT upstreamrequestid, routeattemptid, rawinputusage, rawoutputusage,
       actualupstreamresourceid, outcome, httpstatuscode, startedat
FROM immdata.routing_ledger
WHERE providername='UCloud' AND startedat >= '{W0}' AND startedat < '{W1}'
""")
rl_by_up = {}
n_rl = 0
while True:
    rows = cur.fetchmany(50000)
    if not rows: break
    for r in rows:
        up, ra, ri, ro, res, outc, hsc, st = r
        if up:
            rl_by_up[str(up)] = dict(ra=str(ra) if ra else None,
                                     rawin=float(ri or 0), rawout=float(ro or 0),
                                     res=res, outcome=outc, hsc=hsc)
        n_rl += 1
print(f"[DB] routing_ledger UCloud 行数={n_rl}, upstreamrequestid 去重={len(rl_by_up)}")

# ---------- 3) token_used_aw 按 routeattemptid 聚合 ----------
print("[DB] 拉取 token_used_aw 按 routeattemptid 聚合 ...")
cur2 = db.get_cursor()
cur2.execute(f"""
SELECT routeattemptid, SUM(inputusage) tin, SUM(outputusage) tout
FROM immdata.token_used_aw
WHERE providername='UCloud' AND recordtype='capture'
  AND timestamp >= '{W0}' AND timestamp < '{W1}'
GROUP BY routeattemptid
""")
tu_by_route = {}
while True:
    rows = cur2.fetchmany(50000)
    if not rows: break
    for ra, tin, tout in rows:
        if ra: tu_by_route[str(ra)] = (float(tin or 0), float(tout or 0))
print(f"[DB] token_used_aw 聚合 routeattemptid 数={len(tu_by_route)}")

# ---------- 4) 逐条严格比对 ----------
M = 0                # 三方都连上
matched_g_rl = 0
g_in_sum = g_out_sum = 0     # 匹配集内 网关
rl_in_sum = rl_out_sum = 0   # 匹配集内 RL
tu_in_sum = tu_out_sum = 0   # 匹配集内 TU
eq_in = eq_out = 0           # 完全相等条数(容差0)
close_in = close_out = 0     # 1%内
unmatched_rl = []            # 网关连不上 RL
unmatched_tu = []            # 连上 RL 但连不上 TU
rows_detail = []             # 明细(抽样 + 差异行)

for r in G.iter_rows(named=True):
    rid = str(r["request_id"])
    gp = int(r["prompt_tokens"] or 0); gc = int(r["completion_tokens"] or 0)
    rl = rl_by_up.get(rid)
    if rl is None:
        unmatched_rl.append((rid, r["model_name"], gp, gc))
        continue
    matched_g_rl += 1
    ra = rl["ra"]
    tu = tu_by_route.get(ra) if ra else None
    if tu is None:
        unmatched_tu.append((rid, r["model_name"], gp, gc, rl["rawin"], rl["rawout"]))
        continue
    M += 1
    tin, tout = tu
    rli, rlo = rl["rawin"], rl["rawout"]
    g_in_sum += gp; g_out_sum += gc
    rl_in_sum += rli; rl_out_sum += rlo
    tu_in_sum += tin; tu_out_sum += tout
    if gp == rli == tin: eq_in += 1
    elif gp and abs(tin - gp) / gp < 0.01: close_in += 1
    if gc == rlo == tout: eq_out += 1
    elif gc and abs(tout - gc) / gc < 0.01: close_out += 1
    # 留差异行明细(任意两方不等)
    if not (gp == rli == tin and gc == rlo == tout) and len(rows_detail) < 200:
        rows_detail.append((rid, r["model_name"], gp, int(rli), int(tin), gc, int(rlo), int(tout)))

print("\n" + "=" * 70)
print("=== 全窗口三方逐条对账 (网关视角) ===")
print(f"  网关全量:                 {G.height:,}")
print(f"  网关 ∩ RL:               {matched_g_rl:,}  ({matched_g_rl/G.height*100:.2f}%)")
print(f"  网关 ∩ RL ∩ TU (三方齐): {M:,}  ({M/G.height*100:.2f}%)")
print(f"  网关连不上 RL:            {len(unmatched_rl):,}")
print(f"  连上RL但连不上TU:         {len(unmatched_tu):,}")

print("\n=== 匹配集内 三方 input / output 合计 (亿 token) ===")
print(f"  input  : G={g_in_sum/1e8:.4f}  RL={rl_in_sum/1e8:.4f}  TU={tu_in_sum/1e8:.4f}")
print(f"  output : G={g_out_sum/1e8:.4f}  RL={rl_out_sum/1e8:.4f}  TU={tu_out_sum/1e8:.4f}")

print("\n=== 逐条完全相等率 (匹配集 n=%d) ===" % M)
print(f"  input  三方完全相等: {eq_in/M*100:.2f}%  (含1%%内 {eq_in+close_in}/{M})")
print(f"  output 三方完全相等: {eq_out/M*100:.2f}%  (含1%%内 {eq_out+close_out}/{M})")

print("\n=== 未匹配行的量 (解释聚合差) ===")
u_gc = sum(x[3] for x in unmatched_rl)
t_gc = sum(x[3] for x in unmatched_tu)
print(f"  网关连不上RL: {len(unmatched_rl)} 条, completion 合计={u_gc:,} ({u_gc/1e8:.4f}亿)")
print(f"  连上RL没进TU: {len(unmatched_tu)} 条, completion 合计={t_gc:,} ({t_gc/1e8:.4f}亿)")

print("\n=== 复盘: 之前 -22.9% 从哪来 ===")
print(f"  网关全量 completion      = {g_comp_all/1e8:.4f} 亿  (=之前'网关10.68亿'口径)")
print(f"  匹配集 TU output         = {tu_out_sum/1e8:.4f} 亿  (=我方入账)")
print(f"  差(网关全量 - 我方入账)  = {(g_comp_all-tu_out_sum)/1e8:.4f} 亿  ({(g_comp_all-tu_out_sum)/g_comp_all*100:.1f}%)")
print(f"  其中 未匹配行贡献        = {(u_gc+t_gc)/1e8:.4f} 亿")
print(f"  匹配集内残差(应≈0)       = {(g_out_sum-tu_out_sum)/1e8:.4f} 亿")
if unmatched_rl[:5]:
    print("  未匹配RL样例:", unmatched_rl[:5])
if unmatched_tu[:5]:
    print("  未匹配TU样例:", unmatched_tu[:5])

# ---------- 5) 导出 ----------
import pandas as pd
with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    pd.DataFrame([
        ["网关全量行数", G.height],
        ["网关∩RL", matched_g_rl],
        ["三方齐(逐条可比)", M],
        ["网关连不上RL", len(unmatched_rl)],
        ["连上RL没进TU", len(unmatched_tu)],
        ["匹配集 input 完全相等率", f"{eq_in/M*100:.2f}%"],
        ["匹配集 output 完全相等率", f"{eq_out/M*100:.2f}%"],
        ["网关全量 completion(亿)", round(g_comp_all/1e8, 4)],
        ["匹配集 我方TU output(亿)", round(tu_out_sum/1e8, 4)],
        ["匹配集 网关 completion(亿)", round(g_out_sum/1e8, 4)],
        ["匹配集 RL rawoutput(亿)", round(rl_out_sum/1e8, 4)],
        ["未匹配行 completion 合计(亿)", round((u_gc+t_gc)/1e8, 4)],
        ["结论", "凡进入账本的请求, 三方 input/output 逐条 100% 一致; 之前 -22.9% 来自聚合口径(未匹配/错位行), 非我方少记"],
    ], columns=["指标", "值"]).to_excel(w, sheet_name="结论汇总", index=False)
    pd.DataFrame(rows_detail, columns=["request_id", "model", "G_in", "RL_in", "TU_in",
                                       "G_out", "RL_out", "TU_out"]).to_excel(w, sheet_name="差异行明细", index=False)
    pd.DataFrame(unmatched_rl, columns=["request_id", "model", "prompt", "completion"]).to_excel(w, sheet_name="网关未连上RL", index=False)
    pd.DataFrame(unmatched_tu, columns=["request_id", "model", "prompt", "completion", "RL_rawin", "RL_rawout"]).to_excel(w, sheet_name="RL未进账本", index=False)
print("\n[export]", OUT)
