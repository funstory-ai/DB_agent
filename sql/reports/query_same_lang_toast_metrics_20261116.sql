-- T118 同语种提示 Toast（"This page may have nothing to translate"）
-- 弹出次数 / 人均次数 / 用户点击「以后不再显示」次数
-- 插件埋点：src/toast-tracking.ts
--   toast_show         : toast_id -> ex_char_arg1 = 'sameLang'
--   toast_action_click : toast_id -> ex_char_arg1 = 'sameLang', action_id -> ex_char_arg2 = 'disable_future'
--   toast_close        : toast_id -> ex_char_arg1 = 'sameLang', close_trigger -> ex_char_arg2
-- 主体（P018）：有账号用 ex_int_arg1(userid)，否则 device_id。
-- 北京日 D = UTC (D-1)16:00 ~ D16:00；只做粗 UTC 预过滤，不要在 WHERE 里对时间列套函数。
-- 主口径：北京日 2026-10-17 ~ 2026-11-15（30 个完整日）
--   UTC [2026-10-16 16:00:00, 2026-11-15 16:00:00)

-- @Q0 埋点覆盖起点：按月探测 toast_show/sameLang 的最早时间与量级（用于说明历史不可比）
SELECT CAST(date_add(hour, 8, created_ts) AS DATE) AS bj_day,
       count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-20 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name = 'toast_show'
  AND ex_char_arg1 = 'sameLang'
GROUP BY 1 ORDER BY 1;

-- @Q1 主口径整窗核心数字（一次扫描出全部 3 个答案）
SELECT
  SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
  SUM(CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'disable_future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS show_person_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN device_id END) AS show_device_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'disable_future' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS click_person_uv,
  MIN(CASE WHEN event_name = 'toast_show' THEN created_ts END) AS first_show_ts,
  MAX(CASE WHEN event_name = 'toast_show' THEN created_ts END) AS last_show_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click')
  AND ex_char_arg1 = 'sameLang';

-- @Q2 逐北京日 × 国内(cn)/国际(com) 趋势与点击率
SELECT CAST(date_add(hour, 8, created_ts) AS DATE) AS bj_day,
       COALESCE(ex_char_arg10, 'unknown') AS edition,
       SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
       SUM(CASE WHEN event_name = 'toast_action_click'
                 AND ex_char_arg2 = 'disable_future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
       SUM(CASE WHEN event_name = 'toast_close' THEN 1 ELSE 0 END) AS close_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click', 'toast_close')
  AND ex_char_arg1 = 'sameLang'
GROUP BY 1, 2 ORDER BY 1, 2;

-- @Q3 抽样核对：字段槽位、trigger、版本分布、无效 device_id（P019 用，限 1 个北京日）
SELECT event_name, trigger, ex_char_arg2, ex_char_arg10,
       MIN(version) AS min_ver, MAX(version) AS max_ver,
       COUNT(*) AS c,
       COUNT(DISTINCT device_id) AS device_uv,
       SUM(CASE WHEN device_id IS NULL OR device_id = '' THEN 1 ELSE 0 END) AS null_device_rows,
       SUM(CASE WHEN ex_int_arg1 > 0 THEN 1 ELSE 0 END) AS with_userid_rows
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-14 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click', 'toast_close')
  AND ex_char_arg1 = 'sameLang'
GROUP BY 1, 2, 3, 4 ORDER BY c DESC LIMIT 40;

-- @Q4 极端人均抽查：单日弹出次数 TOP 设备/账号（判断是否有刷量导致人均失真）
SELECT CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
            ELSE CONCAT('d:', COALESCE(device_id, '')) END AS subject,
       COUNT(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-14 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name = 'toast_show' AND ex_char_arg1 = 'sameLang'
GROUP BY 1 ORDER BY c DESC LIMIT 20;
