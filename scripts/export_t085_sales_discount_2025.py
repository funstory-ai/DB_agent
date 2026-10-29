"""T085: build 2025 sales-discount campaign Excel from sql/reports/T085_sales_discount_2025.sql."""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from db import query
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "reports", "T085_sales_discount_2025.sql")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
OUT_XLSX = os.path.join(OUT_DIR, "sales_discount_2025_campaigns.xlsx")

# 2025 标准标价（非活动价，来自全量年费/月费等分布）
STANDARD = {"yearly": 579.6, "monthly": 69.0, "max_yearly": 1599.0,
            "max_monthly": 199.0, "family": 1244.88, "onetime_family": 1253.0}

def run(sql):
    return query(sql)

Q1 = """
WITH base AS (
  SELECT
    id, userid, createtime, amount, amountpaid,
    couponname, subscriptiontype, membertype, ordertype,
    CASE WHEN couponname IS NOT NULL THEN couponname ELSE '未命名折扣/直接降价' END AS campaign_label,
    CASE WHEN amount > 0 AND amountpaid/100.0 < amount*0.98 THEN 1 ELSE 0 END AS is_discounted,
    (couponname IS NOT NULL OR (amount > 0 AND amountpaid/100.0 < amount*0.98)) AS keep_flag
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND COALESCE(amountpaid,0) > 0
    AND UPPER(currency)='CNY'
    AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
)
SELECT
  campaign_label,
  COUNT(*)                                                   AS order_cnt,
  COUNT(DISTINCT userid)                                     AS user_cnt,
  MIN(createtime)                                            AS first_order,
  MAX(createtime)                                            AS last_order,
  SUM(is_discounted)                                         AS discounted_cnt,
  ROUND(AVG(CASE WHEN amount>0 THEN amount END), 2)          AS avg_list,
  ROUND(AVG(amountpaid/100.0), 2)                            AS avg_paid,
  ROUND(AVG(CASE WHEN is_discounted=1 THEN (amount-amountpaid/100.0)/NULLIF(amount,0) END)*100, 1) AS avg_discount_pct
FROM base
WHERE keep_flag = 1
GROUP BY campaign_label
ORDER BY order_cnt DESC
"""

Q2 = """
SELECT couponname, to_char(createtime, '%Y-%m') AS ym, COUNT(*) AS cnt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY' AND couponname IS NOT NULL
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
GROUP BY couponname, ym
"""

Q3 = """
SELECT to_char(createtime, '%Y-%m') AS ym, COUNT(*) AS cnt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY'
  AND couponname IS NULL AND amount>0 AND amountpaid/100.0 < amount*0.98
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
GROUP BY ym
"""

Q4 = """
WITH base AS (
  SELECT
    couponname,
    CASE WHEN couponname IS NOT NULL THEN couponname ELSE '未命名折扣/直接降价' END AS campaign_label,
    subscriptiontype, amount, amountpaid,
    CASE WHEN amount>0 AND amountpaid/100.0 < amount*0.98 THEN 1 ELSE 0 END AS is_discounted
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
    AND UPPER(currency)='CNY'
    AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
)
SELECT campaign_label, subscriptiontype, COUNT(*) AS order_cnt,
       ROUND(AVG(amount),2) AS avg_list, ROUND(AVG(amountpaid/100.0),2) AS avg_paid
FROM base
WHERE couponname IS NOT NULL OR is_discounted=1
GROUP BY campaign_label, subscriptiontype
ORDER BY campaign_label, order_cnt DESC
"""

# ---------- classification ----------
def categorize(label):
    l = label.lower()
    if label == "未命名折扣/直接降价":
        return "未命名直接降价"
    if any(k in l for k in ["618", "double 11", "mid-autumn", "mid year", "summer sale",
                            "christmas", "new year", "black", "11.11", "singles"]):
        return "大促节点"
    if any(k in l for k in ["dedao", "b站", "小宇宙", "达人", "xiaohu", "guizang",
                            "day1global", "有赞", "english", "日本", "韩国", "英语", "edge"]):
        return "渠道/达人合作"
    if any(k in l for k in ["renewal", "续费"]):
        return "续费优惠"
    if any(k in l for k in ["拼团", "family", "family plan"]):
        return "团购/家庭"
    if any(k in l for k in ["专属优惠", "coupon", "85折", "5%", "off", "first year",
                            "limited-time", "special", "优惠"]):
        return "通用优惠券"
    return "其他/未分类"

