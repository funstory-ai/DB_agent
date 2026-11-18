-- T122 直播助手桌面端埋点是否接入 Databend（2026-11-16）
-- 依据：C:\Users\86933\Downloads\live-assistant-analytics-summary.md《直播助手首批埋点说明》2026-10-28
--   设计 13 个事件，仅走 /collect（subject: user_behaviour），桌面直报 8 + 插件透传 5。
-- 结论：已接入 immdata.user_behaviour（首见 2026-10-28 08:49:17 UTC），
--   但只有 12 个事件名与设计稿完全一致；manual_close 未实现，实际为 subtitle_close；
--   另有新增 subtitle_interrupted。全库无 live_assistant 专用表/日汇总表。
-- 时间口径：created_ts 为 UTC；北京日 D = UTC (D-1)16:00 ~ D16:00。
--   WHERE 一律用常量上下界，禁止对 created_ts 套函数后再过滤。
-- 只读 SELECT；禁止 INSERT/UPDATE/DDL。

-- @Q0 元数据盘点：全实例是否有直播/桌面/字幕/助手相关专用表
-- （information_schema.tables 371 行 = system.tables 各库之和；命中仅 immdata.imm_ai_subtitle_event，
--   该表是 AI 字幕日汇总 dates/total_user/vip_count/vip_user，与直播助手无关）
SELECT table_schema, table_name
FROM information_schema.tables
WHERE lower(table_name) LIKE '%live%' OR lower(table_name) LIKE '%subtitle%'
   OR lower(table_name) LIKE '%desktop%' OR lower(table_name) LIKE '%assistant%'
ORDER BY 1, 2;

-- @Q1 设计稿 13 个事件，近 7 天（UTC 2026-11-09 00:00 ~ 2026-11-16 14:00）精确命中
-- 结果：12 个命中，合计 1,970 条；live_assistant_subtitle_manual_close = 0
SELECT event_name,
       count(*) AS pv,
       count(DISTINCT device_id) AS device_uv,
       min(created_ts) AS first_ts,
       max(created_ts) AS last_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN (
    'live_assistant_app_start','live_assistant_login_click','live_assistant_login_success',
    'live_assistant_login_failed','live_assistant_onboarding_step_show',
    'live_assistant_onboarding_complete','live_assistant_install_plugin_click',
    'live_assistant_browser_open','live_assistant_subtitle_start',
    'live_assistant_subtitle_success','live_assistant_subtitle_failed',
    'live_assistant_subtitle_retry','live_assistant_subtitle_manual_close')
GROUP BY event_name ORDER BY pv DESC;

-- @Q2 模糊匹配：捕获改名/新增事件（短窗，避免全表无事件滤扫描）
-- 关键发现：live_assistant_subtitle_close(229) / live_assistant_subtitle_interrupted(3)
--   translate_video_subtitle(5024 万) 等属普通视频字幕翻译，不是直播助手，勿混。
SELECT event_name, count(*) AS pv, min(created_ts) AS first_ts, max(created_ts) AS last_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND (event_name LIKE 'live_assistant%' OR event_name ILIKE '%live%' OR event_name ILIKE '%subtitle%')
GROUP BY event_name ORDER BY pv DESC LIMIT 100;

-- @Q3 逐北京日 × 事件（追溯窗 2026-10-01 起）：首见日与灰度量级
-- 北京日加总 = 3,256 条，与 @Q4 全窗 count 一致；11-01 无数据，11-16 为不完整日。
SELECT CAST(date_add(hour, 8, created_ts) AS DATE) AS bj_day,
       event_name,
       count(*) AS pv,
       count(DISTINCT device_id) AS device_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1, 2 ORDER BY 1, 2;

-- @Q4 全窗总量与首见时间（9-01 起）；@Q4b 验证 10-28 之前确为零
SELECT count(*) AS pv, count(DISTINCT device_id) AS device_uv,
       min(created_ts) AS first_ts, max(created_ts) AS last_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%';
-- 结果：3,256 条 / 105 台 / 首见 2026-10-28 08:49:17 UTC / 末见 2026-11-16 05:43:33 UTC
SELECT count(*) AS pv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-10-28 00:00:00'
  AND event_name LIKE 'live_assistant%';  -- 0

-- @Q5 版本迭代节奏（桌面独立版本号 0.1.x，不是插件 1.33.x）
SELECT version, count(*) AS pv, count(DISTINCT device_id) AS device_uv,
       min(CAST(date_add(hour, 8, created_ts) AS DATE)) AS first_bj_day,
       max(CAST(date_add(hour, 8, created_ts) AS DATE)) AS last_bj_day
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY version ORDER BY pv DESC;

