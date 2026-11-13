"""T107c: SG/MY revenue from the CURRENCY angle (payment currency = SGD/MYR).
VPN-proof, covers app-store mobile users that real_geo attribution misses.
No join to deviceinfo/activation needed -> lightweight, no geo noise, no mobile undercount.
Grain: weekly (Monday-start, Beijing) primary; monthly aggregation as readable lens.
Focus: SGD, MYR (and SGD+MYR combined). Plus full currency-mix context.
Excludes crypto/unknown currencies with no exchange rate.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from db import query
import openpyxl
from openpyxl.styles import Font

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

sql = """
SELECT date_trunc('week', date_add(hour, 8, createtime)) AS bj_week,
       UPPER(o.currency) AS cur,
       COUNT(*) AS orders,
       SUM(CASE WHEN amountpaid>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN amountpaid>0 THEN amountpaid ELSE 0 END)/100.0
           * MAX(COALESCE(x.rate,0)) AS amt_cny
FROM immdata.imt_subscriptiongoodsorder o
LEFT JOIN (SELECT currency, exchangerate AS rate FROM immdata.exchangerates) x
  ON x.currency = UPPER(o.currency)
WHERE COALESCE(isdeleted,0)=0
  AND orderstatus='finished'
  AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
       OR subscriptiontype LIKE 'onetime%')
  AND createtime >= TIMESTAMP '2025-11-01 00:00:00'
  AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
