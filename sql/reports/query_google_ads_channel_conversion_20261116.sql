-- T119：Google Ads 接入后 → 不同渠道转化率 的桥接骨架（2026-11-16）
-- 状态（2026-11-16 13:45 更新）：API 已真实接入，growth.google_ads_daily **49 行**
--   （11-09~15，2 个启用子账号 × 7 campaign × 7 天）。本文件是「按什么键、什么口径 JOIN」的骨架，
--   ⚠️ 不是已交付的转化率；channel_campaign_map 仍为空，Q3 现在会返回 0 行，属预期。
-- ⚠️ 实测口径纠正：4 个启用子账号全部 **CNY / Asia/Shanghai**（不是 USD）；
--   时区与北京日一致，Q3 的日期可直接等值 JOIN；金额是人民币本币，与 immdata 的 CNY 收入同币种。
--   MCC 4623896831 显示 USD 只是界面折算，禁止拿界面 $ 数与库内 ¥ 相除（P045）。
-- ⚠️ P043：以下所有 immdata/webdata 侧数字均为 11-16 探查实测，改口径必须重跑核对。

-- ============ Q0 先做：campaign 名对齐（决定后面能不能 JOIN）============
-- 实测：我方埋点里有两套 campaign 名，且都不同于 Google Ads 后台名，必须人工映射
--   webdata.ads_webapp_new_user_attribution : googlekeywords_pdf_translate / _zh-Hans / _ko (PDF 站)
--   immdata.imt_campaigninfo              : googlekeywords_website_translate_download / _zh-Hans / _video_* (插件站)
--   Google Ads 后台 campaign 名            : 13:45 实测为【第三套命名】中文投放系列名，与上两套都不同：
--     网页翻译_繁体_目标安装_20240816 / 网页翻译_简体_目标安装_20241106 /
--     视频翻译_简体_目标安装_20250325 / 视频翻译_繁体_目标安装_20240929 /
--     文档翻译_简体_目标安装_20241106 / 文档翻译_繁体_目标安装_20240904 /
--     网页翻译_韩语_目标安装_20241225
--     ⇒ 必须人工确认映射后填 growth.channel_campaign_map，禁止按名字相等 JOIN、禁止猜值（P045）
SELECT DISTINCT campaign_name, count(*) AS rows, min(report_date) AS d0, max(report_date) AS d1
FROM growth.google_ads_daily
GROUP BY campaign_name ORDER BY campaign_name;

-- 映射表填法（示意，禁止照抄猜测值 / P045）：
-- INSERT INTO growth.channel_campaign_map VALUES
--   ('<Google Ads 后台 campaign 名>', '<utm_campaign>', '<utm_source>', '<utm_medium>', '<渠道组>', '2026-01-01','2099-12-31','人工核对');


-- ============ Q1 广告侧：天 × campaign 的点击/展示/花费 ============
-- ⚠️ 原版写死 currency='USD' 会返回 0 行（实测入库全为 CNY）。按账号+币种分组，不写死币种；
--    跨币种金额禁止直接 sum，若要合并需业务给汇率。
SELECT report_date, customer_id, currency, campaign_name,
       sum(clicks)      AS clicks,
       sum(impressions) AS impressions,
       sum(cost_amount) AS cost_amount,
       sum(cost_amount) / nullif(sum(clicks), 0) AS cpc
FROM growth.google_ads_daily
WHERE granularity = 'CAMPAIGN'
GROUP BY report_date, customer_id, currency, campaign_name
ORDER BY report_date, campaign_name;


-- ============ Q2 我方分母（官网新用户）：必须去重，不能 sum ============
-- ⚠️ 实测坑：ads_webapp_new_user_attribution 是多维预聚合表，
--    function_type(6) × version_type(4) × interface_language_group(6) ≈ 96 个组合，
--    同一批 dnu 在每个组合里重复记一次；直接 sum(dnu) 会放大（11-09 全站 sum 远大于真实）。
--    正确取法：只取 function_type='all' AND version_type='all' AND interface_language_group='all'。
--    实测 11-09~15 google 相关 campaign 在 all/all/all 下每日仅 1~4 个 dnu，
--    而截图 5227 点击 —— 量级差 3 个数量级，说明这张表不是全量渠道分母，
--    只可代表「官网该口径的新用户」，绝不能拿它当 Google Ads 点击的分母直接算 CVR。
SELECT dt, campaign, source, medium, sum(dnu) AS dnu_dedup
FROM webdata.ads_webapp_new_user_attribution
WHERE dt BETWEEN '2026-11-09' AND '2026-11-15'
  AND function_type = 'all' AND version_type = 'all' AND interface_language_group = 'all'
  AND (lower(campaign) LIKE '%google%' OR lower(source) LIKE '%google%')
