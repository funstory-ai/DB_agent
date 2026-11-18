-- =============================================================================
-- 飞书表「谷歌_繁体_网页翻译」逐日自动更新：取数 SQL（草稿，只读，2026-11-17）
-- 用途：把用户贴的 2026-10-23~11-15 共 24 行逐列对回库内，确认哪些列可自动更新。
-- 状态：⚠️ 仅取数逻辑，尚未接入飞书、未建任何定时任务、未写库。
-- =============================================================================
--
-- 【对账结论 / 11-17 14:11 只读实测】
-- 表 = Google Ads 后台 campaign「网页翻译_繁体_目标安装_20240816」的日报，
--      customer_id=6036515162, campaign_id=21597353947, SEARCH / MAXIMIZE_CONVERSIONS。
--   用户表第 1/2/3 列（花费、展示、点击） == google_ads_campaign_daily 该 campaign 逐日原值：
--      24 天中 13 天完全一致，11 天差 1~2 点击 / ¥2.31~6.91，合计 ¥18.33 / 7 点击 / 13 展示，
--      来自 Google 侧历史回刷（用户表是当时的静态快照，库内是最新值），不是口径错。
--   第 4 列 CPC = 花费 / 点击（24/24 天精确复算）；第 6 列 CPA = 花费 / 第 5 列（24/24 天精确复算）。
--   第 5 列 == imt_campaigninfo 按北京日、utmcampaign='googlekeywords_website_translate_download'
--      的 count(DISTINCT deviceid)，24/24 天逐日完全一致（例：11-09~15 = 142/156/164/172/173/132/132）。
--   ⚠️ 该 campaign 的落地页表 91 行 URL 100% 只带这一个 UTM，点击 8050 / ¥21199.13 与
--      campaign 日报完全相等 ⇒ 繁体/简体不能靠 UTM 名字区分，必须按 campaign_id 过滤。
--   ⚠️ Google 自报 conversions（126~200/天）与第 5 列（83~173/天）不是同一个东西，
--      且 conversion_value 不是收入；禁止拿 conversions 替换第 5 列。
--   ✅ 14:18 用户补表头（共 16 列）：日期/消费/展现/点击/平均点击价格/安装/
--      单用户获客成本/translated/registered/clickTry/tryPro/paid/
--      pro月费订单数/max月费订单数/pro年费订单数/max年费订单数。
--      前 6 列已 100% 对上；第 7 列 translated 基本可复算（见 Q5）；
--      第 8~15 列是「安装队列 + 30 天窗口」漏斗，仓内无定稿 SQL，口径待确认（P025/P045）。
--
-- 【时间口径】北京自然日 D = UTC (D-1)16:00 ~ D 16:00。
--   广告侧 report_date 是账户时区 Asia/Shanghai，可直接等值 JOIN；
--   我方侧禁止在 WHERE 里 to_date(date_add(...))（百亿级表会全表扫被 kill），
--   粗 UTC 窗保分区裁剪，北京日只放在 SELECT 投影。
--   下方固定窗 = 北京日 2026-10-23~11-15 ⇒ UTC 2026-10-22 16:00 ~ 2026-11-15 16:00。
--   自动更新时把两处窗口同时换成需要回刷的区间（建议 T-8 ~ T-1，覆盖 Google 7 天回刷）。
--
-- 【回刷注意】03:40 的 Google 同步每天回刷近 7 天，历史天花费/点击会变、我方设备数不变
--   ⇒ CPA/CPC 会跟着变。写飞书必须按日期覆盖更新（MERGE 语义），不能只追加当天行。
-- =============================================================================


-- ============ Q1 主查询：一次产出可自动更新的 7 列（日期 + 6 个指标）============
-- 对应飞书表第 1~6 个数值列：花费 / 展示 / 点击 / CPC / 我方设备 / CPA
WITH ads AS (
    SELECT report_date AS dt,
           sum(clicks)                       AS clicks,
           sum(impressions)                   AS impressions,
           round(sum(cost_micros) / 1e6, 2)   AS cost_cny
    FROM immdata.google_ads_campaign_daily
    WHERE customer_id = '6036515162'
      AND campaign_id = '21597353947'
      AND report_date BETWEEN '2026-10-23' AND '2026-11-15'
    GROUP BY 1
),
ours AS (
    SELECT to_date(date_add(hour, 8, createtime)) AS dt,
           count(DISTINCT deviceid)               AS devices
    FROM immdata.imt_campaigninfo
    WHERE createtime >= '2026-10-22 16:00:00'
      AND createtime <  '2026-11-15 16:00:00'
      AND utmcampaign = 'googlekeywords_website_translate_download'
    GROUP BY 1
)
SELECT a.dt                                              AS report_date,
       a.cost_cny                                          AS cost_cny,
       a.impressions                                        AS impressions,
       a.clicks                                             AS clicks,
       round(a.cost_cny / nullif(a.clicks, 0), 2)          AS cpc_cny,
       o.devices                                           AS our_devices,
       round(a.cost_cny / nullif(o.devices, 0), 2)         AS cpa_cny
