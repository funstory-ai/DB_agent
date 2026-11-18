-- =============================================================================
-- Google Ads 贴源表（ODS）完整建表 SQL / 2026-11-16
-- 目标：自动化看「广告投入 × 营销效果」，渠道级，结果全部走 Superset 侧 SQL。
-- 本文件 = 最小必需表集合（6 张），可整份直接执行；不含结果表 / 中间表 / 映射表 / 宽表。
-- 2026-11-16 16:32 用户定案：「不是全表，是为完成目标的最小限度表；后续新增要方便」。
-- =============================================================================
--
-- 【为什么是这 6 张】按看板必须回答的问题反推，每张都有不可替代的作用：
--   投入总额（对账）        -> ① campaign_daily        账号×日×campaign 花费事实
--   花费按渠道分桶（桥接）  -> ② landingpage_daily     日×campaign×落地页URL，URL 自带 UTM 且带 cost_micros
--   跨账号币种/时区正确     -> ③ customer_snapshot     币种、时区、MCC、自动标记
--   campaign 可读/可过滤    -> ④ campaign_snapshot     中文投放名、状态、渠道类型、出价
--   无落地页数据的渠道兜底  -> ⑤ ad_url_snapshot       广告配置 URL；KOL/display 类 UTM 只在这里出现
--   解释 Google 转化列      -> ⑥ conversion_action_snapshot  动作名/类别/是否计入 conversions
--   效果侧（设备/新装/付费）不落表：Superset SQL 直接读 immdata 既有业务表
--     imt_campaigninfo / imt_deviceinfo / imt_subscriptiongoodsorder / user_behaviour。
--   6 张贴源表与效果侧业务表同在 immdata，无需跨库 JOIN。
--
-- 【同步方式】用户 16:17 定案「一步直接写」：
--   H:\imt_data_synch\google_ads_direct_sync.py 在 ps@ps 上直接
--   Google Ads API → Databend MERGE INTO immdata.*（原库），不经 OSS / imt_load / K8s。
--   脚本按 merge_key 幂等、每日回刷 7 天、失败不删旧数据。
--
-- 【贴源原则】一资源一表，字段 = GAQL 实际 SELECT 出来的原始字段；
--   cost_micros 保留原始 micros，不 /1e6；不存 average_cpc / ctr / cpm 等派生指标；
--   UTM 参数保留在 URL 原文里，解析与渠道归集交给 Superset 侧 SQL。
--   字段来源：11-16 API 实跑（output/google_ads/inventory_20261116.json、
--   scripts/fetch_google_ads_api.py 的 GAQL_CAMPAIGN_DAILY / account_tree），
--   ②⑥ 的 GAQL 与字段于 16:32 再次实跑验证（4 个启用子账号均通过）。
--
-- ⚠️ 本文件只撰写，不在对话里代跑（AGENTS.md：ETL 可撰写、禁止代跑）。
--   **必须先执行本 DDL**：直写脚本会查 system.columns 校验列集合，
--   表不存在或列不齐直接报错停止，不自举建表、不自动加列。
--   脚本 COLUMN_TYPES 与此处逐列对应，改动需两边同步。
-- ⚠️ growth.google_ads_daily（T119 旧宽表，现有 182 行）留在原处，不迁移、不删不改（P044）。
-- ⚠️ 金额按账户本币原值，currency_code 随行存；跨币种禁止直接 sum。
--   MCC 界面 USD 是折算值，不参与对账（P045）。
-- ⚠️ 账户时区实测 Asia/Shanghai = 北京日，report_date 可直接与我方日期 JOIN。
-- ⚠️ ①② 是**同一批点击的两种切分**，禁止相加：
--   11-09~15 中文 5037 点击 / ¥10213.4971 + 韩国 190 / ¥288.96 = 5227 / ¥10502.45711，
--   两边完全相等。① 用于总额对账，② 用于按 UTM 分渠道；② 只覆盖有
--   expanded_landing_page_view 数据的账号（该窗口日本/APP 账号 0 行属正常，非报错）。
-- ⚠️ conversions 是 Google 自归因，不是我方 P013 付费，也不是购买数：
--   实测中文账号 25 个转化动作里 include_in_conversions_metric=True 仅 7 个，
--   且 "Immersive Translate (web) purchase" 为 False。必须用 ⑥ 解释口径。
--   conversions 有归因延迟（日回刷 7 天），与 clicks 不同期，不能直接相除。
-- ⚠️ 所有细分资源各自独立成表，同一批点击在不同维度各记一次，禁止跨表相加。

