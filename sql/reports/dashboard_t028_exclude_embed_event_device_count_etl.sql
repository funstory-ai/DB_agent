-- =============================================================================
-- T028：imm_event_device_count_by_utf8_day 剔集成流量 — 完整写仓补丁（初版·仅 Safari）
-- 【已由 Rule A 取代】现行请用：dashboard_t028_ruleA_embed_kick_etl.sql
--   Rule A = iOS×Safari×userscript OR macOS×Maxthon×userscript（保留 ImtiOS_*）
-- 规范大类：dashboard（P022 / P028）
-- 任务：docs/tasks/anomaly_new_install_surge_ios_20260901.md
-- 本查数仓库只读，勿在只读账号执行
--
-- 执行顺序：§0 核对 → §1 暂停 TASK → §2 回填主表 → §3 回填 _M 表
--          → §4 重建 TASK（主表）→ §5 重建 TASK（_M）→ §6 恢复 TASK → §7 验收
--
-- 剔集成规则（初版；已被 Rule A 取代）：
--   北京日内任一事件满足 install_from='official_userscript' AND browser_name='Safari'
--   → 该 device_id 当日所有事件不进汇总
--
-- 日更 TASK 时间窗说明（勿误读为 32 天）：
--   add_hours(date(北京今日0点), -32) ～ add_hours(..., -8) = 24 小时 = 北京「昨天」
-- =============================================================================


-- =============================================================================
-- §0 执行前核对（只读，可先跑）
-- =============================================================================
-- SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%';
--
-- SELECT MAX(dates) FROM immdata.imm_event_device_count_by_utf8_day;
--
-- -- 改前 Safari 新装/激活（应见 7/28 起跳变、激活率 ~10%）
-- SELECT dates,
--   SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
--   SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation,
--   SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 1.0
--     / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0) AS act_rate
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE browser_name = 'Safari'
--   AND dates BETWEEN '2026-07-24' AND '2026-08-03'
-- GROUP BY 1 ORDER BY 1;


-- =============================================================================
-- §1 暂停自动 TASK（避免回填期间与旧逻辑并发写）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day SUSPEND;
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day_M SUSPEND;


-- =============================================================================
-- §2 回填主表 imm_event_device_count_by_utf8_day
-- 范围：2026-07-28 ～ 2026-08-31（T028 集成暴量窗；可按需改上界）
-- 先删后插，避免旧 grain 残留
-- =============================================================================

DELETE FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-07-28'
  AND dates <= '2026-08-31';

INSERT INTO immdata.imm_event_device_count_by_utf8_day (
  dates, event_name, os_name, platform_type, browser_name,
  device_count, new_device_count, event_count, new_event_count, update_time
)
WITH day_events AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS dates,
    event_name,
    os_name,
    platform_type,
    browser_name,
    device_id,
    is_new_user_today,
    main_frame
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-08-31'), 1), -8)
    AND version <> '1.11.4'
),
embed_device_day AS (
  SELECT DISTINCT
    DATE(add_hours(created_ts, 8)) AS dates,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-08-31'), 1), -8)
    AND version <> '1.11.4'
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND TRIM(browser_name) = 'Safari'
),
filtered AS (
  SELECT d.*
  FROM day_events d
  LEFT JOIN embed_device_day e
    ON d.dates = e.dates AND d.device_id = e.device_id
  WHERE e.device_id IS NULL
)
SELECT
  dates,
  event_name,
  os_name,
  platform_type,
  browser_name,
  COUNT(DISTINCT device_id) AS device_count,
  COUNT(DISTINCT IF(is_new_user_today = '1', device_id, NULL)) AS new_device_count,
  COUNT(
    IF(
      event_name = 'translate_page' AND main_frame = '1'
      OR event_name <> 'translate_page',
      1, NULL
    )
  ) AS event_count,
  COUNT(
    IF(
      is_new_user_today = '1'
      AND (
        event_name = 'translate_page' AND main_frame = '1'
        OR event_name <> 'translate_page'
      ),
      1, NULL
    )
  ) AS new_event_count,
  now() AS update_time
FROM filtered
GROUP BY dates, event_name, os_name, platform_type, browser_name;


-- =============================================================================
-- §3 回填 _M 表 imm_event_device_count_by_utf8_day_M（同日窗；含版本 Top3 minor 逻辑）
-- =============================================================================

DELETE FROM immdata.imm_event_device_count_by_utf8_day_M
WHERE dates >= '2026-07-28'
  AND dates <= '2026-08-31';

