-- T114 | 小米浏览器用户可识别性核查 | 2026-11-13
-- 口径：
--   * 「小米浏览器」在埋点里唯一取值为 browser_name = 'Miui'（UA 原文 XiaoMi/MiuiBrowser/<ver>）。
--     2026-10-14~11-12 全事件扫描确认无 'Xiaomi' / 'Mi Browser' 等其它变体。
--   * 北京日 = created_ts + 8h。D 的 UTC 边界 = (D-1) 16:00 ~ D 16:00。
--     明细表禁止对 created_ts 套函数，必须常量范围比较以保分区裁剪。
--   * imm_event_device_count_by_utf8_day 是日汇总（device_count 按 event/os/platform/browser 分行），
--     按天 SUM 得到的是「设备×维度行之和」，不是跨天去重人数；趋势可用，绝对人数用 Q2 明细。
--   * 本任务只读，不代跑任何写仓语句。

-- Q1【首选·快】按天看小米浏览器设备趋势（日汇总，查 60 天也很快）
SELECT dates,
       os_name,
       SUM(device_count)     AS device_count,
       SUM(new_device_count) AS new_device_count,
       SUM(event_count)      AS event_count
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-09-14' AND dates <= '2026-11-12'
  AND event_name = 'translate_page'
  AND browser_name = 'Miui'
GROUP BY dates, os_name
ORDER BY dates, os_name;

-- Q2【取用户清单】北京日 2026-11-12 单日，小米浏览器活跃设备（明细层最全口径）
-- 实测：1,439 台设备 / 15,657 条事件；is_new_user_today='1' 的 640 台；CN 1,287 台（89.4%）
SELECT device_id,
       MIN(created_ts)                                             AS first_seen_utc,
       MAX(is_new_user_today)                                       AS any_new_flag,
       COUNT(*)                                                     AS event_cnt,
       MAX(real_geo)                                                AS geo_sample,
       MAX(install_from)                                            AS install_from_sample,
       MAX(ex_int_arg1)                                             AS userid_if_logged_in
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00'   -- 北京 11-12 00:00
  AND created_ts <  '2026-11-12 16:00:00'   -- 北京 11-13 00:00
  AND browser_name = 'Miui'
GROUP BY device_id;

-- Q3【档案表补口径】注册设备里的小米浏览器（含 UA 原文，可用于补捞误解析）
-- 实测全表：UA 命中 351 行 / 346 设备；browser='Miui' 的设备 96% 标 edge_store、UTM 全空
SELECT deviceid, userid, browser, browseruseragent, installchannel,
       utmsource, utmcampaign, createtime
FROM immdata.imt_deviceinfo
WHERE COALESCE(isdeleted, 0) = 0
  AND (LOWER(COALESCE(browseruseragent, '')) LIKE '%miuibrowser%'
       OR LOWER(COALESCE(browser, '')) = 'miui');

-- Q4【缺口量化】UA 明确是小米浏览器、但 browser 被解析成别的值
-- 实测 imt_campaigninfo：Miui 1,567 / Chrome 88 / Edge-chromium 1 → 约 5.3% 会漏
-- 这批 UA 带 'swan-mibrowser' 后缀。user_behaviour 无 UA 原文，行为层无法补捞。
SELECT COALESCE(browser, '<NULL>') AS browser,
       COUNT(*) AS row_cnt, COUNT(DISTINCT deviceid) AS dev_cnt
FROM immdata.imt_campaigninfo
WHERE COALESCE(isdeleted, 0) = 0
  AND (LOWER(COALESCE(browseruseragent, '')) LIKE '%miuibrowser%'
       OR LOWER(COALESCE(browseruseragent, '')) LIKE '%xiaomi/miui%')
GROUP BY 1 ORDER BY 2 DESC;

-- Q5【结论性核查】有没有「小米推荐位」专属渠道 / UTM
-- 实测：installchannel 全表 16 个取值，无任何小米相关；
--       imt_campaigninfo 中 browser='Miui' 的 1,567 行 utmsource/utmcampaign/reference 全空；
--       含 'xiaomi' 的归因值只有 via_xiaoming（人名）与用户翻译的 PDF 文件名，与小米无关。
SELECT COALESCE(installchannel, '<NULL>') AS ch, COUNT(*) AS cnt
FROM immdata.imt_deviceinfo
WHERE COALESCE(isdeleted, 0) = 0
GROUP BY 1 ORDER BY 2 DESC;

-- Q6【推荐效果的近似口径，非因果结论】
-- 库内没有推荐位标记，只能用「小米浏览器新设备数的台阶」做增量对照，
-- 需业务侧给出推荐上线日期后再圈定前后窗。11-01~11-10 基线日均 ~125 台，
-- 11-11 = 261（新设备 177）、11-12 = 455（新设备 339）。
-- 若确实要拿到「被推荐来的设备」名单，用 Q2 的 device_id 反查首次出现日：
--   WHERE created_ts >= '<上线日前30天> 16:00:00' AND created_ts < '<窗末> 16:00:00'
--    AND browser_name='Miui' → MIN(created_ts) 落在上线日后 + is_new_user_today='1'
-- 注意 P037：移动端 device_id 大部分不在 imt_deviceinfo，
--   行为 1,439 台 vs 档案表全表 346 台；关联账号/付费必须走 P016 双路径且必然大面积漏。
