-- T097: UTC boundaries equal Beijing 2026-10-28 through 2026-11-12 inclusive.
-- Page campaign is the URL UTM; purchase click trigger is the current URL campaign.
-- Keep all hosts here for scope validation. Exclude non-production hosts in analysis.
SELECT created_ts,event_name,campaign,trigger,site_host,
       device_id,ex_int_arg1 AS login_userid,
       ex_char_arg3 AS fingerprint,ex_char_arg7 AS first_party,
       ex_char_arg8 AS identity_strategy,ex_char_arg9 AS primary_identity,
       CASE WHEN event_name='pricing_purchase_btn_click' THEN ex_char_arg2 END AS click_plan,
       CASE WHEN event_name='pricing_purchase_btn_click' THEN ex_char_arg3 END AS click_channel,
       is_new_user_today,os_name
FROM immdata.user_behaviour
WHERE created_ts>='2026-10-27 16:00:00' AND created_ts<'2026-11-12 16:00:00'
  AND (
    event_name='official_page_view'
    AND campaign IN ('homepage','message_2611_sale','pricing_activity_modal','ad_banner_2026_1111')
    OR event_name='pricing_purchase_btn_click'
    AND trigger IN ('homepage','message_2611_sale','pricing_activity_modal','ad_banner_2026_1111')
  );
