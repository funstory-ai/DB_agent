-- =============================================================================
-- T119 后续：Google Ads ODS 首次同步验收 SQL / 2026-11-17
-- 目标库 immdata（原库），全部只读 SELECT，可在 Superset SQL Lab / bendsql 执行。
--
-- 锚点（参考值，非硬校验）：2026-11-09~15 于 11-16 实测 5227 点击 / 35769 展示 /
--       cost_micros 10502457110 = ¥10502.45711（T119 已与后台截图对账）。
-- ⚠️ 11-17 ps@ps 复跑同窗为 5226 / 35764 / 10503747110 = ¥10503.74711：
--    Google 侧历史回刷（无效点击过滤）会小幅改动历史数据，脚本默认回刷 7 天正是为此。
--    硬校验是 Q3 两表完全相等 + Q4 返回 0 行；Q2 允许小幅浮动，以当日 API 返回为准。
-- ⚠️ ① campaign_daily 与 ② landingpage_daily 是同一批点击的两种切分，禁止相加；
--    conversions 是 Google 自归因、有归因延迟，不是我方 P013 付费，也不是购买数；
--    跨 currency_code 禁止直接 sum。
-- =============================================================================

-- Q1 六表行数与水位：首跑后应全部 > 0；快照表 d_max = 运行日
SELECT 'campaign_daily' AS tbl, count(*) AS rows, min(report_date) AS d_min, max(report_date) AS d_max
FROM immdata.google_ads_campaign_daily
UNION ALL SELECT 'landingpage_daily', count(*), min(report_date), max(report_date)
FROM immdata.google_ads_landingpage_daily
UNION ALL SELECT 'customer_snapshot', count(*), min(snapshot_date), max(snapshot_date)
FROM immdata.google_ads_customer_snapshot
UNION ALL SELECT 'campaign_snapshot', count(*), min(snapshot_date), max(snapshot_date)
FROM immdata.google_ads_campaign_snapshot
UNION ALL SELECT 'ad_url_snapshot', count(*), min(snapshot_date), max(snapshot_date)
FROM immdata.google_ads_ad_url_snapshot
UNION ALL SELECT 'conversion_action_snapshot', count(*), min(snapshot_date), max(snapshot_date)
FROM immdata.google_ads_conversion_action_snapshot;

-- Q2 锚点窗总额：期望 49 行；数值参考 11-16 的 5227/35769/10502457110，
--    Google 回刷后允许小幅差异（11-17 实测 5226/35764/10503747110）
SELECT count(*) AS rows, sum(clicks) AS clicks, sum(impressions) AS impressions,
       sum(cost_micros) AS cost_micros, sum(cost_micros) / 1000000.0 AS cost_cny
FROM immdata.google_ads_campaign_daily
WHERE report_date BETWEEN '2026-11-09' AND '2026-11-15';

-- Q3 ①② 同窗一致性：两行 clicks / impressions / cost_micros 必须完全相等
--    （行数不同是正常的：① 49 行按 campaign，② 254 行按落地页 URL）
SELECT 'campaign_daily' AS src, count(*) AS rows, sum(clicks) AS clicks,
       sum(impressions) AS impressions, sum(cost_micros) AS cost_micros
FROM immdata.google_ads_campaign_daily
WHERE report_date BETWEEN '2026-11-09' AND '2026-11-15'
UNION ALL
SELECT 'landingpage_daily', count(*), sum(clicks), sum(impressions), sum(cost_micros)
FROM immdata.google_ads_landingpage_daily
WHERE report_date BETWEEN '2026-11-09' AND '2026-11-15';

-- Q4 merge_key 唯一性：以下两条都应返回 0 行；有行则后续 MERGE 会报 4001
--    ① (report_date, customer_id, campaign_id)
SELECT report_date, customer_id, campaign_id, count(*) AS n
FROM immdata.google_ads_campaign_daily
GROUP BY 1, 2, 3 HAVING count(*) > 1;
--    ② (report_date, customer_id, campaign_id, expanded_final_url)
SELECT report_date, customer_id, campaign_id, expanded_final_url, count(*) AS n
FROM immdata.google_ads_landingpage_daily
GROUP BY 1, 2, 3, 4 HAVING count(*) > 1;

-- Q5 ② 的 UTM 覆盖率：锚点窗期望 254 行 / 254 带 utm_campaign（100%）
SELECT count(*) AS rows,
       sum(CASE WHEN expanded_final_url LIKE '%utm_campaign=%' THEN 1 ELSE 0 END) AS with_utm
FROM immdata.google_ads_landingpage_daily
WHERE report_date BETWEEN '2026-11-09' AND '2026-11-15';

-- Q6 转化动作口径：期望 66 个动作 / 25 个计入 conversions / purchase 类不计入
SELECT count(*) AS actions,
       sum(CASE WHEN include_in_conversions_metric = TRUE THEN 1 ELSE 0 END) AS included,
       sum(CASE WHEN action_type = 'PURCHASE' AND include_in_conversions_metric = FALSE
                THEN 1 ELSE 0 END) AS purchase_not_counted
FROM immdata.google_ads_conversion_action_snapshot;

-- Q7 批次血缘与写入时间：确认每次同步的 ingest_batch、有无重复批次
SELECT ingest_batch, count(*) AS rows,
       min(ingested_at) AS t_min, max(ingested_at) AS t_max
FROM immdata.google_ads_campaign_daily
GROUP BY ingest_batch ORDER BY t_max DESC;

-- Q8 账号 × 币种 × 时区：跨币种禁止直接 sum，看板按 currency_code 分组
SELECT customer_id, currency_code, account_timezone,
       count(*) AS rows, sum(cost_micros) / 1000000.0 AS cost
FROM immdata.google_ads_campaign_daily
GROUP BY 1, 2, 3 ORDER BY 1;

-- Q9 每日水位：检查有无断日 / 空日，回刷是否覆盖到
SELECT report_date, count(*) AS rows, sum(clicks) AS clicks,
       sum(cost_micros) / 1000000.0 AS cost
FROM immdata.google_ads_campaign_daily
GROUP BY report_date ORDER BY report_date;