-- @Q6 关键字段填充率（近 7 天）；结论见下
--   100%：device_id/version/os_name/interface_language/install_day/install_week/trigger/ex_char_arg10
--   0%  ：os_version / user_type / ex_int_arg1(账号 ID) / platform_type / browser_name
--   ex_int_arg2(耗时) 仅 success/failed/login_success/login_failed/interrupted 有值
SELECT event_name, count(*) AS pv,
       count(nullif(device_id,'')) AS c_device_id,
       count(nullif(version,'')) AS c_version,
       count(nullif(os_name,'')) AS c_os_name,
       count(nullif(os_version,'')) AS c_os_version,
       count(nullif(interface_language,'')) AS c_interface_language,
       count(nullif(install_day,'')) AS c_install_day,
       count(nullif(install_week,'')) AS c_install_week,
       count(nullif(user_type,'')) AS c_user_type,
       count(ex_int_arg1) AS c_ex_int_arg1,
       count(ex_int_arg2) AS c_ex_int_arg2,
       count(nullif(trigger,'')) AS c_trigger,
       count(nullif(platform_type,'')) AS c_platform_type,
       count(nullif(browser_name,'')) AS c_browser_name,
       count(nullif(ex_char_arg2,'')) AS c_ex_char_arg2,
       count(nullif(ex_char_arg3,'')) AS c_ex_char_arg3,
       count(nullif(ex_char_arg9,'')) AS c_ex_char_arg9,
       count(nullif(ex_char_arg10,'')) AS c_ex_char_arg10
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY event_name ORDER BY pv DESC;

-- @Q7 扩展槽位取值盘点：设计稿的 video_platform 是否落库
-- 10 个 ex_char_arg 槽位非空取值只有：a10='com'、a2=阶段/关闭原因、a3=错误码、a9=尝试 ID；
-- 全窗未见 YouTube/Twitch/Kick/TikTok/Facebook/X Spaces 等平台名 ⇒ 直播平台维度缺失。
-- user_behaviour 本身也没有 video_platform 列（设计稿「不新增数据库字段」）。
SELECT 'a2' AS slot, ex_char_arg2 AS val, count(*) AS c FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%' AND ex_char_arg2 IS NOT NULL AND ex_char_arg2 <> ''
GROUP BY 1, 2
UNION ALL
SELECT 'a3', ex_char_arg3, count(*) FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%' AND ex_char_arg3 IS NOT NULL AND ex_char_arg3 <> ''
GROUP BY 1, 2
ORDER BY 1, c DESC;

-- @Q8 subtitle_close 的 ex_char_arg2 分布：与设计稿「手动关闭不含页面切换」不符
-- page_navigation 163 / tab_closed 29 / quick_menu 21 / other 16 ⇒ 不能当「手动关闭次数」用。
SELECT ex_char_arg2, trigger, count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name = 'live_assistant_subtitle_close'
GROUP BY 1, 2 ORDER BY c DESC;

-- @Q9 trigger 枚举：browser_open 按来源区分 login / main_install / onboarding_* 齐全
SELECT event_name, trigger, count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1, 2 ORDER BY 1, c DESC;

-- @Q10 桌面端整体对照（近 1 天，仅作背景）：插件桌面端数据本来就在库里，
--  Chrome/Edge/Safari/Electron + platform_type='desktop' 数千万条/日；
--  直播助手这批是独立上报，browser_name/platform_type 全 NULL，靠 event_name 前缀识别。
SELECT browser_name, platform_type, count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-15 00:00:00' AND created_ts < '2026-11-16 06:00:00'
GROUP BY 1, 2 ORDER BY c DESC LIMIT 15;

-- @Q11 P019 抽样复验（窄路径，不重跑全量聚合）
-- ① manual_close 零命中换模糊路径复验
SELECT event_name, count(*) AS c FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND (event_name ILIKE '%manual%' OR event_name = 'live_assistant_subtitle_manual_close')
GROUP BY 1 ORDER BY c DESC LIMIT 20;  -- 0 行
-- ② 单设备事件序列，核对字段落位/尝试 ID 关联/耗时
SELECT created_ts, event_name, trigger, ex_char_arg2, ex_char_arg3,
       ex_char_arg9, ex_int_arg2, version
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-15 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND device_id = '28f70b1b1d7166b4293d1ba9ad14d4c9'
  AND event_name LIKE 'live_assistant%'
ORDER BY created_ts LIMIT 30;
-- ③ 加总自洽：2,202 条 / 14 事件 / 75 台 = 1,970(设计稿 12 个) + 229(close) + 3(interrupted)
SELECT count(*) AS total, count(DISTINCT event_name) AS events,
       count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%';

