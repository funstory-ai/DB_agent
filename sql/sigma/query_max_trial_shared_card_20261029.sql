-- ============================================================================
-- Stripe Sigma SQL —— 查“一张卡开多个账号、各试一次”的羊毛模式
-- ============================================================================
-- ⚠️ 本文件是 **Stripe Sigma** 方言（Trino / Presto），不是 Databend SQL。
--    在 Stripe Dashboard → Sigma 里运行；不要在 Databend 里跑。
-- 关联任务：databend_sql 仓 T092（query_max_trial_abuse_20261028）
--
-- ⚠️ 列名要点（新版 Sigma / Trino 方言）：
--    - 客户字段统一叫 **customer_id**（不是 customer）：subscriptions / payment_methods / charges 都是。
--    - 卡指纹：payment_methods.**card_fingerprint**（同一张实体卡跨不同 customer 相同）。
--      last4 / brand 可能撞，fingerprint 才唯一，别用 last4 判定“同一张卡”。
--    - 试用信号：subscriptions.**trial_end** IS NOT NULL = 曾经/正在试用。
--
-- 要抓的模式（卡为中心，不是账号为中心）：
--   黑产不断开新账号，每个新号绑【同一张卡】再开试用。每个账号只试 1 次 →
--   按“账号≥N 次试用”过滤会漏掉。正确做法：在【全部试用】里按 card_fingerprint
--   聚合，找挂在很多不同 customer_id 上的卡。
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 【Sigma Query A · 主查询】全量试用里找“一张卡挂多个账号”
--   纯 Sigma 原生判定试用：subscriptions.trial_end IS NOT NULL。
--   不需要从 Databend 带任何名单，直接全扫。
--   关键指标 trial_customers_on_card：这张卡被多少个【不同账号】用来开试用。
-- ----------------------------------------------------------------------------
WITH trial_subs AS (
  SELECT s.id          AS subscription_id,
         s.customer_id AS customer_id
  FROM subscriptions AS s
  WHERE s.trial_end IS NOT NULL               -- Stripe 原生“有过试用”信号
),
cards AS (
  SELECT pm.customer_id,
         pm.card_fingerprint,
         pm.card_brand,
         pm.card_last4,
         pm.card_country,
         pm.card_exp_month,
         pm.card_exp_year
  FROM payment_methods AS pm
  WHERE pm.type = 'card'
    AND pm.customer_id IS NOT NULL
    AND pm.card_fingerprint IS NOT NULL
)
SELECT
  c.card_fingerprint,
  COUNT(DISTINCT ts.customer_id)     AS trial_customers_on_card,
  COUNT(DISTINCT ts.subscription_id) AS trial_subs_on_card,
  ARRAY_AGG(DISTINCT ts.customer_id)    AS customer_ids,
  ARRAY_AGG(DISTINCT ts.subscription_id) AS subscription_ids,
  MIN(c.card_brand)                  AS brand,
  MIN(c.card_last4)                  AS last4,
  MIN(c.card_country)                AS country
FROM trial_subs AS ts
JOIN cards      AS c ON c.customer_id = ts.customer_id
GROUP BY c.card_fingerprint
HAVING COUNT(DISTINCT ts.customer_id) > 1
ORDER BY trial_customers_on_card DESC
LIMIT 200;


