from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def show(t, s):
    print("=" * 60, t)
    for r in query(s)[1][:10]:
        print(r)

show("refunded sample", """
SELECT id, userid, orderstatus, amountpaid, currency, createtime, updatetime
FROM immdata.imt_subscriptiongoodsorder
WHERE orderstatus = 'refunded' AND COALESCE(isdeleted,0)=0
  AND createtime >= '2026-08-01'
LIMIT 5
""")

show("kpi revenue 8/16", """
SELECT d1_revenue_cny, d7_revenue_cny, d30_revenue_cny, arpu_30d, arppu_30d, rev_per_paywall_user_30d
FROM immdata.imm_paywall_daily_kpi WHERE dt_bj = '2026-08-16'
""")

show("refund x cohort rough 8/16", """
SELECT
  COUNT(DISTINCT CASE WHEN o.orderstatus='refunded'
    AND o.createtime >= f.first_paywall_ts
    AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
    AND COALESCE(o.amountpaid,0)>0
    THEN o.userid END) AS d30_refund_users,
  SUM(CASE WHEN o.orderstatus='refunded'
    AND o.createtime >= f.first_paywall_ts
    AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
    AND COALESCE(o.amountpaid,0)>0
    THEN CASE WHEN UPPER(COALESCE(o.currency,'')) IN ('CNY','RMB') THEN o.amountpaid/100.0
         ELSE o.amountpaid * COALESCE(er.exchangerate,0)/100.0 END
    ELSE 0 END) AS d30_refund_cny
FROM immdata.imm_paywall_first_device f
LEFT JOIN immdata.imt_subscriptiongoodsorder o
  ON o.userid = f.userid AND COALESCE(o.isdeleted,0)=0
LEFT JOIN immdata.exchangerates er
  ON UPPER(COALESCE(o.currency,'')) = UPPER(COALESCE(er.currency,''))
WHERE f.first_paywall_dt_bj = '2026-08-16'
""")
