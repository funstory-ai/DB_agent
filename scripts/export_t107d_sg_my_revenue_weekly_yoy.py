"""T107d: SG/MY revenue by WEEK for PRIOR-YEAR window (2024-11..2025-11),
same attribution as T107b (paid orders -> user -> device -> dominant real_geo,
all-history geo mapping = stable across years for clean YoY).
Then build a YoY comparison vs THIS-year weekly deliverable, aligned by
same calendar week (this-year Monday - 364 days = last-year Monday).

Output: output/sg_my_revenue/sg_my_weekly_revenue_yoy_202411_202511.xlsx
  sheet1: 去年同期周收入_SG_MY   (prior-year standalone, same layout as T107b)
  sheet2: YoY周对比             (this-year vs last-year, aligned by 364-day offset)
  sheet3: 月度对照(周归并)YoY    (month-of-Monday approx, both years)
  sheet4: 结论与口径
"""
import sys, time
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query
import openpyxl
from openpyxl.styles import Font

OUT = Path("output/sg_my_revenue")
OUT.mkdir(parents=True, exist_ok=True)
THIS_YEAR_XLSX = OUT / "sg_my_weekly_revenue_202511_202611.xlsx"

def q(sql, retries=6):
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i+1} ({d:.0f}s): {e}")
            time.sleep(d); d *= 2

# ---- prior-year order window ----
WIN_START = "2024-11-01 00:00:00"
WIN_END   = "2025-12-01 00:00:00"

CTES = f"""
WITH paid AS (
  SELECT userid,
         date_trunc('week', date_add(hour, 8, createtime)) AS bj_week,
         currency, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
         OR subscriptiontype LIKE 'onetime%')
    AND createtime >= TIMESTAMP '{WIN_START}'
    AND createtime <  TIMESTAMP '{WIN_END}'
),
paying_users AS (SELECT DISTINCT userid FROM paid),
ud AS (
  SELECT d.userid, d.deviceid
  FROM immdata.imt_deviceinfo d
  WHERE COALESCE(d.isdeleted,0)=0
    AND d.userid IN (SELECT userid FROM paying_users)
),
ug AS (
  SELECT ud.userid, a.real_geo, COUNT(*) AS cnt
  FROM ud JOIN immdata.imm_regional_activation a
    ON a.device_id = ud.deviceid
   AND a.created_ts >= DATE '2020-01-01' AND a.created_ts <= DATE '2026-12-31'
  GROUP BY ud.userid, a.real_geo
),
udom AS (
  SELECT userid, real_geo,
         ROW_NUMBER() OVER (PARTITION BY userid ORDER BY cnt DESC) AS rn
  FROM ug
)
"""

def bucket_case(col="udom.real_geo"):
    return (f"CASE WHEN {col} IS NULL THEN 'NO_GEO' "
            f"WHEN {col} IN ('SG','MY') THEN {col} ELSE 'OTHER' END")

sql_rev = CTES + f"""
SELECT p.bj_week, {bucket_case()} AS bucket, UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN p.amountpaid>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0 AS amt_major,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0
           * MAX(COALESCE(x.rate,0)) AS amt_cny
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT currency, exchangerate AS rate FROM immdata.exchangerates) x
  ON x.currency = UPPER(p.currency)
GROUP BY p.bj_week, bucket, UPPER(p.currency)
ORDER BY p.bj_week, bucket, currency
"""
print("== [prior-year] running weekly revenue query (heavy join) ==")
cols, rows = q(sql_rev)
print("cols:", cols, "rows:", len(rows))

sql_users = CTES + f"""
SELECT p.bj_week, {bucket_case()} AS bucket, COUNT(DISTINCT p.userid) AS paid_users
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
GROUP BY p.bj_week, bucket
ORDER BY p.bj_week, bucket
"""
print("== [prior-year] running weekly users query ==")
ucols, urows = q(sql_users)
print("ucols:", ucols, "urows:", len(urows))

from collections import defaultdict
rev = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
orders = defaultdict(lambda: defaultdict(int))
cash_orders = defaultdict(lambda: defaultdict(int))
for wk, bucket, cur, o, co, amaj, acny in rows:
    rev[wk][bucket][cur] += float(acny or 0)
    orders[wk][bucket] += o
    cash_orders[wk][bucket] += co

users = defaultdict(lambda: defaultdict(int))
for wk, bucket, pu in urows:
    users[wk][bucket] = pu

weeks = sorted(rev.keys())
def cny(wk, bucket):
    return sum(rev[wk].get(bucket, {}).values())
def combined(wk):
    return cny(wk, 'SG') + cny(wk, 'MY')

first_wk, last_wk = weeks[0], weeks[-1]
print("\n=== [prior-year] WEEK(Mon) | SG¥ | MY¥ | COMBINED¥ | notes ===")
for w in weeks:
    flag = ""
    if w == first_wk: flag = "起始不完整"
    elif w == last_wk: flag = "末尾不完整"
    print(f"{str(w)[:10]} | {cny(w,'SG'):,.0f} | {cny(w,'MY'):,.0f} | {combined(w):,.0f} | {flag}")

