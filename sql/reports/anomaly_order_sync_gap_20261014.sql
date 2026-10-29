-- T072 订单同步缺口
-- 主表: immdata.imt_subscriptiongoodsorder（不用 dwd_order_clean，P012）
-- 付费: isdeleted=0 且 orderstatus='finished' 且 amountpaid>0（P013）
-- 日界: 北京自然日，createtime 为 UTC。10-14 = [2026-10-13 16:00, 2026-10-14 16:00)
-- 金额: amountpaid/100；非 CNY/RMB 乘 exchangerates.exchangerate 折人民币（P008）
-- 表文档: docs/tables/immdata/imt_subscriptiongoodsorder.md

-- 1) 近两周付费按日
SELECT
  DATE(ADD_HOURS(o.createtime, 8)) AS dt_bj,
  COUNT(*) AS paid_orders,
  COUNT(DISTINCT o.userid) AS users,
  ROUND(SUM(
    CASE
      WHEN UPPER(COALESCE(o.currency, '')) IN ('CNY', 'RMB') THEN o.amountpaid / 100.0
      ELSE o.amountpaid * COALESCE(er.exchangerate, 0) / 100.0
    END
  ), 2) AS amount_cny,
  MIN(o.createtime) AS min_ct_utc,
  MAX(o.createtime) AS max_ct_utc
FROM immdata.imt_subscriptiongoodsorder o
LEFT JOIN immdata.exchangerates er
  ON UPPER(COALESCE(o.currency, '')) = UPPER(COALESCE(er.currency, ''))
WHERE COALESCE(o.isdeleted, 0) = 0
  AND o.orderstatus = 'finished'
  AND COALESCE(o.amountpaid, 0) > 0
  AND o.createtime >= '2026-09-30 16:00:00'
  AND o.createtime < '2026-10-15 16:00:00'
GROUP BY 1
ORDER BY 1;

-- 2) 日更水位（仅作对照；北京每天 01:00 同步，白天查到停在约 01:xx 是正常现象）
-- 同步仓: H:\imt_data_synch；CronJob Asia/Shanghai "0 1 * * *"
-- 勿与 user_behaviour（另一条链路）对比后断定「业务同步故障」
SELECT NOW() AS now_utc,
  (SELECT MAX(createtime) FROM immdata.imt_subscriptiongoodsorder) AS order_max_ct,
  (SELECT MAX(createtime) FROM immdata.imt_checkoutsession) AS checkout_max_ct,
  (SELECT MAX(createtime) FROM immdata.imt_userinfo) AS userinfo_max_ct;
