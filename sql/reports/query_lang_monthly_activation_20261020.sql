-- T078 分语言月激活人数（按第二套口径发版）
-- 任务：docs/tasks/anomaly_lang_activation_two_sql_20261020.md
--
-- 激活 = 北京自然月内，国际版当天新用户的网页翻译
--   event_name = 'translate_page'
--   is_new_user_today = '1'
--   ex_char_arg10 = 'com'          -- 国际版；2025-09-29 起上报。空值是没带这个字段的包，cn 是国内版
--   母语 = 设备主表 imm_device_native_language（含界面语兜底）
--   人数 = COUNT(DISTINCT device_id)
-- 不用 without_fb，也不按安装月归人。
-- 原第二套外层 avg(dau) 删掉了：内层已经按月去重，avg 不会再平均。
-- 也不再用 hybrid_id：登录用户多台设备会被并成一人。
--
-- 窗：北京 2025-10-01 ≤ 日 < 2026-10-01
--   UTC：created_ts >= '2025-09-30 16:00:00' AND created_ts < '2026-09-30 16:00:00'
-- 已知坑：P017 / P034

SELECT
  l.native_language,
  TO_START_OF_MONTH(ADD_HOURS(b.created_ts, 8)) AS activate_month,
  COUNT(DISTINCT b.device_id) AS activated_devices
FROM immdata.user_behaviour AS b
INNER JOIN immdata.imm_device_native_language AS l
  ON b.device_id = l.device_id
WHERE b.created_ts >= '2025-09-30 16:00:00'
  AND b.created_ts < '2026-09-30 16:00:00'
  AND b.event_name = 'translate_page'
  AND b.is_new_user_today = '1'
  AND b.ex_char_arg10 = 'com'
  AND l.native_language IN ('zh-CN', 'zh-TW', 'ja', 'ko', 'en')
GROUP BY
  l.native_language,
  TO_START_OF_MONTH(ADD_HOURS(b.created_ts, 8))
ORDER BY
  activate_month,
  l.native_language;
