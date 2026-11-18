-- T117 移动端访问 TOP 网页（实际为「App 内置浏览器访问域名 TOP100」）
-- 需求：近 30 个北京自然日，PV + 去重设备 UV，TOP 100；合并常见子域、剔除自家域名
-- 时间窗：北京日 2026-10-14 ~ 2026-11-12 = UTC 2026-10-13 16:00:00 ~ 2026-11-12 16:00:00
-- 口径来源：docs/tasks/query_mobile_top_pages_feasibility_20261113.md
-- 主体：埋点 device_id（P037，不 JOIN imt_deviceinfo）；UV = 访问该域名的去重设备数
-- 事件：user_behaviour.event_name='webview_visit'（App 内置浏览器访问），域名在 ex_char_arg1 的 JSON domain 键
-- 归一：去协议/路径/端口 → 小写 → 循环合并 www.|m.|cn.|en.|amp.|mobile. 前缀 → 剔 host 含 immersivetranslate
-- 注意：domain 值格式混杂（"https://x.com/" 与 "x.com" 与 "m.youtube.com" 并存），归一在 Python 侧做，勿在 SQL 里直接 GROUP BY 原始值

-- @Q_MAIN 主查询（明细；195 万行级，脚本用 get_cursor()+fetchmany 流式聚合，勿 fetchall 到内存）
SELECT get(try_parse_json(ex_char_arg1), 'domain') AS domain,
       device_id,
       os_name,
       ex_char_arg10 AS app_variant,
       created_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit'
  AND lower(os_name) IN ('android', 'ios', 'ipados');

-- @Q_OVERVIEW 30 天总量与字段完备性（脚本 dry-run 对拍用）
SELECT count(*) AS pv,
       count(DISTINCT device_id) AS uv,
       count(DISTINCT get(try_parse_json(ex_char_arg1),'domain')) AS raw_domains,
       sum(CASE WHEN device_id IS NULL OR device_id = '' THEN 1 ELSE 0 END) AS no_dev,
       sum(CASE WHEN device_id = '00000000-0000-0000-0000-000000000000' THEN 1 ELSE 0 END) AS zero_dev,
       sum(CASE WHEN get(try_parse_json(ex_char_arg1),'domain') IS NULL THEN 1 ELSE 0 END) AS no_domain,
       min(created_ts) AS min_ts, max(created_ts) AS max_ts
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit';

-- @Q_SAMPLE_DAY P019 抽样：末日（北京日 11-12）独立窄窗，对拍脚本按天 PV/UV
SELECT count(*) AS pv,
       count(DISTINCT device_id) AS uv,
       count(DISTINCT get(try_parse_json(ex_char_arg1),'domain')) AS raw_domains
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit';

-- @Q_SAMPLE_REBUILD P019 独立路径：SQL 侧先按原始 domain 预聚合，再由脚本用同一归一规则重算
-- 实测 63,572 个原始值 → 49,111 host / 1,827,417 PV / 剔自家 111,313 / 无效 15,442，与脚本逐行聚合四项完全一致
SELECT get(try_parse_json(ex_char_arg1),'domain') AS d, count(*) AS pv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit'
GROUP BY d;

-- @Q_SAMPLE_YOUTUBE P019 抽样：youtube 域名族独立核对（用原始 JSON 串 LIKE，绕开归一逻辑）
-- 实测 252,937 PV / 44,053 UV / 26 个原始值；其中 5,330 PV 属 accounts./consent./studio./music. 等
-- 功能子域（不在合并白名单，单独成 host），扣除后 247,607 = 脚本 youtube.com 的 PV
SELECT count(*) AS pv, count(DISTINCT device_id) AS uv,
       count(DISTINCT get(try_parse_json(ex_char_arg1),'domain')) AS raw_values
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit'
  AND ex_char_arg1 LIKE '%youtube.com%';

-- @Q_SAMPLE_X P019 抽样：x.com 域名族独立核对（对照 TOP2）
-- ⚠️ 原始 JSON 里斜杠被转义为 \/，ex_char_arg1 LIKE '%x.com/%' 会漏掉 https:\/\/x.com\/ 这一大批（实测只命中 1 个值 97,298 PV）；
--    而 LIKE '%x.com%' 又会误含 manga18fx.com / yandex.com / help.x.com 等 13,455 PV。故改用 get() 精确值/前缀匹配。
--    实测 PV 与脚本 x.com 186,961 一致
SELECT count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit'
  AND (get(try_parse_json(ex_char_arg1),'domain') = 'x.com'
       OR get(try_parse_json(ex_char_arg1),'domain') LIKE 'https://x.com/%'
       OR get(try_parse_json(ex_char_arg1),'domain') LIKE 'http://x.com/%'
       OR get(try_parse_json(ex_char_arg1),'domain') = 'www.x.com');

-- @Q_SAMPLE_AO3 P019 合理性：30 天 PV TOP1 archiveofourown.org 按北京日 PV/UV
-- 事实：10-14~10-29 每日约 1.9~2.5 万 PV / 1.4~1.6 千设备；10-30 起降至 0.5~2.6 千 PV。
-- 单设备 30 天最高 3,740 次访问。机制（埋点/上报/客户端变更/自动化）未证实，P043 不作因果判断。
SELECT to_date(date_add(hour, 8, created_ts)) AS bj,
       count(*) AS pv, count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-13 16:00:00'
  AND created_ts <  '2026-11-12 16:00:00'
  AND event_name = 'webview_visit'
  AND get(try_parse_json(ex_char_arg1),'domain') IN ('https://archiveofourown.org/', 'archiveofourown.org')
GROUP BY bj ORDER BY bj;