GROUP BY bj_week, UPPER(o.currency)
HAVING MAX(COALESCE(x.rate,0)) > 0
ORDER BY bj_week, cur
"""
print("== running currency-by-week query ==")
cols, rows = q(sql)
print("cols:", cols, "rows:", len(rows))

from collections import defaultdict
# week -> currency -> (cny, orders)
data = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
for wk, cur, o, co, acny in rows:
    data[wk][cur][0] += float(acny or 0)
    data[wk][cur][1] += o

weeks = sorted(data.keys())
first_wk, last_wk = weeks[0], weeks[-1]

def cny(wk, cur):
    return data[wk].get(cur, [0.0,0])[0]
def ordc(wk, cur):
    return data[wk].get(cur, [0,0])[1]

print("\n=== WEEK(Mon) | SGD¥ | MYR¥ | SGD+MYR¥ | SGD ord | MYR ord | flag ===")
for w in weeks:
    flag = ""
    if w == first_wk: flag = "起始不完整"
    elif w == last_wk: flag = "末尾不完整"
    print(f"{str(w)[:10]} | {cny(w,'SGD'):,.0f} | {cny(w,'MYR'):,.0f} | {cny(w,'SGD')+cny(w,'MYR'):,.0f} | "
          f"{ordc(w,'SGD'):,} | {ordc(w,'MYR'):,} | {flag}")

# trailing 4w avg on complete weeks
complete = [w for w in weeks if w not in (first_wk, last_wk)]
def tavg(cur, n=4):
    if len(complete) < n: return None
    return sum(cny(w,cur) for w in complete[-n:])/n
print("\n=== trailing 4w avg (complete weeks) ===")
for cur in ('SGD','MYR'):
    print(f"  {cur}: {tavg(cur):,.0f}  (prior 4w: { (sum(cny(w,cur) for w in complete[-8:-4])/4 if len(complete)>=8 else float('nan')):,.0f})")

# monthly aggregation (weeks -> month of Monday)
mon = defaultdict(lambda: defaultdict(lambda: [0.0,0]))
for w in weeks:
    mk = f"{w.year}-{w.month:02d}"
    for cur, (v, o) in data[w].items():
        mon[mk][cur][0]+=v; mon[mk][cur][1]+=o

# ---- write Excel ----
wb = openpyxl.Workbook()

# Sheet 1: SGD/MYR weekly focus
ws = wb.active; ws.title = "SG_MY币种周趋势"
hdr = ["周(周一)","SGD收入¥","MYR收入¥","SGD+MYR合计¥","SGD单数","MYR单数","SGD+MYR单数","备注"]
ws.append(hdr)
for c in range(1,len(hdr)+1): ws.cell(1,c).font = Font(bold=True)
for w in weeks:
    flag = ""
    if w == first_wk: flag="起始不完整"
    elif w == last_wk: flag="末尾不完整"
    ws.append([str(w)[:10], round(cny(w,'SGD'),2), round(cny(w,'MYR'),2),
               round(cny(w,'SGD')+cny(w,'MYR'),2), ordc(w,'SGD'), ordc(w,'MYR'),
               ordc(w,'SGD')+ordc(w,'MYR'), flag])
ws.append([])
ws.append(["近4周滚动均值(剔除不完整周):"])
ws.cell(ws.max_row,1).font = Font(bold=True)
for cur in ('SGD','MYR','COMB'):
    if cur=='COMB':
        av = sum(cny(w,'SGD')+cny(w,'MYR') for w in complete[-4:])/4 if len(complete)>=4 else None
    else:
        av = tavg(cur)
    ws.append([f"  {cur} 近4周均", round(av,2) if av is not None else "N/A"])
    ws.cell(ws.max_row,1).font = Font(italic=True)

# Sheet 2: full currency mix monthly (readable context)
ws2 = wb.create_sheet("全币种月度对照")
ws2.append(["月份(周一起算归并)","币种","收入¥","单数"])
for c in range(1,5): ws2.cell(1,c).font = Font(bold=True)
for mk in sorted(mon.keys()):
    for cur in sorted(mon[mk].keys(), key=lambda x:-mon[mk][x][0]):
        ws2.append([mk, cur, round(mon[mk][cur][0],2), mon[mk][cur][1]])

# Sheet 3: full currency weekly detail (top currencies only to keep readable)
ws3 = wb.create_sheet("全币种周明细")
ws3.append(["周(周一)","币种","收入¥","单数"])
for c in range(1,5): ws3.cell(1,c).font = Font(bold=True)
# only include currencies that appear with meaningful total
cur_tot = defaultdict(float)
for w in weeks:
    for cur,(v,o) in data[w].items(): cur_tot[cur]+=v
top_cur = [c for c,t in sorted(cur_tot.items(), key=lambda x:-x[1]) if t>=1000][:20]
for w in weeks:
    for cur in top_cur:
        if cur in data[w]:
            ws3.append([str(w)[:10], cur, round(data[w][cur][0],2), data[w][cur][1]])

# Sheet 4: conclusions
ws4 = wb.create_sheet("结论与口径")
notes = [
 ["SG/MY 收入 —— 货币视角（支付币种 SGD/MYR），按周(周一)，人民币"],
 [""],
 ["为什么另拉一版:"],
 ["1. 上一版(real_geo 主导国家)受 VPN 影响，且经 imt_deviceinfo 关联会漏掉 iOS/Android 移动端付费(取不到国家)。"],
 ["2. 订单支付币种由应用商店区域决定，与 IP 无关 -> VPN-proof；且苹果/谷歌商店的新马用户恰好记本地币种 SGD/MYR -> 正好补上移动端缺口。"],
 ["3. 因此本版是上一版的独立交叉校验：两者方向一致则可信，背离则说明差异来自 VPN/移动端口径。"],
 [""],
 ["口径:"],
 ["4. 付费订单 = imt_subscriptiongoodsorder 中 finished 且 (amountpaid>0 或 兑换码 或 onetime 订阅)，剔除 isdeleted。"],
 ["5. 金额 = (amountpaid/100) × exchangerates(以CNY=1)。仅保留有汇率的法币，剔除加密货币/未知币种(rate=0)。"],
 ["6. 时间窗：createtime+8h 北京时间取所在周(周一为起点)，2025-11 ~ 2026-11。"],
 [""],
 ["重要局限:"],
 ["7. SGD/MYR 总量很小(全窗 SGD≈¥1.7万、MYR≈¥0.9万，合计约¥2.6万/12个月)，周粒度极稀疏、单周常为0或仅1-2单 -> 周趋势噪声极大，请用月度或滚动均值看方向。"],
 ["8. 币种≠居民身份：SG/MY 居民在网页(Stripe)付的是 USD(不计入本版)，而持 SG/MY 商店账号的非居民也会记 SGD/MYR -> 本版是 SG/MY 应用商店消费的近似值，非严格地域收入。"],
 ["9. 不完整周(首/末)已标记，不参与趋势判断。"],
]
for line in notes:
    ws4.append(line)
ws4.cell(1,1).font = Font(bold=True)

path = OUT / "sg_my_revenue_by_currency_202511_202611.xlsx"
wb.save(path)
print("\nSAVED:", path)
