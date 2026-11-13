"""T107e: currency mix of PAYING USERS attributed to SG / MY region
(dominant real_geo). Shows that currency is driven by payment channel,
not geography. Covers both current year (2025-11..2026-11) and
prior year (2024-11..2025-11) in one pass (shared geo mapping).
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

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
WITH paid_all AS (
  SELECT userid,
         CASE WHEN createtime >= TIMESTAMP '2025-11-01 00:00:00'
                   AND createtime <  TIMESTAMP '2026-12-01 00:00:00' THEN 'CY'
              WHEN createtime >= TIMESTAMP '2024-11-01 00:00:00'
                   AND createtime <  TIMESTAMP '2025-12-01 00:00:00' THEN 'LY'
              ELSE NULL END AS yr,
         currency, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
         OR subscriptiontype LIKE 'onetime%')
    AND createtime >= TIMESTAMP '2024-11-01 00:00:00'
    AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
),
paying_users AS (SELECT DISTINCT userid FROM paid_all),
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

sql = CTES + f"""
SELECT p.yr, {bucket_case()} AS bucket, UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN p.amountpaid>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0
           * MAX(COALESCE(x.rate,0)) AS amt_cny
FROM paid_all p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT currency, exchangerate AS rate FROM immdata.exchangerates) x
  ON x.currency = UPPER(p.currency)
