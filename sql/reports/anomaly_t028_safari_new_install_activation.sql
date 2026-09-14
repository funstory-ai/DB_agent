-- T028: Safari 新装 / 激活 / 激活率（与看板「Safari新装激活日活」同口径）
-- 规范大类: anomaly（探查）；口径见 docs/pitfalls.md P034
--
-- 新装: event_name='init_page_daily' AND is_new_user_today='1'，按日 COUNT(DISTINCT device_id)
-- 激活: event_name='translate_page' AND is_new_user_today='1'，按日 COUNT(DISTINCT device_id)
-- 日活: event_name='translate_page'，按日 COUNT(DISTINCT device_id)
-- 激活率: 激活 / 新装（同日）
-- 筛选: browser_name='Safari'（全平台；与截图 DAU ~29k 对齐）
--
-- 剔集成（T028 结论）: 同日设备若 install_from='official_userscript' AND browser_name='Safari' 则排除

WITH daily AS (
  SELECT
    to_date(created_ts) AS d,
    device_id,
    event_name,
    is_new_user_today,
    MAX(CASE
      WHEN LOWER(TRIM(install_from)) = 'official_userscript'
       AND TRIM(browser_name) = 'Safari' THEN 1 ELSE 0 END)
      OVER (PARTITION BY device_id, to_date(created_ts)) AS is_embed
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-07-24'
    AND created_ts < '2026-08-04'
    AND TRIM(browser_name) = 'Safari'
)
SELECT
  d,
  COUNT(DISTINCT CASE
    WHEN event_name = 'init_page_daily' AND is_new_user_today = '1'
    THEN device_id END) AS new_install_raw,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_new_user_today = '1'
    THEN device_id END) AS activation_raw,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page'
    THEN device_id END) AS dau_raw,
  COUNT(DISTINCT CASE
    WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' AND is_embed = 0
    THEN device_id END) AS new_install_ex_embed,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_new_user_today = '1' AND is_embed = 0
    THEN device_id END) AS activation_ex_embed,
  COUNT(DISTINCT CASE
    WHEN event_name = 'translate_page' AND is_embed = 0
    THEN device_id END) AS dau_ex_embed
FROM daily
GROUP BY d
ORDER BY d;
