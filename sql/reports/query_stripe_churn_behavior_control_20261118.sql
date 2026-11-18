-- T128 主动取消 vs 对照组 行为对比（只读）
-- 对照组：窗口内 Stripe 实付 invoice 的 userid，排除全部已取消用户（all_cancel_uids.json，6,398人）
-- 配对：锚点日（北京日）同日 1:1，控制日期分布排除 T127 的时间趋势假象
-- __UIDS__ 由 scripts/stripe_churn_control_20261118.py 注入

SELECT ex_int_arg1 AS userid,
  to_date(date_add(hour,8,created_ts)) AS bj_day,
  count(*) AS ev,
  count_if(event_name='translate_page') AS page,
  count_if(event_name='translate_video_subtitle') AS sub,
  count_if(event_name='error_modal_show') AS err,
  count_if(event_name IN ('go_pricing_page','pricing_purchase_btn_click','shell_pricing_activity_modal_show')) AS pricing
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-15 16:00:00'
  AND created_ts < '2026-11-19 16:00:00'
  AND ex_int_arg1 IN (__UIDS__)
GROUP BY ex_int_arg1, to_date(date_add(hour,8,created_ts))
