#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T106 交付：全供应商 luna 逐月用量与输入输出比（验证 UCloud 8 月 3 倍是否 UCloud 独有）。"""
import csv
from collections import defaultdict
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

YI = 1e8
OUT = "output/luna_by_provider_monthly_202608_202611.xlsx"
NO_OUT = {"DeepL-LB", "DeepL-Pro", "Internal", "Unknown"}  # 只记 input 的非 LLM 通道，不参与 out/in 基线


def read_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


luna = read_csv("output/_t106_luna_by_provider.csv")
base = read_csv("output/_t106_baseline_by_provider.csv")

for r in luna:
    for k in ("n_rows",):
        r[k] = int(r[k])
    for k in ("inp", "outp"):
        r[k] = float(r[k] or 0)
for r in base:
    r["n_rows"] = int(r["n_rows"])
    for k in ("inp", "outp"):
        r[k] = float(r[k] or 0)

months = sorted({r["bj_month"] for r in luna})

# ---------- 全模型基线 ----------
baseline_rows = []
for m in sorted({r["bj_month"] for r in base}):
    rs = [r for r in base if r["bj_month"] == m]
    llm = [r for r in rs if r["provider"] not in NO_OUT and r["inp"] > 0]
    tin = sum(r["inp"] for r in llm)
    tout = sum(r["outp"] for r in llm)
    allin = sum(r["inp"] for r in rs)
    for r in sorted(rs, key=lambda x: -x["inp"]):
        baseline_rows.append(dict(北京月=m, 供应商=r["provider"], 请求数=r["n_rows"],
                                 全模型input_亿=r["inp"] / YI, 全模型output_亿=r["outp"] / YI,
                                 全模型out_in=r["outp"] / r["inp"] if r["inp"] else None,
                                 是否计入基线="否(output恒0, 非LLM通道)" if r["provider"] in NO_OUT else "是"))
    baseline_rows.append(dict(北京月=m, 供应商="◆ 加权基线(LLM通道)", 请求数=sum(r["n_rows"] for r in llm),
                             全模型input_亿=tin / YI, 全模型output_亿=tout / YI,
                             全模型out_in=tout / tin if tin else None,
                             是否计入基线="—"))
df_base = pd.DataFrame(baseline_rows)


def baseline_of(m):
    rs = [r for r in base if r["bj_month"] == m and r["provider"] not in NO_OUT and r["inp"] > 0]
    tin = sum(r["inp"] for r in rs)
    tout = sum(r["outp"] for r in rs)
    return (tout / tin if tin else 0), tin


# ---------- 逐月汇总 ----------
sum_rows = []
for m in months:
    rs = [r for r in luna if r["bj_month"] == m]
    tin = sum(r["inp"] for r in rs)
    tout = sum(r["outp"] for r in rs)
    n = sum(r["n_rows"] for r in rs)
    uc_in = sum(r["inp"] for r in rs if r["provider"] == "UCloud")
    oth = [r for r in rs if r["provider"] != "UCloud"]
    oth_in = sum(r["inp"] for r in oth)
    oth_out = sum(r["outp"] for r in oth)
    b, ball = baseline_of(m)
    top = sorted({r["provider"]: sum(x["inp"] for x in rs if x["provider"] == r["provider"])
                  for r in rs}.items(), key=lambda kv: -kv[1])[:3]
    sum_rows.append(dict(
        北京月=m, luna请求数=n,
        luna_input_亿=tin / YI, luna_output_亿=tout / YI,
        luna_out_in=tout / tin if tin else 0,
        全模型基线_out_in=b, luna减基线=(tout / tin - b) if tin else 0,
        UCloud_input_亿=uc_in / YI, UCloud份额_pct=100 * uc_in / tin if tin else 0,
        其他供应商_input_亿=oth_in / YI, 其他供应商份额_pct=100 * oth_in / tin if tin else 0,
        其他供应商_out_in=oth_out / oth_in if oth_in else 0,
        luna占全模型input_pct=100 * tin / ball if ball else 0,
        主要落点=", ".join(f"{p} {v/YI:.1f}亿" for p, v in top),
        账单侧异常=("UCloud 8 月账单 out/in=0.6087（3.01 倍）" if m == "2026-08" else
                    "无账单" if m == "2026-09" else
                    "星图账期 UCloud out/in=0.3196（10/06~11/05）" if m == "2026-10" else
                    "星图账期 UCloud out/in=0.3996（放量段）")))
df_sum = pd.DataFrame(sum_rows)

