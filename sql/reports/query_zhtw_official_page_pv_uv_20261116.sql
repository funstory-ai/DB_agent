-- T123 上月繁体官网（/zh-TW/）点击量与点击人数
-- 口径（用户 2026-11-16 拍板）：
--   时间窗：2026-10 北京自然日 = UTC 2026-09-30 16:00:00 ~ 2026-10-31 16:00:00
--   点击量 = official_page_view 中「当前页 URL 路径首段 = zh-TW」的事件行数（PV）
--   点击人数 = 同范围内身份 ID 统一去重：身份类型 + 身份值（ex_char_arg8 | ex_char_arg9）
--   范围：仅 /zh-TW/ 页面（不含 /zh-HK/、不按访客界面语言）
-- 数据源：immdata.user_behaviour（官网埋点明细）
-- 注意：
--   1) user_behaviour 必须对 created_ts 做常量范围过滤，禁止对时间列套函数（保持分区裁剪）
--   2) 不可用 LIKE '%/zh-TW/%'：会命中 app.immersivetranslate.com/text#ja/zh-TW/... 等
--      WebApp 文本翻译 hash 路由（2026-10 实测误伤 21,211 条）
--   3) 官网访客三类身份 device_id / fingerprint / first_party 不可互通（T063 指纹→device_id 断链）
--   4) 旧的 imm_official_pv_click_by_utf8_day 已被清理（T066 僵尸表，停更 2025-11-13），不可用

-- Q1【主口径】上月繁体官网点击量 / 点击人数
SELECT
    count(*)                                                   AS click_pv,
    count(DISTINCT concat(ex_char_arg8, '|', ex_char_arg9))     AS click_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-30 16:00:00'
  AND created_ts <  '2026-10-31 16:00:00'
  AND event_name = 'official_page_view'
  AND regexp_extract(ex_char_arg1, '^https?://[^/]+/([^/?#]*)', 1) = 'zh-TW';

-- Q2【P019 抽样 1】逐日加总校验（北京时间切日）
SELECT
    to_date(date_add(hour, 8, created_ts))                      AS dt_bj,
    count(*)                                                   AS click_pv,
    count(DISTINCT concat(ex_char_arg8, '|', ex_char_arg9))     AS click_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-30 16:00:00'
  AND created_ts <  '2026-10-31 16:00:00'
  AND event_name = 'official_page_view'
  AND regexp_extract(ex_char_arg1, '^https?://[^/]+/([^/?#]*)', 1) = 'zh-TW'
GROUP BY 1
ORDER BY 1;

-- Q3【P019 抽样 2】host 构成（披露主站 / onboarding 子域占比）
SELECT
    site_host,
    count(*)                                                   AS click_pv,
    count(DISTINCT concat(ex_char_arg8, '|', ex_char_arg9))     AS click_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-30 16:00:00'
  AND created_ts <  '2026-10-31 16:00:00'
  AND event_name = 'official_page_view'
  AND regexp_extract(ex_char_arg1, '^https?://[^/]+/([^/?#]*)', 1) = 'zh-TW'
GROUP BY 1
ORDER BY 2 DESC;

-- Q4【P019 抽样 3】身份类型分布（验证 UV 去重主体覆盖）
SELECT
    coalesce(ex_char_arg8, '(NULL)')                            AS identity_type,
    count(*)                                                   AS click_pv,
    count(DISTINCT ex_char_arg9)                               AS click_uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-30 16:00:00'
  AND created_ts <  '2026-10-31 16:00:00'
  AND event_name = 'official_page_view'
  AND regexp_extract(ex_char_arg1, '^https?://[^/]+/([^/?#]*)', 1) = 'zh-TW'
GROUP BY 1
ORDER BY 2 DESC;
