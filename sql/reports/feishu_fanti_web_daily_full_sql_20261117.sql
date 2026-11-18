-- =============================================================================
-- 飞书表「谷歌_繁体_网页翻译」完整取数 SQL（16 列）—— 交付给飞书自动更新项目
-- 生成日期：2026-11-17　Database：Databend / immdata
-- 用途：一条 SQL 直接产出飞书表 16 列（日期 + 15 数值），结果按日期覆盖写入飞书。
-- 状态：✅ 只读 SELECT，2026-11-17 实跑通过（24 行 / 16 列）。
--       本文件不含飞书写入逻辑、不建表、不写库；写入由飞书自动更新项目实现。
-- =============================================================================
--
-- 【表身份】Google Ads campaign「网页翻译_繁体_目标安装_20240816」日报
--   customer_id = 6036515162, campaign_id = 21597353947
--   该 campaign 落地页 100% 只带 UTM: googlekeywords_website_translate_download
--
-- 【16 列 → 来源映射】
--   1  日期            report_date          广告侧 report_date（Asia/Shanghai 自然日）
--   2  消费            cost_cny             google_ads_campaign_daily cost_micros/1e6
--   3  展现            impressions          同上
--   4  点击            clicks               同上
--   5  平均点击价格     cpc_cny              消费/点击（round 2）
--   6  安装            install              imt_campaigninfo 该 UTM 北京日去重设备
--   7  单用户获客成本   cpa_cny              消费/安装（round 2）
--   8  translated      translated           该批设备 translated=1 去重数
--   9  registered      registered           设备桥接 user，安装后 0~100 天新建 userid 去重
--   10 clickTry        clickTry             该 user 的 checkout session userid 去重（0~100 天）
--   11 tryPro          tryPro               session goods.EnableTrial=true 且订单 yearly/monthly、AmountPaid=0
--   12 paid            paid                 finished 且 monthly/yearly、AmountPaid>0 订单去重
--   13 pro月费订单数    pro_monthly          subscriptiontype ∈ monthly 系
--   14 max月费订单数    max_monthly          subscriptiontype ∈ max_monthly 系
--   15 pro年费订单数    pro_yearly           subscriptiontype ∈ yearly 系
--   16 max年费订单数    max_yearly           subscriptiontype ∈ max_yearly 系
--
-- 【时间口径】北京日 D = UTC (D-1)16:00 ~ D 16:00。
--   广告侧 report_date 已是 Asia/Shanghai，直接等值；
--   我方侧 WHERE 只放 UTC 粗窗保分区裁剪，北京日只在 SELECT 投影（百亿表禁 WHERE 内 to_date(date_add)）。
--   下方窗口 = 北京日 2026-10-23~11-15；自动更新改成目标区间（见文件末「参数化说明」）。
--
-- 【回刷】03:40 Google 同步每天回刷近 7 天 ⇒ 历史天消费/点击会变；必须按日期覆盖写飞书，不能只追加。
--   漏斗列是 100 天滚动累计 + translated 回填 ⇒ 历史行会缓慢爬升，属正常，不是数据错。
-- =============================================================================

