-- T123：不同渠道转化率【首版基线】定稿 SQL（2026-11-16）
-- 用户 14:25 明确要求「自行判断，不要再问口径」。以下口径由助手依据实测数据选定，
-- 全部可复算；假设与限制写在注释和 output 报表的「口径与限制」sheet 里。
--
-- ★ 前提突破：Google Ads 广告的 final_urls / final_url_suffix 里带 utm_campaign，
--   与 immdata.imt_campaigninfo.utmcampaign 是同一套命名。
--   growth.channel_campaign_map 由 scripts/sync_channel_campaign_map.py 从 API 实测
--   URL 自动解析写入（48 行 / 43 campaign），不是人工猜中文投放名（P045）。
--
-- 口径（默认，可改）：
--   观察窗   : 北京日 2026-11-09 ~ 11-15（UTC 2026-11-08 16:00 ~ 11-15 16:00）
--   渠道粒度 : utm_campaign（广告侧经映射表；我方埋点同名；两侧时区同为 Asia/Shanghai）
--   分母 A   : 广告点击 growth.google_ads_daily（权威，账户本币 CNY）
--   分母 B   : 我方带该 UTM 的去重设备数 imt_campaigninfo（到达口径，含存量启动）
--   分子     : 分母 B 中能桥接到 userid、且观察窗内有 P013 付费单的设备数
--              P013 = orderstatus='finished' 且 (amountpaid>0 或 ordertype='code'
--                     或 subscriptiongoodssnap 含 "SubscriptionType":"onetime")
--   桥接     : imt_campaigninfo.deviceid → imt_deviceinfo.deviceid → userid
--              → imt_subscriptiongoodsorder（订单表不继承营销渠道，必须桥接）
-- ⚠️ 结论边界：这是【渠道级相关漏斗】，不是用户级点击归因。
--    ① 我方 reference 近 1 日 gclid 命中 0 行（实测），click_view 的 GCLID 无处可连；
--    ② 新装第一跳 UTM 稀疏（T119 Q8：单日 google_sem 新装仅 85 台）；
--    ③ 付费侧不继承渠道（T119 Q5：google 命中 0）。
--    ⇒ 分子是**下界**，device_to_paid / CPA 不可当真实 ROI 对外引用。
-- ⚠️ 严格 7 天归因窗要等 11-22 之后数据齐全；本版用同窗付费作可比下界。
-- ⚠️ 一个 campaign 若对应多个 utm_campaign，JOIN 会重复计数；本窗口 7 个 campaign
--    实测均 1:1 映射（映射覆盖校验见 Q0），故可直接使用。

-- ============ Q0 映射覆盖校验（必须为 1:1，否则先去重再 JOIN）============
SELECT ads_campaign_name, count(DISTINCT utm_campaign) AS n_utm,
       count(*) AS map_rows
FROM growth.channel_campaign_map
GROUP BY ads_campaign_name HAVING count(DISTINCT utm_campaign) > 1
ORDER BY n_utm DESC;


-- ============ Q1 广告侧：渠道 × 日（点击 / 展示 / 花费 CNY）============
WITH ads AS (
    SELECT a.report_date, a.campaign_name, a.currency,
           sum(a.clicks) AS clicks, sum(a.impressions) AS impressions,
           sum(a.cost_amount) AS cost_cny
    FROM growth.google_ads_daily a
    WHERE a.granularity = 'CAMPAIGN'
      AND a.report_date BETWEEN '2026-11-09' AND '2026-11-15'
    GROUP BY 1, 2, 3
),
-- ⚠️ Q0 实测有 2 个 KOL campaign 一对多 UTM（日本/韩国博主加热）。
--    直接 JOIN 会让同一批点击重复计到多个 UTM 上；这里按 campaign 去重归集，
--    保证点击总数不被放大。这两个 campaign 本窗口无数据，不影响基线数字；
--    若要细分到博主，需业务侧给出分摊规则，不自行猜（P045）。
m1 AS (
    SELECT ads_campaign_name,
           min(utm_campaign)   AS utm_campaign,
           min(channel_group)  AS channel_group
    FROM growth.channel_campaign_map
    GROUP BY ads_campaign_name
)
SELECT a.report_date, m.channel_group, m.utm_campaign, a.campaign_name,
       a.currency, a.clicks, a.impressions, a.cost_cny,
       a.cost_cny / nullif(a.clicks, 0) AS cpc_cny
