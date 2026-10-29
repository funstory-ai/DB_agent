-- T085: 2025 打折销售活动清单（CNY）
-- 大类: query | 需求: 去年(2025)做过哪些「标价打折」的销售活动
-- 口径:
--   表: immdata.imt_subscriptiongoodsorder；COALESCE(isdeleted,0)=0；orderstatus='finished'；COALESCE(amountpaid,0)>0
--   币种: UPPER(currency)='CNY'（其他币种 amount/amountpaid 单位不稳，P008，不纳入）
--   时间窗: createtime ∈ [2025-01-01, 2026-01-01)
--   标价: amount(元)；实付: amountpaid/100(元, 最小货币单位整数, P008)
--   打折(可度量): amountpaid/100 < amount*0.98
--   活动标识: couponname（有券号=命名活动；无券号但打折=「未命名折扣/直接降价」）
--   重要: 命名活动的促销价已写入 amount（故 amount≈实付，直接「实付<标价」 nearly 0）；
--         折扣幅度要看「活动×产品」表的成交价 vs 标准价（年费579.6/月费69/Max年费1599/Max月费199）
--   主体: 订单行；付费人数 = COUNT(DISTINCT userid)

-- Q1) 活动清单（按 couponname 聚合；无券号打折单列）
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
ORDER BY order_cnt DESC;

-- Q2) 命名活动 × 月份（用于峰值月份与月度趋势）
SELECT
  couponname,
  to_char(createtime, '%Y-%m') AS ym,
  COUNT(*) AS cnt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY' AND couponname IS NOT NULL
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
GROUP BY couponname, ym;

-- Q3) 未命名直接降价 × 月份
SELECT
  to_char(createtime, '%Y-%m') AS ym,
  COUNT(*) AS cnt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY'
  AND couponname IS NULL AND amount>0 AND amountpaid/100.0 < amount*0.98
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
GROUP BY ym;

-- Q4) 活动 × 产品(subscriptiontype) 明细（看成交价 vs 标准价）
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
SELECT
  campaign_label, subscriptiontype,
  COUNT(*) AS order_cnt,
  ROUND(AVG(amount),2) AS avg_list,
  ROUND(AVG(amountpaid/100.0),2) AS avg_paid
FROM base
WHERE couponname IS NOT NULL OR is_discounted=1
GROUP BY campaign_label, subscriptiontype
ORDER BY campaign_label, order_cnt DESC;
