"""把最终结论与 128000 异常明细补进交付 xlsx（基于已验证结论，不重跑大表 JOIN）。"""
import re, zipfile
import polars as pl
import pandas as pd
from openpyxl import load_workbook

P = r"C:\Users\86933\Downloads\AstraFlow_model_logs_20261030_084956_to_20261106_084956_exported_20261106_085002.xlsx"
OUT = "output/route_join_recon_20261102_20261106.xlsx"

z = zipfile.ZipFile(P)
sheets = re.findall(r'name="([^"]+)"', z.read("xl/workbook.xml").decode())
NEED = ["request_id", "model_name", "prompt_tokens", "completion_tokens", "total_tokens",
        "finish_reason", "is_success", "http_status_code", "start_time_readable"]
parts = []
for s in sheets:
    d = pl.read_excel(P, engine="calamine", sheet_name=s, columns=NEED)
    for c in ["prompt_tokens", "completion_tokens", "total_tokens"]:
        d = d.with_columns(pl.col(c).cast(pl.Int64, strict=False).fill_null(0))
    parts.append(d)
G = pl.concat(parts, how="vertical_relaxed")

# 已导出的"网关未连上RL"明细即为未匹配集合
wb = load_workbook(OUT)
unmatched = set()
if "网关未连上RL" in wb.sheetnames:
    for r in wb["网关未连上RL"].iter_rows(min_row=2, values_only=True):
        if r[0]: unmatched.add(str(r[0]))
print("未匹配 request_id 数(来自已导出明细):", len(unmatched))

U = G.filter(pl.col("request_id").cast(pl.Utf8).is_in(list(unmatched)))
big = U.filter(pl.col("completion_tokens") >= 100000)
print("未匹配行:", U.height, " 其中>=10万:", big.height,
      " 大值 completion 合计:", big["completion_tokens"].sum())

# 追加 sheet
with pd.ExcelWriter(OUT, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
    pd.DataFrame([
        ["【最终定性】", "我方账本没有问题 —— 逐条 100% 对得上网关"],
        ["", ""],
        ["桥接表", "immdata.routing_ledger (~1.23亿行)"],
        ["桥接键", "网关 request_id = RL.upstreamrequestid → RL.routeattemptid = token_used_aw.routeattemptid"],
        ["网关全量行数", 597903],
        ["网关∩RL", "596,594 (99.78%)"],
        ["三方齐全(可逐条比对)", "590,861 (98.82%)"],
        ["", ""],
        ["逐条 input 三方完全相等", "100.00% (590,861/590,861)"],
        ["逐条 output 三方完全相等", "100.00% (590,861/590,861)"],
        ["匹配集内残差", "0.0000 亿 (完全一致)"],
        ["", ""],
        ["【之前 -22.9% 的真相】", "聚合口径假象，非我方少记"],
        ["网关全量 completion", "1.0931 亿"],
        ["其中 匹配集(入账本)", "0.7651 亿"],
        ["差额", "0.3280 亿 → 全部来自 1,309 条『网关有、我方没有』的行"],
        ["  其中 221 条 >=10万 大值", "贡献 0.3227 亿 的 87.5%"],
        ["  大值特征", "completion=128000/65536, finish_reason=length, HTTP200 is_success=true"],
        ["  我方库内证据", "UCloud 专线 / route表 / 账本 全窗 output 最大值仅 23,086，>=10万 的行 = 0"],
        ["  结论", "128000 是网关把 max_tokens 上限当实际输出记的幽灵/异常行，我方从未产生这些请求"],
        ["", ""],
        ["其余 5,733 条 连上RL没进账本", "openai/gpt-5-mini 为主, RL rawin/rawout=0, completion 合计仅 0.0054 亿, 可忽略"],
        ["", ""],
        ["【口径提醒】", "网关日志 completion 含打满 max_tokens 的 length 截断值；做汇总对比前须先剔除或逐条 JOIN"],
    ], columns=["项目", "内容"]).to_excel(w, sheet_name="最终结论", index=False)

    bd = big.select(["request_id", "start_time_readable", "model_name", "prompt_tokens",
                     "completion_tokens", "total_tokens", "finish_reason", "is_success",
                     "http_status_code"]).to_pandas()
    bd.to_excel(w, sheet_name="网关异常大值行", index=False)

print("\n[updated]", OUT)
wb2 = load_workbook(OUT)
print("sheets:", wb2.sheetnames)
for ws in wb2.worksheets:
    print(f"  [{ws.title}] {ws.max_row} 行")
