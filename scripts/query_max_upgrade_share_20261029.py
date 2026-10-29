"""Max 会员「存量升级补差价」占比 + 金额分布（只读；复现 P047 证据）。

结论前置：
- Max 付费用户中，相当比例在买 Max 之前已有非 Max 会员付费单（= 从存量会员升级补差价）。
- Max 单的 amountpaid 跨度极大（¥1 ~ ¥数百万），含大量小额，证明记录的是「差价」而非 Max 全价。
- 因此 `membership='max'` 不能当「全新年费/新增收入」直接统计，须剔存量升级（P047）。

运行：在 scripts/ 目录下用隔离 python 执行。
"""
from db import query


def run(title, sql):
    print("\n==== " + title + " ====")
    cols, rows = query(sql)
    print("COLUMNS:", cols)
    for r in rows[:80]:
        print(r)


# 1) 升级自存量会员的 Max 用户占比（首笔 Max 单之前有非 Max 会员付费单）
run("Max 用户中升级自存量会员比例（P047 核心证据）", """
WITH max_first AS (
  SELECT userid, MIN(createtime) AS first_max_ct
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND membership='max' AND COALESCE(amountpaid,0)>0 AND userid IS NOT NULL
  GROUP BY userid
),
nonmax_before AS (
  SELECT DISTINCT o.userid
  FROM immdata.imt_subscriptiongoodsorder o
  JOIN max_first m ON o.userid = m.userid
  WHERE COALESCE(o.isdeleted,0)=0 AND o.orderstatus='finished'
    AND o.membership <> 'max'
    AND o.subscriptiontype IN ('monthly','yearly','two_yearly')
    AND COALESCE(o.amountpaid,0) > 0
    AND o.createtime < m.first_max_ct
)
SELECT
  (SELECT COUNT(*) FROM max_first) AS max_user_cnt,
  (SELECT COUNT(*) FROM nonmax_before) AS upgraded_from_prior_membership_cnt,
  ROUND((SELECT COUNT(*) FROM nonmax_before) * 100.0
        / NULLIF((SELECT COUNT(*) FROM max_first),0), 2) AS upgraded_pct
""")


# 2) Max 付费单 amountpaid 分桶（看差价小额是否存在）
run("Max 付费单 amountpaid 分桶（membership='max'）", """
SELECT
  CASE
    WHEN amountpaid <= 1000 THEN 'a <=10.00'
    WHEN amountpaid <= 10000 THEN 'b 10~100'
    WHEN amountpaid <= 50000 THEN 'c 100~500'
    WHEN amountpaid <= 100000 THEN 'd 500~1000'
    WHEN amountpaid <= 300000 THEN 'e 1000~3000'
    WHEN amountpaid <= 1000000 THEN 'f 3000~10000'
    ELSE 'g >10000' END AS bucket,
  subscriptiontype,
  COUNT(*) AS n,
  MIN(amountpaid) AS min_amt,
  MAX(amountpaid) AS max_amt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
  AND membership='max' AND COALESCE(amountpaid,0) > 0
GROUP BY bucket, subscriptiontype
ORDER BY subscriptiontype, bucket
""")