-- ----------------------------------------------------------------------------
-- 【Sigma Query B · 只锁 Max】在 Query A 基础上限定“Max 试用”的订阅
--   若想严格只看 Max（而非所有 tier 的试用），把 Databend Step 0 导出的 Max 试用
--   subscriptionid 全集作为 IN 条件；其余不变。
--   ⚠️ 60k 全集无法内联进 IN()（限长/极慢），故全集不实际；优先用 Query A。
-- ----------------------------------------------------------------------------
WITH trial_subs AS (
  SELECT s.id          AS subscription_id,
         s.customer_id AS customer_id
  FROM subscriptions AS s
  WHERE s.id IN (
    'sub_xxx1', 'sub_xxx2'   -- ← 替换为 Databend Step 0 导出的 Max 试用 subscriptionid
  )
),
cards AS (
  SELECT pm.customer_id,
         pm.card_fingerprint,
         pm.card_brand,
         pm.card_last4,
         pm.card_country
  FROM payment_methods AS pm
  WHERE pm.type = 'card'
    AND pm.customer_id IS NOT NULL
    AND pm.card_fingerprint IS NOT NULL
)
SELECT
  c.card_fingerprint,
  COUNT(DISTINCT ts.customer_id)     AS max_trial_customers_on_card,
  COUNT(DISTINCT ts.subscription_id) AS max_trial_subs_on_card,
  ARRAY_AGG(DISTINCT ts.customer_id) AS customer_ids,
  MIN(c.card_brand)                  AS brand,
  MIN(c.card_last4)                  AS last4,
  MIN(c.card_country)                AS country
FROM trial_subs AS ts
JOIN cards      AS c ON c.customer_id = ts.customer_id
GROUP BY c.card_fingerprint
HAVING COUNT(DISTINCT ts.customer_id) > 1
ORDER BY max_trial_customers_on_card DESC
LIMIT 200;


-- ----------------------------------------------------------------------------
-- 【Sigma Query C · 复核】已知某 fingerprint，列出它上面所有账号与订阅
--   拿到 Query A/B 命中的 fingerprint 后，逐张卡展开看明细（含 Stripe email）。
-- ----------------------------------------------------------------------------
SELECT
  pm.customer_id                         AS customer_id,
  c.email,
  c.name,
  s.id                                  AS subscription_id,
  s.status,
  s.trial_end,
  pm.card_fingerprint,
  pm.card_brand,
  pm.card_last4,
  pm.card_country,
  pm.created                             AS card_attached_at
FROM payment_methods AS pm
JOIN subscriptions   AS s ON s.customer_id = pm.customer_id
LEFT JOIN customers  AS c ON c.id = pm.customer_id
WHERE pm.type = 'card'
  AND pm.card_fingerprint = '<填 Query A/B 命中的 fingerprint>'
  AND s.trial_end IS NOT NULL
ORDER BY pm.customer_id, s.created;


-- ============================================================================
-- 以下为 Databend 侧步骤（注释掉，只在 Databend 跑，不要在 Sigma 里跑）
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 【Databend Step 0】导出 Max 试用的 subscriptionid 全集（给 Query B 用）
--   口径：finished + amountpaid=0 + 非兑换码 + membership='max'（P013）。
--   这是“全部试用”，不是≥N次；一行一个订阅。
-- ----------------------------------------------------------------------------
-- SELECT DISTINCT subscriptionid
-- FROM immdata.imt_subscriptiongoodsorder
-- WHERE COALESCE(isdeleted,0)=0
--   AND orderstatus='finished'
--   AND COALESCE(amountpaid,0)=0
--   AND LOWER(ordertype) NOT IN ('code')          -- 排除兑换码（P013）
--   AND membership='max'
--   AND subscriptionid IS NOT NULL;


-- ----------------------------------------------------------------------------
-- 【Databend Step 1】复核某张共享卡上的订阅里有多少是 Max 试用
--   把 Query A/C 得到的 subscriptionid 列表粘进来，确认命中簇确实是 Max 试用。
-- ----------------------------------------------------------------------------
-- SELECT
--   COUNT(*)                                            AS total_subs,
--   COUNT_IF(LOWER(membership)='max'
--           AND COALESCE(amountpaid,0)=0
--           AND LOWER(ordertype) NOT IN ('code'))       AS max_trial_subs
-- FROM immdata.imt_subscriptiongoodsorder
-- WHERE subscriptionid IN ( /* Query A/C 得到的 subscriptionid 列表 */ );