-- ============================================================
-- 以下 @Q12~@Q16 为 14:37「漏斗可行性」追问补查（F1~F12），可复现。
-- 时点说明：user_behaviour 近实时写入，14:37 快照近 7 天 2,255 条 / 76 台、
--   全窗 3,309 条，比 13:46 已交付的 2,202 / 3,256 多几十条，属正常追加（P044）。
--   这些数字只用于判断可行性，不替换上面 @Q1~@Q11 已交付格子。
-- ============================================================

-- @Q12 各漏斗节点 PV / 设备 UV（同时给全窗，判断灰度规模是否够拆分）
SELECT event_name, count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1 ORDER BY pv DESC;

-- @Q13 设备级「有序相邻转化」：无 session_id，只能按 device_id + min(ts) 近似，
--   用于证明该近似会串错会话（install_plugin_click→browser_open 有序 0 / 同时命中 36）。
--   完整 9 节点写法见任务档；此处给核心 4 节点的最小复现。
SELECT
  count(*) AS total_devices,
  count(CASE WHEN t_app IS NOT NULL AND t_login IS NOT NULL AND t_login >= t_app THEN 1 END) AS ord_app_login,
  count(CASE WHEN t_complete IS NOT NULL AND t_install IS NOT NULL AND t_complete >= t_install THEN 1 END) AS ord_complete_before_install,
  count(CASE WHEN t_complete IS NOT NULL AND t_install IS NOT NULL THEN 1 END) AS both_complete_install,
  count(CASE WHEN t_install IS NOT NULL AND t_browser IS NOT NULL AND t_browser >= t_install THEN 1 END) AS ord_install_browser,
  count(CASE WHEN t_install IS NOT NULL AND t_browser IS NOT NULL THEN 1 END) AS both_install_browser
FROM (
  SELECT device_id,
    min(CASE WHEN event_name='live_assistant_app_start' THEN created_ts END) AS t_app,
    min(CASE WHEN event_name='live_assistant_login_click' THEN created_ts END) AS t_login,
    min(CASE WHEN event_name='live_assistant_onboarding_complete' THEN created_ts END) AS t_complete,
    min(CASE WHEN event_name='live_assistant_install_plugin_click' THEN created_ts END) AS t_install,
    min(CASE WHEN event_name='live_assistant_browser_open' THEN created_ts END) AS t_browser
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
    AND event_name LIKE 'live_assistant%'
  GROUP BY device_id) t;

-- @Q14 尝试 ID 覆盖：证明只有登录 3 + 字幕 6 事件带 ex_char_arg9，桌面 5 事件 0%
SELECT event_name, count(*) AS pv,
       count(nullif(ex_char_arg9,'')) AS with_attempt,
       count(DISTINCT nullif(ex_char_arg9,'')) AS distinct_attempt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1 ORDER BY pv DESC;

-- @Q15 尝试级终态覆盖：登录 244 次 click 中 153 次无终态；
--   字幕 408 个 start 尝试中 155 个无终态 ⇒ 「成功率」分母必须先定口径。
--   （字幕版：把三个登录事件换成 subtitle_click/start/success/failed 同理，见任务档 F10）
SELECT count(*) AS attempt_ids,
  sum(CASE WHEN has_click>0 THEN 1 END) AS ids_with_click,
  sum(CASE WHEN has_click>0 AND has_success>0 THEN 1 END) AS ids_click_success,
  sum(CASE WHEN has_click>0 AND has_failed>0 THEN 1 END) AS ids_click_failed,
  sum(CASE WHEN has_click>0 AND has_success=0 AND has_failed=0 THEN 1 END) AS ids_click_no_result
FROM (
  SELECT ex_char_arg9,
    sum(CASE WHEN event_name='live_assistant_login_click' THEN 1 ELSE 0 END) AS has_click,
    sum(CASE WHEN event_name='live_assistant_login_success' THEN 1 ELSE 0 END) AS has_success,
    sum(CASE WHEN event_name='live_assistant_login_failed' THEN 1 ELSE 0 END) AS has_failed
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
    AND event_name IN ('live_assistant_login_click','live_assistant_login_success','live_assistant_login_failed')
    AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> ''
  GROUP BY ex_char_arg9) t;