FROM ads a
LEFT JOIN ours o ON o.dt = a.dt
ORDER BY 1;


-- ============ Q2 投入侧单表校验（与 Q1 的 cost/impressions/clicks 应完全相等）============
SELECT report_date,
       sum(clicks)                     AS clicks,
       sum(impressions)               AS impressions,
       round(sum(cost_micros)/1e6, 2) AS cost_cny,
       round(sum(conversions), 2)     AS google_conversions
FROM immdata.google_ads_campaign_daily
WHERE customer_id = '6036515162' AND campaign_id = '21597353947'
  AND report_date BETWEEN '2026-10-23' AND '2026-11-15'
GROUP BY 1 ORDER BY 1;


-- ============ Q3 效果侧单表校验（与 Q1 的 our_devices 应完全相等）============
SELECT to_date(date_add(hour, 8, createtime)) AS bj_date,
       count(DISTINCT deviceid)             AS devices
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-10-22 16:00:00'
  AND createtime <  '2026-11-15 16:00:00'
  AND utmcampaign = 'googlekeywords_website_translate_download'
GROUP BY 1 ORDER BY 1;


-- ============ Q4 渠道来源校验（这个 campaign 的 UTM 是否只有一种）============
-- 实测：1 行，utm=googlekeywords_website_translate_download，91 行 / 8050 点击 / ¥21199.13
SELECT regexp_extract(expanded_final_url, 'utm_campaign=([^&]+)', 1) AS utm_campaign,
       count(*) AS rows, sum(clicks) AS clicks,
       round(sum(cost_micros)/1e6, 2) AS cost_cny
FROM immdata.google_ads_landingpage_daily
WHERE customer_id = '6036515162' AND campaign_id = '21597353947'
  AND report_date BETWEEN '2026-10-23' AND '2026-11-15'
GROUP BY 1 ORDER BY cost_cny DESC;


-- ============ Q5 第 7 列 translated 复算（14:17 实跑）============
-- imt_campaigninfo.translated 是回填标志，历史越早库内当前值比飞书静态快照多几台：
--   10-23 飞书 101 / 库 103；11-09~15 飞书 126/147/148/165/163/118/123
--   vs 库 126/147/148/166/163/118/124 ⇒ 24 天差 0~6 台，近 5 天几乎完全一致。
SELECT to_date(date_add(hour, 8, createtime)) AS bj_date,
       count(DISTINCT deviceid) AS install,
       count(DISTINCT CASE WHEN translated = 1 THEN deviceid END) AS translated
FROM immdata.imt_campaigninfo
WHERE createtime >= '2026-10-22 16:00:00'
  AND createtime <  '2026-11-15 16:00:00'
  AND utmcampaign = 'googlekeywords_website_translate_download'
GROUP BY 1 ORDER BY 1;


-- =============================================================================
-- 【第 8~15 列：✅ 14:33 用户提供现成 SQL，来源已确认，见下方 Q6】
-- 历史排查记录（14:17，保留备查）：paid == 后四列之和 24/24；max月费/max年费 24 天全 0；
--   曾排除「设备桥接 userid 数」「真新装 30 天队列」「isdeleted 过滤」「Google conversions」。
--   这些排除项均基于错误假设（30 天窗口 / installtime 队列），用户给出真 SQL 后已作废。
-- =============================================================================
--
-- =============================================================================
-- ✅ 14:33 用户提供后端现成 SQL（MySQL 语法），确认后 8 列来源，已翻译为 Databend 版 = Q6
--    原 SQL 逻辑：UTM 安装队列（c.utmcampaign 非空）× 安装后 100 天窗口
--      registerIn100day  = 设备桥接 user 后 0~100 天内创建的 userid 去重
--      clickIn100day     = 该 user 的 checkout session userid 去重（0~100 天）
--      TryIn100day       = session 挂的 goods.EnableTrial=true 且订单 yearly/monthly、AmountPaid=0
--      SubscribeIn100day = orderstatus=finished 且 monthly/yearly、AmountPaid>0
--      后四列 = 付费订单按 subscriptiontype 拆分（yearly / monthly / max_yearly / max_monthly）
--    ⚠️ 是 100 天窗口，不是之前推测的 30 天；窗口随「当前日期 - 安装日」增长，
--       早期日期的飞书静态快照必然小于库内当前累计值（与 Google 回刷同类问题）。
--    ⚠️ 原 SQL 用 date_diff(day, c.CreateTime, X.CreateTime)：未做北京日 +8，
--       c 侧用 add_hours(CreateTime,8) 分组；这里 c 侧保留 +8，事件侧保持原值以复现。
--    JOIN 链 c→d→u→s→o 全部 count(DISTINCT) ⇒ 行数膨胀不影响计数，但单设备多 session/订单。
--
-- 【14:35 逐日比对结论：Q6 就是飞书表后 8 列的来源，口径正确】
-- 与飞书 24 天逐列对比（库内当前值 vs 飞书静态快照），所有差异方向均为「库 ≥ 飞书」、
--   无一负值；paid == 四列之和 0 违例；max月费/max年费 24/24 全 0 完全吻合；
--   11-09~11-11 连续 3 天 10 列全部一致。吻合天数(共24)：
--   安装 24 / translated 5 / registered 10 / clickTry 13 / tryPro 20 / paid 16 /
--   pro月 19 / max月 24 / pro年 18 / max年 24。
-- 差异是「100 天滚动窗口 + 回填标志」的快照时点效应：飞书每行的窗口只算到它被导出的那天，
--   早期安装日（10-23~11-08）离快照日久 ⇒ 后续注册/试用/付费陆续进入窗口，库内当前值更大；
--   越靠近快照日越一致。已用 fuse_snapshot 回退到 11-16 19:00 重跑：吻合仅小幅上升
--   (translated 5→7 / registered 10→12)，证明飞书行非同一时刻快照，无法用单一时间点复原。
--   ⇒ 自动更新统一用库内当前值（T 时点的滚动累计），口径一致；但要接受历史行会缓慢爬升，
--     与飞书旧快照存在差异属正常，不是数据错（与 Google 回刷同类）。
-- =============================================================================

