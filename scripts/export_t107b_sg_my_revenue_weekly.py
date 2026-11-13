"""T107b: SG/MY revenue trend by WEEK (Monday-start), last 12 months (2025-11..2026-11),
Beijing time. Same attribution as T107 (paid orders -> user -> device -> dominant real_geo).

Buckets: SG, MY, COMBINED(SG+MY), NO_GEO (mobile / no deviceinfo), OTHER.
Revenue: (amountpaid/100) * exchangerate -> CNY (amountpaid is in minor units / cents).
VPN noise mitigated by dominant-geo-per-user. Mobile undercount explicit (NO_GEO).
First/last week flagged as 不完整 (partial) and excluded from trend judgment.
Also emits a monthly-reference sheet (weeks grouped by month-of-Monday, approximate).
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query
import openpyxl
from openpyxl.styles import Font, Alignment
from datetime import date, timedelta

OUT = Path("output/sg_my_revenue")
OUT.mkdir(parents=True, exist_ok=True)

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

CTES = """
WITH paid AS (
  SELECT userid,
         date_trunc('week', date_add(hour, 8, createtime)) AS bj_week,
         currency, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
         OR subscriptiontype LIKE 'onetime%')
    AND createtime >= TIMESTAMP '2025-11-01 00:00:00'
    AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
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

# ---- Q1: revenue by week x bucket x currency ----
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
print("== running weekly revenue query (heavy join) ==")
cols, rows = q(sql_rev)
print("cols:", cols, "rows:", len(rows))

# ---- Q2: distinct paid users by week x bucket ----
sql_users = CTES + f"""
SELECT p.bj_week, {bucket_case()} AS bucket, COUNT(DISTINCT p.userid) AS paid_users
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
GROUP BY p.bj_week, bucket
ORDER BY p.bj_week, bucket
"""
print("== running weekly users query ==")
ucols, urows = q(sql_users)
print("ucols:", ucols, "urows:", len(urows))

# ---- aggregate in Python ----
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

# partial-week flags (first & last natural weeks are incomplete at the 12-month edges)
first_wk, last_wk = weeks[0], weeks[-1]

print("\n=== WEEK(Mon) | SG¥ | MY¥ | COMBINED¥ | SG+MY orders | SG users | MY users | NO_GEO¥ | flag ===")
for w in weeks:
    flag = ""
    if w == first_wk: flag = "起始不完整"
    elif w == last_wk: flag = "末尾不完整"
    print(f"{str(w)[:10]} | {cny(w,'SG'):,.0f} | {cny(w,'MY'):,.0f} | {combined(w):,.0f} | "
          f"{orders[w]['SG']+orders[w]['MY']:,} | {users[w].get('SG',0):,} | {users[w].get('MY',0):,} | "
          f"{cny(w,'NO_GEO'):,.0f} | {flag}")

# currency mix for SG+MY (validation)
print("\n=== currency mix for SG+MY combined (validation) ===")
mix = defaultdict(float)
for w in weeks:
    for cur, v in rev[w].get('SG', {}).items(): mix[cur]+=v
    for cur, v in rev[w].get('MY', {}).items(): mix[cur]+=v
for cur, v in sorted(mix.items(), key=lambda x:-x[1]):
    print(f"  {cur}: {v:,.0f} CNY")

# ---- write Excel ----
wb = openpyxl.Workbook()
ws = wb.active; ws.title = "周收入_SG_MY"
hdr = ["周(周一)","SG收入¥","MY收入¥","SG+MY合计¥","SG付费单数","MY付费单数",
       "SG+MY付费单数","SG付费用户","MY付费用户","无地理(移动端漏算)¥","其它地区¥","备注"]
ws.append(hdr)
for c in range(1, len(hdr)+1):
    ws.cell(1,c).font = Font(bold=True)
for w in weeks:
    note = ""
    if w == first_wk: note = "起始不完整(部分天数在窗外汇总)"
    elif w == last_wk: note = "末尾不完整(数据截至~11-09)"
    ws.append([str(w)[:10], round(cny(w,'SG'),2), round(cny(w,'MY'),2), round(combined(w),2),
               orders[w].get('SG',0), orders[w].get('MY',0),
               orders[w].get('SG',0)+orders[w].get('MY',0),
               users[w].get('SG',0), users[w].get('MY',0),
               round(cny(w,'NO_GEO'),2), round(cny(w,'OTHER'),2), note])