-- @Q16 字段空缺总表（近 7 天合并）：0% 列与「表内不存在的 video_platform」
SELECT count(*) AS pv,
  count(nullif(os_version,'')) AS c_os_version,
  count(nullif(user_type,'')) AS c_user_type,
  count(ex_int_arg1) AS c_ex_int_arg1,
  count(nullif(platform_type,'')) AS c_platform_type,
  count(nullif(browser_name,'')) AS c_browser_name,
  count(nullif(ex_char_arg1,'')) AS c_ex_char_arg1,
  count(nullif(ex_char_arg4,'')) AS c_ex_char_arg4,
  count(ex_int_arg2) AS c_ex_int_arg2,
  count(nullif(ex_char_arg9,'')) AS c_ex_char_arg9,
  count(nullif(ex_char_arg10,'')) AS c_ex_char_arg10
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%';
-- video_platform 不在 information_schema.columns 中（@Q0 同批核查），
--   a1/a4~a8 槽位非空行数均为 0，故无任何列承载直播平台值。

-- ============================================================
-- 以下 @Q17~@Q21 为 14:47「去掉单链后，其余 5 项能否完成」实算（S1~S5）。
-- 时点 14:47 快照 2,258 条；口径按同事截图原文；结论见任务档对应章节。
-- 一次性拉明细在 Python 内算全部指标，保证分子分母同粒度（P044）。
-- ============================================================

-- @Q17 P0 字幕启动成功率：成功/(成功+明确失败)，按 version，尝试 ID 去重
-- 结果 96/(96+159)=37.65%；0.1.6 25.0% / 0.1.7 25.0% / 0.1.9 50.4%。
-- video_platform 维度不可做（列不存在）；subtitle_interrupted 3 条待业务确认是否计入失败。
SELECT version,
  count(DISTINCT CASE WHEN event_name='live_assistant_subtitle_success' THEN ex_char_arg9 END) AS succ,
  count(DISTINCT CASE WHEN event_name='live_assistant_subtitle_failed' THEN ex_char_arg9 END) AS fail
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN ('live_assistant_subtitle_success','live_assistant_subtitle_failed')
  AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> ''
GROUP BY 1 ORDER BY 1;

-- @Q18 P0 失败原因分布：必须限定 event_name，否则串入 login_failed 的 5 个错误码
-- Top10 实际只有 3 行：session_start×session_start_failed 150 / host_connect×desktop_unavailable 5 /
--   readiness×readiness_timeout 4。
SELECT ex_char_arg2 AS fail_stage, ex_char_arg3 AS err_code, count(*) AS c,
       count(DISTINCT ex_char_arg9) AS attempts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name = 'live_assistant_subtitle_failed'
GROUP BY 1, 2 ORDER BY c DESC LIMIT 10;

-- @Q19 P1 登录成功率与耗时：两口径 82.4% vs 30.7%，分母必须先确认（P025）
SELECT count(DISTINCT CASE WHEN event_name='live_assistant_login_click' THEN ex_char_arg9 END) AS click,
       count(DISTINCT CASE WHEN event_name='live_assistant_login_success' THEN ex_char_arg9 END) AS succ,
       count(DISTINCT CASE WHEN event_name='live_assistant_login_failed' THEN ex_char_arg9 END) AS fail
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN ('live_assistant_login_click','live_assistant_login_success','live_assistant_login_failed')
  AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> '';
-- 耗时明细（P50/P90 在 Python 算）：login_success n=75 P50 18,303ms / P90 48,913ms；
--   login_failed n=16 中 11 条 ≈300,008ms 为 5 分钟超时固定值，不可当真实分布。
SELECT event_name, ex_int_arg2 FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN ('live_assistant_login_success','live_assistant_login_failed')
  AND ex_int_arg2 IS NOT NULL;

-- @Q20 P2 重试率（141/409=34.47% 可做）与手动关闭率（做不了）
SELECT
  sum(CASE WHEN event_name='live_assistant_subtitle_retry' THEN 1 ELSE 0 END) AS retry_pv,
  count(DISTINCT CASE WHEN event_name='live_assistant_subtitle_start' THEN ex_char_arg9 END) AS start_attempts,
  sum(CASE WHEN event_name='live_assistant_subtitle_manual_close' THEN 1 ELSE 0 END) AS manual_close_pv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant_subtitle%';
-- 实际关闭事件的原因枚举：page_navigation 168 / tab_closed 30 / quick_menu 22 / other 17，
--   设计稿明确手动关闭不含页面切换/异常结束 ⇒ 无干净分子；改交付「关闭原因分布」。
SELECT ex_char_arg2 AS close_reason, trigger, count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name = 'live_assistant_subtitle_close'
GROUP BY 1, 2 ORDER BY c DESC;

-- @Q21 P2 新老用户：按 install_week 分桶的设备数（76 台里 66 台挤在 202646）
-- 首日漏斗按「首次 app_start 的北京日」界定，逐桶节点覆盖在 Python 内算；
-- 202646 桶：66→56→46→32→29→14，其余三桶仅 2/4/4 台，无对比价值。
SELECT install_week, count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1 ORDER BY 1;