-- ============ Q6 后 8 列（translated~max年费）复算：用户 SQL 的 Databend 版 ============
-- utmcampaign 换成繁体 campaign 的 'googlekeywords_website_translate_download'。
-- c 侧加 UTC 粗过滤保分区裁剪；北京日 2026-10-17~11-16 ⇒ UTC 10-16 16:00 ~ 11-16 16:00。
SELECT event_datetime AS report_date,
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
  SELECT to_date(date_add(hour,8,c.createtime)) AS event_datetime,
         c.utmcampaign, c.utmsource, c.utmmedium,
         count(DISTINCT c.deviceid) AS install,
         count(DISTINCT IF(c.translated = 1, c.deviceid, NULL)) AS translated,
         coalesce(count(DISTINCT IF(datediff(day,c.createtime,u.createtime) BETWEEN 0 AND 100, u.id, NULL)),0) AS registerIn100day,
         coalesce(count(DISTINCT IF(datediff(day,c.createtime,s.createtime) BETWEEN 0 AND 100, s.userid, NULL)),0) AS clickIn100day,
         coalesce(count(DISTINCT IF(get(try_parse_json(s.subscriptiongoodssnap),'EnableTrial') = TRUE
                                    AND o.subscriptiontype IN ('yearly','monthly') AND o.amountpaid = 0
                                    AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS TryIn100day,
         coalesce(count(DISTINCT IF(o.orderstatus = 'finished'
                                    AND (o.subscriptiontype LIKE '%monthly%' OR o.subscriptiontype LIKE '%yearly%')
                                    AND o.amountpaid > 0 AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS SubscribeIn100day,
         coalesce(count(DISTINCT IF(o.subscriptiontype IN ('yearly','onetime_yearly','onetime_dogpay_yearly')
                                    AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                    AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS yearlyIn100day,
         coalesce(count(DISTINCT IF(o.subscriptiontype IN ('monthly','onetime_dogpay_monthly')
                                    AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                    AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS monthlyIn100day,
         coalesce(count(DISTINCT IF(o.subscriptiontype IN ('max_yearly','onetime_dogpay_max_yearly','onetime_max_yearly')
                                    AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                    AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS max_yearlyIn100day,
         coalesce(count(DISTINCT IF(o.subscriptiontype IN ('max_monthly','onetime_dogpay_max_monthly')
                                    AND o.orderstatus = 'finished' AND o.amountpaid > 0
                                    AND datediff(day,c.createtime,o.createtime) BETWEEN 0 AND 100, o.id, NULL)),0) AS max_monthlyIn100day
  FROM (((immdata.imt_campaigninfo c
          LEFT JOIN immdata.imt_deviceinfo d ON c.deviceid = d.deviceid)
         LEFT JOIN immdata.imt_userinfo u ON d.userid = u.id)
         LEFT JOIN immdata.imt_checkoutsession s ON u.id = s.userid)
         LEFT JOIN immdata.imt_subscriptiongoodsorder o ON s.userid = o.userid
  WHERE c.utmcampaign = 'googlekeywords_website_translate_download'
    AND c.createtime >= '2026-10-16 16:00:00' AND c.createtime < '2026-11-16 16:00:00'
  GROUP BY event_datetime, c.utmcampaign, c.utmsource, c.utmmedium
) v
WHERE event_datetime >= to_date('2026-10-17') AND event_datetime < to_date('2026-11-17')
GROUP BY event_datetime
ORDER BY event_datetime;