# 4-week moving avg helper column? add a small summary block below
ws.append([])
ws.append(["近4周滚动均值(剔除不完整周):"])
ws.cell(ws.max_row,1).font = Font(bold=True)
# compute 4-week trailing avg on complete weeks (exclude first/last)
complete = [w for w in weeks if w not in (first_wk, last_wk)]
def trailing_avg(bucket, n=4):
    if len(complete) < n: return None
    lastn = complete[-n:]
    return sum(combined(w) if bucket=='COMBINED' else cny(w,bucket) for w in lastn)/n
for label, b in [("SG",'SG'),("MY",'MY'),("SG+MY",'COMBINED')]:
    av = trailing_avg(b)
    ws.append([f"  {label} 近4周均", round(av,2) if av is not None else "N/A"])
    ws.cell(ws.max_row,1).font = Font(italic=True)

# sheet: 分币种 by week
ws2 = wb.create_sheet("分币种_周_SG_MY")
ws2.append(["周(周一)","地区","币种","收入¥","付费单数"])
for c in range(1,6): ws2.cell(1,c).font = Font(bold=True)
for w in weeks:
    for bucket in ('SG','MY'):
        for cur, v in sorted(rev[w].get(bucket, {}).items(), key=lambda x:-x[1]):
            ws2.append([str(w)[:10], bucket, cur, round(v,2), cash_orders[w].get(bucket,0)])

# sheet: 月度对照 (weeks grouped by month-of-Monday, approximate)
ws3 = wb.create_sheet("月度对照(周归并)")
ws3.append(["月份(周一起算归并)","SG收入¥","MY收入¥","SG+MY合计¥","SG+MY付费单数","无地理¥"])
for c in range(1,7): ws3.cell(1,c).font = Font(bold=True)
mon_rev = defaultdict(lambda: defaultdict(float))
mon_ord = defaultdict(int)
mon_nogeo = defaultdict(float)
for w in weeks:
    mkey = f"{w.year}-{w.month:02d}"
    mon_rev[mkey]['SG'] += cny(w,'SG')
    mon_rev[mkey]['MY'] += cny(w,'MY')
    mon_ord[mkey] += orders[w].get('SG',0)+orders[w].get('MY',0)
    mon_nogeo[mkey] += cny(w,'NO_GEO')
for mk in sorted(mon_rev.keys()):
    ws3.append([mk, round(mon_rev[mk]['SG'],2), round(mon_rev[mk]['MY'],2),
                round(mon_rev[mk]['SG']+mon_rev[mk]['MY'],2), mon_ord[mk], round(mon_nogeo[mk],2)])
ws3.append([])
ws3.append(["注: 跨月周按该周周一所在月归并，为近似值，精确月度见月度版交付。"])

# sheet: 结论与口径
ws4 = wb.create_sheet("结论与口径")
notes = [
 ["SG/MY 近12个月收入趋势（按周，周一起算；按用户主导 real_geo 归属，人民币）"],
 [""],
 ["口径:"],
 ["1. 付费订单 = imt_subscriptiongoodsorder 中 orderstatus='finished' 且 (amountpaid>0 或 兑换码 ordertype='code' 或 subscriptiontype 以 'onetime' 开头)，剔除 isdeleted。"],
 ["2. 地区归属 = 订单 userid -> imt_deviceinfo 取 deviceid -> imm_regional_activation 取该用户最常出现的 real_geo（主导国家）。"],
 ["3. VPN 噪声处理：同一用户若偶尔出现在其它国家，取出现次数最多的国家，稀释偶发 VPN 尖峰。"],
 ["4. 移动端缺口：iOS/Android 设备号大多不在 imt_deviceinfo，这部分付费用户取不到国家 -> 归入 NO_GEO（不计入 SG/MY），故 SG/MY 收入为下界、非全量。"],
 ["5. 金额 = (amountpaid/100) × exchangerates(以CNY=1)，amountpaid 为最小货币单位(分)。"],
 ["6. 时间窗：订单 createtime 按北京时间(createtime+8h)取所在周(周一为起点)，区间 2025-11 ~ 2026-11。"],
 ["7. 不完整周：首周(部分天数在窗外汇总)与末周(数据截至~11-09)已标记为不完整，不参与趋势判断。"],
 ["8. SG/MY 合计 = SG + MY；OTHER = 非 SG/MY 且能取到国家的；NO_GEO = 取不到国家的(主要为移动端)。"],
 ["9. 周粒度样本量小(SG+MY 约 ¥2.5万/周)，单周波动大；看趋势请用 4 周滚动均值或月度对照，绝对值噪声较高。"],
]
for line in notes:
    ws4.append(line)
ws4.cell(1,1).font = Font(bold=True)

path = OUT / "sg_my_weekly_revenue_202511_202611.xlsx"
wb.save(path)
print("\nSAVED:", path)
