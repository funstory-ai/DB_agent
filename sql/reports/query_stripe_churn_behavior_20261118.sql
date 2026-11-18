-- T127 Stripe 主动取消流失 × 流失前行为分析（只读）
-- 占位符 __INVOICES__ / __UIDS__ 由 scripts/stripe_churn_report_20261118.py 动态注入；
-- 窗口：Stripe canceled_at 北京日 2026-10-19~11-17；行为回溯 [T0-30d,T0)，T0=各 userid 最后取消日。
-- 时区：我方 created_ts 为 UTC naive，北京日 = to_date(date_add(hour,8,created_ts))。

-- Q1 主动取消 invoice -> 我方 userid 映射（P018 有账号归 userid）
SELECT invoiceid, userid, useremail, amountpaid, currency, orderstatus, createtime
FROM immdata.imt_subscriptiongoodsorder
WHERE invoiceid IN (__INVOICES__)

-- Q2 流失前行为日级矩阵：按 userid × 北京日聚合关键事件
-- 事件 ex_int_arg1=userid 仅登录事件（覆盖约 40–45%，P037 移动端缺口需披露）
SELECT
  ex_int_arg1 AS userid,
  to_date(date_add(hour, 8, created_ts)) AS bj_day,
  count(*) AS events_all,
  count_if(event_name = 'translate_page') AS translate_page,
  count_if(event_name = 'translate_video_subtitle') AS translate_subtitle,
  count_if(event_name = 'error_modal_show') AS error_modal,
  count_if(event_name IN ('go_pricing_page', 'pricing_purchase_btn_click', 'shell_pricing_activity_modal_show')) AS pricing_visit,
  count_if(event_name = 'subscription_manage_click') AS sub_manage_click
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-18 16:00:00'
  AND created_ts < '2026-11-18 16:00:00'
  AND ex_int_arg1 IN (__UIDS__)
GROUP BY ex_int_arg1, to_date(date_add(hour, 8, created_ts))