WITH ads AS (
    SELECT report_date AS dt,
           sum(clicks) AS clicks,
           sum(impressions) AS impressions,
           round(sum(cost_micros)/1e6, 2) AS cost_cny
    FROM immdata.google_ads_campaign_daily
    WHERE customer_id = '6036515162'
      AND campaign_id = '21597353947'
      AND report_date BETWEEN '2026-10-23' AND '2026-11-15'
    GROUP BY 1
),
funnel AS (
    SELECT event_datetime AS dt,
           sum(install) AS install,
           sum(translated) AS translated,
           sum(registerin100day) AS registered,
           sum(clickin100day) AS clickTry,
           sum(tryin100day) AS tryPro,
           sum(subscribein100day) AS paid,
           sum(monthlyin100day) AS pro_monthly,
           sum(max_monthlyin100day) AS max_monthly,
           sum(yearlyin100day) AS pro_yearly,
           sum(max_yearlyin100day) AS max_yearly
    FROM (
        SELECT to_date(date_add(hour, 8, c.createtime)) AS event_datetime,
               c.utmcampaign, c.utmsource, c.utmmedium,
               count(DISTINCT c.deviceid) AS install,
               count(DISTINCT IF(c.translated = 1, c.deviceid, NULL)) AS translated,
               coalesce(count(DISTINCT IF(datediff(day, c.createtime, u.createtime) BETWEEN 0 AND 100, u.id, NULL)), 0) AS registerIn100day,
               coalesce(count(DISTINCT IF(datediff(day, c.createtime, s.createtime) BETWEEN 0 AND 100, s.userid, NULL)), 0) AS clickIn100day,
               coalesce(count(DISTINCT IF(get(try_parse_json(s.subscriptiongoodssnap), 'EnableTrial') = TRUE
                                          AND o.subscriptiontype IN ('yearly', 'monthly')
                                          AND o.amountpaid = 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS TryIn100day,
               coalesce(count(DISTINCT IF(o.orderstatus = 'finished'
                                          AND (o.subscriptiontype LIKE '%monthly%' OR o.subscriptiontype LIKE '%yearly%')
                                          AND o.amountpaid > 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS SubscribeIn100day,
               coalesce(count(DISTINCT IF(o.subscriptiontype IN ('yearly', 'onetime_yearly', 'onetime_dogpay_yearly')
                                          AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS yearlyIn100day,
               coalesce(count(DISTINCT IF(o.subscriptiontype IN ('monthly', 'onetime_dogpay_monthly')
                                          AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS monthlyIn100day,
               coalesce(count(DISTINCT IF(o.subscriptiontype IN ('max_yearly', 'onetime_dogpay_max_yearly', 'onetime_max_yearly')
                                          AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS max_yearlyIn100day,
               coalesce(count(DISTINCT IF(o.subscriptiontype IN ('max_monthly', 'onetime_dogpay_max_monthly')
                                          AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                          AND datediff(day, c.createtime, o.createtime) BETWEEN 0 AND 100, o.id, NULL)), 0) AS max_monthlyIn100day
        FROM (((immdata.imt_campaigninfo c
                LEFT JOIN immdata.imt_deviceinfo d ON c.deviceid = d.deviceid)
               LEFT JOIN immdata.imt_userinfo u ON d.userid = u.id)
               LEFT JOIN immdata.imt_checkoutsession s ON u.id = s.userid)
               LEFT JOIN immdata.imt_subscriptiongoodsorder o ON s.userid = o.userid
        WHERE c.utmcampaign = 'googlekeywords_website_translate_download'
          AND c.createtime >= '2026-10-22 16:00:00'
          AND c.createtime <  '2026-11-15 16:00:00'
        GROUP BY event_datetime, c.utmcampaign, c.utmsource, c.utmmedium
    ) v
    WHERE event_datetime BETWEEN to_date('2026-10-23') AND to_date('2026-11-15')
    GROUP BY event_datetime
)
SELECT a.dt                                       AS report_date,
       a.cost_cny                                  AS cost_cny,
       a.impressions                               AS impressions,
       a.clicks                                    AS clicks,
       round(a.cost_cny / nullif(a.clicks, 0), 2)  AS cpc_cny,
       f.install                                   AS install,
       round(a.cost_cny / nullif(f.install, 0), 2) AS cpa_cny,
       f.translated, f.registered, f.clickTry, f.tryPro, f.paid,
       f.pro_monthly, f.max_monthly, f.pro_yearly, f.max_yearly
FROM ads a
LEFT JOIN funnel f ON f.dt = a.dt
ORDER BY 1;

-- =============================================================================
-- 【参数化说明 / 自动更新时怎么改】
-- 设目标北京日区间 [D1, D2]（例：每天回刷近 8 天则 D1=T-8, D2=T-1）：
--   ① ads 侧：report_date BETWEEN '<D1>' AND '<D2>'
--   ② funnel 内层 UTC 粗窗：c.createtime >= '<D1-1> 16:00:00'
--                        AND c.createtime <  '<D2+1> 16:00:00'
--      （即北京 D1 00:00 的 UTC 时刻 到 北京 D2 24:00 的 UTC 时刻）
--   ③ funnel 外层：event_datetime BETWEEN to_date('<D1>') AND to_date('<D2>')
-- 三处必须同时改，否则日期对不齐。
--
-- 【飞书写入约定】
--   - 按 report_date 覆盖同日期行（MERGE/UPSERT 语义），不要 append 重复日期行。
--   - 数值列保留 2 位小数仅用于消费/CPC/CPA；其余为整数。
--   - 若某天 ads 有数据但 funnel 无数据（极少，如当天埋点未到），funnel 列为 NULL；
--     建议跳过该行或留空，不要写 0（0 会被当成真实转化）。
--
-- 【已验证的锚点（2026-11-17 实跑）】
--   24 行 / 16 列；首行 2026-10-23 = 消费1001.63 / 展现2268 / 点击402 / CPC2.49 /
--   安装107 / CPA9.36，与飞书表完全一致。
--   逐列对飞书吻合天数(共24)：安装24 / max月24 / max年24 / tryPro20 / pro月19 /
--   pro年18 / paid16 / clickTry13 / registered10 / translated5；差异全部为「库≥飞书」。
-- =============================================================================