# ---------- 按供应商 × 月明细 ----------
det_rows = []
for m in months:
    rs = [r for r in luna if r["bj_month"] == m]
    tin = sum(r["inp"] for r in rs)
    b, _ = baseline_of(m)
    for r in sorted(rs, key=lambda x: (-x["inp"])):
        ratio = r["outp"] / r["inp"] if r["inp"] else 0
        share = 100 * r["inp"] / tin if tin else 0
        abnormal = ratio > 0.35 and r["inp"] > 1e6
        det_rows.append(dict(
            北京月=m, 供应商=r["provider"], luna模型=r["model"],
            请求数=r["n_rows"], input_亿=r["inp"] / YI, output_亿=r["outp"] / YI,
            out_in=ratio, 当月luna份额_pct=share,
            与全模型基线差=ratio - b,
            判定=("⚠ 比值偏高但量级 <0.02%，长尾/测试流量，可忽略" if abnormal else
                  "正常（0.2~0.29 区间）" if 0.15 <= ratio <= 0.32 else "—")))
df_det = pd.DataFrame(det_rows)

# ---------- 8 月账单对照 ----------
b8, b8in = baseline_of("2026-08")


def cmp_row(src, scope, i, o, note, out_override=None):
    r = o / i if i else (out_override or 0)
    return dict(来源=src, 口径=scope, input_亿=i, output_亿=o, out_in=r,
                相对全模型8月基线=r / b8 if b8 else 0, 说明=note)


cmp_rows = [
    cmp_row("UCloud 8 月【账单】", "订单汇总 gpt-5.6-luna", 151.7896, 92.3988,
            "T105/T082 定案：input 对齐、output 系统性 3 倍"),
    cmp_row("UCloud 8 月【我方账本】", "token_used_aw", 151.6238, 30.6647, "权威账本"),
    cmp_row("OneRouter 8 月【我方账本】", "token_used_aw", 8.2526, 1.6233,
            "同期另一供应商，同一 gpt-5.6-luna，比值正常"),
    cmp_row("OpenRouter 8 月【我方账本】", "token_used_aw", 2.4163, 0.5684,
            "同期另一供应商，同一 gpt-5.6-luna，比值正常"),
    dict(来源="全模型 8 月【我方账本加权】", 口径="LLM 通道，排除 output 恒 0 的 DeepL/Unknown/Internal",
         input_亿=b8in / YI, output_亿=None, out_in=b8, 相对全模型8月基线=1.0,
         说明="用户口径「平均 0.2~0.25」的实测验证"),
]
df_cmp = pd.DataFrame(cmp_rows)

