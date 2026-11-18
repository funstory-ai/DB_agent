-- T116 | T114 追问：小米浏览器数据的平台构成 | 2026-11-13
-- 口径：
--   * 北京日 2026-11-12 单日 = UTC 2026-11-11 16:00:00 ~ 2026-11-12 16:00:00，
--     与 T114 Q2 完全一致，禁止对 created_ts 套函数。
--   * 主体 device_id；COUNT(DISTINCT device_id) 不计 NULL device_id。
--     实测本窗 15,657 条事件里 1,785 条（11.4%）device_id 为 NULL，
--     故 GROUP BY device_id 会比 COUNT(DISTINCT device_id) 多 1 组（NULL 组）。
--   * 17 台设备同日跨两个 os_name 上报，分平台去重数相加（1,455）> 总去重（1,439）。
--   * 日汇总 device_count 按 event/os/platform/browser 分行，不是跨天去重人数。
--   * 只读，不代跑任何写仓语句。

-- Q1【平台构成】11-12 北京日 Miui 各平台（同一次查询内出总数与各平台，保 P044 一致性）
SELECT COUNT(DISTINCT device_id)                                                   AS total_dev,
       COUNT(DISTINCT CASE WHEN os_name='Android' THEN device_id END)              AS android_dev,
       COUNT(DISTINCT CASE WHEN os_name='Linux'   THEN device_id END)              AS linux_dev,
       COUNT(DISTINCT CASE WHEN os_name='iOS'     THEN device_id END)              AS ios_dev,
       SUM(CASE WHEN device_id IS NULL THEN 1 ELSE 0 END)                          AS null_dev_events
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
  AND browser_name = 'Miui';
-- 实测：1,439 / 811 / 639 / 5 / 1,785

-- Q2【各平台明细：事件量、新设备、浏览器版本线】
SELECT os_name, platform_type,
       COUNT(DISTINCT device_id) AS dev, COUNT(*) AS evt,
       COUNT(DISTINCT CASE WHEN is_new_user_today='1' THEN device_id END) AS new_dev,
       MIN(browser_version) AS bv_min, MAX(browser_version) AS bv_max
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
  AND browser_name = 'Miui'
GROUP BY 1,2 ORDER BY 3 DESC;
-- Android/mobile 811 / 9750 / 489；Linux/desktop 639 / 5897 / 158；iOS/mobile 5 / 10 / 4

-- Q3【跨 OS 重合 + 空 device_id 分布】
WITH d AS (
  SELECT device_id, COUNT(DISTINCT os_name) AS n_os
  FROM immdata.user_behaviour
  WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
    AND browser_name='Miui'
  GROUP BY device_id
)
SELECT n_os, COUNT(*) AS dev_groups FROM d GROUP BY 1 ORDER BY 1;
-- 1 → 1,423 组（含 NULL device_id 组 1 个）；2 → 17 台

SELECT os_name, platform_type, COUNT(*) AS evt,
       SUM(CASE WHEN device_id IS NULL THEN 1 ELSE 0 END) AS null_dev_evt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-11-11 16:00:00' AND created_ts < '2026-11-12 16:00:00'
  AND browser_name='Miui'
GROUP BY 1,2 ORDER BY 1;
-- Android 1,136/9,750 (11.7%)；Linux 649/5,897 (11.0%)；iOS 0/10 —— 空 ID 不偏斜平台占比

-- Q4【UA 原文：桌面 vs 手机到底长什么样】
SELECT COALESCE(platform,'<NULL>') AS platform, COUNT(*) AS cnt
FROM immdata.imt_campaigninfo
WHERE COALESCE(browser,'')='Miui' AND COALESCE(isdeleted,0)=0
GROUP BY 1 ORDER BY 2 DESC;
-- Linux 804 / Android OS 762 / iOS 1（全表累计）

SELECT CASE WHEN browseruseragent LIKE '%X11; Linux x86_64%' THEN 'X11_Linux_desktop'
            WHEN browseruseragent LIKE '%Mobile Safari%'      THEN 'Android_Mobile'
            WHEN browseruseragent LIKE '%iPhone%' OR browseruseragent LIKE '%iPad%' THEN 'iOS'
            ELSE 'other' END AS ua_shape,
       COUNT(*) AS cnt, MIN(browseruseragent) AS ua_sample
FROM immdata.imt_campaigninfo
WHERE COALESCE(browser,'')='Miui' AND COALESCE(isdeleted,0)=0
GROUP BY 1 ORDER BY 2 DESC;
-- 桌面 UA：Mozilla/5.0 (X11; Linux x86_64) ... Chrome/135.0.7049.79 Safari/537.36
--          XiaoMi/MiuiBrowser/20.6.1061104（无 Mobile / Android 字样，os_version='unknown'）
-- 手机 UA：Mozilla/5.0 (Linux; U; Android 16; zh-cn; <机型> Build/...) ... Mobile Safari/537.36
--          XiaoMi/MiuiBrowser/20.32.1021111
-- 版本线不同：桌面 18.9/20.6/20.8，手机 13.16/15.4/20.32
-- ⚠️ 库内无设备型号、行为表不存 UA 原文，无法判定桌面组是「PC 版小米浏览器」
--    还是「安卓设备切桌面 UA 模式」；需客户端补上报或业务侧确认（P043）。

-- Q5【11-11 起的突增来自哪个平台】日汇总 translate_page
SELECT dates, os_name, SUM(device_count) AS dev, SUM(new_device_count) AS new_dev
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates >= '2026-11-01' AND dates <= '2026-11-12'
  AND event_name='translate_page' AND browser_name='Miui'
GROUP BY 1,2 ORDER BY 1,2;
-- 基线 11-01~10：Linux 58~129/日 > Android 22~40/日（桌面是存量主力）
-- 11-11 Android 157(新127) / Linux 104(新50)；11-12 Android 311(新261) / Linux 144(新78)
-- → 增量几乎全在 Android 手机端，Linux 仅小幅同步上扬。仍无推荐位归因证据（P043）。

-- Q6【另一种理解：其它主流浏览器都在什么平台】11-12 translate_page
SELECT browser_name, os_name, SUM(device_count) AS dev
FROM immdata.imm_event_device_count_by_utf8_day
WHERE dates = '2026-11-12' AND event_name='translate_page'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40;
-- Chrome: Windows 352,779 / macOS 102,713；Edge: Windows 204,018 / Android 17,742
-- UC Browser: Android 17,184；Safari: macOS 16,279 / iOS 11,475；Electron: Windows 3,496
