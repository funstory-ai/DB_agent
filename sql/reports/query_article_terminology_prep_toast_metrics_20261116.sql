-- T121 术语智能提取告知 Toast（「术语提取中...」/ "Extracting terms..."）
-- 弹出次数 / 人均次数 / 用户点击「以后不再显示」次数；口径逐项对齐 T118(sameLang) / T120(runtimePressure)
-- 插件：src/article-terminology/preparation-notice.ts
--   toast_show         : toast_id -> ex_char_arg1 = 'article-terminology-preparing'
--   toast_action_click : 同 toast_id，action_id -> ex_char_arg2 = 'never-show-future'
--     ⚠️ 注意：本弹窗按钮 id 是 never-show-future（连字符），不是 T118/T120 的 disable_future
--   toast_close        : 同 toast_id，close_trigger -> ex_char_arg2
-- 主体（P018）：有账号用 ex_int_arg1(userid)，否则 device_id。
-- 北京日 D = UTC (D-1)16:00 ~ D16:00；只做粗 UTC 预过滤，不要在 WHERE 里对时间列套函数。
-- 主口径：北京日 2026-10-17 ~ 2026-11-15（30 个完整日）= UTC [2026-10-16 16:00:00, 2026-11-15 16:00:00)
-- 辅口径：北京日 2026-08-28 ~ 2026-11-15（80 天）= UTC [2026-08-27 16:00:00, 2026-11-15 16:00:00)

-- @Q0 全窗逐日：埋点/功能覆盖起点 + 整窗自洽校验
SELECT CAST(date_add(hour, 8, created_ts) AS DATE) AS bj_day, COUNT(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-27 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name = 'toast_show'
  AND ex_char_arg1 = 'article-terminology-preparing'
GROUP BY 1 ORDER BY 1;

-- @Q1 主口径整窗核心数字（一次扫描出 3 个答案；同时给全部 action_click 用于校验按钮 id）
SELECT
  SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
  SUM(CASE WHEN event_name = 'toast_action_click' THEN 1 ELSE 0 END) AS all_action_click_cnt,
  SUM(CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'never-show-future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS show_person_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN device_id END) AS show_device_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'never-show-future' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS click_person_uv,
  MIN(CASE WHEN event_name = 'toast_show' THEN created_ts END) AS first_show_ts,
  MAX(CASE WHEN event_name = 'toast_show' THEN created_ts END) AS last_show_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click')
  AND ex_char_arg1 = 'article-terminology-preparing';

-- @Q1B 辅口径全窗（80 个北京日）
SELECT
  SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
  SUM(CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'never-show-future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS show_person_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN device_id END) AS show_device_uv,
  COUNT(DISTINCT CASE WHEN event_name = 'toast_action_click'
            AND ex_char_arg2 = 'never-show-future' THEN
    CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
         ELSE CONCAT('d:', COALESCE(device_id, '')) END END) AS click_person_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-27 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click')
  AND ex_char_arg1 = 'article-terminology-preparing';

-- @Q2 逐北京日 × 国内(cn)/国际(com)：趋势 + 逐日加总校验
SELECT CAST(date_add(hour, 8, created_ts) AS DATE) AS bj_day,
       COALESCE(ex_char_arg10, 'unknown') AS edition,
       SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
       SUM(CASE WHEN event_name = 'toast_action_click'
                 AND ex_char_arg2 = 'never-show-future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
       SUM(CASE WHEN event_name = 'toast_close' THEN 1 ELSE 0 END) AS close_cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click', 'toast_close')
  AND ex_char_arg1 = 'article-terminology-preparing'
GROUP BY 1, 2 ORDER BY 1, 2;

-- @Q3 抽样核对（单北京日 11-15）：字段槽位、trigger、版本、action_id 全集、无效 device_id
SELECT event_name, trigger, ex_char_arg2, ex_char_arg3, ex_char_arg10,
       MIN(version) AS min_ver, MAX(version) AS max_ver,
       COUNT(*) AS c, COUNT(DISTINCT device_id) AS device_uv,
       SUM(CASE WHEN device_id IS NULL OR device_id = '' THEN 1 ELSE 0 END) AS null_device_rows,
       SUM(CASE WHEN ex_int_arg1 > 0 THEN 1 ELSE 0 END) AS with_userid_rows
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-14 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click', 'toast_close')
  AND ex_char_arg1 = 'article-terminology-preparing'
GROUP BY 1, 2, 3, 4, 5 ORDER BY c DESC LIMIT 40;

-- @Q4 分版整窗聚合：与 Q1 的 show/click 加总自洽（人数分版不可相加）
SELECT COALESCE(ex_char_arg10, 'unknown') AS edition,
       SUM(CASE WHEN event_name = 'toast_show' THEN 1 ELSE 0 END) AS show_cnt,
       SUM(CASE WHEN event_name = 'toast_action_click'
                 AND ex_char_arg2 = 'never-show-future' THEN 1 ELSE 0 END) AS never_show_click_cnt,
       COUNT(DISTINCT CASE WHEN event_name = 'toast_show' THEN device_id END) AS show_device_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click')
  AND ex_char_arg1 = 'article-terminology-preparing'
GROUP BY 1 ORDER BY 1;

-- @Q5 事件识别：主窗内所有含 termin 的 toast_id 分布，确认没有同义 id、并列出已排除的其它术语 toast
SELECT ex_char_arg1 AS toast_id, event_name, COUNT(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-16 16:00:00' AND created_ts < '2026-11-15 16:00:00'
  AND event_name IN ('toast_show', 'toast_action_click', 'toast_close')
  AND LOWER(ex_char_arg1) LIKE '%termin%'
GROUP BY 1, 2 ORDER BY c DESC LIMIT 60;

-- @Q6 单日主体弹出次数分布（P019 合理性）
SELECT c, COUNT(*) AS subjects
FROM (
  SELECT CASE WHEN ex_int_arg1 > 0 THEN CAST(ex_int_arg1 AS VARCHAR)
              ELSE CONCAT('d:', COALESCE(device_id, '')) END AS subject,
         COUNT(*) AS c
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-14 16:00:00' AND created_ts < '2026-11-15 16:00:00'
    AND event_name = 'toast_show' AND ex_char_arg1 = 'article-terminology-preparing'
  GROUP BY 1
) t
GROUP BY c ORDER BY c;
