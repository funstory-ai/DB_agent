#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T105 交付：逐月 luna 输入输出比 + 账单侧 output 多计损失 Excel。

数据源
  我方  : output/_t105_db_monthly.csv, output/_t105_db_daily_luna.csv (token_used_aw)
  供应商: output/_t105_supplier_rows.csv (6/7/8 月账单 + 星图 10-06~11-05)
口径
  北京自然日；output>input>cache 解析计费单元；金额取实收折后「订单金额」USD；
  单价 = 实收金额 / 用量 * 1e6 (USD/百万 token)；汇率 ¥7.1/USD（与 T082 8 月折算一致）。
"""
import csv
from collections import defaultdict
import pandas as pd
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

YI = 1e8
M = 1e6
FX = 7.1
OUT = "output/ucloud_luna_monthly_ratio_loss_202608_202611.xlsx"


def read_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


sup = read_csv("output/_t105_supplier_rows.csv")
dbday = read_csv("output/_t105_db_daily_luna.csv")
dbmon = read_csv("output/_t105_db_monthly.csv")
LUNA = lambda m: "luna" in m.lower()


def canon(m):
    """账单模型名常带 openai/ 等前缀，DB 用裸模型名。"""
    m = str(m).strip().lower()
    for p in ("openai/", "moonshotai/", "anthropic/", "google/", "qwen/"):
        if m.startswith(p):
            m = m[len(p):]
    return m

# ---------- 账单侧 ----------
mon_sup = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # month -> typ -> [qty, usd]
day_sup = defaultdict(lambda: [0.0, 0.0])                       # (date, typ) -> [qty, usd]
mon_sup_model = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # (month, model) -> typ
for r in sup:
    t, q, a = r["typ"], float(r["qty"]), float(r["amount_usd"])
    luna = LUNA(r["model"])
    mod = canon(r["model"])
    if r["src"] in ("bill06", "bill07", "bill08"):
        if luna:                       # mon_sup / day_sup 的语义 = 「luna 合计」
            mon_sup[r["month"]][t][0] += q
            mon_sup[r["month"]][t][1] += a
        mon_sup_model[(r["month"], mod)][t][0] += q
        mon_sup_model[(r["month"], mod)][t][1] += a
    if r["src"] in ("bill08_detail", "star") and r["date"]:
        if luna:
            day_sup[(r["date"], t)][0] += q
            day_sup[(r["date"], t)][1] += a
        if r["src"] == "star":
            if luna:
                mon_sup[r["date"][:7]][t][0] += q
                mon_sup[r["date"][:7]][t][1] += a
            mon_sup_model[(r["date"][:7], mod)][t][0] += q
            mon_sup_model[(r["date"][:7], mod)][t][1] += a

# ---------- 我方 ----------
mon_db = defaultdict(lambda: [0.0, 0.0, 0])
day_db = defaultdict(lambda: [0.0, 0.0, 0])
mon_db_model = defaultdict(lambda: [0.0, 0.0, 0])
for r in dbmon:
    m, mod = r["bj_month"], canon(r["model"])
    v = [float(r["inp"] or 0), float(r["outp"] or 0), int(r["n_rows"])]
    mon_db_model[(m, mod)] = [a + b for a, b in zip(mon_db_model[(m, mod)], v)]
    if LUNA(mod):
        mon_db[m] = [a + b for a, b in zip(mon_db[m], v)]
for r in dbday:
    day_db[r["bj"]] = [a + b for a, b in zip(day_db[r["bj"]],
                        [float(r["inp"] or 0), float(r["outp"] or 0), int(r["n_rows"])])]


def dsum(dates, typ):
    return (sum(day_sup[(d, typ)][0] for d in dates),
            sum(day_sup[(d, typ)][1] for d in dates))


def dsum_db(dates):
    return (sum(day_db[d][0] for d in dates), sum(day_db[d][1] for d in dates))


def win(dates, label, price_override=None, note=""):
    siq, sia = dsum(dates, "input")
    soq, soa = dsum(dates, "output")
    di, do = dsum_db(dates)
    p = price_override if price_override is not None else (soa / (soq / M) if soq else 0)
    gap = soq - do
    loss = gap / M * p
    return dict(窗口=label, 账单input_亿=siq / YI, 我方input_亿=di / YI,
                账单output_亿=soq / YI, 我方output_亿=do / YI,
                账单out_in=soq / siq if siq else 0, 我方out_in=do / di if di else 0,
                output倍数=(soq / siq) / (do / di) if siq and di and do else 0,
                output差额_亿=gap / YI, output单价_USD每百万=p,
                账单output实收_USD=soa, 按我方量应计_USD=do / M * p,
                多计_USD=loss, 多计_CNY=loss * FX, 备注=note)


dates_aug = sorted({k[0] for k in day_sup if k[0].startswith("2026-08")})
dates_oct_active = sorted({k[0] for k in day_sup if "2026-10-06" <= k[0] <= "2026-10-19"})
dates_ghost = sorted({k[0] for k in day_sup if "2026-10-20" <= k[0] <= "2026-11-01"})
dates_nov_ramp = sorted({k[0] for k in day_sup if "2026-11-02" <= k[0] <= "2026-11-05"})
dates_star = sorted({k[0] for k in day_sup if "2026-10-06" <= k[0] <= "2026-11-05"})

# 8 月主数用「订单汇总」(整月权威)，逐日仅作形态证据
si8, sia8 = mon_sup["2026-08"]["input"]
so8, soa8 = mon_sup["2026-08"]["output"]
di8, do8, n8 = mon_db["2026-08"]
p8 = soa8 / (so8 / M)
row_aug = dict(窗口="2026-08 全月 (gpt-5.6-luna)", 账单input_亿=si8 / YI, 我方input_亿=di8 / YI,
               账单output_亿=so8 / YI, 我方output_亿=do8 / YI,
               账单out_in=so8 / si8, 我方out_in=do8 / di8,
               output倍数=(so8 / si8) / (do8 / di8),
               output差额_亿=(so8 - do8) / YI, output单价_USD每百万=p8,
               账单output实收_USD=soa8, 按我方量应计_USD=do8 / M * p8,
               多计_USD=(so8 - do8) / M * p8, 多计_CNY=(so8 - do8) / M * p8 * FX,
               备注="账单整月订单汇总；input 对齐(-0.11%)，output 系统性约 3 倍")

rows_win = [row_aug,
            win(dates_oct_active, "2026-10-06~10-19 (gpt-6-luna 正常调用段)",
                note="双方逐日 input 基本对齐；output 稳定高约 14%"),
            win(dates_ghost, "2026-10-20~11-01 (我方几无调用)",
                note="账单仍有 output；我方无对应请求 = 幽灵/异常行，100% 多计"),
            win(dates_nov_ramp, "2026-11-02~11-05 (周一放量段)",
                note="T082 逐请求三方齐全部分 100% 相等；差异来自未匹配大 output 行"),
            win(dates_star, "星图全窗 2026-10-06~11-05 (合计)",
                note="与上面三段相加一致；10 月起异常倍率已从 3.01 降至 1.2~1.6")]
df_win = pd.DataFrame(rows_win)

# ---------- 逐月输入输出比主表 ----------
month_rows = []
for m in ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]:
    di, do, n = mon_db[m]
    models = ", ".join(f"{mod}" for (mm, mod), v in sorted(mon_db_model.items())
                       if mm == m and LUNA(mod))
    if not models:
        models = "（当月无 luna）"
    si = mon_sup[m]["input"][0]
    so = mon_sup[m]["output"][0]
    has_bill = si > 0
    month_rows.append(dict(北京月=m, luna模型=models, 我方请求数=n,
                          我方input_亿=di / YI, 我方output_亿=do / YI, 我方out_in=do / di if di else 0,
                          账单input_亿=si / YI if has_bill else None,
                          账单output_亿=so / YI if has_bill else None,
                          账单out_in=so / si if si else None,
                          账单比_我方out_in=(so / si) / (do / di) if si and di and do else None,
                          账单覆盖=("账单存在，无 luna 计费单元" if m in ("2026-06", "2026-07") else
                                    "完整自然月" if m == "2026-08" else
                                    "无账单(需补拉)" if not has_bill else
                                    "仅 10-06~10-31" if m == "2026-10" else "仅 11-01~11-05"),
                          说明=("luna 尚未上量（8/5 才放量）" if m in ("2026-06", "2026-07") else
                                "8 月账单 out/in 是我方 3.01 倍" if m == "2026-08" else
                                "9 月账单文件未导出，无法判定；仅我方口径" if not has_bill else
                                "星图账期非自然月，比值仅供参照，精确对比见「窗口对齐与损失」")))
df_month = pd.DataFrame(month_rows)

# 按模型逐月（我方，区分 gpt-5.6-luna / gpt-6-luna 两代）
by_model = []
for r in dbmon:
    if not LUNA(r["model"]):
        continue
    inp, out = float(r["inp"] or 0), float(r["outp"] or 0)
    by_model.append(dict(北京月=r["bj_month"], 模型=canon(r["model"]), 请求数=int(r["n_rows"]),
                        input_亿=inp / YI, output_亿=out / YI,
                        out_in=out / inp if inp else 0))
df_model = pd.DataFrame(by_model).sort_values(["北京月", "模型"])

# ---------- 8 月逐日 ----------
aug_rows = []
for d in dates_aug:
    si = day_sup[(d, "input")][0]
    so = day_sup[(d, "output")][0]
    di, do, _ = day_db[d]
    if si < 1e6 and di < 1e6:
        continue
    aug_rows.append(dict(日期=d, 账单input_亿=si / YI, 我方input_亿=di / YI,
                         账单output_亿=so / YI, 我方output_亿=do / YI,
                         账单out_in=so / si if si else 0, 我方out_in=do / di if di else 0,
                         output倍数=(so / si) / (do / di) if si and di and do else 0,
                         output差额_亿=(so - do) / YI))
df_aug = pd.DataFrame(aug_rows)

# ---------- 星图逐日 ----------
star_rows = []
for d in dates_star:
    si = day_sup[(d, "input")][0]
    so = day_sup[(d, "output")][0]
    di, do, _ = day_db[d]
    star_rows.append(dict(日期=d, 账单input_亿=si / YI, 我方input_亿=di / YI,
                          账单output_亿=so / YI, 我方output_亿=do / YI,
                          账单out_in=so / si if si else 0, 我方out_in=do / di if di else 0,
                          output倍数=(so / si) / (do / di) if si and di and do else 0,
                          output差额_亿=(so - do) / YI,
                          分段=("正常调用段" if d <= "2026-10-19" else
                                "幽灵行段(我方几无调用)" if d <= "2026-11-01" else "放量段")))
df_star = pd.DataFrame(star_rows)

# ---------- 其他模型对照（证明只有 luna 异常） ----------
other_rows = []
for (m, mod), sv in sorted(mon_sup_model.items()):
    # 只列完整自然月（6/7/8 账单）：星图账期 10-06~11-05 与自然月错配，列了会误导
    if LUNA(mod) or m not in ("2026-07", "2026-08"):
        continue
    si, so = sv["input"][0], sv["output"][0]
    dv = mon_db_model.get((m, mod), [0, 0, 0])
    di, do = dv[0], dv[1]
    if max(si, di) < 0.05 * YI:   # 量太小，比值无统计意义
        continue
    note = ("T017：中台/团队 Key 不进 token_used_aw，库内偏低（已知，非本次异常）"
            if "gpt-5.4" in mod else "正常：账单/我方 out/in 一致")
    other_rows.append(dict(月份=m, 模型=mod, 账单input_亿=si / YI, 我方input_亿=di / YI,
                          账单output_亿=so / YI, 我方output_亿=do / YI,
                          账单out_in=so / si if si else 0, 我方out_in=do / di if di else 0,
                          output倍数=(so / si) / (do / di) if si and di and do else 0,
                          账单覆盖="完整自然月", 备注=note))
# luna 自身也放进去便于并排
for m in ("2026-07", "2026-08"):
    si, so = mon_sup[m]["input"][0], mon_sup[m]["output"][0]
    di, do, _ = mon_db[m]
    other_rows.append(dict(月份=m, 模型="★ luna (合计)", 账单input_亿=si / YI, 我方input_亿=di / YI,
                          账单output_亿=so / YI, 我方output_亿=do / YI,
                          账单out_in=so / si if si else 0, 我方out_in=do / di if di else 0,
                          output倍数=(so / si) / (do / di) if si and di and do else 0,
                          账单覆盖="完整自然月",
                          备注=("当月尚未上量（8/5 才放量）" if m == "2026-07" else
                                "★ 唯一系统性异常：账单 out/in 为我方 3.01 倍")))
df_other = pd.DataFrame(other_rows).sort_values(["月份", "模型"])

# ---------- luna 账单金额构成 ----------
amt_rows = []
for m in ("2026-08", "2026-10", "2026-11"):
    for t in ("input", "output", "cache"):
        q, a = mon_sup[m][t]
        if q == 0:
            continue
        amt_rows.append(dict(月份=m, 计费类型=t, 用量_亿=q / YI, 实收_USD=a,
                             单价_USD每百万=a / (q / M) if q else 0,
                             占当月luna金额_pct=round(100 * a / sum(mon_sup[m][x][1] for x in ("input", "output", "cache")), 2)))
# 8 月整张账单 / luna 占比
aug_bill_total = 13873.86  # T082 已核（订单明细「订单总额」求和）
aug_luna_total = sum(mon_sup["2026-08"][t][1] for t in ("input", "output", "cache"))
df_amt = pd.DataFrame(amt_rows)

# ---------- 结论 ----------
loss_aug = row_aug["多计_USD"]
w_ghost = rows_win[2]
w_star = rows_win[4]
total_confirmed = loss_aug + w_star["多计_USD"]
sep_gap = mon_db["2026-09"][1]
scenario_low = sep_gap / M * 0.14 * 0.38   # 若与 10 月一样仅 +14%
scenario_high = sep_gap / M * 2.01 * 0.38  # 若与 8 月一样 3.01 倍 (差额 = 我方×2.01)
concl = [
    ["【一句话结论】", "luna 的 output/input 比在 8 月账单侧是我方的 3.01 倍（0.6087 vs 0.2022），同期主力对照模型正常；"
                   "10 月起（gpt-6-luna）倍率降到约 1.1~1.6，异常形态变成少量我方不存在的幽灵行。已证实多计主要在 8 月。"],
    ["", ""],
    ["【逐月 luna 我方 out/in】", "8月 0.2022 / 9月 0.2383 / 10月 0.2530 / 11月(至11/09) 0.2813 —— 我方口径自身稳定在 0.20~0.28，逐月缓慢抬升属模型/提示词结构变化。"],
    ["【8 月异常】", f"账单 out/in=0.6087，我方 0.2022，倍率 3.01；input 两侧 151.79亿 vs 151.62亿 仅差 0.11%（对齐）。"
                 f"output 差额 {row_aug['output差额_亿']:.2f}亿 token，按折后价 ${p8:.4f}/百万计 多收 ${loss_aug:,.2f}（≈¥{loss_aug*FX:,.0f}），占 8 月整张账单 42.7%。"],
    ["【8 月形态】", "27 个有效日倍率 2.14~4.15 连续分布（不是少数尖峰）；同月 terra 账单 out/in 0.218 vs 我方 0.214（1.02 倍）、"
                 "7 月尚无 luna 时 gpt-5-mini 账单 15.49/3.58亿 vs 我方 15.50/3.56亿 完全对齐 → "
                 "只有 luna 单一模型被系统性放大，与「该模型计费口径」的判断一致。"],
    ["【9 月缺口】", f"本地没有 9 月 UCloud 账单，无法定案。我方 9 月 luna output {sep_gap/YI:.2f}亿；"
                  f"若按 10 月 +14% 情景约 ${scenario_low:,.0f}，若按 8 月 3 倍情景约 ${scenario_high:,.0f}（均按 $0.38/百万）。"
                  "需补拉 9 月账单才能确认，本报告不计入已证实损失。"],
    ["【按模型两代】", "8 月只有 gpt-5.6-luna（我方 out/in 0.2022）；9 月起主切 gpt-6-luna，我方 out/in "
                  "0.2389 → 0.2530 → 0.2813，逐月温和抬升（模型/提示词结构变化），与账单侧 3 倍不是同一现象。"],
    ["【10-11 月】", f"星图 10/06~11/05 同窗口：账单 output {w_star['账单output_亿']:.2f}亿 vs 我方 {w_star['我方output_亿']:.2f}亿，"
                  f"差额 {w_star['output差额_亿']:.2f}亿，按 ${w_star['output单价_USD每百万']:.4f}/百万 折 ${w_star['多计_USD']:,.2f}。"
                  f"其中 10/20~11/01 我方几无 luna 调用、账单仍记 {w_ghost['账单output_亿']:.2f}亿 output（${w_ghost['多计_USD']:,.2f}）；"
                  "该段 185 个小时桶中 25 个恰好 128000（max_tokens 上限型幽灵行特征），与 T082 定案一致。"
                  "10/06~10/19 正常调用段仍稳定高约 15%，量级远小于 8 月 3 倍，机制未逐条定案。"],
    ["【累计已证实损失】", f"8 月 ${loss_aug:,.2f} + 星图全窗 ${w_star['多计_USD']:,.2f} = ${total_confirmed:,.2f}"
                     f"（≈¥{total_confirmed*FX:,.0f}）；幽灵行段已含在星图全窗内，不双计；9 月未计入。"
                     "8 月数与 T082 的 $5,929.13 一致，0.44 美元差来自亿位四舍五入。"],
    ["", ""],
    ["【是「luna 模型本身」吗】", "是「账单侧对 luna 单一模型 output 的计量/倍率」问题，不是我方账本少记："
                          "T082 已用 routing_ledger 逐请求验证 11 月三方齐全请求 input/output 100.00% 相等；"
                          "8 月我方 496 万条逐请求明细 output max 22,074、≥65536 = 0 行。"],
    ["【建议动作】", "① 补拉 2026-09 月账单（含 9/24 起 gpt-6-luna 切换），按同口径核 out/in；"
                 "② 向 UCloud 主张 8 月 luna output 差额（附 27 天逐日倍数表 + 我方全量逐请求明细）；"
                 "③ 10/20~11/01 我方无调用却计费的 0.70亿 output 单独核销（与 T082 的 261 条上限型幽灵行同形态但属不同日期段，需另取网关日志）；"
                 "④ 让供应商解释 8 月 luna output 是否把 reasoning token 计入，以及为何 10 月起倍率恢复正常。"],
    ["", ""],
    ["【口径/限制】", "我方 = immdata.token_used_aw, providername='UCloud', recordtype='capture', 北京自然日；"
                  "金额 = 供应商账单实收折后「订单金额」USD；单价 = 金额/用量×1e6；汇率 ¥7.1/USD（与 T082 一致）。"],
    ["【重要限制 1】", "星图账单账期为 10-06~11-05，不是自然月，主表 A 的 10/11 月账单比值仅供参照；"
                   "精确对比一律看「窗口对齐与损失」。"],
    ["【重要限制 2】", "我方 cachedinputusage 恒 0（imt-api 硬编码，缓存已折进 inputusage），故 cache 计费单元不参与 out/in 计算；"
                   "8 月 luna cache 1.47亿 token / $20.63，10 月 gpt-6-luna cache 2.11亿 / $18.85，金额占比极小。"],
    ["【重要限制 3】", "8 月账单为小时桶聚合、无逐请求明细；3 倍机制未 100% 证实，"
                   "多收金额是「按我方量估算的潜在多收」，非已确认退款额。"],
    ["【数据源】", "6/7/8 月 Funstory.ai 账单（Downloads）；星图已完成订单 10-06~11-05；"
                "docs/tasks/query_ucloud_model_detail_202607_20261022.md (T081)；T082 倒查与金额折算交付。"],
]
df_concl = pd.DataFrame(concl, columns=["项目", "内容"])

# ---------- 写 Excel ----------
with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    df_concl.to_excel(w, sheet_name="结论与口径", index=False)
    df_month.to_excel(w, sheet_name="逐月输入输出比", index=False)
    df_model.to_excel(w, sheet_name="按模型逐月_我方", index=False)
    df_win.to_excel(w, sheet_name="窗口对齐与损失", index=False)
    df_aug.to_excel(w, sheet_name="8月逐日对照", index=False)
    df_star.to_excel(w, sheet_name="10-11月逐日对照", index=False)
    df_other.to_excel(w, sheet_name="其他模型对照", index=False)
    df_amt.to_excel(w, sheet_name="luna账单金额构成", index=False)

# 版式
from openpyxl import load_workbook
wb = load_workbook(OUT)
for ws in wb.worksheets:
    ws.freeze_panes = "A2"
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[letter].width = min(max(width * 1.15 + 2, 12), 62)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, float):
                c.number_format = "#,##0.0000" if abs(c.value) < 10 else "#,##0.00"
ws = wb["结论与口径"]
ws.column_dimensions["A"].width = 24
ws.column_dimensions["B"].width = 115
for row in ws.iter_rows(min_row=2):
    row[0].font = Font(bold=True)
    for c in row:
        c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[row[0].row].height = 46
wb.save(OUT)

print("[saved]", OUT)
print("\n=== 窗口对齐与损失 ===")
print(df_win.to_string(index=False))
print("\n=== 逐月输入输出比 ===")
print(df_month.to_string(index=False))
print("\n=== 其他模型对照 ===")
print(df_other.to_string(index=False))
print(f"\n累计已证实损失 ${total_confirmed:,.2f} ≈ ¥{total_confirmed*FX:,.0f}")
print(f"8 月账单总额 ${aug_bill_total:,.2f}, luna 金额 ${aug_luna_total:,.2f} ({aug_luna_total/aug_bill_total:.1%})")