INSERT INTO immdata.imm_event_device_count_by_utf8_day_M (
  dates, event_name, os_name, platform_type, browser_name,
  device_count, new_device_count, event_count, new_event_count, update_time
)
WITH day_data AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS dates,
    event_name,
    os_name,
    platform_type,
    browser_name,
    device_id,
    is_new_user_today,
    main_frame,
    version,
    to_int32(split_part(version, '.', 1)) AS v1,
    to_int32(split_part(version, '.', 2)) AS v2,
    concat(split_part(version, '.', 1), '.', split_part(version, '.', 2)) AS version_minor
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-08-31'), 1), -8)
    AND ex_char_arg10 = 'com'
    AND version IS NOT NULL
    AND version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+$'
),
embed_device_day AS (
  SELECT DISTINCT
    DATE(add_hours(created_ts, 8)) AS dates,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-08-31'), 1), -8)
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND TRIM(browser_name) = 'Safari'
),
filtered_day_data AS (
  SELECT d.*
  FROM day_data d
  LEFT JOIN embed_device_day e
    ON d.dates = e.dates AND d.device_id = e.device_id
  WHERE e.device_id IS NULL
),
latest_minor AS (
  SELECT version_minor
  FROM (
    SELECT
      version_minor,
      v1,
      v2,
      row_number() OVER (ORDER BY v1 DESC, v2 DESC) AS rn
    FROM (
      SELECT version_minor, v1, v2
      FROM filtered_day_data
      WHERE event_name = 'translate_page'
      GROUP BY version_minor, v1, v2
    ) AS t
  ) AS s
  WHERE rn <= 3
)
SELECT
  dates,
  event_name,
  os_name,
  platform_type,
  browser_name,
  COUNT(DISTINCT device_id) AS device_count,
  COUNT(DISTINCT IF(is_new_user_today = '1', device_id, NULL)) AS new_device_count,
  COUNT(
    IF(
      event_name = 'translate_page' AND main_frame = '1'
      OR event_name <> 'translate_page',
      1, NULL
    )
  ) AS event_count,
  COUNT(
    IF(
      is_new_user_today = '1'
      AND (
        event_name = 'translate_page' AND main_frame = '1'
        OR event_name <> 'translate_page'
      ),
      1, NULL
    )
  ) AS new_event_count,
  now() AS update_time
FROM filtered_day_data
WHERE version_minor IN (SELECT version_minor FROM latest_minor)
GROUP BY dates, event_name, os_name, platform_type, browser_name;


-- =============================================================================
-- §4 重建日更 TASK：update_imm_event_device_count_by_utf8_day
-- 逻辑与 §2 相同，时间窗为滚动「北京昨天」
-- =============================================================================

DROP TASK IF EXISTS update_imm_event_device_count_by_utf8_day;

CREATE TASK update_imm_event_device_count_by_utf8_day
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 0 17 * * *' 'UTC'
COMMENT = '统计前一天使用数据（剔 official_userscript×Safari 集成）；北京约每天01:00'
AS
REPLACE INTO immdata.imm_event_device_count_by_utf8_day (
  dates, event_name, os_name, platform_type, browser_name,
  device_count, new_device_count, event_count, new_event_count, update_time
)
ON (dates, event_name, os_name, platform_type, browser_name)
SELECT *
FROM (
  WITH day_events AS (
    SELECT
      DATE(add_hours(created_ts, 8)) AS dates,
      event_name,
      os_name,
      platform_type,
      browser_name,
      device_id,
      is_new_user_today,
      main_frame
    FROM immdata.user_behaviour
    WHERE created_ts >= add_hours(date(add_hours(now(), 8)), -32)
      AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
      AND version <> '1.11.4'
  ),
  embed_device_day AS (
    SELECT DISTINCT
      DATE(add_hours(created_ts, 8)) AS dates,
      device_id
    FROM immdata.user_behaviour
    WHERE created_ts >= add_hours(date(add_hours(now(), 8)), -32)
      AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
      AND version <> '1.11.4'
      AND LOWER(TRIM(install_from)) = 'official_userscript'
      AND TRIM(browser_name) = 'Safari'
  ),
  filtered AS (
    SELECT d.*
    FROM day_events d
    LEFT JOIN embed_device_day e
      ON d.dates = e.dates AND d.device_id = e.device_id
    WHERE e.device_id IS NULL
  )
  SELECT
    dates,
    event_name,
    os_name,
    platform_type,
    browser_name,
    COUNT(DISTINCT device_id) AS device_count,
    COUNT(DISTINCT IF(is_new_user_today = '1', device_id, NULL)) AS new_device_count,
    COUNT(
      IF(
        event_name = 'translate_page' AND main_frame = '1'
        OR event_name <> 'translate_page',
        1, NULL
      )
    ) AS event_count,
    COUNT(
      IF(
        is_new_user_today = '1'
        AND (
          event_name = 'translate_page' AND main_frame = '1'
          OR event_name <> 'translate_page'
        ),
        1, NULL
      )
    ) AS new_event_count,
    now() AS update_time
  FROM filtered
  GROUP BY dates, event_name, os_name, platform_type, browser_name
  ORDER BY dates, event_name, os_name, platform_type, browser_name
);


