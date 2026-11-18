-- T126 Stripe × 行为数据 商业分析试水（近30天）
-- 窗口统一 UTC：北京日 2026-10-19 ~ 2026-11-17（不含 11-18）
-- 只读；行为表必带 created_ts 范围；不写库

-- Q1 我方 Stripe 渠道付费订单 → userid 映射（对账与行为分层的主键桥）
SELECT invoiceid, userid, useremail, amountpaid, currency, ordertype, createtime
FROM immdata.imt_subscriptiongoodsorder
WHERE invoiceid LIKE 'in_%'
  AND orderstatus = 'finished'
  AND createtime >= '2026-10-18 16:00:00'
  AND createtime <  '2026-11-17 16:00:00';

-- Q2 我方 Stripe 渠道付费规模（按币种，分新订/续费可疑的 ordertype）
SELECT currency, ordertype,
       count(*) AS orders,
       count(DISTINCT userid) AS users,
       sum(amountpaid) AS amount_minor
FROM immdata.imt_subscriptiongoodsorder
WHERE invoiceid LIKE 'in_%' AND orderstatus = 'finished'
  AND createtime >= '2026-10-18 16:00:00' AND createtime < '2026-11-17 16:00:00'
GROUP BY currency, ordertype ORDER BY amount_minor DESC;

-- Q3 付费用户的翻译行为（按 userid 聚合；ex_int_arg1 仅登录事件，覆盖率在结论披露）
-- 注意：IN 子查询限定在这批付费 userid，避免全表 30 天扫描放大
SELECT ex_int_arg1 AS userid,
       count_if(event_name = 'translate_page') AS page_events,
       count_if(event_name = 'translate_video_subtitle') AS subtitle_events,
       count(*) AS total_events
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-18 16:00:00'
  AND created_ts <  '2026-11-17 16:00:00'
  AND event_name IN ('translate_page', 'translate_video_subtitle')
  AND ex_int_arg1 IN (
      SELECT DISTINCT userid FROM immdata.imt_subscriptiongoodsorder
      WHERE invoiceid LIKE 'in_%' AND orderstatus = 'finished'
        AND createtime >= '2026-10-18 16:00:00' AND createtime < '2026-11-17 16:00:00'
        AND userid IS NOT NULL
  )
GROUP BY ex_int_arg1;

-- Q4 抽样：5 笔已支付 invoice 在我方订单的金额（对账用，P019）
SELECT invoiceid, amountpaid, currency, orderstatus, ordertype, userid
FROM immdata.imt_subscriptiongoodsorder
WHERE invoiceid IN (
  'in_1UcomdGc8iUjvqOFGscXHk12',
  'in_1UcojEGc8iUjvqOFYTEzdC9Q',
  'in_1UcoYMGc8iUjvqOFN7S1fSmE',
  'in_1UcoXMGc8iUjvqOFISLKMflX',
  'in_1UcOpVGc8iUjvqOFqLfAmwP5'
);
