-- T097: exact order-source -> checkout -> order linkage; no account-level renewal attribution.
-- Windows are UTC corresponding to Beijing 2026-10-28 through 2026-11-12.
WITH source_ranked AS (
 SELECT id AS source_id,checkoutsessiontableid,userid,utmcampaign,
        createtime AS source_ts,deviceid,
        CAST(TRY_PARSE_JSON(extenddata):orderFrom AS STRING) AS order_from,
        ROW_NUMBER() OVER(PARTITION BY checkoutsessiontableid ORDER BY createtime DESC,id DESC) AS rn,
        COUNT(*) OVER(PARTITION BY checkoutsessiontableid) AS source_rows
 FROM immdata.imt_subscriptionordersource
 WHERE COALESCE(isdeleted,0)=0
   AND createtime>='2026-10-26 16:00:00' AND createtime<'2026-11-13 16:00:00'
), src AS (
 SELECT * FROM source_ranked WHERE rn=1
 AND utmcampaign IN ('homepage','message_2611_sale','pricing_activity_modal','ad_banner_2026_1111')
)
SELECT s.source_id,s.utmcampaign AS campaign,s.source_ts,s.deviceid AS source_device,
       s.order_from,s.source_rows,c.id AS checkout_id,c.userid AS checkout_userid,
       c.createtime AS checkout_ts,c.paytime,c.orderstatus AS checkout_status,
       c.subscriptiontype AS checkout_plan,c.checkoutsessionid,
       o.id AS order_id,o.userid AS order_userid,o.createtime AS order_ts,
       o.orderstatus,o.ordertype,o.amountpaid,o.subscriptiontype,o.membership,o.dateperiod,
       CASE WHEN LOWER(o.ordertype)='code'
            OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
            THEN 1 ELSE 0 END AS is_code,
       CASE WHEN o.orderstatus='finished' AND
            (COALESCE(o.amountpaid,0)>0 OR LOWER(o.ordertype)='code'
             OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%')
            THEN 1 ELSE 0 END AS is_paid,
       CASE WHEN o.orderstatus='finished' AND COALESCE(o.amountpaid,0)=0
             AND NOT (LOWER(COALESCE(o.ordertype,''))='code'
               OR COALESCE(CAST(o.subscriptiongoodssnap AS STRING),'') LIKE '%"SubscriptionType":"onetime%')
            THEN 1 ELSE 0 END AS is_trial
FROM src s
LEFT JOIN immdata.imt_checkoutsession c ON c.id=s.checkoutsessiontableid AND COALESCE(c.isdeleted,0)=0
LEFT JOIN immdata.imt_subscriptiongoodsorder o ON o.checkoutsessionid=c.checkoutsessionid
  AND NULLIF(c.checkoutsessionid,'') IS NOT NULL AND COALESCE(o.isdeleted,0)=0
  AND o.createtime>='2026-10-27 16:00:00' AND o.createtime<'2026-11-12 16:00:00'
WHERE c.createtime>='2026-10-27 16:00:00' AND c.createtime<'2026-11-12 16:00:00';
