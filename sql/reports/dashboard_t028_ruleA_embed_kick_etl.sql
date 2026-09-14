-- =============================================================================
-- T028 Rule A：imm_event_device_count_by_utf8_day 剔低质 userscript 集成
-- 规范大类：dashboard（P022 / P028 / P034）
-- 任务：docs/tasks/anomaly_new_install_surge_ios_20260901.md
-- 本查数仓库只读，勿在只读账号执行
--
-- 相对初版 T028（仅 Safari×userscript）的变更：
--   Rule A = 只踢低质嵌入，保留 App UA（ImtiOS_* 等）原 userscript
--   1) iOS  × Safari  × official_userscript
--   2) macOS × Maxthon × official_userscript
--
-- 执行顺序：§0 核对 → §1 暂停 TASK → §2 回填主表 → §3 回填 _M 表
--          → §4 重建 TASK（主表）→ §5 重建 TASK（_M）→ §6 恢复 TASK → §7 验收
--
-- 回填窗：2026-07-28 ～ 2026-09-01
--   （含此前仅踢 Safari 的日期，需重刷以补踢 Maxthon；上界可按需延到「昨天」）
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
-- -- 改前：macOS / Maxthon 新装应见 7/28 起抬升、激活率极低
-- SELECT dates,
--   SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
--   SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation,
--   ROUND(
--     SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 100.0
--       / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0),
--     2
--   ) AS act_rate_pct
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE browser_name = 'Maxthon'
--   AND dates BETWEEN '2026-07-24' AND '2026-08-10'
-- GROUP BY 1 ORDER BY 1;


-- =============================================================================
-- §1 暂停自动 TASK（避免回填期间与旧逻辑并发写）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day SUSPEND;
ALTER TASK IF EXISTS update_imm_event_device_count_by_utf8_day_M SUSPEND;


-- =============================================================================
-- §2 回填主表 imm_event_device_count_by_utf8_day
-- 范围：2026-07-28 ～ 2026-09-01（可按需改上界到昨天）
-- 先删后插，避免旧 grain 残留
-- =============================================================================

DELETE FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-07-28'
  AND dates <= '2026-09-01';

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
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND version <> '1.11.4'
),
embed_device_day AS (
  -- Rule A：低质嵌入 userscript（保留 ImtiOS_* 等 App UA）
  SELECT DISTINCT
    DATE(add_hours(created_ts, 8)) AS dates,
    device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-07-28'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND version <> '1.11.4'
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
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
  AND dates <= '2026-09-01';

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
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
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
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
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
COMMENT = '统计前一天使用数据（RuleA剔 userscript×iOS Safari / macOS Maxthon）；北京约每天01:00'
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
      AND (
        (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
        OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
      )
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
COMMENT = '统计前一天使用数据（Top3 minor；RuleA剔 userscript×iOS Safari / macOS Maxthon）'
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
    AND (
      (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
      OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
    )
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
-- -- 7.1 TASK definition 须含 Rule A（Maxthon + ios Safari）
-- SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%';
-- -- 期望 COMMENT / 定义中可见 Maxthon 与 os_name='ios'
--
-- -- 7.2 Safari 新装/激活仍平滑（Rule A 含 iOS Safari）
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
-- -- 期望：7/28 后新装 ~1.2k–1.5k/日，激活率 ~73–82%
--
-- -- 7.3 Maxthon 新装应接近清空（macOS×userscript×Maxthon 被踢）
-- SELECT dates,
--   SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
--   SUM(IF(event_name = 'translate_page', new_device_count, 0)) AS activation
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE browser_name = 'Maxthon'
--   AND dates BETWEEN '2026-07-28' AND '2026-08-10'
-- GROUP BY 1 ORDER BY 1;
-- -- 期望：新装接近 0（或仅非 macOS / 非 userscript 残留，量级极小）
--
-- -- 7.4 macOS 整体激活率应回升
-- SELECT dates,
--   SUM(IF(event_name = 'init_page_daily', new_device_count, 0)) AS new_install,
--   ROUND(
--     SUM(IF(event_name = 'translate_page', new_device_count, 0)) * 100.0
--       / NULLIF(SUM(IF(event_name = 'init_page_daily', new_device_count, 0)), 0),
--     2
--   ) AS act_rate_pct
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE os_name = 'macOS'
--   AND dates BETWEEN '2026-07-24' AND '2026-08-10'
-- GROUP BY 1 ORDER BY 1;
--
-- -- 7.5 回填窗内无重复 grain
-- SELECT dates, COUNT(*) AS rows,
--   COUNT(DISTINCT (dates, event_name, os_name, platform_type, browser_name)) AS grains
-- FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE dates BETWEEN '2026-07-28' AND '2026-09-01'
-- GROUP BY dates
-- HAVING rows <> grains
-- LIMIT 10;
