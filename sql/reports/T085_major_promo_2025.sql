-- T085 衍生：2025 大促活动清单（剔除达人/渠道/通用券/续费）
-- 范围：CNY、finished、实付>0、createtime ∈ [2025-01-01, 2026-01-01)
-- amount=标准标价；amountpaid/100=折扣后实付；折扣=(amount-amountpaid/100)/amount

-- Q1) 全部命名活动聚合（后续在脚本中拆分大促 / 排除）
SELECT
  couponname,
  COUNT(*)                                              AS order_cnt,
  COUNT(DISTINCT userid)                                AS user_cnt,
  MIN(createtime)                                       AS first_o,
  MAX(createtime)                                       AS last_o,
  arg_max(to_char(createtime,'%m'), c)                  AS peak_month,
  ROUND(AVG(amount),2)                                  AS avg_list,
  ROUND(AVG(amountpaid/100.0),2)                        AS avg_paid
FROM (
  SELECT couponname, createtime, userid, amount, amountpaid,
         COUNT(*) OVER (PARTITION BY couponname) AS c
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
    AND UPPER(currency)='CNY'
    AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
    AND couponname IS NOT NULL
) t
GROUP BY couponname, c
ORDER BY order_cnt DESC;

-- Q2) 活动 × 产品（折扣对比标准价）
SELECT
  couponname,
  subscriptiontype,
  COUNT(*)                                   AS n,
  ROUND(AVG(amount),2)                        AS list_avg,
  ROUND(AVG(amountpaid/100.0),2)             AS paid_avg,
  ROUND(1 - AVG(amountpaid/100.0)/AVG(amount), 4) AS disc_rate
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY'
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
  AND couponname IS NOT NULL
GROUP BY couponname, subscriptiontype;

-- Q3) 活动 × 月份（月度趋势）
SELECT
  couponname,
  to_char(createtime,'%Y-%m') AS ym,
  COUNT(*)                    AS cnt
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished' AND COALESCE(amountpaid,0)>0
  AND UPPER(currency)='CNY'
  AND createtime >= '2025-01-01' AND createtime < '2026-01-01'
  AND couponname IS NOT NULL
GROUP BY couponname, ym;