GROUP BY dt, campaign, source, medium
ORDER BY dt, dnu_dedup DESC;


-- ============ Q3 渠道级 CPA / CVR 骨架（待口径确认后才可当结论）============
-- 分子/分母三选一必须由业务定：官网新用户 / 插件新装设备 / 付费订单。
-- 时间口径：✅ 13:45 实测 4 个启用子账号时区均 Asia/Shanghai，与北京日一致，可直接等值 JOIN。
-- 币种：✅ cost_amount 为 CNY 本币，与 immdata 收入同币种，可直接算 CPA（MCC 界面 USD 折算值不用）。
-- ⚠️ channel_campaign_map 目前是空表，本查询现返回 0 行；映射确认后才有结果。
WITH ads AS (
    SELECT report_date, customer_id, currency, campaign_name,
           sum(clicks) clicks, sum(cost_amount) cost_amount
    FROM growth.google_ads_daily WHERE granularity = 'CAMPAIGN'
    GROUP BY report_date, customer_id, currency, campaign_name
),
web AS (
    SELECT dt, campaign, sum(dnu) dnu
    FROM webdata.ads_webapp_new_user_attribution
    WHERE function_type='all' AND version_type='all' AND interface_language_group='all'
    GROUP BY dt, campaign
)
SELECT a.report_date, m.channel_group, a.campaign_name, a.currency,
       a.clicks, a.cost_amount, w.dnu,
       a.cost_amount / nullif(w.dnu, 0) AS cpa,          -- 每新用户获客成本（账户本币）
       w.dnu / nullif(a.clicks, 0)     AS click_to_newuser_rate
FROM ads a
JOIN growth.channel_campaign_map m ON a.campaign_name = m.ads_campaign_name
LEFT JOIN web w ON w.dt = a.report_date AND w.campaign = m.utm_campaign
ORDER BY a.report_date, m.channel_group;


-- ============ Q4 我方分母（插件设备级，量级更接近投放）============
-- T119 Q1/Q7 实测：imt_campaigninfo 近 7 天 203,392 设备，google/gclid 命中 4,616；
--   user_behaviour 单日 init_page_daily 带 googlekeywords_* 约 4 万+设备，
--   但 is_new_user_today='1' 的新装只有 85 台带 google_sem
--   ⇒ 渠道 UTM 主要在存量启动里，新装第一跳标记稀疏，这是归因窗口要解决的核心问题。
-- 列名实测：createtime(timestamp)、deviceid、utmcampaign/utmmedium/utmsource、isdeleted。
-- ⚠️ 北京日只放在 SELECT 投影，WHERE 用粗 UTC 窗保分区裁剪（禁止在 WHERE 里 to_date(date_add(...))）。
SELECT to_date(date_add(hour, 8, createtime)) AS bj_date,
       utmsource, utmcampaign, count(DISTINCT deviceid) AS devices
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-11-08 16:00:00' AND createtime < '2026-11-15 16:00:00'
  AND (lower(coalesce(utmsource,'')) LIKE '%google%' OR lower(coalesce(utmcampaign,'')) LIKE '%google%')
GROUP BY 1, 2, 3 ORDER BY 1, devices DESC;


-- ============ Q5 我方分子（付费）：需桥接，订单表不带营销渠道 ============
-- T119 Q5/Q6 实测：imt_subscriptionordersource 近 30 天 76,064 行，google 命中 0，
--   TOP 全是产品内入口 ⇒ 不能在订单表直接按渠道分组。
-- 正解链路：user_behaviour.device_id → imt_deviceinfo.deviceid → userid → imt_subscriptiongoodsorder
--   （T119 Q9 连通性：85 台带渠道新装 → 51 台连到 userid → 60%；近 30 天 1 单付费。
--     ⚠️ 该数字只是连通性验证，付费窗与新装日不同窗，不是转化率。）
-- 付费单口径 P013；北京日切 createtime + 8h。归因窗口 / 去重主体(P018) 待定，定完再写正式 SQL。
