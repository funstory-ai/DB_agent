"""
T082 续：用 immdata.routing_ledger 当桥，做 网关(request_id) <-> token_used_aw 的
逐请求(行级) 1:1 对账。routing_ledger 同时持有 upstreamrequestid(网关UUID) 和
routeattemptid(token_used_aw 的键)，是唯一的桥接表。

链路:
  gateway.request_id  =  routing_ledger.upstreamrequestid
                      -> routing_ledger.routeattemptid
                      =  token_used_aw.routeattemptid

重点比较三方的 token:
  网关 prompt/completion  (UCloud 自家日志)
  routing_ledger.rawinputusage/rawoutputusage  (我们路由器抓到的上游原始用量)
  token_used_aw.inputusage/outputusage          (我们最终入账/计费)
"""
import sys, json
sys.path.insert(0, "scripts")
import db
import polars as pl
from collections import defaultdict

W0 = "2026-11-02 00:00:00"   # UTC 窗口，与网关 UTC_2026-11-02 sheet 对齐
W1 = "2026-11-03 00:00:00"
GATE_P = r"C:\Users\86933\Downloads\AstraFlow_model_logs_20261030_084956_to_20261106_084956_exported_20261106_085002.xlsx"
SHEET = "UTC_2026-11-02"

# 1) 网关: request_id -> (prompt, completion, model, cache_hit)
g = pl.read_excel(GATE_P, engine="calamine", sheet_name=SHEET,
                  columns=["request_id","model_name","prompt_tokens","completion_tokens","cache_hit_tokens"])
gw = {}
for r in g.iter_rows(named=True):
    rid = str(r["request_id"])
    gw[rid] = (int(r["prompt_tokens"] or 0), int(r["completion_tokens"] or 0),
               str(r["model_name"]), int(r["cache_hit_tokens"] or 0))
print(f"[网关] {SHEET}: {len(gw)} 条 request_id")

# 2) routing_ledger (UCloud, 窗口): upstreamrequestid -> 记录
print("[DB] 拉取 routing_ledger (UCloud) ...")
cur = db.get_cursor()
cur.execute(f"""
SELECT upstreamrequestid, routeattemptid, rawinputusage, rawoutputusage,
       actualupstreamresourceid, rawusagejson, outcome, httpstatuscode
FROM immdata.routing_ledger
WHERE providername='UCloud'
  AND startedat >= '{W0}' AND startedat < '{W1}'
""")
rl_by_up = {}
rl_by_route = {}
n_rl = 0
while True:
    rows = cur.fetchmany(50000)
    if not rows: break
    for r in rows:
        up, ra, ri, ro, res, rawjson, outc, hsc = r
        rec = dict(ra=str(ra) if ra else None, rawin=ri or 0, rawout=ro or 0, res=res,
                   rawjson=rawjson, outcome=outc, hsc=hsc)
        if up: rl_by_up[str(up)] = rec
        if ra: rl_by_route[str(ra)] = rec
        n_rl += 1
print(f"[DB] routing_ledger UCloud 行数={n_rl}, upstreamrequestid 去重={len(rl_by_up)}, routeattemptid 去重={len(rl_by_route)}")

# 3) token_used_aw 按 routeattemptid 聚合 (UCloud, 窗口)
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
n_tu = 0
while True:
    rows = cur2.fetchmany(50000)
    if not rows: break
    for ra, tin, tout in rows:
        if ra: tu_by_route[str(ra)] = (float(tin or 0), float(tout or 0))
        n_tu += 1
print(f"[DB] token_used_aw 聚合 routeattemptid 数={len(tu_by_route)} (原始行 {n_tu})")

# 4) 三方行级比对
matched_gw_rl = 0      # 网关 request_id 能在 rl 找到
matched_gw_tu = 0      # 进而能在 tu 找到
n_comp = 0
sum_g_c = 0; sum_rl_o = 0; sum_tu_o = 0   # completion/output 三方合计
# 差异分布
diff_g_vs_tu = []      # (gateway completion - TU output) 仅 output 维度, 用比例
diff_rl_vs_tu = []     # RL rawoutput vs TU output
under_records = []     # TU output 明显低于网关 completion 的样例
for rid, (gp, gc, model, ch) in gw.items():
    rl = rl_by_up.get(rid)
    if rl is None:
        continue
    matched_gw_rl += 1
    ra = rl.get("ra")
    if ra is None:
        continue
    tu = tu_by_route.get(ra)
    if tu is None:
        continue
    matched_gw_tu += 1
    tin, tout = tu
    rlo = rl["rawout"]
    n_comp += 1
    sum_g_c += gc; sum_rl_o += rlo; sum_tu_o += tout
    if gc > 0:
        diff_g_vs_tu.append(tout / gc)
        diff_rl_vs_tu.append(tout / rlo if rlo > 0 else None)
        if tout < gc * 0.9 and len(under_records) < 12:
            under_records.append((rid, model, gp, gc, int(rlo), int(tout)))

print("\n=== 链接率 (网关侧视角, 11-02) ===")
print(f"  网关总行数:                 {len(gw)}")
print(f"  网关∩routing_ledger:        {matched_gw_rl}  ({matched_gw_rl/len(gw)*100:.2f}%)")
print(f"  网关∩routing∩token_used_aw: {matched_gw_tu}  ({matched_gw_tu/len(gw)*100:.2f}%)")

print("\n=== 三方 output(completion) 汇总对比 (亿 token) ===")
print(f"  网关 completion:  {sum_g_c/1e8:.4f}")
print(f"  RL rawoutput:     {sum_rl_o/1e8:.4f}")
print(f"  TU outputusage:   {sum_tu_o/1e8:.4f}")
print(f"  TU / 网关 = {sum_tu_o/sum_g_c*100:.1f}%    TU / RL = {sum_tu_o/sum_rl_o*100:.1f}%")

# 比例分布
import statistics
gv = [x for x in diff_g_vs_tu if x is not None]
rv = [x for x in diff_rl_vs_tu if x is not None]
print(f"\n=== 逐请求 TU.output / 网关.completion 比例分布 (n={len(gv)}) ===")
print(f"  中位数={statistics.median(gv)*100:.1f}%  mean={statistics.mean(gv)*100:.1f}%  p10={sorted(gv)[len(gv)//10]*100:.1f}%  p90={sorted(gv)[int(len(gv)*0.9)]*100:.1f}%")
print(f"  完全相等(0.99~1.01)占比 = {sum(1 for x in gv if 0.99<=x<=1.01)/len(gv)*100:.1f}%")
print(f"  <0.9 (我方明显少记) 占比 = {sum(1 for x in gv if x<0.9)/len(gv)*100:.1f}%")
print(f"  >1.1 (我方多记)       占比 = {sum(1 for x in gv if x>1.1)/len(gv)*100:.1f}%")

rv2=[x for x in rv if x is not None]
print(f"\n=== 逐请求 TU.output / RL.rawoutput 比例分布 (n={len(rv2)}) ===")
print(f"  中位数={statistics.median(rv2)*100:.1f}%  p10={sorted(rv2)[len(rv2)//10]*100:.1f}%  p90={sorted(rv2)[int(len(rv2)*0.9)]*100:.1f}%")

print("\n=== 我方 output 明显低于网关 completion 的样例 (前12) ===")
print(f"  {'request_id':38s} {'model':16s} {'gw_p':>8s} {'gw_c':>8s} {'RL_o':>8s} {'TU_o':>8s}")
for rid, model, gp, gc, rlo, tout in under_records:
    print(f"  {rid:38s} {model:16s} {gp:8d} {gc:8d} {rlo:8d} {tout:8d}")
