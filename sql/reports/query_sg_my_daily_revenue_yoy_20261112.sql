-- T112: 新加坡/马来西亚 按天收入（今年 10/25-11/12 与去年同月日，北京自然日，人民币）
-- 口径与 T107 / T107d 完全一致，仅把时间粒度由「月/周」改为「北京自然日」：
--   付费订单 = imt_subscriptiongoodsorder 中 orderstatus='finished' 且
--            (amountpaid>0 或 兑换码 ordertype='code' 或 subscriptiontype LIKE 'onetime%')，剔除 isdeleted
--   地区归属（按 IP）= 订单 userid -> imt_deviceinfo.deviceid -> imm_regional_activation
--            取该用户全历史出现次数最多的 real_geo（主导国家，两年同一套映射，YoY 可比）
--   金额 = (amountpaid/100) * exchangerates.exchangerate（CNY=1 基准；amountpaid 为分）
--   Buckets: SG / MY / NO_GEO（移动端等取不到国家）/ OTHER；SG+MY = SG + MY
-- 注意：real_geo 受 VPN/漫游影响（T107 抽样证实碎片化），主导国家稀释噪声；
--       移动端设备号多不在 imt_deviceinfo -> NO_GEO，SG/MY 为下界非全量（P037）。
--       2026-11-12 为当天，业务表北京 01:00 日更、副本水位约 01:xx（P043 正常），该日不完整。
--
-- 占位符 {{LY_LO}} {{LY_HI}} {{TY_LO}} {{TY_HI}} 由 canonical 脚本按 --start / --end 推导后替换：
--   北京日 D 的 UTC 边界 = (D-1) 16:00:00 ~ D 16:00:00。
--   TY=今年窗口 / LY=去年同月日窗口；两段以 OR 拼接，避免把中间一年扫进来。
-- 段落标记 -- @Q_xxx 由 scripts/export_sg_my_daily_revenue_yoy.py 读取；@CTES 为其公共前置部分。

-- @Q_RATE  汇率维表核对（P046）
SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
FROM immdata.exchangerates
GROUP BY UPPER(currency)
ORDER BY currency;

-- @Q_ORDER_COVER  两段窗口付费订单的币种覆盖 + 汇率匹配缺口（P046：不得置 0 漏算）
SELECT UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(COALESCE(p.amountpaid,0))/100.0 AS amt_major,
       MAX(x.rate) AS rate,
       SUM(CASE WHEN x.rate IS NULL THEN 1 ELSE 0 END) AS unmatched_orders
FROM immdata.imt_subscriptiongoodsorder p
LEFT JOIN (SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
           FROM immdata.exchangerates GROUP BY UPPER(currency)) x
  ON x.currency = UPPER(p.currency)
WHERE COALESCE(p.isdeleted,0)=0
  AND p.orderstatus='finished'
  AND (COALESCE(p.amountpaid,0)>0 OR LOWER(p.ordertype)='code' OR p.subscriptiontype LIKE 'onetime%')
  AND ((p.createtime >= TIMESTAMP '{{LY_LO}}' AND p.createtime < TIMESTAMP '{{LY_HI}}')
    OR (p.createtime >= TIMESTAMP '{{TY_LO}}' AND p.createtime < TIMESTAMP '{{TY_HI}}'))
GROUP BY UPPER(p.currency)
ORDER BY orders DESC;

-- @Q_WATERMARK  两段窗口订单落库水位（确认 11-12 为不完整日）
SELECT 'TY' AS seg, COUNT(*) AS orders, MIN(createtime) AS min_ct, MAX(createtime) AS max_ct
FROM immdata.imt_subscriptiongoodsorder
WHERE createtime >= TIMESTAMP '{{TY_LO}}' AND createtime < TIMESTAMP '{{TY_HI}}'
UNION ALL
SELECT 'LY', COUNT(*), MIN(createtime), MAX(createtime)
FROM immdata.imt_subscriptiongoodsorder
WHERE createtime >= TIMESTAMP '{{LY_LO}}' AND createtime < TIMESTAMP '{{LY_HI}}';