-- ============================================================
-- 以下 @Q22~@Q26 为 14:54「video_platform 会不会塞在某个字段里」深度排查（A~G）。
-- 结论：没有。全库无该列；全窗 3,312 行 × 63 列逐列扫描关键词命中 0；
--   ex_int_arg1/3~10 全空；a1/a4~a8 全空；两个疑似线索（a2='platforms'、
--   a9 的 generic-live- 前缀）均排除；平台名只在另一批插件画质埋点的事件名里、设备交集 0。
-- ============================================================

-- @Q22 全库元数据：精确查 video_platform 列（0 行）；immdata 含 platform/video 的列
--   全是 platform_type（设备端类型）或日汇总计数列；imt_*.platform 抽样为 Windows 10/Android OS 等 OS 值。
SELECT table_schema, table_name, column_name FROM information_schema.columns
WHERE lower(column_name) LIKE '%video_platform%' ORDER BY 1,2;  -- 0 行
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema='immdata'
  AND (lower(column_name) LIKE '%platform%' OR lower(column_name) LIKE '%video%')
ORDER BY 1,2;
SELECT platform FROM immdata.imt_deviceinfo WHERE platform IS NOT NULL LIMIT 8;

-- @Q23 全窗全字段扫描（3,312 行 × 63 列，Python 侧逐列 distinct + 关键词/JSON 特征）
--   关键词：六平台名、别名、中文名、URL 片段、video_platform/live_platform/platform=/platform:
--   结果：命中 0 列，含 JSON/键值结构单元格 0 个。
SELECT * FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%';

-- @Q24 所有扩展槽位非空率：除 ex_int_arg2(耗时) 外整数槽位全空；a1/a4~a8 全空
SELECT count(*) AS pv,
  count(ex_int_arg1) AS i1, count(ex_int_arg2) AS i2, count(ex_int_arg3) AS i3,
  count(ex_int_arg4) AS i4, count(ex_int_arg5) AS i5, count(ex_int_arg6) AS i6,
  count(ex_int_arg7) AS i7, count(ex_int_arg8) AS i8, count(ex_int_arg9) AS i9,
  count(ex_int_arg10) AS i10,
  count(nullif(ex_char_arg1,'')) AS a1, count(nullif(ex_char_arg4,'')) AS a4,
  count(nullif(ex_char_arg5,'')) AS a5, count(nullif(ex_char_arg6,'')) AS a6,
  count(nullif(ex_char_arg7,'')) AS a7, count(nullif(ex_char_arg8,'')) AS a8
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%';

-- @Q25 两个疑似线索：均非平台维度
--   ① a2='platforms' 58 条只属 onboarding_step_show，是引导步骤名（展示平台列表页）。
SELECT event_name, count(*) AS c FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%' AND ex_char_arg2 = 'platforms'
GROUP BY 1;
--   ② a9 非标准前缀只有 generic-live- 一种（32 个 ID / 97 行 / 15 台 / 全 trigger=progress_retry）。
SELECT DISTINCT ex_char_arg9 FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant%' AND ex_char_arg9 LIKE 'generic-live-%';

-- @Q26 平台名只出现在另一批插件埋点的「事件名」里，且与直播助手设备交集 0
--   facebook_live_quality_intent 16 / facebook_live_quality_requested 5 / youtube_live_quality_intent 2，
--   共 23 条 / 2 台 / 插件 1.34.4 Chrome desktop；a1=fixed_720 等画质档位。
SELECT event_name, count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND (event_name ILIKE '%youtube%' OR event_name ILIKE '%twitch%' OR event_name ILIKE '%kick%'
    OR event_name ILIKE '%tiktok%' OR event_name ILIKE '%facebook%' OR event_name ILIKE '%twitter%'
    OR event_name ILIKE '%spaces%' OR event_name ILIKE '%bilibili%' OR event_name ILIKE '%douyin%')
GROUP BY 1 ORDER BY pv DESC;
-- 设备交集：直播助手 device_id 全为 32 位 hex、平台事件全为 64 位 base64，精确交集 0。
SELECT length(device_id) AS id_len, count(DISTINCT device_id) AS devices
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND (event_name LIKE 'live_assistant%'
    OR event_name ILIKE '%facebook_live%' OR event_name ILIKE '%youtube_live%')
GROUP BY 1 ORDER BY 1;

