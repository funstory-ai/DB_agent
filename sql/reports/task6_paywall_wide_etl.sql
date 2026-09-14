-- =============================================================================
-- 付费墙监测：宽表中间表 + 增量 TASK（写仓最终定稿 · 整段执行）
-- 规范大类：dashboard；P022
-- 任务：docs/tasks/dashboard_paywall_roi_20260817.md
-- 本查数仓库只读，勿在只读账号执行本文件
--
-- 本文件为最终宽表写仓脚本（合并原 wide_etl_patch + wide_rate_dau_patch）：
--   imm_paywall_daily_wide_hit
--   imm_paywall_daily_wide_paywall_rate（六维 dau，与 hit 同 grain INNER JOIN）
-- 幂等：两表均 DROP+CREATE+INSERT；整段跑两遍不叠层。
-- 禁止：五维 dau 贴六维 hit（Filter 全空时 SUM(dau)≈kpi×N）。
--
-- 关联：
--   主 ETL   sql/reports/task6_paywall_daily_etl.sql（须先有 first_device）
--   挂板读表 sql/reports/task6_paywall_daily_board.sql
-- =============================================================================


-- -----------------------------------------------------------------------------
-- §0 暂停 / 删除宽表 TASK（重建前）
-- -----------------------------------------------------------------------------
ALTER TASK IF EXISTS update_imm_paywall_daily_wide_hit SUSPEND;
ALTER TASK IF EXISTS update_imm_paywall_daily_wide_paywall_rate SUSPEND;
DROP TASK IF EXISTS update_imm_paywall_daily_wide_hit;
DROP TASK IF EXISTS update_imm_paywall_daily_wide_paywall_rate;


-- -----------------------------------------------------------------------------
-- §1 建表（DROP+CREATE 幂等）
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS immdata.imm_paywall_daily_wide_hit;
DROP TABLE IF EXISTS immdata.imm_paywall_daily_wide_paywall_rate;

CREATE TABLE immdata.imm_paywall_daily_wide_hit (
  dt_bj DATE,
  install_from VARCHAR,
  platform_type VARCHAR,
  campaign VARCHAR,
  lang_bucket VARCHAR,
  ab_tag VARCHAR,
  exp_group VARCHAR,
  paywall_uv BIGINT,
  update_time TIMESTAMP
);

CREATE TABLE immdata.imm_paywall_daily_wide_paywall_rate (
  dt_bj DATE,
  install_from VARCHAR,
  platform_type VARCHAR,
  campaign VARCHAR,
  lang_bucket VARCHAR,
  ab_tag VARCHAR,
  exp_group VARCHAR,
  paywall_uv BIGINT,
  dau BIGINT,
  paywall_rate DOUBLE,
  update_time TIMESTAMP
);


-- -----------------------------------------------------------------------------
-- §2 全量回填
-- -----------------------------------------------------------------------------

-- §2.1 wide_hit
INSERT INTO immdata.imm_paywall_daily_wide_hit
(
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  paywall_uv, update_time
)
WITH hit_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'user_need_pro'
    AND b.trigger = 'freeUsageLimitModal'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= '2026-05-06 16:00:00'
    AND b.created_ts < add_hours(date(add_hours(now(), 8)), -8)
)
SELECT
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  COUNT(DISTINCT device_id), NOW()
FROM hit_events
GROUP BY 1, 2, 3, 4, 5, 6, 7;


