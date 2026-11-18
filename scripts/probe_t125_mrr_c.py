# -*- coding: utf-8 -*-
"""T125: 验证用户给的 MRR C列（有效订阅用户）SQL 是否正确。
原样跑用户 SQL，对比 datapack MRR 表 C 列历史值。"""
import sys
sys.path.insert(0, r"H:\databend_sql\scripts")
from db import query

SQL = r"""
WITH bounds AS (
SELECT DATEADD(month, n, CAST('2024-06-01' AS DATE)) AS as_of
FROM (
SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14
UNION ALL SELECT 15 UNION ALL SELECT 16 UNION ALL SELECT 17 UNION ALL SELECT 18 UNION ALL SELECT 19
UNION ALL SELECT 20 UNION ALL SELECT 21 UNION ALL SELECT 22 UNION ALL SELECT 23 UNION ALL SELECT 24
UNION ALL SELECT 25 UNION ALL SELECT 26 UNION ALL SELECT 27
) t
),
member_orders AS (
SELECT
userid,
createtime,
DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted, 0) = 0
AND orderstatus = 'finished'
AND userid IS NOT NULL
AND COALESCE(subscriptionday, 0) > 0
AND (
COALESCE(amountpaid, 0) > 0
OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
OR LOWER(COALESCE(ordertype, '')) = 'code'
)
)
SELECT
DATEADD(day, -1, b.as_of) AS month_end,
b.as_of AS as_of_exclusive,
COUNT(DISTINCT m.userid) AS active_member_userid_cnt
FROM bounds b
INNER JOIN member_orders m
ON m.createtime < b.as_of
AND m.cover_end >= b.as_of
GROUP BY b.as_of
ORDER BY b.as_of
"""

if __name__ == "__main__":
    try:
        cols, rows = query(SQL)
        print("列名:", cols)
        print("行数:", len(rows))
        print("month_end | as_of_exclusive | active_member_userid_cnt")
        for r in rows:
            print(r)
    except Exception as e:
        print("SQL 执行出错:", type(e).__name__, str(e)[:2000])