# ---------- run queries ----------
camp_cols, camp_rows = run(Q1)
cm_cols, cm_rows = run(Q2)   # couponname x ym
um_cols, um_rows = run(Q3)   # unnamed discounted x ym
mix_cols, mix_rows = run(Q4)  # campaign x product

ci = {c: i for i, c in enumerate(camp_cols)}
cmi = {c: i for i, c in enumerate(cm_cols)}
umi = {c: i for i, c in enumerate(um_cols)}
mi = {c: i for i, c in enumerate(mix_cols)}

# peak month per campaign (named)
peak = {}
for r in cm_rows:
    name = r[cmi["couponname"]]
    ym = r[cmi["ym"]]
    cnt = r[cmi["cnt"]]
    if name not in peak or cnt > peak[name][1]:
        peak[name] = (ym, cnt)

# unnamed monthly
unnamed_month = {r[umi["ym"]]: r[umi["cnt"]] for r in um_rows}
tot_unnamed = sum(unnamed_month.values())

# named monthly totals
named_month = {}
for r in cm_rows:
    ym = r[cmi["ym"]]
    named_month[ym] = named_month.get(ym, 0) + r[cmi["cnt"]]

# dominant product per campaign (from mix)
dom_prod = {}
prod_by_camp = {}
for r in mix_rows:
    lab = r[mi["campaign_label"]]
    st = r[mi["subscriptiontype"]]
    cnt = r[mi["order_cnt"]]
    prod_by_camp.setdefault(lab, []).append((st, cnt))
for lab, lst in prod_by_camp.items():
    lst.sort(key=lambda x: -x[1])
    dom_prod[lab] = lst[0][0]
    # also human readable list
    prod_by_camp[lab] = lst