-- §2.2 wide_paywall_rate（六维 dau，与 hit 同 grain）
INSERT INTO immdata.imm_paywall_daily_wide_paywall_rate
(
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  paywall_uv, dau, paywall_rate, update_time
)
WITH hit_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'user_need_pro'
    AND b.trigger = 'freeUsageLimitModal'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= '2026-05-06 16:00:00'
    AND b.created_ts < add_hours(date(add_hours(now(), 8)), -8)
),
dau_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'translate_page'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= '2026-05-06 16:00:00'
    AND b.created_ts < add_hours(date(add_hours(now(), 8)), -8)
),
hit AS (
  SELECT dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
         COUNT(DISTINCT device_id) AS paywall_uv
  FROM hit_events
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
dau AS (
  SELECT dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
         COUNT(DISTINCT device_id) AS dau
  FROM dau_events
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  h.dt_bj, h.install_from, h.platform_type, h.campaign, h.lang_bucket, h.ab_tag, h.exp_group,
  h.paywall_uv, d.dau,
  h.paywall_uv * 1.0 / NULLIF(d.dau, 0), NOW()
FROM hit h
INNER JOIN dau d
  ON h.dt_bj = d.dt_bj
 AND h.install_from = d.install_from
 AND h.platform_type = d.platform_type
 AND h.campaign = d.campaign
 AND h.lang_bucket = d.lang_bucket
 AND h.ab_tag = d.ab_tag
 AND h.exp_group = d.exp_group;


-- -----------------------------------------------------------------------------
-- §3 TASK · 近 31 北京日增量（UTC 21:50 / 21:55，在 daily_dim 21:40 之后）
-- -----------------------------------------------------------------------------

CREATE TASK update_imm_paywall_daily_wide_hit
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 50 21 * * *' 'UTC'
COMMENT = '付费墙：近31日 wide_hit 六维宽表'
AS
BEGIN
  DELETE FROM immdata.imm_paywall_daily_wide_hit
  WHERE dt_bj >= DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1))
    AND dt_bj <= add_days(date(add_hours(now(), 8)), -1);

  INSERT INTO immdata.imm_paywall_daily_wide_hit
(
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  paywall_uv, update_time
)
WITH win AS (
  SELECT
    add_hours(DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1)), -8) AS ts_lo,
    add_hours(date(add_hours(now(), 8)), -8) AS ts_hi,
    DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1)) AS dt_lo,
    add_days(date(add_hours(now(), 8)), -1) AS dt_hi
),
hit_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  CROSS JOIN win w
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'user_need_pro'
    AND b.trigger = 'freeUsageLimitModal'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= w.ts_lo
    AND b.created_ts < w.ts_hi
    AND CAST(DATEADD(hour, 8, b.created_ts) AS DATE) >= w.dt_lo
    AND CAST(DATEADD(hour, 8, b.created_ts) AS DATE) <= w.dt_hi
)
SELECT
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  COUNT(DISTINCT device_id), NOW()
FROM hit_events
GROUP BY 1, 2, 3, 4, 5, 6, 7;
END;


CREATE TASK update_imm_paywall_daily_wide_paywall_rate
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 55 21 * * *' 'UTC'
COMMENT = '付费墙：近31日 wide_paywall_rate 六维宽表（六维 dau）'
AS
BEGIN
  DELETE FROM immdata.imm_paywall_daily_wide_paywall_rate
  WHERE dt_bj >= DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1))
    AND dt_bj <= add_days(date(add_hours(now(), 8)), -1);

  INSERT INTO immdata.imm_paywall_daily_wide_paywall_rate