# ============ YoY comparison: read THIS-year xlsx ============
print("\n== reading THIS-year weekly xlsx ==")
wb_ty = openpyxl.load_workbook(THIS_YEAR_XLSX, data_only=True)
ws_ty = wb_ty["周收入_SG_MY"]
ty = {}  # week_str -> dict(SG, MY, COMB)
for r in ws_ty.iter_rows(values_only=True):
    if not r or not r[0] or not str(r[0]).startswith("20"):
        continue
    if isinstance(r[3], (int, float)) is False:
        continue
    wk = str(r[0])[:10]
    # cols: 周,SG,MY,COMB,SG单,MY单,SG+MY单,SG用户,MY用户,NO_GEO,OTHER,备注
    sg = float(r[1] or 0); my = float(r[2] or 0); comb = float(r[3] or 0)
    note = str(r[11] or "") if len(r) > 11 else ""
    ty[wk] = {"SG": sg, "MY": my, "COMB": comb, "note": note}
print(f"  this-year weeks loaded: {len(ty)}")

# map THIS-year week -> last-year counterpart (Monday - 364 days)
def yoy_pair(ty_wk_str):
    y, m, d = map(int, ty_wk_str.split("-"))
    import datetime
    ty_date = datetime.date(y, m, d)
    ly_date = ty_date - timedelta(days=364)
    return ly_date.strftime("%Y-%m-%d")

ly = {}  # week_str -> dict(SG,MY,COMB,note)
for w in weeks:
    wk = str(w)[:10]
    note = ""
    if w == first_wk: note = "起始不完整"
    elif w == last_wk: note = "末尾不完整"
    ly[wk] = {"SG": cny(w,'SG'), "MY": cny(w,'MY'), "COMB": combined(w), "note": note}

# ============ build combined workbook ============
wb = openpyxl.Workbook()
# sheet1: prior-year standalone
ws1 = wb.active; ws1.title = "去年同期周收入_SG_MY"
hdr1 = ["周(周一)","SG收入¥","MY收入¥","SG+MY合计¥","SG付费单数","MY付费单数",
        "SG+MY付费单数","SG付费用户","MY付费用户","无地理(移动端漏算)¥","其它地区¥","备注"]
ws1.append(hdr1)
for c in range(1, len(hdr1)+1):
    ws1.cell(1,c).font = Font(bold=True)
for w in weeks:
    note = ""
    if w == first_wk: note = "起始不完整(部分天数在窗外汇总)"
    elif w == last_wk: note = "末尾不完整(数据截至~11-09)"
    ws1.append([str(w)[:10], round(cny(w,'SG'),2), round(cny(w,'MY'),2), round(combined(w),2),
                orders[w].get('SG',0), orders[w].get('MY',0),
                orders[w].get('SG',0)+orders[w].get('MY',0),
                users[w].get('SG',0), users[w].get('MY',0),
                round(cny(w,'NO_GEO'),2), round(cny(w,'OTHER'),2), note])

# sheet2: YoY weekly comparison (this-year complete weeks aligned to last-year counterpart)
ws2 = wb.create_sheet("YoY周对比")
hdr2 = ["今年周(周一)","去年同期周(周一)","SG今年¥","SG去年¥","SG同比%",
        "MY今年¥","MY去年¥","MY同比%","合计今年¥","合计去年¥","合计同比%","备注"]
ws2.append(hdr2)
for c in range(1, len(hdr2)+1):
    ws2.cell(1,c).font = Font(bold=True)
def pct(a, b):
    if b is None or b == 0: return None
    return (a - b) / b * 100.0
# iterate this-year weeks (exclude its incomplete first/last by note), align to last-year
ty_first = sorted(ty.keys())[0]
ty_last = sorted(ty.keys())[-1]
rows_yoy = []
for ty_wk in sorted(ty.keys()):
    rec = ty[ty_wk]
    ly_wk = yoy_pair(ty_wk)
    ly_rec = ly.get(ly_wk)
    note = rec.get("note", "")
    # flag if counterpart missing or incomplete
    if ly_rec is None:
        ly_sg = ly_my = ly_comb = None
        note += " | 去年无对应周"
    else:
        ly_sg = ly_rec["SG"]; ly_my = ly_rec["MY"]; ly_comb = ly_rec["COMB"]
        if ly_rec["note"]:
            note += f" | 去年{ly_wk}不完整"
    rows_yoy.append((ty_wk, ly_wk, rec["SG"], ly_sg, rec["MY"], ly_my, rec["COMB"], ly_comb, note))
# also include last-year weeks that have no this-year counterpart (edges)
for ly_wk in sorted(ly.keys()):
    if ly_wk not in [yoy_pair(tw) for tw in ty.keys()]:
        lr = ly[ly_wk]
        rows_yoy.append((None, ly_wk, None, lr["SG"], None, lr["MY"], None, lr["COMB"],
                         "今年无对应周(边界)"))
