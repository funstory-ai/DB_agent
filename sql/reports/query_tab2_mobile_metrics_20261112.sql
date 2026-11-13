-- T111 / Tab2（浏览页）移动端 7 指标 + 平台登录引导漏斗
-- 规范大类: query ；任务文档: docs/tasks/query_tab2_mobile_metrics_20261112.md
-- 只读；仅 immdata.user_behaviour；粗 UTC 时间窗预过滤保分区裁剪，北京日在 SELECT 里切。
-- 占位符由 scripts/export_tab2_mobile_metrics.py 替换：@W0@ @W1@ @PRIOR@ @HIST@ @EVENTS@ @SUBJ_EVENTS@ @FEED_EVENTS@ @FUNNEL_EVENTS@
-- 北京日 = to_date(date_add('hour',8,created_ts))；主口径仅国际版 ex_char_arg10='com'。
-- 实测事件名修正：文档 tab2_login_card_cta_click -> 库内 tab2_login_cta_click。
--
-- 每个 -- @Q_xxx 段是一条独立只读 SQL；脚本按段名拆分执行。

-- @Q_COUNTS
-- 逐北京日 × 事件 × 版本标记的事件数（人均进入次数、口径体检用）
SELECT to_date(date_add('hour', 8, created_ts)) AS bj_day,
       event_name,
       coalesce(ex_char_arg10, '(null)') AS edition,
       count(*) AS events
FROM immdata.user_behaviour
WHERE created_ts >= '@W0@' AND created_ts < '@W1@'
  AND event_name IN (@EVENTS@)
GROUP BY bj_day, event_name, edition

-- @Q_SUBJECT_DAYS
-- 逐北京日 × 事件 × 设备 一行；uid 取当日该事件下最大 ex_int_arg1（设备→账号映射在 Python 侧按 min 收口）
-- 覆盖：日活、留存、付费、卡片曝光的去重主体集合
SELECT to_date(date_add('hour', 8, created_ts)) AS bj_day,
       event_name,
       device_id,
       max(ex_int_arg1) AS uid,
       max(ex_char_arg10) AS edition
FROM immdata.user_behaviour
WHERE created_ts >= '@W0@' AND created_ts < '@W1@'
  AND event_name IN (@SUBJ_EVENTS@)
GROUP BY bj_day, event_name, device_id

-- @Q_FEED
-- 会话级原始行：duration(1 条=1 会话，P50/P90)、detail_enter(内容点击)、card_impression(口径体检)
-- 载荷在 ex_char_arg1 JSON：duration_ms / viewed_card_count / trigger_type
SELECT device_id,
       ex_int_arg1 AS uid,
       ex_char_arg10 AS edition,
       event_name,
       created_ts,
       to_date(date_add('hour', 8, created_ts)) AS bj_day,
       try_cast(get(try_parse_json(ex_char_arg1), 'duration_ms') AS BIGINT) AS dur_ms,
       try_cast(get(try_parse_json(ex_char_arg1), 'viewed_card_count') AS BIGINT) AS viewed_cnt,
       get(try_parse_json(ex_char_arg1), 'trigger_type') AS trigger_type
FROM immdata.user_behaviour
WHERE created_ts >= '@W0@' AND created_ts < '@W1@'
  AND event_name IN (@FEED_EVENTS@)

-- @Q_FUNNEL
-- 登录引导漏斗逐事件时间轴（相邻步 ≤30 分钟，按月汇总）
SELECT device_id,
       ex_int_arg1 AS uid,
       ex_char_arg10 AS edition,
       event_name,
       created_ts,
       to_date(date_add('hour', 8, created_ts)) AS bj_day
FROM immdata.user_behaviour
WHERE created_ts >= '@W0@' AND created_ts < '@W1@'
  AND event_name IN (@FUNNEL_EVENTS@)

-- @Q_ENTRY
-- app_tab2_enter.entry_type 结构（app_open = 打开 App 即落在 Tab2，被动进入；tab_switch = 主动切 Tab）
SELECT get(try_parse_json(ex_char_arg1), 'entry_type') AS entry_type,
       count(*) AS events,
       count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '@W0@' AND created_ts < '@W1@'
  AND event_name = 'app_tab2_enter'
  AND ex_char_arg10 = 'com'
GROUP BY entry_type

-- @Q_PRIOR
-- 「首次使用 Tab2」的左删失回看：主窗开始之前出现过 app_tab2_enter 的设备（该事件最早 2026-03-17）
SELECT device_id, max(ex_int_arg1) AS uid
FROM immdata.user_behaviour
WHERE created_ts >= '@PRIOR@' AND created_ts < '@W0@'
  AND event_name = 'app_tab2_enter'
GROUP BY device_id

-- @Q_HIST
-- 补充参考：登录卡片 5 事件 + login/sign_up 的历史月度总量（频控稀疏度；不参与 30 天主口径）
SELECT to_char(date_add('hour', 8, created_ts), 'YYYY-MM') AS ym,
       event_name,
       count(*) AS events,
       count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '@HIST@' AND created_ts < '@W1@'
  AND event_name IN (@FUNNEL_EVENTS@)
GROUP BY ym, event_name