(
  dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
  paywall_uv, dau, paywall_rate, update_time
)
WITH win AS (
  SELECT
    add_hours(DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1)), -8) AS ts_lo,
    add_hours(date(add_hours(now(), 8)), -8) AS ts_hi,
    DATEADD(day, -30, add_days(date(add_hours(now(), 8)), -1)) AS dt_lo,
    add_days(date(add_hours(now(), 8)), -1) AS dt_hi
),
hit_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  CROSS JOIN win w
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'user_need_pro'
    AND b.trigger = 'freeUsageLimitModal'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= w.ts_lo AND b.created_ts < w.ts_hi
),
dau_events AS (
  SELECT
    CAST(DATEADD(hour, 8, b.created_ts) AS DATE) AS dt_bj,
    b.device_id,
    COALESCE(NULLIF(b.install_from, ''), '(null)') AS install_from,
    COALESCE(b.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(b.campaign, ''), '(null)') AS campaign,
    CASE
      WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, ''))
             IN ('zh-cn', 'zh', 'zh-hans')
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh-cn%'
        OR LOWER(COALESCE(NULLIF(n.native_language, ''), b.interface_language, '')) LIKE 'zh_cn%'
      THEN 'zh_cn' ELSE 'other'
    END AS lang_bucket,
    CASE
      WHEN b.ab_tag IS NOT NULL AND LENGTH(TRIM(b.ab_tag)) = 1
       AND LOWER(TRIM(b.ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(b.ab_tag)) ELSE 'other'
    END AS ab_tag,
    COALESCE(fd.exp_group, '(unset)') AS exp_group
  FROM immdata.user_behaviour b
  CROSS JOIN win w
  LEFT JOIN immdata.imm_device_native_language n ON n.device_id = b.device_id
  LEFT JOIN immdata.imm_paywall_first_device fd ON fd.device_id = b.device_id
  WHERE b.event_name = 'translate_page'
    AND b.device_id IS NOT NULL AND b.device_id <> ''
    AND b.created_ts >= w.ts_lo AND b.created_ts < w.ts_hi
),
hit AS (
  SELECT dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
         COUNT(DISTINCT device_id) AS paywall_uv
  FROM hit_events
  WHERE dt_bj >= (SELECT dt_lo FROM win) AND dt_bj <= (SELECT dt_hi FROM win)
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
dau AS (
  SELECT dt_bj, install_from, platform_type, campaign, lang_bucket, ab_tag, exp_group,
         COUNT(DISTINCT device_id) AS dau
  FROM dau_events
  WHERE dt_bj >= (SELECT dt_lo FROM win) AND dt_bj <= (SELECT dt_hi FROM win)
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  h.dt_bj, h.install_from, h.platform_type, h.campaign, h.lang_bucket, h.ab_tag, h.exp_group,
  h.paywall_uv, d.dau,
  h.paywall_uv * 1.0 / NULLIF(d.dau, 0), NOW()
FROM hit h
INNER JOIN dau d
  ON h.dt_bj = d.dt_bj
 AND h.install_from = d.install_from
 AND h.platform_type = d.platform_type
 AND h.campaign = d.campaign
 AND h.lang_bucket = d.lang_bucket
 AND h.ab_tag = d.ab_tag
 AND h.exp_group = d.exp_group;
END;


-- -----------------------------------------------------------------------------
-- §4 启动 TASK
-- -----------------------------------------------------------------------------
ALTER TASK update_imm_paywall_daily_wide_hit RESUME;
ALTER TASK update_imm_paywall_daily_wide_paywall_rate RESUME;


-- -----------------------------------------------------------------------------
-- §5 验收（§2 跑完后执行；本仓只读可跑）
-- -----------------------------------------------------------------------------
-- 5.1 触墙 UV 与 kpi 一致
-- SELECT SUM(paywall_uv) FROM immdata.imm_paywall_daily_wide_hit WHERE dt_bj = '2026-08-16';
-- SELECT paywall_uv FROM immdata.imm_paywall_daily_kpi WHERE dt_bj = '2026-08-16';
--
-- 5.2 Filter 全空触墙率 ≈ kpi（六维 dau；抽 2026-08-16）
-- SELECT SUM(paywall_uv)*1.0/NULLIF(SUM(dau),0) AS wide_rate
-- FROM immdata.imm_paywall_daily_wide_paywall_rate WHERE dt_bj = '2026-08-16';
-- SELECT paywall_rate FROM immdata.imm_paywall_daily_kpi WHERE dt_bj = '2026-08-16';
-- 期望 wide_rate ≈ 0.0212（与 kpi 差 <0.001）
--
-- 5.3 SUM(dau) 不再虚高（抽 2026-08-16）
-- SELECT SUM(dau) wide_dau, (SELECT dau FROM immdata.imm_paywall_daily_kpi WHERE dt_bj='2026-08-16') kpi_dau
-- FROM immdata.imm_paywall_daily_wide_paywall_rate WHERE dt_bj = '2026-08-16';
-- 期望 wide_dau ≈ 505741（约 +0.5% 内，非 ×10）
--
-- 5.4 SUM(paywall_uv) 仍 ≈ kpi
-- SELECT SUM(paywall_uv) FROM immdata.imm_paywall_daily_wide_paywall_rate WHERE dt_bj = '2026-08-16';
-- SELECT paywall_uv FROM immdata.imm_paywall_daily_kpi WHERE dt_bj = '2026-08-16';
