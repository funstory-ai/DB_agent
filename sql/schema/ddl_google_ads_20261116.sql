-- T119 / Google Ads 接入 Databend 目标表结构（2026-11-16）
-- 执行：F:/python312/python.exe scripts/setup_google_ads_schema.py
-- 说明：外部投放数据与生产数仓隔离，单独放 growth 库；现有 scripts/db.py 保持只读不变。
-- 所有金额字段均为「账户币种原值」，不是 micros；来自 API 时须先 /1e6。
-- ⚠️ 2026-11-16 实测：4623896831 是 MCC 经理账号（USD），其下 4 个启用子账号均为 CNY。
--    界面 $ 金额是 MCC 层折算值；库内按 customer_id 存各子账号本币，禁止跨币种直接 sum。

CREATE DATABASE IF NOT EXISTS growth;

-- ① 广告侧事实表：一张表容纳多粒度，CSV 与后续 API 写同一张表
-- 去重策略：每次导入生成 ingest_batch，重跑时先 DELETE 同批次再 INSERT（见 ingest 脚本）
CREATE TABLE IF NOT EXISTS growth.google_ads_daily (
    report_date        DATE,
    granularity        VARCHAR,          -- ACCOUNT / CAMPAIGN / AD_GROUP / KEYWORD / SEARCH_TERM
    customer_id        VARCHAR,          -- 去横线，如 4623896831
    campaign_id        VARCHAR,
    campaign_name      VARCHAR,          -- 与 webdata.ads_webapp_new_user_attribution.campaign 对齐的关键键
    ad_group_id        VARCHAR,
    ad_group_name      VARCHAR,
    criterion_id       VARCHAR,
    keyword_text       VARCHAR,
    clicks             BIGINT,
    impressions        BIGINT,
    cost_amount        DECIMAL(20,4),    -- 该 customer_id 的账户本币，非 micros
    average_cpc        DECIMAL(20,4),
    conv_count         DECIMAL(20,2),    -- Google 自归因转化，未导出时填 0 且看 metric_flags
    conv_value         DECIMAL(20,2),
    currency           VARCHAR,          -- 按账号实测，CNY / USD 均可能
    account_timezone   VARCHAR,          -- 广告账户时区；与北京日对齐前必须确认
    metric_flags       VARCHAR,          -- 本次导入实际提供的指标清单，逗号分隔
    source_type        VARCHAR,          -- CSV / API
    source_file        VARCHAR,
    ingest_batch       VARCHAR,
    ingested_at        TIMESTAMP
);

-- ② 导入批次台账：P043 追溯「当时真正导了哪个文件、什么范围、合计多少」
CREATE TABLE IF NOT EXISTS growth.ingest_log (
    ingest_batch    VARCHAR,
    source_type     VARCHAR,
    source_file     VARCHAR,
    granularity     VARCHAR,
    row_count       BIGINT,
    date_min        DATE,
    date_max        DATE,
    sum_clicks      BIGINT,
    sum_impressions BIGINT,
    sum_cost        DECIMAL(20,4),
    note            VARCHAR,
    ingested_at     TIMESTAMP
);

-- ③ 渠道映射表：Google Ads 后台 campaign 名 ≠ 埋点 utm_campaign，必须人工维护映射
-- 空表起步，待 CSV/API 到位后按实测名称填入；禁止写死猜测值（P045）
CREATE TABLE IF NOT EXISTS growth.channel_campaign_map (
    ads_campaign_name VARCHAR,
    utm_campaign      VARCHAR,
    utm_source        VARCHAR,
    utm_medium        VARCHAR,
    channel_group     VARCHAR,
    valid_from        DATE,
    valid_to          DATE,
    note              VARCHAR
);
