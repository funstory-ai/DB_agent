-- T119 渠道归因字段可行性探查（只读，2026-11-16）
-- 目的：回答「现有 immdata 到底有没有渠道标记、能不能支撑不同渠道转化率」。
-- 性质：字段覆盖率 / 取值分布探查，不是正式交付数字；时间窗为探查窗。
-- 执行：scripts/probe_channel_attribution.py 按 @Qn 分段执行。

-- @Q1
-- 订单来源快照（最接近付费归因的一张表）近 30 天 UTM 填充率
SELECT
  count(*) AS rows_total,
  sum(case when utmsource is not null and trim(utmsource) <> '' then 1 else 0 end) AS has_source,
  sum(case when utmcampaign is not null and trim(utmcampaign) <> '' then 1 else 0 end) AS has_campaign,
  sum(case when utmmedium is not null and trim(utmmedium) <> '' then 1 else 0 end) AS has_medium,
  sum(case when lower(concat(coalesce(utmsource,''),'|',coalesce(utmcampaign,''),'|',coalesce(utmmedium,''),'|',coalesce(extenddata,''))) like '%google%'
            or lower(coalesce(extenddata,'')) like '%gclid%' then 1 else 0 end) AS google_like
FROM immdata.imt_subscriptionordersource
WHERE createtime >= '2026-10-16 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0

-- @Q2
-- 订单来源快照近 30 天 utmsource × utmcampaign 取值 TOP
SELECT coalesce(utmsource,'<NULL>') AS src, coalesce(utmcampaign,'<NULL>') AS camp, count(*) AS cnt
FROM immdata.imt_subscriptionordersource
WHERE createtime >= '2026-10-16 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0
GROUP BY coalesce(utmsource,'<NULL>'), coalesce(utmcampaign,'<NULL>')
ORDER BY cnt DESC LIMIT 25

-- @Q3
-- 设备表近 30 天 UTM 填充率与 google 命中
SELECT
  count(*) AS rows_total,
  sum(case when utmsource is not null and trim(utmsource) <> '' then 1 else 0 end) AS has_source,
  sum(case when utmcampaign is not null and trim(utmcampaign) <> '' then 1 else 0 end) AS has_campaign,
  sum(case when lower(concat(coalesce(utmsource,''),'|',coalesce(utmcampaign,''),'|',coalesce(utmmedium,''))) like '%google%' then 1 else 0 end) AS google_like,
  count(distinct deviceid) AS devices
FROM immdata.imt_deviceinfo
WHERE createtime >= '2026-10-16 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0

-- @Q4
-- 设备表近 30 天 installchannel（安装渠道）取值 TOP
SELECT coalesce(installchannel,'<NULL>') AS ch, count(*) AS cnt
FROM immdata.imt_deviceinfo
WHERE createtime >= '2026-10-16 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0
GROUP BY coalesce(installchannel,'<NULL>')
ORDER BY cnt DESC LIMIT 20

-- @Q5
-- campaigninfo 近 7 天 UTM / reference 填充率与 google / gclid 命中
SELECT
  count(*) AS rows_total,
  count(distinct deviceid) AS devices,
  sum(case when utmsource is not null and trim(utmsource) <> '' then 1 else 0 end) AS has_source,
  sum(case when utmcampaign is not null and trim(utmcampaign) <> '' then 1 else 0 end) AS has_campaign,
  sum(case when reference is not null and trim(reference) <> '' then 1 else 0 end) AS has_reference,
  sum(case when lower(concat(coalesce(utmsource,''),'|',coalesce(utmcampaign,''),'|',coalesce(utmmedium,''),'|',coalesce(reference,''))) like '%google%'
            or lower(coalesce(reference,'')) like '%gclid%' then 1 else 0 end) AS google_like
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-11-09 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0

-- @Q6
-- campaigninfo 近 7 天 utmsource × utmcampaign 取值 TOP
SELECT coalesce(utmsource,'<NULL>') AS src, coalesce(utmcampaign,'<NULL>') AS camp, count(*) AS cnt
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-11-09 00:00:00' AND createtime < '2026-11-16 00:00:00'
  AND coalesce(isdeleted,0)=0
GROUP BY coalesce(utmsource,'<NULL>'), coalesce(utmcampaign,'<NULL>')
ORDER BY cnt DESC LIMIT 25

-- @Q7
-- 行为表单日新装事件的 campaign / install_from 取值 TOP（北京日 11-12 = UTC 11-11 16:00 ~ 11-12 16:00）
SELECT coalesce(campaign,'<NULL>') AS camp, coalesce(install_from,'<NULL>') AS src,
       count(*) AS cnt, count(distinct device_id) AS dev
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
  AND event_name = 'init_page_daily'
GROUP BY coalesce(campaign,'<NULL>'), coalesce(install_from,'<NULL>')
ORDER BY cnt DESC LIMIT 25

-- @Q8
-- 单日新装设备按渠道分组 + 能否连到设备表账号（分母可行性）
-- 北京日 11-12；P034 新装 = init_page_daily AND is_new_user_today='1'（含重装老号，探查用）
WITH ch AS (
  SELECT device_id,
         case when max(case when campaign like 'googlekeywords%' then 1 else 0 end) = 1 then 'google_sem'
              when max(case when campaign is not null and trim(campaign) not in ('','none','0') then 1 else 0 end) = 1 then 'other_campaign'
              else 'no_campaign' end AS channel
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND device_id IS NOT NULL
  GROUP BY device_id
)
SELECT c.channel,
       count(*) AS new_devices,
       count(distinct d.userid) AS linked_users,
       count(distinct case when d.userid is not null then c.device_id end) AS devices_with_account
FROM ch c
LEFT JOIN immdata.imt_deviceinfo d
  ON c.device_id = d.deviceid AND coalesce(d.isdeleted,0)=0
GROUP BY c.channel
ORDER BY new_devices DESC

-- @Q9
-- 按渠道看近 30 天付费账号数（分子可行性示范；P013 付费口径，非交付数字）
WITH ch AS (
  SELECT device_id,
         case when max(case when campaign like 'googlekeywords%' then 1 else 0 end) = 1 then 'google_sem'
              when max(case when campaign is not null and trim(campaign) not in ('','none','0') then 1 else 0 end) = 1 then 'other_campaign'
              else 'no_campaign' end AS channel
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
    AND event_name = 'init_page_daily' AND is_new_user_today = '1'
    AND device_id IS NOT NULL
  GROUP BY device_id
),
u AS (
  SELECT DISTINCT c.channel, d.userid
  FROM ch c
  JOIN immdata.imt_deviceinfo d ON c.device_id = d.deviceid AND coalesce(d.isdeleted,0)=0
  WHERE d.userid IS NOT NULL
),
paid AS (
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE createtime >= '2026-10-16 00:00:00' AND createtime < '2026-11-16 00:00:00'
    AND coalesce(isdeleted,0)=0 AND orderstatus = 'finished'
    AND (coalesce(amountpaid,0) > 0 OR lower(ordertype) = 'code')
)
SELECT u.channel,
       count(distinct u.userid) AS users,
       count(distinct case when p.userid is not null then u.userid end) AS paid_users
FROM u LEFT JOIN paid p ON u.userid = p.userid
GROUP BY u.channel
ORDER BY users DESC
