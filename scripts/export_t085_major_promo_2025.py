# -*- coding: utf-8 -*-
"""构建 2025 大促活动清单（剔除达人/渠道/通用券/续费）。T085 衍生。"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from db import query
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
OUT_XLSX = os.path.join(OUT_DIR, "sales_discount_2025_major_promo.xlsx")
SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "reports", "T085_major_promo_2025.sql")

# 大促白名单（季节性平台级大促；国庆并入中秋活动）
MAJOR = {
    "618 MID YEAR": "618 年中大促",
    "Limited-Time Summer Sale": "夏日/暑期大促",
    "2025 Double 11 Mega Sale": "双11 大促",
    "Mid-Autumn Sale Pro": "中秋大促（普通/Pro）",
    "Mid-Autumn Sale Max": "中秋·国庆大促（Max）",
    "Christmas & New Year Sale": "圣诞·新年大促",
}

# 排除项的归类（仅用于说明，便于用户核对剔除是否合理）
def classify(name):
    n = name.lower()
    if any(k in name for k in ["达人", "dedao", "b站", "有赞", "小宇宙", "Edge", "公众号", "博主",
                                "katlas", "Web3", "科技侠", "老王", "yann", "JNomadL", "skku",
                                "Immersive Translate", "Student", "立青", "xiaohu", "guizang",
                                "Cydiar", "TW Friends", "2025Friends"]):
        return "达人/渠道/个人推广"
    if any(k in name for k in ["专属优惠", "% OFF", "% off", "折优惠", "折扣码", "Coupon", "优惠券",
                               "双十一快闪", "首月", "First Year", "Special", "Renewal", "Family Plan",
                               "开发测试", "20241111", "2024618"]):
        return "通用券/续费/测试/旧券残留"
    return "其他"

STANDARD = {
    "yearly": 579.6, "monthly": 69.0, "max_yearly": 1599.0, "max_monthly": 199.0,
    "two_yearly": 1159.2, "family": 1188.0,
}

def run(sql):
    cols, rows = query(sql)
    return cols, rows

def sql_statements(path):
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"\r?\n-- Q\d+\)", "\n" + txt)
    stmts = []
    for p in parts:
        lines = p.split("\n")
        start = None
        for i, ln in enumerate(lines):
            s = ln.strip().upper()
            if s.startswith("SELECT") or s.startswith("WITH"):
                start = i
                break
        if start is None:
            continue
        body = "\n".join(lines[start:]).strip()
        stmts.append(body)
    return stmts

def floatize(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

# ---------- styles ----------
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
SUB_FONT = Font(bold=True, size=11, color="1F4E78")
WARN_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center")

def style_header(ws, ncols, row=1):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

def autosize(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

# ---------- run queries ----------
stmts = sql_statements(SQL_PATH)
assert len(stmts) == 3, f"expected 3 statements, got {len(stmts)}"
all_cols, all_rows = run(stmts[0])
prod_cols, prod_rows = run(stmts[1])
month_cols, month_rows = run(stmts[2])

ai = {c: i for i, c in enumerate(all_cols)}
pi = {c: i for i, c in enumerate(prod_cols)}
mi = {c: i for i, c in enumerate(month_cols)}

# build dicts
all_by_name = {r[ai["couponname"]]: r for r in all_rows}
prod_by_name = {}
for r in prod_rows:
    prod_by_name.setdefault(r[pi["couponname"]], []).append(r)
month_by_name = {}
for r in month_rows:
    month_by_name.setdefault(r[mi["couponname"]], {})[r[mi["ym"]]] = r[mi["cnt"]]

MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]

wb = openpyxl.Workbook()

# ===== Sheet 1: 大促活动清单 =====
ws1 = wb.active
ws1.title = "大促活动清单"
ws1.append(["类别", "活动名称(couponname)", "订单数", "付费人数", "首单", "末单", "峰值月份",
            "平均成交价(元)", "折扣率", "主要产品", "覆盖产品"])
major_sorted = sorted(MAJOR.keys(), key=lambda n: -all_by_name[n][ai["order_cnt"]])
for name in major_sorted:
    r = all_by_name[name]
    paid = floatize(r[ai["avg_paid"]])
    prods = prod_by_name.get(name, [])
    prods_sorted = sorted(prods, key=lambda x: -x[pi["n"]])
    dom = prods_sorted[0][pi["subscriptiontype"]] if prods_sorted else "-"
    allp = ", ".join(f'{p[pi["subscriptiontype"]]}({p[pi["n"]]})' for p in prods_sorted)
    # discount: weighted by product standard? use overall avg paid vs representative list
    # show per the dominant product's discount
    disc_disp = ""
    if prods_sorted:
        p0 = prods_sorted[0]
        la = floatize(p0[pi["list_avg"]]); pa = floatize(p0[pi["paid_avg"]])
        if la and pa is not None and la > 0:
            disc_disp = f"{(1-pa/la)*100:.0f}%"
    ws1.append([
        MAJOR[name], name, r[ai["order_cnt"]], r[ai["user_cnt"]],
        str(r[ai["first_o"]])[:10], str(r[ai["last_o"]])[:10], r[ai["peak_month"]],
        paid, disc_disp, dom, allp,
    ])
style_header(ws1, 11)
autosize(ws1, [22, 30, 9, 9, 12, 12, 9, 14, 8, 16, 40])
ws1.freeze_panes = "A2"
# 高亮国庆Max
for row in ws1.iter_rows(min_row=2):
    if row[1].value == "Mid-Autumn Sale Max":
        for c in row:
            c.fill = WARN_FILL

# ===== Sheet 2: 大促×产品（折扣对比标准价）=====
ws2 = wb.create_sheet("大促×产品")
ws2.append(["活动类别", "活动名称", "产品", "订单数", "标准标价(元)", "活动成交均价(元)", "折扣率", "较标准省(元)"])
for name in major_sorted:
    for p in sorted(prod_by_name.get(name, []), key=lambda x: -x[pi["n"]]):
        st = p[pi["subscriptiontype"]]
        la = floatize(p[pi["list_avg"]]); pa = floatize(p[pi["paid_avg"]])
        std = STANDARD.get(st)
        disc = f"{(1-pa/la)*100:.0f}%" if (la and pa is not None and la > 0) else ""
        save = round(pa - (std if std is not None else la), 2) if pa is not None else None
        ws2.append([MAJOR[name], name, st, p[pi["n"]], std if std is not None else la,
                    pa, disc, save])
style_header(ws2, 8)
autosize(ws2, [22, 30, 14, 9, 14, 16, 8, 12])
ws2.freeze_panes = "A2"

# ===== Sheet 3: 大促月度趋势 =====
ws3 = wb.create_sheet("大促月度趋势")
header = ["活动类别", "活动名称"] + MONTHS + ["合计"]
ws3.append(header)
totals = {m: 0 for m in MONTHS}
for name in major_sorted:
    mm = month_by_name.get(name, {})
    row = [MAJOR[name], name] + [mm.get(m, 0) for m in MONTHS]
    s = sum(mm.get(m, 0) for m in MONTHS)
    row.append(s)
    ws3.append(row)
    for m in MONTHS:
        totals[m] += mm.get(m, 0)
ws3.append(["大促合计", ""] + [totals[m] for m in MONTHS] + [sum(totals.values())])
style_header(ws3, len(header))
for c in range(1, len(header) + 1):
    ws3.cell(row=ws3.max_row, column=c).font = Font(bold=True)
autosize(ws3, [22, 30] + [9] * 13)
ws3.freeze_panes = "C2"

# ===== Sheet 4: 已排除清单（达人/渠道/通用券等，供核对）=====
ws4 = wb.create_sheet("已排除清单")
ws4.append(["归类", "活动名称(couponname)", "订单数", "说明"])
for name in sorted(all_by_name.keys(), key=lambda n: -all_by_name[n][ai["order_cnt"]]):
    if name in MAJOR:
        continue
    r = all_by_name[name]
    ws4.append([classify(name), name, r[ai["order_cnt"]], "按需求剔除：非大促"])
style_header(ws4, 4)
autosize(ws4, [26, 34, 9, 22])
ws4.freeze_panes = "A2"

# ===== Sheet 5: 口径说明 =====
ws5 = wb.create_sheet("口径说明")
notes = [
    ("2025 大促活动清单（仅大促，已剔除达人/渠道）", ""),
    ("", ""),
    ("数据表", "immdata.imt_subscriptiongoodsorder（订阅商品订单，业务库只读副本，日更）"),
    ("过滤", "COALESCE(isdeleted,0)=0；orderstatus='finished'；COALESCE(amountpaid,0)>0"),
    ("币种", "UPPER(currency)='CNY'。其他币种 amount/amountpaid 单位不稳（P008），不纳入"),
    ("时间窗", "createtime ∈ [2025-01-01, 2026-01-01)（自然年 2025；createtime=下单时间）"),
    ("标价/实付", "amount=标准标价(元)；amountpaid/100=折扣后实付(元；最小货币单位整数，P008)"),
    ("折扣度量", "折扣率=(标准标价−活动成交均价)/标准标价，对所有 CNY 订单可直接度量"),
    ("大促口径", "仅 6 个季节性平台级大促：618 / 夏日特惠 / 双11 / 中秋(Pro) / 中秋·国庆(Max) / 圣诞新年"),
    ("关于国庆 Max", "2025 中秋(10/6)与国庆(10/1-7)重叠为 8 天长假，无独立'国庆'活动名；Max 打折归于'Mid-Autumn Sale Max'。"
                     "国庆窗口(10/1-10/15)139 单 Max 年费 ¥1599→¥852(≈47折)；全活动 178 单 ¥1599→¥879(≈45折)"),
    ("已剔除", "达人/渠道/个人推广、通用券、续费券、旧券残留(2024 双11/618)、测试券 —— 详见'已排除清单'"),
    ("2025 标准标价", "年费579.6 / 月费69 / Max年费1599 / Max月费199 / 两年1159.2 / 家庭约1188"),
    ("关于 588", "用户提及年费588；2025 实际年费标准价 579.6，588 疑为更早/取整口径"),
    ("验证方式", "直接查询业务库核对：列出全量 couponname+月度分布；钻取 10 月 Max 年费折扣来源（见 sql/adhoc/verify_major_promo_2025.py）"),
    ("交付", "T085 衍生 · 2026-10-26 · 脚本 scripts/export_t085_major_promo_2025.py"),
]
for a, b in notes:
    ws5.append([a, b])
ws5["A1"].font = TITLE_FONT
ws5["A3"].font = SUB_FONT
for row in ws5.iter_rows(min_row=3):
    row[0].font = Font(bold=True)
    row[1].alignment = WRAP
autosize(ws5, [16, 90])

os.makedirs(OUT_DIR, exist_ok=True)
wb.save(OUT_XLSX)
print("saved:", os.path.abspath(OUT_XLSX))
print("大促数:", len(major_sorted), "| 排除数:", len(all_by_name) - len(MAJOR))