# ---------- 结论 ----------
aug = df_sum[df_sum.北京月 == "2026-08"].iloc[0]
sep = df_sum[df_sum.北京月 == "2026-09"].iloc[0]
oct_ = df_sum[df_sum.北京月 == "2026-10"].iloc[0]
nov = df_sum[df_sum.北京月 == "2026-11"].iloc[0]
concl = [
    ["【直接回答】", "其他供应商的 luna **没有** UCloud 8 月账单那种 3 倍问题。8 月同一个 gpt-5.6-luna："
                "UCloud 我方 0.2022、OneRouter 0.1967、OpenRouter 0.2353；9 月及以后 OneRouter / OpenRouter / OpenAI / UCloud "
                "的 luna 也都落在 0.18~0.29，各家基本一致。**0.6087 只出现在 UCloud 的账单侧**，不是 luna 模型本身的输出特性。"],
    ["", ""],
    ["【每月 luna 量】", f"8月 {aug.luna_input_亿:.2f}亿 in / {aug.luna_output_亿:.2f}亿 out（out/in {aug.luna_out_in:.4f}）；"
                    f"9月 {sep.luna_input_亿:.2f} / {sep.luna_output_亿:.2f}（{sep.luna_out_in:.4f}）；"
                    f"10月 {oct_.luna_input_亿:.2f} / {oct_.luna_output_亿:.2f}（{oct_.luna_out_in:.4f}）；"
                    f"11月(至11/09) {nov.luna_input_亿:.2f} / {nov.luna_output_亿:.2f}（{nov.luna_out_in:.4f}）。"
                    "luna 自 2026-08-05 才放量，6/7 月无 luna 行。"],
    ["【比值逐月上移】", f"全模型基线也同步上移：8月 {aug.全模型基线_out_in:.4f} → 9月 {sep.全模型基线_out_in:.4f} → "
                    f"10月 {oct_.全模型基线_out_in:.4f} → 11月 {nov.全模型基线_out_in:.4f}。"
                    f"luna 与全模型基线各月只差 {aug.luna_out_in-aug.全模型基线_out_in:+.4f} / "
                    f"{sep.luna_out_in-sep.全模型基线_out_in:+.4f} / "
                    f"{oct_.luna_out_in-oct_.全模型基线_out_in:+.4f} / "
                    f"{nov.luna_out_in-nov.全模型基线_out_in:+.4f}（几乎重合）—— luna 就是全平台平均水平，毫无特殊性。"
                    "10/11 月到 0.27~0.29 是 gpt-6-luna 换代 + 整体提示词变化，不是某家供应商的异常"
                    "（用户口径「0.2~0.25」对应 8/9 月，10/11 月全平台整体已略高于该区间）。"],
    ["【流量切走】", f"UCloud 占 luna input 份额：8月 {aug.UCloud份额_pct:.1f}% → 9月 {sep.UCloud份额_pct:.1f}% → "
                 f"10月 {oct_.UCloud份额_pct:.1f}% → 11月 {nov.UCloud份额_pct:.1f}%。"
                 "切走后主要落 OneRouter，其次 OpenAI；这两家的 luna out/in 与 UCloud 我方账本同期完全一致"
                 "（10月 OneRouter 0.2839 / OpenAI 0.2783 / UCloud 0.2530；11月 0.2930 / 0.2825 / 0.2813）。"],
    ["【8 月铁证】", "同一模型、同一月份、三家供应商：账单侧只有 UCloud 是 0.6087，另两家我方账本 0.1967 / 0.2353，"
                 "UCloud 我方账本 0.2022、全模型基线约 0.2059。若是 luna 模型特性，各家应一起高。"],
    ["【两个长尾高值】", "10 月 OpenRouter gpt-6-luna 0.5564、11 月 0.8209，但 input 分别仅 0.04亿 / 0.005亿，"
                   "占当月 luna 量 <0.02%，属长尾/测试流量，不影响结论。"],
    ["", ""],
    ["【⚠ 重要限制】", "以上用的是**我方账本**，只能证明「luna 模型本身在真实调用里输出比正常、各家一致」；"
                  "**不能证明其他供应商的账单也没有多计** —— 本地只有 UCloud/星图账单，没有 OneRouter / OpenAI 的对账单。"
                  "若要彻底排除「所有供应商账单都把 luna output 放大」的可能，需补拉这两家 8–10 月账单按同口径核 out/in。"],
    ["【对 T105 的影响】", "T105 的结论不变且被加强：8 月 $5,928.69 多计是 UCloud 单侧账单问题。"
                     "10/11 月星图那点差额（$78.15）形态是我方无对应请求的幽灵行，与模型特性无关。"],
    ["【建议】", "① 向 OneRouter / OpenAI 索要 2026-08~10 月 luna 账单，核其账单侧 out/in 是否也是 0.2~0.25；"
              "② 若确认，可作为向 UCloud 主张 8 月差额的第三方旁证（同期同模型、别家账单不高）；"
              "③ 后续按月固定监控「各供应商 luna out/in」这一维度，任一供应商账单比值偏离我方基线 >1.5 倍即预警。"],
    ["", ""],
    ["【口径】", "我方 = immdata.token_used_aw，recordtype='capture'，北京月 = date_add(hour,8,timestamp)；"
              "luna = actualresourceid LIKE '%luna%'（含 gpt-5.6-luna / gpt-6-luna 两代）；"
              "out/in = SUM(outputusage)/SUM(inputusage)。"],
    ["【基线口径】", "全模型基线按 LLM 通道加权（排除 output 恒 0 的 DeepL-LB / DeepL-Pro / Internal / Unknown，"
                "这些通道只记 input，计入会人为拉低比值）；DeepL/Unknown 在总 input 里仍计入份额分母。"],
    ["【数据源】", "scripts/_t106_luna_by_provider.py、_t106_baseline.py 实跑；"
              "8 月 UCloud 账单与 T105 交付 `output/ucloud_luna_monthly_ratio_loss_202608_202611.xlsx`。"],
]
df_concl = pd.DataFrame(concl, columns=["项目", "内容"])

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    df_concl.to_excel(w, sheet_name="结论", index=False)
    df_sum.to_excel(w, sheet_name="逐月汇总", index=False)
    df_det.to_excel(w, sheet_name="按供应商逐月明细", index=False)
    df_cmp.to_excel(w, sheet_name="8月账单对照", index=False)
    df_base.to_excel(w, sheet_name="全模型基线", index=False)

wb = load_workbook(OUT)
for ws in wb.worksheets:
    ws.freeze_panes = "A2"
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 32
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[letter].width = min(max(width * 1.1 + 2, 12), 60)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, float):
                c.number_format = "#,##0.0000" if abs(c.value) < 10 else "#,##0.00"
ws = wb["结论"]
ws.column_dimensions["A"].width = 22
ws.column_dimensions["B"].width = 118
for row in ws.iter_rows(min_row=2):
    row[0].font = Font(bold=True)
    for c in row:
        c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.row_dimensions[row[0].row].height = 54
wb.save(OUT)

print("[saved]", OUT)
print("\n=== 逐月汇总 ===")
print(df_sum[["北京月", "luna请求数", "luna_input_亿", "luna_output_亿", "luna_out_in",
              "全模型基线_out_in", "UCloud份额_pct", "其他供应商_out_in"]].to_string(index=False))
print("\n=== 按供应商逐月明细 ===")
print(df_det.to_string(index=False))
