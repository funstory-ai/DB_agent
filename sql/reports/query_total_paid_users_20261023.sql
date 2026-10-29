-- 总付费用户（累计 lifetime，含已流失/过期会员）：口径见任务 T082
-- 付费定义（P013）：orderstatus='finished' 且 ( amountpaid>0 或 兑换码 )
--   兑换码 = LOWER(ordertype)='code' 或 subscriptiongoodssnap 里 "SubscriptionType":"onetime*"
-- 主体（P018-D）：订单 userid；同一账号多设备只算 1 人；userid 不为空
-- 排除订单软删 COALESCE(isdeleted,0)=0；refunded 不计入付费（与 P013 一致）
-- 不限制时间窗 = 累计至今；同一账号多笔付费订单只算 1 个用户（P044 同源同查询）
WITH paid_users AS (
  SELECT
    o.userid,
    MAX(CASE WHEN COALESCE(o.amountpaid,0) > 0 THEN 1 ELSE 0 END) AS has_cash,
    MAX(CASE WHEN LOWER(o.ordertype)='code'
              OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
             THEN 1 ELSE 0 END) AS has_code
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted,0) = 0
    AND o.orderstatus = 'finished'
    AND o.userid IS NOT NULL
    AND (
      COALESCE(o.amountpaid,0) > 0
      OR LOWER(o.ordertype)='code'
      OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
    )
  GROUP BY o.userid
)
SELECT
  COUNT(*)                                                            AS total_paid_users,
  -- 账号仍有效（imt_userinfo 未软删）的子集，对应“当前有效”口径
  SUM(CASE WHEN COALESCE(u.isdeleted,0)=0 THEN 1 ELSE 0 END)          AS acct_not_deleted,
  -- 账号已软删或找不到（仍付过费，但账户不再有效）
  SUM(CASE WHEN COALESCE(u.isdeleted,0)<>0 OR u.id IS NULL THEN 1 ELSE 0 END) AS acct_deleted_or_missing,
  -- 付费路径拆分（可重叠：同一人可能既现金又兑换码）
  SUM(CASE WHEN p.has_cash=1 THEN 1 ELSE 0 END)                        AS users_with_cash,
  SUM(CASE WHEN p.has_code=1 THEN 1 ELSE 0 END)                        AS users_with_code,
  SUM(CASE WHEN p.has_cash=0 AND p.has_code=1 THEN 1 ELSE 0 END)       AS users_code_only
FROM paid_users p
LEFT JOIN immdata.imt_userinfo u ON u.id = p.userid;