-- @Q27 文档逐字复核（15:24 追问）：文档「上报字段」表写了 video_platform「直播平台，仅直播事件填写」，
--   但同一份文档第 9 行「不新增数据库字段」+ 第 45 行「仅使用现有字段」+ 第 68 行「logs 每条事件为 JSON 字符串」
--   ⇒ 它是 /collect 上报 payload 字段，不是数据库列；落库需服务端映射。
--   「仅直播事件」= 文档第 29~31 行「插件透传的直播字幕事件」5 个（桌面 8 事件不填），
--   故本组查询只筛 event_name LIKE 'live_assistant_subtitle%'，结论：库内仍 0 命中。

-- @Q27-H1 这批直播事件在库内的实际事件名与量级（manual_close 仍为 0；改名 close + 新增 interrupted）
SELECT event_name, count(*) AS pv, count(DISTINCT device_id) AS uv,
       min(created_ts) AS first_ts, max(created_ts) AS last_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN ('live_assistant_subtitle_start','live_assistant_subtitle_success',
    'live_assistant_subtitle_failed','live_assistant_subtitle_retry',
    'live_assistant_subtitle_close','live_assistant_subtitle_interrupted',
    'live_assistant_subtitle_manual_close')
GROUP BY 1 ORDER BY pv DESC;
--   实测：start 606 / close 360 / failed 221 / retry 177 / success 171 / interrupted 8，合计 1,543 条。

-- @Q27-H2a 只查这批直播事件：所有字符列 DISTINCT 组合，Python 侧逐列扫平台关键词
--   （youtube/youtu.be/twitch/kick/tiktok/facebook/twitter/x.com/spaces/中文别名/video_platform/live_platform 等）
SELECT DISTINCT event_name, trigger, ex_char_arg1, ex_char_arg2, ex_char_arg3,
       ex_char_arg4, ex_char_arg5, ex_char_arg6, ex_char_arg7, ex_char_arg8,
       ex_char_arg9, ex_char_arg10, version, os_name, os_version, interface_language,
       install_day, install_week, user_type, platform_type, browser_name, browser_version,
       real_geo, site_host, page_type, translation_service, campaign, ab_tag,
       source_language, target_language, engine_name, install_from, is_new_user_today
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant_subtitle%';
--   实测 1,542 组合行 / 33 列：命中平台关键词的列 0 个；a1/a4~a8 全空、a10 唯一 com、
--   a2 8 值、a3 4 值、trigger 仅 progress_retry/quick_menu、version 7 个 0.1.x。

-- @Q27-H2b 整数槽位：除 ex_int_arg2 耗时外全 0 个非 NULL ⇒ 不存在数字编码的平台枚举
SELECT count(*) AS pv,
       count(ex_int_arg1) AS i1, count(ex_int_arg2) AS i2, count(ex_int_arg3) AS i3,
       count(ex_int_arg4) AS i4, count(ex_int_arg5) AS i5, count(ex_int_arg6) AS i6,
       count(ex_int_arg7) AS i7, count(ex_int_arg8) AS i8, count(ex_int_arg9) AS i9,
       count(ex_int_arg10) AS i10
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-01 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name LIKE 'live_assistant_subtitle%';
--   实测 pv=1543，i2=400（388 distinct，耗时），其余全 0。

-- @Q27-H2c 是否存在把 /collect 的 JSON payload 原串塞进某列：逐列扫 '{' / 引号 / 'video_platform' 字样 → 0 个单元格。

-- @Q27-H3 全库元数据：无同名列，无原始上报日志表可反查
SELECT table_schema, table_name, column_name FROM information_schema.columns
WHERE lower(column_name) LIKE '%video_platform%' ORDER BY 1,2;                       -- 0 行
SELECT column_name FROM information_schema.columns
WHERE table_schema='immdata' AND table_name='user_behaviour'
  AND (lower(column_name) LIKE '%video%' OR lower(column_name) LIKE '%live%'
    OR lower(column_name) LIKE '%platform%') ORDER BY 1;                              -- 仅 platform_type
SELECT table_schema, table_name FROM information_schema.tables
WHERE lower(table_name) LIKE '%collect%' OR lower(table_name) LIKE '%raw_log%'
   OR lower(table_name) LIKE '%payload%' ORDER BY 1,2;                               -- 仅 babel_novel 无关表
-- 注：文档第 78 行引用的 live-assistant-analytics-design.md 本地不存在，无法核对字段映射细则（P043）。

-- @Q28 漏斗口径三分（15:56 追问）：严格漏斗做不了，但「宽松漏斗」（设备集合、不考虑顺序）能做。
--   同一锚点 11-09~11-16 14:00 UTC，2,258 行 / 76 台。三种主体不可混：
--   PV(条数) / UV(去重设备) / 尝试ID ex_char_arg9(仅登录3+字幕6事件)。
--   ⚠️ 按 PV 逐层比会倒挂（install_plugin_click 108 → browser_open 338 = 313%），
--      按本层UV/上层UV 也会倒挂（36 → 71 = 197.2%）⇒ 分子必须取「与上层交集」。