-- @CTES
WITH paid AS (
  SELECT userid,
         date_trunc('day', date_add(hour, 8, createtime)) AS bj_day,
         currency, amountpaid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted,0)=0
    AND orderstatus='finished'
    AND (COALESCE(amountpaid,0)>0 OR LOWER(ordertype)='code' OR subscriptiontype LIKE 'onetime%')
    AND ((createtime >= TIMESTAMP '{{LY_LO}}' AND createtime < TIMESTAMP '{{LY_HI}}')
      OR (createtime >= TIMESTAMP '{{TY_LO}}' AND createtime < TIMESTAMP '{{TY_HI}}'))
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
         ROW_NUMBER() OVER (PARTITION BY userid ORDER BY cnt DESC, real_geo) AS rn
  FROM ug
)

-- @Q_REV  逐日 × 地区桶 × 币种 收入（正式结果）
SELECT p.bj_day,
       CASE WHEN udom.real_geo IS NULL THEN 'NO_GEO'
            WHEN udom.real_geo IN ('SG','MY') THEN udom.real_geo
            ELSE 'OTHER' END AS bucket,
       UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN p.amountpaid ELSE 0 END)/100.0 AS amt_major,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN p.amountpaid ELSE 0 END)/100.0
           * COALESCE(MAX(x.rate),0) AS amt_cny
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
           FROM immdata.exchangerates GROUP BY UPPER(currency)) x
  ON x.currency = UPPER(p.currency)
GROUP BY p.bj_day, bucket, UPPER(p.currency)
ORDER BY p.bj_day, bucket, currency;

-- @Q_USERS  逐日 × 地区桶 付费用户数
SELECT p.bj_day,
       CASE WHEN udom.real_geo IS NULL THEN 'NO_GEO'
            WHEN udom.real_geo IN ('SG','MY') THEN udom.real_geo
            ELSE 'OTHER' END AS bucket,
       COUNT(DISTINCT p.userid) AS paid_users
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
GROUP BY p.bj_day, bucket
ORDER BY p.bj_day, bucket;

-- @Q_GEO_SANITY  主导国家桶分布（验 bucket 是否串组、量级）
SELECT CASE WHEN real_geo IS NULL THEN 'NO_GEO'
            WHEN real_geo IN ('SG','MY') THEN real_geo
            ELSE 'OTHER' END AS bucket,
       COUNT(*) AS users
FROM udom WHERE rn = 1
GROUP BY bucket
ORDER BY bucket;

-- @Q_P046_DETAIL  币种匹配不到汇率表「且有实付金额」的订单，按地区桶核查影响面（P046）
-- 兑换码 amountpaid 为空（currency 常为 NULL）不计入：P046 第 6 条明确不算折算问题。
SELECT COALESCE(UPPER(p.currency),'<NULL>') AS currency,
       CASE WHEN udom.real_geo IS NULL THEN 'NO_GEO'
            WHEN udom.real_geo IN ('SG','MY') THEN udom.real_geo
            ELSE 'OTHER' END AS bucket,
       COUNT(*) AS orders,
       SUM(COALESCE(p.amountpaid,0))/100.0 AS amt_major
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
           FROM immdata.exchangerates GROUP BY UPPER(currency)) x
  ON x.currency = UPPER(p.currency)
WHERE COALESCE(p.amountpaid,0) > 0 AND x.rate IS NULL
GROUP BY COALESCE(UPPER(p.currency),'<NULL>'), bucket
ORDER BY bucket, currency;

-- @Q_TIE  主导国家 cnt 并列的用户数（解释与 T107b 周版 0.3~0.7% 的细微差异）
SELECT COUNT(*) AS tied_users FROM (
  SELECT userid FROM (
    SELECT userid, cnt, RANK() OVER (PARTITION BY userid ORDER BY cnt DESC) AS rk FROM ug
  ) t
  WHERE rk = 1
  GROUP BY userid
  HAVING COUNT(*) > 1
) u;
