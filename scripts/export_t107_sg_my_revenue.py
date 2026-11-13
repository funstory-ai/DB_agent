"""T107: SG/MY revenue trend, last 12 months (2025-11..2026-11), Beijing month.

Attribution: paid orders (imt_subscriptiongoodsorder, finished + paid per P013)
  -> imt_deviceinfo (userid -> deviceid)
  -> imm_regional_activation (user's dominant real_geo, most-frequent)
Revenue: (amountpaid/100) * exchangerate -> CNY (amountpaid is in minor units / cents).
Buckets: SG, MY, COMBINED(SG+MY), NO_GEO (mobile / no deviceinfo -> excluded from SG/MY), OTHER.
VPN noise mitigated by dominant-geo-per-user. Mobile undercount is explicit (NO_GEO).
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query
import openpyxl
from openpyxl.styles import Font, Alignment

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
         date_trunc('month', date_add(hour, 8, createtime)) AS bj_mon,
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

# ---- Q1: revenue by month x bucket x currency ----
sql_rev = CTES + f"""
SELECT p.bj_mon, {bucket_case()} AS bucket, UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN p.amountpaid>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0 AS amt_major,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0
           * MAX(COALESCE(x.rate,0)) AS amt_cny
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT currency, exchangerate AS rate FROM immdata.exchangerates) x
  ON x.currency = UPPER(p.currency)
GROUP BY p.bj_mon, bucket, UPPER(p.currency)
ORDER BY p.bj_mon, bucket, currency
"""
print("== running revenue query (heavy join) ==")
cols, rows = q(sql_rev)
print("cols:", cols, "rows:", len(rows))

# ---- Q2: distinct paid users by month x bucket ----
sql_users = CTES + f"""
SELECT p.bj_mon, {bucket_case()} AS bucket, COUNT(DISTINCT p.userid) AS paid_users
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
GROUP BY p.bj_mon, bucket
ORDER BY p.bj_mon, bucket
"""
print("== running users query ==")
ucols, urows = q(sql_users)
print("ucols:", ucols, "urows:", len(urows))

# ---- aggregate in Python ----
from collections import defaultdict
# month -> bucket -> currency -> dict
rev = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
orders = defaultdict(lambda: defaultdict(int))
cash_orders = defaultdict(lambda: defaultdict(int))
for mon, bucket, cur, o, co, amaj, acny in rows:
    rev[mon][bucket][cur] += float(acny or 0)
    orders[mon][bucket] += o
    cash_orders[mon][bucket] += co

users = defaultdict(lambda: defaultdict(int))
for mon, bucket, pu in urows:
    users[mon][bucket] = pu

months = sorted(rev.keys())
def cny(mon, bucket):
    return sum(rev[mon].get(bucket, {}).values())
def combined(mon):
    return cny(mon, 'SG') + cny(mon, 'MY')

print("\n=== MONTH | SG¥ | MY¥ | COMBINED¥ | SG+MY orders | SG users | MY users | NO_GEO¥ ===")
for m in months:
    print(f"{str(m)[:10]} | {cny(m,'SG'):,.0f} | {cny(m,'MY'):,.0f} | {combined(m):,.0f} | "
          f"{orders[m]['SG']+orders[m]['MY']:,} | {users[m].get('SG',0):,} | {users[m].get('MY',0):,} | {cny(m,'NO_GEO'):,.0f}")

# currency mix for SG+MY (validation)
print("\n=== currency mix for SG+MY combined (validation) ===")
mix = defaultdict(float)
for m in months:
    for cur, v in rev[m].get('SG', {}).items(): mix[cur]+=v
    for cur, v in rev[m].get('MY', {}).items(): mix[cur]+=v
for cur, v in sorted(mix.items(), key=lambda x:-x[1]):
    print(f"  {cur}: {v:,.0f} CNY")

# ---- write Excel ----
wb = openpyxl.Workbook()
ws = wb.active; ws.title = "月度收入_SG_MY"
hdr = ["月份","SG收入¥","MY收入¥","SG+MY合计¥","SG付费单数","MY付费单数",
       "SG+MY付费单数","SG付费用户","MY付费用户","无地理(移动端漏算)¥","其它地区¥"]
ws.append(hdr)
for c in range(1, len(hdr)+1):
    ws.cell(1,c).font = Font(bold=True)
for m in months:
    ws.append([str(m)[:10], round(cny(m,'SG'),2), round(cny(m,'MY'),2), round(combined(m),2),
               orders[m].get('SG',0), orders[m].get('MY',0),
               orders[m].get('SG',0)+orders[m].get('MY',0),
               users[m].get('SG',0), users[m].get('MY',0),
               round(cny(m,'NO_GEO'),2), round(cny(m,'OTHER'),2)])

# sheet: 分币种
ws2 = wb.create_sheet("分币种_SG_MY")
ws2.append(["月份","地区","币种","收入¥","付费单数"])
for c in range(1,6): ws2.cell(1,c).font = Font(bold=True)
for m in months:
    for bucket in ('SG','MY'):
        for cur, v in sorted(rev[m].get(bucket, {}).items(), key=lambda x:-x[1]):
            ws2.append([str(m)[:10], bucket, cur, round(v,2), cash_orders[m].get(bucket,0)])

# sheet: 结论与口径
ws3 = wb.create_sheet("结论与口径")
notes = [
 ["SG/MY 近12个月收入趋势（按用户主导 real_geo 归属，人民币）"],
 [""],
 ["口径:"],
 ["1. 付费订单 = imt_subscriptiongoodsorder 中 orderstatus='finished' 且 (amountpaid>0 或 兑换码 ordertype='code' 或 subscriptiontype 以 'onetime' 开头)，剔除 isdeleted。"],
 ["2. 地区归属 = 订单 userid -> imt_deviceinfo 取 deviceid -> imm_regional_activation 取该用户最常出现的 real_geo（主导国家）。"],
 ["3. VPN 噪声处理：同一用户若偶尔出现在其它国家，取出现次数最多的国家，稀释偶发 VPN 尖峰。"],
 ["4. 移动端缺口：iOS/Android 设备号大多不在 imt_deviceinfo，这部分付费用户取不到国家 -> 归入 NO_GEO（不计入 SG/MY），故 SG/MY 收入为下界、非全量。"],
 ["5. 金额 = (amountpaid/100) × exchangerates(以CNY=1)，amountpaid 为最小货币单位(分)。汇率表覆盖 SGD/MYR/USD/CNY 等全部相关币种。"],
 ["6. 时间窗：订单 createtime 按北京时间(createtime+8h)取月份，区间 2025-11 ~ 2026-11。"],
 ["7. SG/MY 合计 = SG + MY；OTHER = 非 SG/MY 且能取到国家的；NO_GEO = 取不到国家的(主要为移动端)。"],
]
for line in notes:
    ws3.append(line)
ws3.cell(1,1).font = Font(bold=True)

path = OUT / "sg_my_monthly_revenue_202511_202611.xlsx"
wb.save(path)
print("\nSAVED:", path)
