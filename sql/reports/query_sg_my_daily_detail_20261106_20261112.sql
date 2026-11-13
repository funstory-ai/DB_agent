-- T112 交付后追问：2026-11-06（北京日）MY 桶「CNY 2971.8」这一格背后的逐笔订单明细。
--
-- P044（解释已交付格子必须用同一次查询、同一粒度、同一时间锚点）：
--   * 下面 @CTES 逐字复刻 T112 定稿 query_sg_my_daily_revenue_yoy_20261112.sql 的公共前置，
--     含两段窗口 OR、付费单 P013、用户主导 real_geo 的决胜键 ORDER BY cnt DESC, real_geo；
--     paid 仅额外带出 id/createtime/ordertype/subscriptiontype/membership 等展示列，不改变行集。
--   * @Q_CHECK 用 T112 原 Q_REV 的聚合逻辑，只加「北京日=目标日 + 桶=目标桶」过滤，
--     用于复算 2971.8 / 1200.28 / 214.37，自证明细与已交付格子同口径。
--   * @Q_DETAIL 输出逐笔订单；兑换码（amountpaid 为空/0）也列出并用 is_cash 标记，
--     它们不进 amt_major，但会计入订单数（T112 Q_REV 的 COUNT(*)）。
--   * 占位符 {{LY_LO}} {{LY_HI}} {{TY_LO}} {{TY_HI}} 与 T112 同名同值；北京日 D 的 UTC 边界
--     = (D-1) 16:00:00 ~ D 16:00:00。本文件不修改 T112 定稿 SQL、不改动任何交付数字。
--
-- 复用：scripts/query_sg_my_daily_detail_20261106.py --day 2026-11-06 --bucket MY
--       默认窗口与 T112 一致（今年 10-25~11-12 / 去年同月日），可换日/换桶复查其它格子。

-- @CTES
WITH paid AS (
  SELECT id, userid, createtime, ordertype, subscriptiontype, membership,
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
  SELECT userid, real_geo, cnt,
         ROW_NUMBER() OVER (PARTITION BY userid ORDER BY cnt DESC, real_geo) AS rn
  FROM ug
)

-- @Q_CHECK  复算该日该桶的分币种汇总（必须与交付表逐格相等）
SELECT CAST(p.bj_day AS DATE) AS bj_day,
       UPPER(p.currency) AS currency,
       COUNT(*) AS orders,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN 1 ELSE 0 END) AS cash_orders,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN p.amountpaid ELSE 0 END)/100.0 AS amt_major,
       COALESCE(MAX(x.rate),0) AS rate,
       SUM(CASE WHEN COALESCE(p.amountpaid,0)>0 THEN p.amountpaid ELSE 0 END)/100.0
           * COALESCE(MAX(x.rate),0) AS amt_cny
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
           FROM immdata.exchangerates GROUP BY UPPER(currency)) x
  ON x.currency = UPPER(p.currency)
WHERE CAST(p.bj_day AS DATE) = DATE '{{DAY}}'
  AND udom.real_geo = '{{BUCKET}}'
GROUP BY CAST(p.bj_day AS DATE), UPPER(p.currency)
ORDER BY currency;

-- @Q_DETAIL  该日该桶逐笔订单明细
SELECT p.id AS order_id,
       p.userid,
       p.createtime AS utc_time,
       date_add(hour, 8, p.createtime) AS bj_time,
       UPPER(p.currency) AS currency,
       COALESCE(p.amountpaid,0) AS amountpaid_cents,
       COALESCE(p.amountpaid,0)/100.0 AS amt_major,
       COALESCE(x.rate,0) AS rate,
       COALESCE(p.amountpaid,0)/100.0 * COALESCE(x.rate,0) AS amt_cny,
       CASE WHEN COALESCE(p.amountpaid,0)>0 THEN 1 ELSE 0 END AS is_cash,
       p.ordertype,
       p.subscriptiontype,
       p.membership,
       udom.real_geo AS dominant_geo,
       udom.cnt AS geo_votes
FROM paid p
LEFT JOIN udom ON udom.userid = p.userid AND udom.rn = 1
LEFT JOIN (SELECT UPPER(currency) AS currency, MAX(exchangerate) AS rate
           FROM immdata.exchangerates GROUP BY UPPER(currency)) x
  ON x.currency = UPPER(p.currency)
WHERE CAST(p.bj_day AS DATE) = DATE '{{DAY}}'
  AND udom.real_geo = '{{BUCKET}}'
ORDER BY p.createtime, p.id;
