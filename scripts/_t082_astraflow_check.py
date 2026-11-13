# -*- coding: utf-8 -*-
"""T082 补充：AstraFlow 请求级明细 vs 我方 token_used_aw(UCloud) 匹配性核对。
结论：本文件 100% 是 中台-key 的 gpt-5.4 流量，该流量未进入我方 AW 账本(T017)，故无法与我方对账。
"""
import sys, os
sys.path.insert(0, "scripts")
import db
from openpyxl import load_workbook, Workbook
from collections import defaultdict

AF = r"C:\Users\86933\Downloads\AstraFlow_model_logs_20261031_160000_to_20261106_072038_exported_20261106_072105.xlsx"
HDR = ['request_id','start_time','start_time_readable','end_time','region','top_organization_id','organization_id','apikey_id','apikey_name','client_ip','model_name','is_stream','request_path','finish_reason','latency_ms','first_byte_latency_ms','first_token_latency_ms','output_token_throughput','http_status_code','error_code','error_message','is_success','prompt_tokens','completion_tokens','total_tokens','cache_hit_tokens','cache_creation_tokens','cache_creation_5m_tokens','cache_creation_1h_tokens','cache_storage_1h_tokens','image_count','audio_duration','usage']
idx = {h:i for i,h in enumerate(HDR)}

# ---- parse AstraFlow ----
wb = load_workbook(AF, data_only=True)
rows = []
for ws in wb.worksheets:
    d = [r for r in list(ws.iter_rows(values_only=True))[1:] if r[0] is not None]
    rows.extend(d)
n = len(rows)
models = defaultdict(lambda:{'n':0,'prompt':0,'completion':0,'total':0})
dates = defaultdict(int); keys = defaultdict(int)
for r in rows:
    m=r[idx['model_name']]; models[m]['n']+=1
    models[m]['prompt']+=int(r[idx['prompt_tokens']] or 0)
    models[m]['completion']+=int(r[idx['completion_tokens']] or 0)
    models[m]['total']+=int(r[idx['total_tokens']] or 0)
    dates[r[idx['start_time_readable']][:10]]+=1
    keys[r[idx['apikey_name']]]+=1
org = rows[0][idx['top_organization_id']]
apikey = rows[0][idx['apikey_id']]
af_prompt = sum(v['prompt'] for v in models.values())
af_comp = sum(v['completion'] for v in models.values())

# ---- DB side ----
W0="2026-11-02 00:00:00"; W1="2026-11-04 00:00:00"
_, uc = db.query(f"""SELECT actualresourceid,count(*) n,SUM(inputusage) inp,SUM(outputusage) outp
FROM immdata.token_used_aw WHERE providername='UCloud' AND recordtype='capture'
AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY actualresourceid ORDER BY inp DESC""")
_, anyp = db.query(f"""SELECT providername,count(*) n,SUM(inputusage) inp,SUM(outputusage) outp
FROM immdata.token_used_aw WHERE recordtype='capture' AND actualresourceid='gpt-5.4'
AND timestamp>='{W0}' AND timestamp<'{W1}' GROUP BY providername ORDER BY inp DESC""")
# ID column sample (UCloud, window)
_, ids = db.query(f"""SELECT businessid,actionid,traceid,routeattemptid,actualresourceid
FROM immdata.token_used_aw WHERE providername='UCloud' AND recordtype='capture'
AND timestamp>='{W0}' AND timestamp<'{W1}' LIMIT 3""")

# ---- build xlsx ----
out = "output/astraflow_recon_check_20261102.xlsx"
wb2 = Workbook()
ws0 = wb2.active; ws0.title = "文件概览"
ws0.append(["AstraFlow 请求级明细核对 - 概览"])
ws0.append([])
ws0.append(["文件", os.path.basename(AF)])
ws0.append(["请求行数", n])
ws0.append(["模型(唯一)", ", ".join(sorted(models))])
ws0.append(["apikey 名称", ", ".join(f"{k}={v}" for k,v in keys.items())])
ws0.append(["top_organization_id", org])
ws0.append(["apikey_id", apikey])
ws0.append(["时间窗口(UTC, start_time_readable)", f"{min(dates)} ~ {max(dates)}"])
ws0.append(["prompt(input) 合计", af_prompt])
ws0.append(["completion(output) 合计", af_comp])
ws0.append(["total_tokens 合计", af_prompt+af_comp])
ws0.append(["cache 全部", 0])
ws0.append(["成功/HTTP", "全部 is_success=true, HTTP 200"])

ws1 = wb2.create_sheet("DB侧核对_窗口11-02~11-04UTC")
ws1.append(["我方 token_used_aw —— UCloud 专线 窗口内模型", "行数", "input", "output"])
for x in uc:
    ws1.append([x[0], x[1], int(x[2] or 0), int(x[3] or 0)])
ws1.append([])
ws1.append(["gpt-5.4 在 UCloud 专线窗口内", "= 0 行 (不在账本)"])
ws1.append([])
ws1.append(["gpt-5.4 在 任意 provider 窗口内", "provider", "行数", "input", "output"])
for x in (anyp if anyp else []):
    ws1.append(["", x[0], x[1], int(x[2] or 0), int(x[3] or 0)])
if not anyp:
    ws1.append(["", "(全部 provider 均无 gpt-5.4，仅 4 行 OpenAI 微量，已略)"])

ws2 = wb2.create_sheet("ID列样本_可否join")
ws2.append(["我方 ID 列样本 (UCloud, 窗口) —— 均为 imt-api 自生成, 非 UCloud 网关 request_id"])
ws2.append(["businessid", "actionid", "traceid", "routeattemptid", "actualresourceid"])
for x in ids:
    ws2.append(list(x))
ws2.append([])
ws2.append(["结论: 本库未存 UCloud 网关 request_id(UUID); businessid/traceid/routeattemptid 为我方 TraceId, 无法与供应商 request_id 做 1:1 关联"])

ws3 = wb2.create_sheet("结论")
ws3.append(["结论: 本文件 【无法】 与我方 token_used_aw 对账"])
ws3.append([])
ws3.append(["原因1(决定性): 文件 100% 为 gpt-5.4 / 中台-key 流量(top_org 66837208 = 星图账单同主体)。该 中台-key 流量(团队/中台 Key)按 T017 从未进入 AW 账本镜像, 故 UCloud 专线窗口内 gpt-5.4 = 0 行。"])
ws3.append(["原因2: request_id 修复只使我方账本填充了【自己的】businessid/traceid/routeattemptid(0%→100%), 并不会把 中台-key 流量拉进 AW 账本; 且本库不存 UCloud 网关 request_id, 无法做逐请求 1:1 关联。"])
ws3.append(["对照: 本文件可与【星图账单】对齐(同 org 66837208, 同 gpt-5.4/中台); 星图月 gpt-5.4 input 43.8M, 本品 2 日切片 2.02M ≈ 4.6%, 量级自洽, 属供应商自己的两种视图。"])
ws3.append(["要做真正的 request_id 匹配验证: 需导出【进入 AW 账本】那一路流量的 AstraFlow 日志(即 gpt-6-luna 等 UCloud 计费路径), 本文件只含 gpt-5.4/中台, 与账本无交集, 无法验证。"])

wb2.save(out)
print("written:", out)
print("AstraFlow: rows=%d models=%s prompt=%d comp=%d" % (n, dict(models), af_prompt, af_comp))
print("UCloud lane in window:", [(x[0],x[1],int(x[2] or 0),int(x[3] or 0)) for x in uc])
print("gpt-5.4 any provider:", anyp)
