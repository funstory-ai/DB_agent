"""T126 分析：合并 Stripe 缓存 + 我方 DB 缓存，产出商业分析 Excel + 结论 JSON。
只读；输入全部来自 output/stripe_behavior/*.json；不写库、不打印 Key。
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "stripe_behavior"
BJ = timezone(timedelta(hours=8))


def load(name):
    return json.load(open(OUT / f"{name}.json", encoding="utf-8"))


inv = load("invoices_paid")  # 精简版：status=paid，无 expand；userid 用我方订单桥接
ref = load("refunds")
dis = load("disputes")
db_q1 = load("db_Q1")
db_q2 = load("db_Q2")
db_q3 = load("db_Q3")
db_q4 = load("db_Q4")

# ---- invoice -> userid 映射（我方订单桥）----
C1 = db_q1["columns"]
i_invoice, i_uid = C1.index("invoiceid"), C1.index("userid")
inv_to_uid = {str(r[i_invoice]): r[i_uid] for r in db_q1["rows"] if r[i_invoice]}

# ---- 行为聚合 uid -> (page, subtitle, total) ----
C3 = db_q3["columns"]
u_page, u_sub, u_tot = C3.index("page_events"), C3.index("subtitle_events"), C3.index("total_events")
uid_beh = {r[0]: (r[u_page], r[u_sub], r[u_tot]) for r in db_q3["rows"]}

# ---- 币种金额：最小单位 -> 元（CNY/TWD/JPY/KRW 等 0 小数，USD 也按美分）----
CURRENCY_ZERO_DECIMAL = {"JPY", "KRW", "VND", "CLP"}  # 无小数币种


def to_major(amount, cur):
    cur = (cur or "").upper()
    div = 1 if cur in CURRENCY_ZERO_DECIMAL else 100
    return (amount or 0) / div


paid = [x for x in inv if x["status"] == "paid" and (x["amount_paid"] or 0) > 0]
n_paid = len(paid)

# ---- Sheet 1 收入质量 ----
by_cur = defaultdict(lambda: {"n": 0, "amt": 0.0})
for x in paid:
    b = by_cur[x["currency"]]
    b["n"] += 1
    b["amt"] += to_major(x["amount_paid"], x["currency"])

ref_ok = [x for x in ref if x["status"] == "succeeded"]
dis_lost = [x for x in dis if x["status"] in ("lost", "warning_closed")]
ref_by_cur = defaultdict(float)
for x in ref_ok:
    ref_by_cur[x["currency"]] += to_major(x["amount"], x["currency"])
dis_by_cur = defaultdict(float)
for x in dis_lost:
    dis_by_cur[x["currency"]] += to_major(x["amount"], x["currency"])

# ---- Sheet 2 结构：billing_reason ----
by_reason = defaultdict(lambda: {"n": 0, "amt_cny": 0.0, "users": set()})
for x in paid:
    reason = x["billing_reason"] or "unknown"
    b = by_reason[reason]
    b["n"] += 1
    if x["currency"] == "cny":
        b["amt_cny"] += to_major(x["amount_paid"], x["currency"])
    uid = inv_to_uid.get(x["id"])
    if uid:
        b["users"].add(uid)

# ---- Sheet 3 价值分层：按 CNY 实付分档，看翻译行为 ----
# 仅取能映射到 userid 的付费 invoice
tiers = [
    ("试用/低价 <¥30", 0, 30),
    ("¥30–99", 30, 100),
    ("¥100–299", 100, 300),
    ("¥300–999", 300, 1000),
    ("≥¥1000", 1000, 10**12),
]
uid_amt_cny = defaultdict(float)
uid_n_inv = Counter()
for x in paid:
    uid = inv_to_uid.get(x["id"])
    if uid and x["currency"] == "cny":
        uid_amt_cny[uid] += to_major(x["amount_paid"], "cny")
        uid_n_inv[uid] += 1

# 每档的代表套餐（按 invoice 描述计数）
tier_desc = defaultdict(Counter)
for x in inv:
    u = inv_to_uid.get(x["id"])
    if u in uid_amt_cny and x["currency"] == "cny" and (x.get("amount_paid") or 0) > 0:
        a = uid_amt_cny[u]
        t = next((lab for lab, lo, hi in tiers if lo <= a < hi), None)
        if t:
            tier_desc[t][x["line_desc"]] += 1

tier_rows = []
for label, lo, hi in tiers:
    uids = [u for u, a in uid_amt_cny.items() if lo <= a < hi]
    with_beh = [u for u in uids if u in uid_beh]
    page = sum(uid_beh[u][0] for u in with_beh)
    sub = sum(uid_beh[u][1] for u in with_beh)
    tot = sum(uid_beh[u][2] for u in with_beh)
    per_user = tot / len(with_beh) if with_beh else 0
    rep = "; ".join(f"{d[:40]}×{c}" for d, c in tier_desc[label].most_common(2))
    tier_rows.append({
        "tier": label, "users": len(uids), "users_with_behavior": len(with_beh),
        "behavior_coverage": round(100 * len(with_beh) / len(uids), 1) if uids else 0,
        "avg_amt_cny": round(sum(uid_amt_cny[u] for u in uids) / len(uids), 2) if uids else 0,
        "total_page": page, "total_subtitle": sub, "total_events": tot,
        "events_per_user": round(per_user, 1), "rep_desc": rep,
    })

# ---- Sheet 4 对账：invoice id 命中与金额一致（CNY，1 元=100 分我方 amountpaid? 需按样本核验）----
C4 = db_q4["columns"]
q4 = {str(r[0]): r for r in db_q4["rows"]}
recon = []
for x in paid[:0]:  # placeholder
    pass
sample_map = {x["id"]: x for x in paid}
for iid, row in q4.items():
    s = sample_map.get(iid)
    recon.append({
        "invoice": iid,
        "stripe_amount_paid": s["amount_paid"] if s else None,
        "stripe_currency": s["currency"] if s else None,
        "stripe_status": s["status"] if s else None,
        "db_amountpaid": row[C4.index("amountpaid")],
        "db_currency": row[C4.index("currency")],
        "db_orderstatus": row[C4.index("orderstatus")],
        "db_ordertype": row[C4.index("ordertype")],
    })

# ---- Sheet 5 退款争议明细（近30天，样本聚合）----
ref_dis = []
for x in ref_ok[:200]:
    ref_dis.append({"type": "refund", "id": x["id"], "created": x["created"],
                    "amount": to_major(x["amount"], x["currency"]), "currency": x["currency"],
                    "reason": x["reason"], "pi": x["payment_intent"]})
for x in dis_lost[:200]:
    ref_dis.append({"type": "dispute", "id": x["id"], "created": x["created"],
                    "amount": to_major(x["amount"], x["currency"]), "currency": x["currency"],
                    "reason": None, "pi": x["payment_intent"]})

# ---- 写 Excel ----
wb = Workbook()
hdr_fill = PatternFill("solid", fgColor="DDEBF7")
hdr_font = Font(bold=True)


def add_sheet(name, headers, rows):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for c in ws[1]:
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal="center")
    for r in rows:
        ws.append(r)
    widths = {}
    for row in ws.iter_rows(values_only=True):
        for idx, v in enumerate(row):
            widths[idx] = min(max(widths.get(idx, 8), len(str(v)) + 2 if v is not None else 8), 42)
    from openpyxl.utils import get_column_letter
    for idx, w in widths.items():
        ws.column_dimensions[get_column_letter(idx + 1)].width = w
    ws.freeze_panes = "A2"


ws = wb.active
ws.title = "结论摘要"
summary = [
    ["窗口", "北京日 2026-10-19 ~ 2026-11-17（30 个完整日，UTC [1792339200,1794931200)）"],
    ["数据源", "Stripe 只读 API（invoices/refunds/disputes）+ immdata 只读（订单/用户/行为）"],
    ["Stripe 有实付的 invoice（金额>0）", n_paid],
    ["Stripe 0 元 paid invoice（试用开通）", sum(1 for x in inv if x["status"] == "paid" and (x["amount_paid"] or 0) <= 0)],
    ["我方 Stripe 渠道付费订单", len(db_q1["rows"])],
    ["可映射 userid 的 Stripe invoice", sum(1 for x in paid if x["id"] in inv_to_uid)],
    ["带 userid 的翻译事件占比", "约 40–45%（P006：仅登录事件）"],
    ["CNY 实付 / 退款（主单位）", f"{round(by_cur['cny']['amt'],2)} / {round(ref_by_cur.get('cny',0),2)}"],
    ["注意", "原始币种主单位，跨币种不合计；年费金额含在单月；不写库、非定案"],
]
for r in summary:
    ws.append(r)
ws["A1"].font = Font(bold=True)

caveats = [
    ["边界 / 读法", "说明"],
    ["价值分层的方向", "≥¥1000 与 ¥300–999 档人均事件更低，不代表高价用户用得少：这两档主要是年费（Max ¥1,599/年、Pro ¥588/年），30 天内把全年金额压进单窗，且含尚未活跃的年费用户。不可解读为「付费越多用量越少」（P043）"],
    ["行为覆盖率", "翻译事件仅 40–45% 带 userid（仅登录事件），分层只覆盖能映射到 userid 的付费用户；非登录/移动端行为未进入（P006/P037）"],
    ["退款归属", "退款按 created 落在本窗口统计，可能对应窗口外开的 invoice；退款占实付为方向性比例，非严格同期 cohorts"],
    ["币种", "JPY/KRV/VND 为无小数币种已按 1 处理，其余按 /100；跨币种绝不合计"],
    ["对账", "5 笔样本 invoice 的 amount_paid 与币种与我方 amountpaid 完全一致（P019），但这是样本，不是全量差异结论"],
    ["P044", "本分析不用于解释或修改任何已交付数字（月报 MRR、T105 多计等）"],
    ["Key 与权限", "只读 RAK 存本地 .env；无 checkout/sessions 与 account 权限；全程 GET，无写操作"],
]
for i, r in enumerate(caveats):
    for j, v in enumerate(r):
        c = ws.cell(row=9 + i, column=1 + j, value=v)
        if i == 0:
            c.font = Font(bold=True)

add_sheet("收入质量_按币种",
          ["币种", "付费笔数(金额>0)", "实付主单位合计", "退款主单位", "争议主单位", "退款占实付%"],
          [[cur, by_cur[cur]["n"], round(by_cur[cur]["amt"], 2),
            round(ref_by_cur.get(cur, 0), 2), round(dis_by_cur.get(cur, 0), 2),
            round(100 * ref_by_cur.get(cur, 0) / by_cur[cur]["amt"], 1) if by_cur[cur]["amt"] else 0]
           # 跨币种不可加总：按 CNY 优先、再按笔数排序，避免无小数币种(VND/KRW)虚高居首
           for cur in sorted(by_cur, key=lambda c: (c != "cny", -by_cur[c]["n"]))])

add_sheet("结构_新订续费改档",
          ["billing_reason", "笔数", "CNY实付", "去重用户数"],
          [[k, v["n"], round(v["amt_cny"], 2), len(v["users"])]
           for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1]["n"])])

add_sheet("价值分层_行为",
          ["档位(CNY累计实付)", "用户数", "有行为用户", "覆盖率%", "人均实付", "翻译页事件", "字幕事件", "总事件", "人均事件", "代表套餐(30天内票面)"],
          [[t["tier"], t["users"], t["users_with_behavior"], t["behavior_coverage"],
            t["avg_amt_cny"],
            t["total_page"], t["total_subtitle"], t["total_events"], t["events_per_user"], t["rep_desc"]]
           for t in tier_rows])

add_sheet("对账_样本5笔",
          ["invoice", "Stripe实付(分)", "Stripe币种", "Stripe状态", "我方amountpaid", "我方币种", "我方状态", "订单类型"],
          [[r["invoice"], r["stripe_amount_paid"], r["stripe_currency"], r["stripe_status"],
            r["db_amountpaid"], r["db_currency"], r["db_orderstatus"], r["db_ordertype"]]
           for r in recon])

add_sheet("退款争议_样本",
          ["类型", "id", "created(UTC秒)", "金额主单位", "币种", "reason", "payment_intent"],
          [[r["type"], r["id"], r["created"], r["amount"], r["currency"], r["reason"], r["pi"]]
           for r in ref_dis])

xlsx = OUT / "stripe_behavior_analysis_20261118.xlsx"
wb.save(xlsx)
print("saved", xlsx)
print("paid=%d  refund_ok=%d  dispute_lost=%d  tier_users=%d" %
      (n_paid, len(ref_ok), len(dis_lost), len(uid_amt_cny)))