# ---------- build workbook ----------
wb = Workbook()
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def style_header(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HEAD_FILL; cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

def autosize(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

# Sheet 1: 活动清单
ws1 = wb.active
ws1.title = "活动清单"
ws1.append(["类别", "活动名称(couponname)", "订单数", "付费人数", "首单时间", "末单时间",
            "峰值月份", "平均成交价(元)", "平均折扣%", "主要产品"])
# campaign rows already sorted by order_cnt desc
for r in camp_rows:
    label = r[ci["campaign_label"]]
    order_cnt = r[ci["order_cnt"]]
    user_cnt = r[ci["user_cnt"]]
    first_o = r[ci["first_order"]]
    last_o = r[ci["last_order"]]
    avg_paid = r[ci["avg_paid"]]
    avg_disc = r[ci["avg_discount_pct"]]
    is_unnamed = (label == "未命名折扣/直接降价")
    pk = peak.get(label, ("-", 0))[0] if not is_unnamed else "-"
    dom = dom_prod.get(label, "-")
    ws1.append([
        categorize(label), label, order_cnt, user_cnt,
        str(first_o), str(last_o), pk,
        float(avg_paid) if avg_paid is not None else None,
        float(avg_disc) if avg_disc is not None else None,
        dom,
    ])
style_header(ws1, 10)
autosize(ws1, [15, 34, 9, 10, 20, 20, 9, 14, 11, 14])
ws1.freeze_panes = "A2"
tot_orders = sum(r[ci["order_cnt"]] for r in camp_rows)
tot_disc = sum(r[ci["discounted_cnt"]] for r in camp_rows)
ws1.append(["合计", "（打折活动合计）", tot_orders, "", "", "", "", "", "", ""])
for c in range(1, 11):
    ws1.cell(row=ws1.max_row, column=c).font = Font(bold=True)

# Sheet 2: 月度趋势
ws2 = wb.create_sheet("月度趋势")
ws2.append(["月份", "命名活动订单数(有券号)", "直接降价订单数(无券号)", "活动合计"])
months = sorted(set(list(named_month.keys()) + list(unnamed_month.keys())))
for ym in months:
    n = named_month.get(ym, 0)
    u = unnamed_month.get(ym, 0)
    ws2.append([ym, n, u, n + u])
style_header(ws2, 4)
autosize(ws2, [10, 22, 22, 12])
ws2.freeze_panes = "A2"

# Sheet 3: 活动×产品
ws3 = wb.create_sheet("活动×产品")
ws3.append(["活动名称(couponname)", "产品(subscriptiontype)", "订单数",
            "平均成交价(元)", "2025标准价(元)", "对比标准价"])
for r in mix_rows:
    label = r[mi["campaign_label"]]
    st = r[mi["subscriptiontype"]]
    cnt = r[mi["order_cnt"]]
    al = r[mi["avg_list"]]
    ap = r[mi["avg_paid"]]
    std = STANDARD.get(st)
    ap_f = float(ap) if ap is not None else None
    delta = (round(ap_f - std, 2) if (ap_f is not None and std is not None) else None)
    ws3.append([label, st, cnt,
                float(ap) if ap is not None else None,
                std, delta])
style_header(ws3, 6)
autosize(ws3, [34, 24, 9, 14, 14, 12])
ws3.freeze_panes = "A2"

# Sheet 4: 口径说明
ws4 = wb.create_sheet("口径说明")
notes = [
    ["2025 打折销售活动清单 — 口径说明"],
    [""],
    ["数据表", "immdata.imt_subscriptiongoodsorder（订阅商品订单，业务库只读副本，日更）"],
    ["过滤", "COALESCE(isdeleted,0)=0；orderstatus='finished'；COALESCE(amountpaid,0)>0"],
    ["币种", "UPPER(currency)='CNY'。其他币种 amount/amountpaid 单位不稳（P008），不纳入"],
    ["时间窗", "createtime ∈ [2025-01-01, 2026-01-01)（自然年 2025；createtime=下单时间）"],
    ["标价/实付", "amount(元)；amountpaid/100(元；最小货币单位整数，P008)"],
    ["可度量打折", "amountpaid/100 < amount*0.98"],
    ["活动标识", "couponname；有券号=命名活动；无券号但打折=「未命名折扣/直接降价」"],
    ["关键说明", "amount=产品标准标价，amountpaid/100=活动折扣后实际成交；折扣=(amount-amountpaid/100)/amount，对所有 CNY 订单可直接度量。「活动×产品」表给出按产品对比标准价的差额"],
    ["2025 标准标价", "年费(yearly)579.6 / 月费(monthly)69 / Max年费1599 / Max月费199 / 家庭版约1244.88（非活动价）"],
    ["关于 588", "用户提到年费标价588；2025 实际年费标准价为 579.6，588 疑为更早/取整口径"],
    ["打折规模", f"2025 CNY 付费订单约 13.7 万；其中打折/活动订单 {tot_orders:,}（命名活动 {tot_orders - tot_unnamed}，直接降价 {tot_unnamed}；详见各表）"],
    ["主体", "订单行；付费人数 = COUNT(DISTINCT userid)"],
    ["交付", "T085 · 2026-10-26 · 脚本 scripts/export_t085_sales_discount_2025.py"],
]
for row in notes:
    ws4.append(row)
ws4.cell(row=1, column=1).font = Font(bold=True, size=13)
for r in range(3, len(notes) + 1):
    ws4.cell(row=r, column=1).font = Font(bold=True)
autosize(ws4, [14, 92])

os.makedirs(OUT_DIR, exist_ok=True)
wb.save(OUT_XLSX)
print("SAVED:", OUT_XLSX)
print("campaigns:", len(camp_rows), "| named months:", len(named_month), "| unnamed months:", len(unnamed_month), "| mix rows:", len(mix_rows))
print("total activity orders:", tot_orders, "| total measurably-discounted:", tot_disc)
