-- T028 补洞：2026-09-01 仍为旧 TASK 写入（update_time=2026-09-01 17:00 UTC），需单日回填
-- 验证：表内 Safari 新装 12758 vs behaviour 剔集成后 1317
-- 写仓执行（可与主补丁 §2 同逻辑，仅改日期窗）

DELETE FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates = '2026-09-01';

INSERT INTO immdata.imm_event_device_count_by_utf8_day (
  dates, event_name, os_name, platform_type, browser_name,
  device_count, new_device_count, event_count, new_event_count, update_time
)
WITH day_events AS (
  SELECT
    DATE(add_hours(created_ts, 8)) AS dates,
    event_name, os_name, platform_type, browser_name,
    device_id, is_new_user_today, main_frame
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-09-01'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND version <> '1.11.4'
),
embed_device_day AS (
  SELECT DISTINCT DATE(add_hours(created_ts, 8)) AS dates, device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(to_date('2026-09-01'), 1), -32)
    AND created_ts <  add_hours(add_days(to_date('2026-09-01'), 1), -8)
    AND version <> '1.11.4'
    AND LOWER(TRIM(install_from)) = 'official_userscript'
    AND TRIM(browser_name) = 'Safari'
),
filtered AS (
  SELECT d.* FROM day_events d
  LEFT JOIN embed_device_day e ON d.dates = e.dates AND d.device_id = e.device_id
  WHERE e.device_id IS NULL
)
SELECT
  dates, event_name, os_name, platform_type, browser_name,
  COUNT(DISTINCT device_id),
  COUNT(DISTINCT IF(is_new_user_today = '1', device_id, NULL)),
  COUNT(IF(event_name = 'translate_page' AND main_frame = '1' OR event_name <> 'translate_page', 1, NULL)),
  COUNT(IF(is_new_user_today = '1' AND (event_name = 'translate_page' AND main_frame = '1' OR event_name <> 'translate_page'), 1, NULL)),
  now()
FROM filtered
GROUP BY dates, event_name, os_name, platform_type, browser_name;

-- _M 表同日（若看板用到）
DELETE FROM immdata.imm_event_device_count_by_utf8_day_M WHERE dates = '2026-09-01';
-- （INSERT 体同主补丁 §3，日期窗改为 2026-09-01）

-- 验收：
-- SELECT SUM(IF(event_name='init_page_daily',new_device_count,0)) FROM immdata.imm_event_device_count_by_utf8_day
-- WHERE browser_name='Safari' AND dates='2026-09-01';  -- 期望 ~1317
