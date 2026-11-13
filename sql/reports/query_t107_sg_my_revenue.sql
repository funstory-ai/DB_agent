-- T107: 新加坡/马来西亚 近12个月收入趋势（按用户主导 real_geo 归属，人民币）
-- 时间窗：订单 createtime 北京月，2025-11 ~ 2026-11（2026-11 为不完整月，不参与趋势）
-- 口径：
--   付费订单 = imt_subscriptiongoodsorder 中 orderstatus='finished' 且
--            (amountpaid>0 或 兑换码 ordertype='code' 或 subscriptiontype 以 'onetime' 开头)，剔除 isdeleted
--   地区归属 = 订单 userid -> imt_deviceinfo 取 deviceid -> imm_regional_activation 取该用户最常出现的 real_geo（主导国家）
--   金额 = (amountpaid/100) * exchangerates（CNY=1 基准）；amountpaid 为最小货币单位(分)
--   Buckets: SG / MY / COMBINED(SG+MY) / NO_GEO(移动端等取不到国家) / OTHER
-- 注意：real_geo 受 VPN/漫游影响，单用户常跨多国（抽样证实），主导地理已稀释但 SG/MY 绝对值带噪声；
--       移动端(iOS/安卓)设备号多不在 imt_deviceinfo -> 归入 NO_GEO，SG/MY 为下界非全量。

WITH paid AS (
  SELECT userid,
         date_trunc('month', date_add(hour, 8, createtime)) AS bj_mon,
         currency, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code'
         OR subscriptiontype LIKE 'onetime%')
    AND createtime >= TIMESTAMP '2025-11-01 00:00:00'
    AND createtime <  TIMESTAMP '2026-12-01 00:00:00'
),
paying_users AS (SELECT DISTINCT userid FROM paid),
ud AS (
  SELECT d.userid, d.deviceid
  FROM immdata.imt_deviceinfo d
  WHERE COALESCE(d.isdeleted,0)=0
    AND d.userid IN (SELECT userid FROM paying_users)
),
ug AS (
  SELECT ud.userid, a.real_geo, COUNT(*) AS cnt
  FROM ud JOIN immdata.imm_regional_activation a
    ON a.device_id = ud.deviceid
   AND a.created_ts >= DATE '2020-01-01' AND a.created_ts <= DATE '2026-12-31'
  GROUP BY ud.userid, a.real_geo
),
udom AS (
  SELECT userid, real_geo,
         ROW_NUMBER() OVER (PARTITION BY userid ORDER BY cnt DESC) AS rn
  FROM ug
)
-- 收入：月 × 地区 × 币种
SELECT p.bj_mon,
       CASE WHEN udom.real_geo IS NULL THEN 'NO_GEO'
            WHEN udom.real_geo IN ('SG','MY') THEN udom.real_geo
            ELSE 'OTHER' END AS bucket,
       UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN p.amountpaid>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0 AS amt_major,
       SUM(CASE WHEN p.amountpaid>0 THEN p.amountpaid ELSE 0 END)/100.0
           * MAX(COALESCE(x.rate,0)) AS amt_cny
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT currency, exchangerate AS rate FROM immdata.exchangerates) x
  ON x.currency = UPPER(p.currency)
GROUP BY p.bj_mon, bucket, UPPER(p.currency)
ORDER BY p.bj_mon, bucket, currency;

-- 付费用户数：月 × 地区
SELECT p.bj_mon,
       CASE WHEN udom.real_geo IS NULL THEN 'NO_GEO'
            WHEN udom.real_geo IN ('SG','MY') THEN udom.real_geo
            ELSE 'OTHER' END AS bucket,
       COUNT(DISTINCT p.userid) AS paid_users
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
GROUP BY p.bj_mon, bucket
ORDER BY p.bj_mon, bucket;