for ty_wk, ly_wk, sg_t, sg_l, my_t, my_l, cb_t, cb_l, note in rows_yoy:
    ws2.append([
        ty_wk or "", ly_wk,
        round(sg_t,2) if sg_t is not None else None,
        round(sg_l,2) if sg_l is not None else None,
        round(pct(sg_t, sg_l),1) if (sg_t is not None and sg_l is not None) else None,
        round(my_t,2) if my_t is not None else None,
        round(my_l,2) if my_l is not None else None,
        round(pct(my_t, my_l),1) if (my_t is not None and my_l is not None) else None,
        round(cb_t,2) if cb_t is not None else None,
        round(cb_l,2) if cb_l is not None else None,
        round(pct(cb_t, cb_l),1) if (cb_t is not None and cb_l is not None) else None,
        note,
    ])

# sheet3: monthly approx YoY (month-of-Monday)
ws3 = wb.create_sheet("月度对照(周归并)YoY")
ws3.append(["月份(周一起算归并)","SG今年¥","SG去年¥","MY今年¥","MY去年¥","合计今年¥","合计去年¥"])
for c in range(1,8): ws3.cell(1,c).font = Font(bold=True)
# this-year monthly from ty xlsx monthly sheet
ty_mon = {}
ws_ty_m = wb_ty["月度对照(周归并)"]
for r in ws_ty_m.iter_rows(values_only=True):
    if not r or not r[0] or not str(r[0]).startswith("20"):
        continue
    ty_mon[str(r[0])[:7]] = {"SG": float(r[1] or 0), "MY": float(r[2] or 0),
                             "COMB": float(r[3] or 0)}
# last-year monthly from ly weeks grouped by month-of-Monday
ly_mon = defaultdict(lambda: defaultdict(float))
for w in weeks:
    mk = f"{w.year}-{w.month:02d}"
    ly_mon[mk]['SG'] += cny(w,'SG'); ly_mon[mk]['MY'] += cny(w,'MY')
all_mon = sorted(set(ty_mon.keys()) | set(ly_mon.keys()))
for mk in all_mon:
    t = ty_mon.get(mk, {"SG":0,"MY":0,"COMB":0})
    l = ly_mon.get(mk, {"SG":0,"MY":0})
    ws3.append([mk, round(t["SG"],2), round(l["SG"],2), round(t["MY"],2), round(l["MY"],2),
                round(t["COMB"],2), round(l["SG"]+l["MY"],2)])

# sheet4: notes
ws4 = wb.create_sheet("结论与口径")
notes = [
 ["SG/MY 去年同期(2024-11~2025-11) 按周收入 + 同比对照（按用户主导 real_geo 归属，人民币）"],
 [""],
 ["口径(与今年周版 T107b 完全一致):"],
 ["1. 付费订单 = finished 且 (amountpaid>0 或 兑换码 code 或 onetime*)，剔除 isdeleted。"],
 ["2. 地区归属 = userid -> imt_deviceinfo -> imm_regional_activation 取该用户全历史最常出现的 real_geo(主导国家)。"],
 ["3. 两年用同一套「用户归属国」映射(全历史主导 geo)，使 YoY 仅反映收入变化、geo 分配稳定，不被逐年 VPN 噪声干扰。"],
 ["4. VPN 噪声：取最常出现国家稀释偶发 VPN 尖峰；移动端缺口(NO_GEO)同今年版存在，SG/MY 为下界。"],
 ["5. 金额 = (amountpaid/100) × exchangerates(CNY=1)，amountpaid 为分(最小货币单位)。"],
 ["6. 时间窗：订单 createtime+8h 取所在周(周一为起点)，去年区间 2024-11 ~ 2025-11。"],
 ["7. 同比对齐：今年周一日期 − 364 天 = 去年同一日历周(均为周一)。边界周无对应者单独标注。"],
 ["8. 不完整周：首/末自然周(部分天数在窗外汇总/数据截至~11-09)标注为不完整，不参与同比判断。"],
 ["9. 月度对照按「周一起算归并到月」为近似值，仅用于跨年量级对照，非精确自然月。"],
 ["10. 同口径货币版(SGD/MYR 仅移动端)及今年月度完整版参见同目录其它交付文件。"],
]
for line in notes:
    ws4.append(line)
ws4.cell(1,1).font = Font(bold=True)

path = OUT / "sg_my_weekly_revenue_yoy_202411_202511.xlsx"
wb.save(path)
print("\nSAVED:", path)
print("\n=== 关键 YoY 摘要(今年完整周 vs 去年同周) ===")
for ty_wk, ly_wk, sg_t, sg_l, my_t, my_l, cb_t, cb_l, note in rows_yoy:
    if ty_wk and sg_l is not None and "不完整" not in (note or ""):
        ps = pct(cb_t, cb_l)
        print(f"{ty_wk} vs {ly_wk}: COMB {cb_t:,.0f} vs {cb_l:,.0f} ({ps:+.1f}%)  SG {pct(sg_t,sg_l):+.1f}%  MY {pct(my_t,my_l):+.1f}%")