WHERE p.yr IS NOT NULL
GROUP BY p.yr, bucket, UPPER(p.currency)
ORDER BY p.yr, bucket, amt_cny DESC
"""
print("== running currency-mix query (shared geo mapping) ==")
cols, rows = q(sql)
print("rows:", len(rows))

from collections import defaultdict
data = {}
for yr, bucket, cur, o, co, acny in rows:
    data.setdefault(yr, {}).setdefault(bucket, {}).setdefault(
        cur, {"orders":0,"cash":0,"cny":0.0})
    d = data[yr][bucket][cur]
    d["orders"] += o; d["cash"] += co; d["cny"] += float(acny or 0)

# ---- build Excel ----
wb = openpyxl.Workbook()
hdr_fill = PatternFill("solid", fgColor="D9D9D9")
def style_header(ws):
    for c in range(1, 6):
        ws.cell(1, c).font = Font(bold=True); ws.cell(1, c).fill = hdr_fill
        ws.cell(1, c).alignment = Alignment(horizontal="center")

# one sheet per year, bucket rows (SG, MY) x currency
for yr, label in [("CY","今年(2025-11~2026-11)"), ("LY","去年(2024-11~2025-11)")]:
    ws = wb.create_sheet(f"货币构成_{label}")
    ws.append(["地区","币种","付费单数","付费笔数(实付>0)","收入¥"]); style_header(ws)
    for bucket in ("SG","MY"):
        curd = data[yr].get(bucket, {})
        tot_o = sum(v["orders"] for v in curd.values())
        tot_c = sum(v["cash"] for v in curd.values())
        tot_cny = sum(v["cny"] for v in curd.values())
        if tot_o == 0:
            continue
        ws.append([f"{bucket} (合计)", "", tot_o, tot_c, round(tot_cny,2)])
        ws.cell(ws.max_row,1).font = Font(bold=True)
        for cur, v in sorted(curd.items(), key=lambda x:-x[1]["cny"]):
            share = (v["cny"]/tot_cny*100) if tot_cny else 0
            ws.append([f"  {bucket}", cur, v["orders"], v["cash"], round(v["cny"],2)])
            ws.cell(ws.max_row, 5).number_format = '#,##0'
            # append share as comment-like column? add separate column
        # add share% in a 6th column header
    # add 占比% column header retroactively
    ws.insert_cols(6)
    ws.cell(1,6, "收入占比%"); ws.cell(1,6).font = Font(bold=True); ws.cell(1,6).fill = hdr_fill
    for r in range(2, ws.max_row+1):
        region = ws.cell(r,1).value
        if region and "合计" in str(region):
            ws.cell(r,6, 100.0)
        elif region and str(region).strip().startswith(("SG","MY")) and ws.cell(r,5).value not in (None,""):
            pass  # share filled below per-bucket
    # recompute share per bucket properly
    # simpler: iterate and set share based on its bucket total
    bucket_tot = {}
    for r in range(2, ws.max_row+1):
        reg = ws.cell(r,1).value
        if reg and "合计" in str(reg):
            bucket_tot[reg[0]] = ws.cell(r,5).value or 0
    for r in range(2, ws.max_row+1):
        reg = ws.cell(r,1).value
        if reg and str(reg).strip().startswith(("SG","MY")) and "合计" not in str(reg):
            b = str(reg).strip(); tot = bucket_tot.get(b,0)
            val = ws.cell(r,5).value or 0
            ws.cell(r,6, round(val/tot*100,1) if tot else 0)

# sheet: notes
ws4 = wb.create_sheet("结论与口径")
notes = [
 ["SG / MY 地区付费用户的货币构成（按用户主导 real_geo 归属；今年 & 去年）"],
 [""],
 ["关键结论: 币种由【支付渠道】决定，不随地理走。"],
 ["- 移动端(iOS App Store / Google Play)付费 -> 记本地币: SG 用户记 SGD，MY 用户记 MYR。"],
 ["- 网页/桌面(插件/Stripe 等)付费 -> 记 USD / CNY / TWD 等(按结账区域)，绝不可能是 SGD/MYR。"],
 ["- 因此同一 SG/MY 地区用户会同时出现多种币种，不能靠币种反推地区(见 P046 及前文)。"],
 [""],
 ["口径:"],
 ["1. 付费订单 = finished 且 (amountpaid>0 或 兑换码 code 或 onetime*)，剔除 isdeleted。"],
 ["2. 地区归属 = userid -> imt_deviceinfo -> imm_regional_activation 取该用户全历史最常出现的 real_geo(主导国家)。"],
 ["3. 移动端缺口: iOS/Android 设备号多不在 imt_deviceinfo -> 取不到国家者归入 NO_GEO，未在本表 SG/MY 内。"],
 ["4. 金额 = (amountpaid/100) × exchangerates(CNY=1)，amountpaid 为最小货币单位(分)，币种统一 UPPER(P046)。"],
 ["5. SG/MY 合计 = 该主导地区全部付费订单(含各币种)；占比为该币种占该地区收入的比例。"],
]
for line in notes: ws4.append(line)
ws4.cell(1,1).font = Font(bold=True)

# remove default first sheet if empty
if wb.sheetnames[0] == "Sheet" and wb["Sheet"].max_row == 0:
    del wb["Sheet"]

path = OUT / "sg_my_currency_mix_202411_202611.xlsx"
wb.save(path)
print("\nSAVED:", path)

# console summary
for yr, label in [("CY","今年(2025-11~2026-11)"), ("LY","去年(2024-11~2025-11)")]:
    print(f"\n=== {label} 货币构成 ===")
    for bucket in ("SG","MY"):
        curd = data[yr].get(bucket, {})
        tot_cny = sum(v["cny"] for v in curd.values())
        tot_o = sum(v["orders"] for v in curd.values())
        if tot_o == 0:
            print(f"  [{bucket}] 无数据"); continue
        print(f"  [{bucket}] 合计 ¥{tot_cny:,.0f} / {tot_o:,} 单:")
        for cur, v in sorted(curd.items(), key=lambda x:-x[1]["cny"]):
            sh = v["cny"]/tot_cny*100 if tot_cny else 0
            cur_s = str(cur) if cur is not None else "(空/NULL)"
            print(f"     {cur_s:<14} {v['orders']:>7,} 单  ¥{v['cny']:>12,.0f}  ({sh:4.1f}%)")