-- 【不建库 / 全落原库】2026-11-17 用户明确「全放在原库下，没让你新建一个库」：
--   原库 = immdata（业务表 80 张；H:\imt_data_synch 的 imt_load 写仓默认目标库）。
--   ⚠️ growth 是 11-16 T119 期间新建的库（仅 3 张表，创建时间 03:13），本次
--      不沿用、不新建、不迁移；其中三张旧表保留不动（P044，见下）。
--   本文件只建表，不含任何 CREATE DATABASE / CREATE SCHEMA。

-- ① 账号 × 日 × campaign：唯一的投入事实表（指标全部是 API 原值）
--    merge_key = (report_date, customer_id, campaign_id)
CREATE TABLE IF NOT EXISTS immdata.google_ads_campaign_daily (
    report_date         DATE,
    customer_id         VARCHAR,
    campaign_id         VARCHAR,
    campaign_name       VARCHAR,
    currency_code       VARCHAR,          -- 账户本币，实测 4 个启用子账号均 CNY
    account_timezone    VARCHAR,          -- 实测 Asia/Shanghai
    clicks              BIGINT,
    impressions         BIGINT,
    cost_micros         BIGINT,           -- 原始 micros；SQL 侧 /1e6 才是金额
    conversions         DOUBLE,           -- Google 自归因转化，不是我方 P013 付费
    conversions_value   DOUBLE,
    api_version         VARCHAR,
    gaql                VARCHAR,          -- 本次真正执行的 GAQL（P043 追溯）
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- ② 账号 × 日 × campaign × 落地页URL：渠道桥接事实表（本轮新增）
--    expanded_final_url 原样保存，utm_source / utm_medium / utm_campaign 都在 URL 里，
--    Superset 侧解析即可按渠道桶汇总 cost_micros / clicks，无需映射表、无需按 campaign 猜 UTM。
--    实测中文账号 30 天 932 行 UTM 覆盖 100%（6 个 utm_campaign）；
--    加 metrics.conversions 不改变分段（216 行、clicks/cost 合计不变）。
--    一个 campaign 有多个 UTM 时，本表按 URL 天然分摊，解决旧映射表的一对多问题。
--    merge_key = (report_date, customer_id, campaign_id, expanded_final_url)
CREATE TABLE IF NOT EXISTS immdata.google_ads_landingpage_daily (
    report_date         DATE,
    customer_id         VARCHAR,
    campaign_id         VARCHAR,
    campaign_name       VARCHAR,
    expanded_final_url  VARCHAR,          -- 原样 URL，含 utm_* / gad_* / gbraid 等参数
    currency_code       VARCHAR,
    account_timezone    VARCHAR,
    clicks              BIGINT,
    impressions         BIGINT,
    cost_micros         BIGINT,           -- 原始 micros；与 ① 同一批花费，禁止相加
    conversions         DOUBLE,
    conversions_value   DOUBLE,
    api_version         VARCHAR,
    gaql                VARCHAR,
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- ③ 账号树 / 账号配置日快照（币种、时区、自动标记、跟踪模板）
--    merge_key = (snapshot_date, customer_id)
CREATE TABLE IF NOT EXISTS immdata.google_ads_customer_snapshot (
    snapshot_date       DATE,
    customer_id         VARCHAR,
    descriptive_name    VARCHAR,
    manager             BOOLEAN,
    level               BIGINT,
    status              VARCHAR,
    currency_code       VARCHAR,
    time_zone           VARCHAR,
    auto_tagging_enabled BOOLEAN,
    tracking_url_template VARCHAR,
    final_url_suffix    VARCHAR,
    api_version         VARCHAR,
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- ④ campaign 配置日快照（中文投放名、渠道类型、URL 后缀原文）
--    merge_key = (snapshot_date, customer_id, campaign_id)
CREATE TABLE IF NOT EXISTS immdata.google_ads_campaign_snapshot (
    snapshot_date       DATE,
    customer_id         VARCHAR,
    campaign_id         VARCHAR,
    campaign_name       VARCHAR,
    status              VARCHAR,
    advertising_channel_type  VARCHAR,
    bidding_strategy_type     VARCHAR,
    final_url_suffix    VARCHAR,
    tracking_url_template     VARCHAR,
    api_version         VARCHAR,
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- ⑤ 广告最终到达网址原文快照（UTM 的配置侧来源，一行一个 URL）
--    final_urls 是 repeated 字段，展开为多行并带 url_index，不解析、不归集、不建映射表。
--    与 ② 互补：实测 KOL / display 类 UTM（13 个小说名 utm_source）只在这里出现，
--    expanded_landing_page_view 没有这些渠道的数据；没有这张表，这部分花费无法打渠道标签。
--    merge_key = (snapshot_date, customer_id, campaign_id, ad_group_id, ad_id, url_index)
CREATE TABLE IF NOT EXISTS immdata.google_ads_ad_url_snapshot (
    snapshot_date       DATE,
    customer_id         VARCHAR,
    campaign_id         VARCHAR,
    campaign_name       VARCHAR,
    ad_group_id         VARCHAR,
    ad_id               VARCHAR,
    ad_name             VARCHAR,
    url_index           BIGINT,
    final_url           VARCHAR,          -- 原样 URL，含 utm_* / gad_* / gbraid 等参数
    final_url_suffix    VARCHAR,
    tracking_url_template     VARCHAR,
    api_version         VARCHAR,
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- ⑥ 转化动作配置日快照（本轮新增）：解释 ①② 里的 conversions 到底算的是什么
--    action_type / status / category / counting_type 存 protobuf 枚举名（HIDDEN / PURCHASE ...）。
--    include_in_conversions_metric=False 的动作不计入 metrics.conversions；
--    primary_for_goal 标识该账号的主转化目标。
--    实测 4 个账号均有数据：中文 25 / 日本 13 / 韩国 13 / APP 15 行。
--    merge_key = (snapshot_date, customer_id, conversion_action_id)
CREATE TABLE IF NOT EXISTS immdata.google_ads_conversion_action_snapshot (
    snapshot_date       DATE,
    customer_id         VARCHAR,
    conversion_action_id     VARCHAR,
    conversion_action_name   VARCHAR,
    action_type         VARCHAR,          -- API 原字段 conversion_action.type，避开 SQL 关键字 type
    status              VARCHAR,
    category            VARCHAR,
    include_in_conversions_metric BOOLEAN,
    primary_for_goal    BOOLEAN,
    counting_type       VARCHAR,
    api_version         VARCHAR,
    ingest_batch        VARCHAR,
    ingested_at         TIMESTAMP
);

-- =============================================================================
-- 【暂缓，但已实跑验证可用】以下不属于「完成渠道级投入×效果」的最小集合，
-- 属投放优化 / 精细化下钻，等 Superset 侧确实要看再加。加表不改写库逻辑：
--   1) 在本文件加一张 CREATE TABLE；
--   2) 在 google_ads_direct_sync.py 加 GAQL 常量、COLUMN_TYPES 一项、
--      _rows_<资源>() builder、RESOURCES 一项；其余（连接/校验/MERGE/幂等）全部复用。
--
--   google_ads_campaign_conversion_daily  按 segments.conversion_action 拆转化
--       （中文账号 11-09~15 实测 43 行；可把 154.78/天 的 conversions 拆成具体动作）
--   google_ads_keyword_daily              关键词层（30 天实测 6,254 行）
--   google_ads_search_term_daily         搜索词层（30 天实测 29,105 行）
--   google_ads_adgroup_daily / google_ads_geo_daily / google_ads_device_daily
--       广告组 / 地域 / 设备×网络（30 天实测 182 / 1,089 / 267 行）
--
--   ⚠️ 一律「一资源一表 + 贴源字段」，仍不建结果表、中间表或映射表。
-- =============================================================================