-- @Q28-L1 各节点 PV / UV / 独立覆盖率（统一分母 = 窗口总活跃设备 76）
SELECT event_name, count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
  AND event_name IN ('live_assistant_app_start','live_assistant_login_click',
    'live_assistant_login_success','live_assistant_onboarding_step_show',
    'live_assistant_onboarding_complete','live_assistant_install_plugin_click',
    'live_assistant_browser_open','live_assistant_subtitle_start','live_assistant_subtitle_success')
GROUP BY 1 ORDER BY pv DESC;

-- @Q28-L2/L4 通用模板：任意相邻两层，一次算出「宽松交集转化」与「按时间有序转化」
--   把 A / B 换成相邻两事件即可逐层跑；本例 = install_plugin_click -> browser_open（失真最严重的一对）
WITH sets AS (
  SELECT device_id,
    max(CASE WHEN event_name='live_assistant_install_plugin_click' THEN 1 ELSE 0 END) AS up_flag,
    max(CASE WHEN event_name='live_assistant_browser_open' THEN 1 ELSE 0 END) AS cur_flag,
    min(CASE WHEN event_name='live_assistant_install_plugin_click' THEN created_ts END) AS up_ts,
    min(CASE WHEN event_name='live_assistant_browser_open' THEN created_ts END) AS cur_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-09 00:00:00' AND created_ts < '2026-11-16 14:00:00'
    AND event_name IN ('live_assistant_install_plugin_click','live_assistant_browser_open')
  GROUP BY device_id)
SELECT sum(up_flag) AS up_uv, sum(cur_flag) AS cur_uv,
       sum(CASE WHEN up_flag=1 AND cur_flag=1 THEN 1 ELSE 0 END) AS both_uv,
       round(100.0*sum(CASE WHEN up_flag=1 AND cur_flag=1 THEN 1 ELSE 0 END)/nullif(sum(up_flag),0),1)
         AS loose_pct,                                    -- 交集/上层 = 100.0%
       sum(CASE WHEN up_flag=1 AND cur_flag=1 AND cur_ts>=up_ts THEN 1 ELSE 0 END) AS ordered_uv,
       round(100.0*sum(CASE WHEN up_flag=1 AND cur_flag=1 AND cur_ts>=up_ts THEN 1 ELSE 0 END)
             /nullif(sum(CASE WHEN up_flag=1 AND cur_flag=1 THEN 1 ELSE 0 END),0),1)
         AS ordered_pct                                  -- 有序率 = 0.0%（整窗 min(ts) 串错会话）
FROM sets;

-- @Q28-L3 累积集合嵌套：从 app_start 起，每一步都做过的设备（不考虑顺序）
--   实测 76 → 70 → 65 → 62 → 53 → 27 → 27 → 13 → 9 台（终点占 app_start 11.8%）。
--   可用 9 个 max(CASE WHEN ...) 标志 + 逐层 AND 计数实现；窗口拉长会变大，不是转化率。

-- ============================================================================
-- @Q29 对照外部报告 live-assistant-data-review.html（报告窗 UTC 10-28~11-15）
--   报告窗 = created_ts >= '2026-10-28 00:00:00' AND < '2026-11-16 00:00:00'
--   与本题定稿窗（11-09~11-16 14:00）不同，仅用于逐项对照，不替换已交付格子。
-- ============================================================================

-- @Q29-M1 报告窗全量事件盘点：实测 3,137 行 / 14 事件名 / 102 台
--   报告只取 4 个事件名凑成「1,225 行直播事件」（start 573 + app_start 289 +
--   failed 210 + success 153），漏 close 342 / browser_open 466 / login_click 362 等。
SELECT event_name, count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
  AND event_name LIKE 'live_assistant%'
GROUP BY 1 ORDER BY pv DESC;

-- @Q29-N1 按尝试 ID 判定「无结果」：210 个无终态里 205 个有 close，只有 3 个真空
--   ⇒ 不是「埋点闭环缺失」，主体是会话以 close 结束；close 不能当失败计入分母。
WITH s AS (
  SELECT ex_char_arg9,
    max(CASE WHEN event_name='live_assistant_subtitle_start'       THEN 1 ELSE 0 END) AS has_start,
    max(CASE WHEN event_name='live_assistant_subtitle_success'      THEN 1 ELSE 0 END) AS has_succ,
    max(CASE WHEN event_name='live_assistant_subtitle_failed'       THEN 1 ELSE 0 END) AS has_fail,
    max(CASE WHEN event_name='live_assistant_subtitle_close'        THEN 1 ELSE 0 END) AS has_close,
    max(CASE WHEN event_name='live_assistant_subtitle_retry'        THEN 1 ELSE 0 END) AS has_retry,
    max(CASE WHEN event_name='live_assistant_subtitle_interrupted'  THEN 1 ELSE 0 END) AS has_inter
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
    AND event_name LIKE 'live_assistant_subtitle%'
    AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> ''
  GROUP BY 1)