-- =============================================================================
-- §5 重建日更 TASK：update_imm_event_device_count_by_utf8_day_M
-- =============================================================================

DROP TASK IF EXISTS update_imm_event_device_count_by_utf8_day_M;

CREATE TASK update_imm_event_device_count_by_utf8_day_M
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 0 17 * * *' 'UTC'
COMMENT = '统计前一天使用数据（Top3 minor；剔 official_userscript×Safari 集成）'
AS
REPLACE INTO immdata.imm_event_device_count_by_utf8_day_M (
  dates, event_name, os_name, platform_type, browser_name,
  device_count, new_device_count, event_count, new_event_count, update_time
)
ON (dates, event_name, os_name, platform_type, browser_name)
WITH day_data AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS dates,
    event_name,
    os_name,
    platform_type,
    browser_name,
    device_id,
    is_new_user_today,
    main_frame,
    version,
    to_int32(split_part(version, '.', 1)) AS v1,
    to_int32(split_part(version, '.', 2)) AS v2,
    concat(split_part(version, '.', 1), '.', split_part(version, '.', 2)) AS version_minor
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(date(add_hours(now(), 8)), -32)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
    AND ex_char_arg10 = 'com'
    AND version IS NOT NULL
    AND version REGEXP '^[0-9]+\\.[0-9]+\\.[0-9]+$'
),
embed_device_day AS (
  SELECT DISTINCT
    DATE(add_hours(created_ts, 8)) AS dates,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(date(add_hours(now(), 8)), -32)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND TRIM(browser_name) = 'Safari'
),
filtered_day_data AS (
  SELECT d.*
  FROM day_data d
  LEFT JOIN embed_device_day e
    ON d.dates = e.dates AND d.device_id = e.device_id
  WHERE e.device_id IS NULL
),
latest_minor AS (
  SELECT version_minor
  FROM (
    SELECT
      version_minor,
      v1,
      v2,
      row_number() OVER (ORDER BY v1 DESC, v2 DESC) AS rn
    FROM (
      SELECT version_minor, v1, v2
      FROM filtered_day_data
      WHERE event_name = 'translate_page'
      GROUP BY version_minor, v1, v2
    ) AS t
  ) AS s
  WHERE rn <= 3
)
SELECT
  dates,
  event_name,
  os_name,
  platform_type,
  browser_name,
  COUNT(DISTINCT device_id) AS device_count,
  COUNT(DISTINCT IF(is_new_user_today = '1', device_id, NULL)) AS new_device_count,
  COUNT(
    IF(
      event_name = 'translate_page' AND main_frame = '1'
      OR event_name <> 'translate_page',
      1, NULL
    )
  ) AS event_count,
  COUNT(
    IF(
      is_new_user_today = '1'
      AND (
        event_name = 'translate_page' AND main_frame = '1'
        OR event_name <> 'translate_page'
      ),
      1, NULL
    )
  ) AS new_event_count,
  now() AS update_time
FROM filtered_day_data
WHERE version_minor IN (SELECT version_minor FROM latest_minor)
GROUP BY dates, event_name, os_name, platform_type, browser_name
ORDER BY dates, event_name, os_name, platform_type, browser_name;


-- =============================================================================
-- §6 恢复 TASK
-- =============================================================================
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day RESUME;
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day_M RESUME;


-- =============================================================================
-- §7 验收（§2 回填 + §4 TASK 改完后跑）
-- =============================================================================
-- -- 7.1 TASK definition 须含 embed_device_day / official_userscript
-- SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%';
--
-- -- 7.2 Safari 新装/激活应恢复平滑（参考 T028 behaviour 直查剔集成后）
-- SELECT dates,
--   SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
--   SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation,
--   ROUND(
--     SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 100.0
--       / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0),
--     2
--   ) AS act_rate_pct
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE browser_name = 'Safari'
--   AND dates BETWEEN '2026-07-24' AND '2026-08-03'
-- GROUP BY 1 ORDER BY 1;
-- -- 期望：7/27～8/03 新装 ~1.2k–1.5k/日，激活率 ~73–82%
--
-- -- 7.3 回填窗内无重复 grain
-- SELECT dates, COUNT(*) AS rows, COUNT(DISTINCT (dates, event_name, os_name, platform_type, browser_name)) AS grains
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE dates BETWEEN '2026-07-28' AND '2026-08-31'
-- GROUP BY dates
-- HAVING rows <> grains
-- LIMIT 10;