FROM ads a
JOIN m1 m ON a.campaign_name = m.ads_campaign_name
ORDER BY a.report_date, m.utm_campaign;


-- ============ Q2 我方分母 B：UTM campaign × 日 去重设备 ============
-- ⚠️ WHERE 用粗 UTC 窗保分区裁剪；北京日只在 SELECT 投影里算（禁止在 WHERE 里 to_date(date_add(...))）
SELECT to_date(date_add(hour, 8, createtime)) AS bj_date,
       utmcampaign AS utm_campaign,
       count(DISTINCT deviceid) AS devices
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-15 16:00:00'
  AND coalesce(isdeleted, 0) = 0
  AND utmcampaign LIKE 'googlekeywords_%'
GROUP BY 1, 2
ORDER BY 1, devices DESC;


-- ============ Q3 分子：渠道 × 付费设备（P013 桥接）============
WITH ch AS (
    SELECT deviceid, utmcampaign AS utm_campaign, min(createtime) AS first_seen
    FROM immdata.imt_campaigninfo
    WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-15 16:00:00'
      AND coalesce(isdeleted, 0) = 0
      AND utmcampaign LIKE 'googlekeywords_%'
    GROUP BY deviceid, utmcampaign
),
u AS (
    SELECT DISTINCT c.utm_campaign, c.deviceid, d.userid
    FROM ch c
    JOIN immdata.imt_deviceinfo d
      ON c.deviceid = d.deviceid AND coalesce(d.isdeleted, 0) = 0
    WHERE d.userid IS NOT NULL
),
paid AS (
    SELECT DISTINCT userid
    FROM immdata.imt_subscriptiongoodsorder
    WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-16 00:00:00'
      AND coalesce(isdeleted, 0) = 0
      AND orderstatus = 'finished'
      AND (coalesce(amountpaid, 0) > 0
           OR lower(ordertype) = 'code'
           OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%')
)
SELECT u.utm_campaign,
       count(DISTINCT u.deviceid) AS devices_linked,
       count(DISTINCT CASE WHEN p.userid IS NOT NULL THEN u.deviceid END) AS paid_devices
FROM u LEFT JOIN paid p ON p.userid = u.userid
GROUP BY 1
ORDER BY devices_linked DESC;


-- ============ Q5 我方分母 B：按渠道【整体】去重 ============
-- ⚠️ Q2 是逐日 count(distinct deviceid)，同一设备跨日会重复，禁止把 7 天相加当渠道总量。
--    主表（渠道汇总）必须用本段；Q2 只用于「逐日 × 渠道」sheet。
SELECT utmcampaign AS utm_campaign,
       count(DISTINCT deviceid) AS devices
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-15 16:00:00'
  AND coalesce(isdeleted, 0) = 0
  AND utmcampaign LIKE 'googlekeywords_%'
GROUP BY 1
ORDER BY devices DESC;


-- ============ Q4 对照：安装商店渠道（不依赖 Google Ads 的第二套「不同渠道」）============
-- 分母 = 观察窗内该 installchannel 的新装设备；分子 = 同窗 P013 付费设备。
-- 这套口径两侧都在 immdata，链路干净，可与 Q1~Q3 的营销渠道口径互相校验。
WITH dev AS (
    SELECT deviceid, coalesce(installchannel, '<NULL>') AS installchannel
    FROM immdata.imt_deviceinfo
    WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-15 16:00:00'
      AND coalesce(isdeleted, 0) = 0
    GROUP BY deviceid, coalesce(installchannel, '<NULL>')
),
u AS (
    SELECT d.installchannel, d.deviceid, di.userid
    FROM dev d
    JOIN immdata.imt_deviceinfo di
      ON d.deviceid = di.deviceid AND coalesce(di.isdeleted, 0) = 0
    WHERE di.userid IS NOT NULL
),
paid AS (
    SELECT DISTINCT userid
    FROM immdata.imt_subscriptiongoodsorder
    WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-16 00:00:00'
      AND coalesce(isdeleted, 0) = 0 AND orderstatus = 'finished'
      AND (coalesce(amountpaid, 0) > 0 OR lower(ordertype) = 'code'
           OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%')
)
SELECT u.installchannel,
       count(DISTINCT u.deviceid) AS new_devices,
       count(DISTINCT CASE WHEN p.userid IS NOT NULL THEN u.deviceid END) AS paid_devices
FROM u LEFT JOIN paid p ON p.userid = u.userid
GROUP BY 1
ORDER BY new_devices DESC;
