-- =====================================================================
-- Max 试用薅羊毛检测（T089）
-- 库：immdata（只读副本，日更，asof≈最近一次北京 01:00 同步）
-- 口径：
--   试用（P013）：orderstatus='finished' AND COALESCE(amountpaid,0)=0
--                 AND 非兑换码（ordertype<>'code' 且 snap 不含 onetime*）
--   Max 限定：LOWER(membership)='max'
--   重复试用：同一 userid 产生 >=2 笔 Max 试用单
--   突发(burst)：该 userid 的所有 Max 试用单落在 <=1 天内（秒/分钟级，
--                配合顺序 userid 段，呈脚本/批量注册特征）
--   纯羊毛：突发重复试用 且 全站（任意 membership）从未付费/兑换码
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Max 订单总览（分母确认）
-- ---------------------------------------------------------------------
SELECT
  SUM(CASE WHEN COALESCE(amountpaid,0)=0
           AND LOWER(COALESCE(ordertype,''))<>'code'
           AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
          THEN 1 ELSE 0 END) AS trial_orders,
  COUNT(DISTINCT CASE WHEN COALESCE(amountpaid,0)=0
           AND LOWER(COALESCE(ordertype,''))<>'code'
           AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
          THEN userid END) AS trial_users,
  SUM(CASE WHEN COALESCE(amountpaid,0)>0
           OR LOWER(COALESCE(ordertype,''))='code'
           OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
          THEN 1 ELSE 0 END) AS paid_or_code_orders,
  COUNT(DISTINCT CASE WHEN COALESCE(amountpaid,0)>0
           OR LOWER(COALESCE(ordertype,''))='code'
           OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
          THEN userid END) AS paid_or_code_users
FROM immdata.imt_subscriptiongoodsorder
WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
  AND LOWER(COALESCE(membership,''))='max';

-- ---------------------------------------------------------------------
-- 2) 每个 userid 的 Max 试用次数分布 + 是否曾付费 Max
-- ---------------------------------------------------------------------
WITH max_trials AS (
  SELECT userid, COUNT(*) AS n_trial,
         MIN(createtime) AS first_trial, MAX(createtime) AS last_trial
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND LOWER(COALESCE(membership,''))='max'
    AND COALESCE(amountpaid,0)=0
    AND LOWER(COALESCE(ordertype,''))<>'code'
    AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
  GROUP BY userid
),
ever_paid AS (
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND LOWER(COALESCE(membership,''))='max'
    AND (COALESCE(amountpaid,0)>0
         OR LOWER(COALESCE(ordertype,''))='code'
         OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%')
)
SELECT
  CASE WHEN t.n_trial=1 THEN '1'
       WHEN t.n_trial=2 THEN '2'
       WHEN t.n_trial=3 THEN '3'
       WHEN t.n_trial=4 THEN '4'
       WHEN t.n_trial BETWEEN 5 AND 9 THEN '5-9'
       ELSE '10+' END AS trial_bucket,
  COUNT(*) AS users,
  SUM(t.n_trial) AS trial_orders_in_bucket,
  COUNT(CASE WHEN p.userid IS NULL THEN 1 END) AS users_never_paid_max
FROM max_trials t
LEFT JOIN ever_paid p ON p.userid = t.userid
GROUP BY 1
ORDER BY CASE trial_bucket WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3
         WHEN '4' THEN 4 WHEN '5-9' THEN 5 ELSE 6 END;

-- ---------------------------------------------------------------------
-- 3) 重复试用（>=2）按间隔分类：突发 / 近距 / 长期
-- ---------------------------------------------------------------------
WITH max_trials AS (
  SELECT userid, COUNT(*) AS n_trial,
         MIN(createtime) AS first_trial, MAX(createtime) AS last_trial
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND LOWER(COALESCE(membership,''))='max'
    AND COALESCE(amountpaid,0)=0
    AND LOWER(COALESCE(ordertype,''))<>'code'
    AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
  GROUP BY userid
  HAVING COUNT(*)>=2
)
SELECT
  CASE WHEN date_diff('day', first_trial, last_trial) <= 1 THEN 'burst(<=1天)'
       WHEN date_diff('day', first_trial, last_trial) <= 30 THEN 'near(2-30天)'
       ELSE 'spread(>30天)' END AS span_class,
  COUNT(*) AS users,
  SUM(n_trial) AS trial_orders
FROM max_trials
GROUP BY 1 ORDER BY 1;

-- ---------------------------------------------------------------------
-- 4) 突发重复试用按首试日期聚类（识别批量/脚本特征）
-- ---------------------------------------------------------------------
WITH mt AS (
  SELECT userid, COUNT(*) AS n_trial,
         MIN(createtime) AS first_trial, MAX(createtime) AS last_trial,
         MIN(ordertype) AS o1, MAX(ordertype) AS o2
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND LOWER(COALESCE(membership,''))='max'
    AND COALESCE(amountpaid,0)=0
    AND LOWER(COALESCE(ordertype,''))<>'code'
    AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
  GROUP BY userid
  HAVING COUNT(*)>=2 AND date_diff('day', MIN(createtime), MAX(createtime)) <= 1
)
SELECT to_date(first_trial) AS day, n_trial,
       COUNT(*) AS users,
       MIN(userid) AS min_uid, MAX(userid) AS max_uid,
       MAX(o1)=MIN(o2) AS same_ordertype
FROM mt
GROUP BY day, n_trial
ORDER BY day, n_trial DESC;

-- ---------------------------------------------------------------------
-- 5) 纯羊毛党名单（突发重复试用 且 全站从未付费/兑换码）—— 可导出处置
-- ---------------------------------------------------------------------
WITH burst AS (
  SELECT userid, COUNT(*) AS n_trial,
         MIN(createtime) AS first_trial, MAX(createtime) AS last_trial
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND LOWER(COALESCE(membership,''))='max'
    AND COALESCE(amountpaid,0)=0
    AND LOWER(COALESCE(ordertype,''))<>'code'
    AND CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
  GROUP BY userid
  HAVING COUNT(*)>=2 AND date_diff('day', MIN(createtime), MAX(createtime)) <= 1
)
SELECT b.userid, b.n_trial, b.first_trial, b.last_trial
FROM burst b
LEFT JOIN (
  SELECT DISTINCT userid FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0
         OR LOWER(COALESCE(ordertype,''))='code'
         OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%')
) p ON p.userid=b.userid
WHERE p.userid IS NULL
ORDER BY b.first_trial;