SELECT count(*) AS all_ids,
       sum(has_start) AS start_ids,                       -- 572
       sum(CASE WHEN has_start=1 AND has_succ+has_fail>0 THEN 1 ELSE 0 END) AS closed_ids, -- 362
       sum(CASE WHEN has_start=1 AND has_succ+has_fail=0 THEN 1 ELSE 0 END) AS noresult_ids, -- 210
       sum(CASE WHEN has_start=1 AND has_succ+has_fail=0 AND has_close=1 THEN 1 ELSE 0 END)
         AS noresult_with_close,                        -- 205
       sum(CASE WHEN has_start=1 AND has_succ+has_fail=0 AND has_close=0
                  AND has_retry=0 AND has_inter=0 THEN 1 ELSE 0 END) AS noresult_truly_empty -- 3
FROM s;

-- @Q29-O1 close 的关闭原因（报告把该事件整体剔除了）
SELECT ex_char_arg2 AS close_reason, trigger, count(*) AS c
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
  AND event_name='live_assistant_subtitle_close'
GROUP BY 1,2 ORDER BY c DESC;
-- 实测汇总：page_navigation 221 / quick_menu 52 / tab_closed 47 / other 22

-- @Q29-O2 登录三态：报告 90.4% 只算闭环，另有 206 次 click 无终态（56.9%）
WITH l AS (
  SELECT ex_char_arg9,
    max(CASE WHEN event_name='live_assistant_login_click'   THEN 1 ELSE 0 END) AS has_click,
    max(CASE WHEN event_name='live_assistant_login_success' THEN 1 ELSE 0 END) AS has_succ,
    max(CASE WHEN event_name='live_assistant_login_failed'  THEN 1 ELSE 0 END) AS has_fail
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
    AND event_name IN ('live_assistant_login_click','live_assistant_login_success',
                       'live_assistant_login_failed')
    AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> ''
  GROUP BY 1)
SELECT sum(has_click) AS clicks,                        -- 362
       sum(has_succ)  AS succ,                          -- 141
       sum(has_fail)  AS fail,                          -- 15
       sum(CASE WHEN has_click=1 AND has_succ+has_fail=0 THEN 1 ELSE 0 END) AS no_result, -- 206
       round(100.0*sum(has_succ)/nullif(sum(has_succ)+sum(has_fail),0),1) AS pct_closed,  -- 90.4
       round(100.0*sum(has_succ)/nullif(sum(has_click),0),1)               AS pct_all_clicks -- 39.0
FROM l;

-- @Q29-N2 generic-live- 前缀占比：报告写「多为」，实测只有 32/935 = 3.42%
--   用 SELECT DISTINCT ex_char_arg9 拉回后按前缀归类；SQL 侧等价写法：
SELECT count(*) AS distinct_ids,
       sum(CASE WHEN ex_char_arg9 LIKE 'generic-live-%' THEN 1 ELSE 0 END) AS generic_live_ids
FROM (
  SELECT DISTINCT ex_char_arg9 FROM immdata.user_behaviour
  WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
    AND event_name LIKE 'live_assistant%'
    AND ex_char_arg9 IS NOT NULL AND ex_char_arg9 <> '') t;

-- @Q29-P1 失败耗时按入口（复算报告 25.8s / 3.8s，完全一致；须限定 session_start）
SELECT trigger, count(*) AS n, round(avg(ex_int_arg2)/1000,1) AS avg_sec
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
  AND event_name='live_assistant_subtitle_failed'
  AND ex_char_arg2='session_start' AND ex_int_arg2 IS NOT NULL
GROUP BY 1 ORDER BY n DESC;
-- quick_menu 131 / 25.8s ; progress_retry 55 / 3.8s

-- @Q29-P3 重试不必推算：start 里 trigger='progress_retry' 直接 93；
--   但 subtitle_retry 共 164 条（progress_retry 93 + quick_menu 71），报告只覆盖 56.7%
SELECT event_name, trigger, count(*) AS n
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-28 00:00:00' AND created_ts < '2026-11-16 00:00:00'
  AND event_name IN ('live_assistant_subtitle_start','live_assistant_subtitle_retry')
GROUP BY 1,2 ORDER BY 1, n DESC;
