# -*- coding: utf-8 -*-
"""T125: MRR C列 SQL 深度验证
1) 补 n=28 算 202609
2) 时区测试：createtime +8h 与否的历史值对比
3) 与 datapack MRR C 列历史逐月对比
"""
import sys
sys.path.insert(0, r"H:\databend_sql\scripts")
from db import query

# datapack MRR 表 C 列历史值（T027 定稿）
DP = {202601:46508, 202602:47226, 202603:49159, 202604:49828, 202605:51123, 202606:52181}

BASE = """
WITH bounds AS (
SELECT DATEADD(month, n, CAST('2024-06-01' AS DATE)) AS as_of
FROM (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14
UNION ALL SELECT 15 UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24
UNION ALL SELECT 25 UNION ALL SELECT 26 UNION ALL SELECT 27 UNION ALL SELECT 28) t
),
member_orders AS (
SELECT userid, {CT} AS ct,
DATEADD(day, COALESCE(subscriptionday, 0), {CT}) AS cover_end
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted, 0) = 0 AND orderstatus = 'finished'
AND userid IS NOT NULL AND COALESCE(subscriptionday, 0) > 0
AND (COALESCE(amountpaid, 0) > 0
OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
OR LOWER(COALESCE(ordertype, '')) = 'code')
)
SELECT DATEADD(day, -1, b.as_of) AS month_end,
COUNT(DISTINCT m.userid) AS cnt
FROM bounds b INNER JOIN member_orders m
ON m.ct < b.as_of AND m.cover_end >= b.as_of
GROUP BY b.as_of ORDER BY b.as_of
"""

def run(ct_expr, label):
    cols, rows = query(BASE.format(CT=ct_expr))
    d = {}
    for me, cnt in rows:
        ym = me.year * 100 + me.month
        d[ym] = int(cnt)
    print("===", label, "===")
    print("ym     SQL值   datapack   差异")
    for ym in sorted(d):
        if ym >= 202601:
            dp = DP.get(ym)
            print(ym, d[ym], dp if dp else "-", (d[ym]-dp) if dp else "", sep="\t")
    return d

if __name__ == "__main__":
    d0 = run("createtime", "原版(createtime 直接比 date)")
    d8 = run("DATE_ADD(hour, 8, createtime)", "加8h(北京时间)")
    print()
    print("202609 值: 原版=", d0.get(202609), " 加8h=", d8.get(202609))
