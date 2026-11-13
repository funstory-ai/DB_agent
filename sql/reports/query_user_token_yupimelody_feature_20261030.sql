-- 用途：单用户「功能」维度日消耗 + 前窗/后窗对比（镜像 T067 方法论）
-- 主体：yupimelody24@gmail.com -> immdata.imt_userinfo.id = 6515557
-- 主表：immdata.token_used_aw（AW 账单，billing-ledger 落表）
-- 口径：recordtype='capture'；token = inputusage + outputusage
--       日标签 = 北京自然日：to_char(date_add(hour,8,timestamp),'%Y-%m-%d')
--       注：timestamp 为 UTC，bj_day = D 等价于 UTC ∈ [D-1 16:00, D 16:00)，故用 UTC 边界精确等价于北京日窗（避免对 timestamp 套函数导致全表扫）
-- 功能维度：productline（web_page=网页翻译 / subtitle_f=字幕翻译 / unknow+unknown=未归类）
-- 之前窗口（Pro 额度期）：北京日 2026-10-02 ~ 2026-10-19  -> UTC 2026-10-01 16:00:00 ~ 2026-10-19 16:00:00
-- 当前窗口（被质疑流量包期）：北京日 2026-10-22 ~ 2026-10-30 -> UTC 2026-10-21 16:00:00 ~ 2026-10-30 16:00:00

-- ========== 1) 之前窗口：每日 × 功能（token）==========
SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
       CASE WHEN productline='web_page' THEN '网页翻译'
            WHEN productline='subtitle_f' THEN '字幕/视频翻译'
            ELSE '未归类' END AS feat,
       count(*) AS req_n,
       sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid=6515557 AND recordtype='capture'
  AND timestamp >= '2026-10-01 16:00:00' AND timestamp < '2026-10-19 16:00:00'
GROUP BY 1,2 ORDER BY 1,2;

-- ========== 2) 当前窗口：每日 × 功能（token）==========
SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
       CASE WHEN productline='web_page' THEN '网页翻译'
            WHEN productline='subtitle_f' THEN '字幕/视频翻译'
            ELSE '未归类' END AS feat,
       count(*) AS req_n,
       sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid=6515557 AND recordtype='capture'
  AND timestamp >= '2026-10-21 16:00:00' AND timestamp < '2026-10-30 16:00:00'
GROUP BY 1,2 ORDER BY 1,2;

-- ========== 3) 功能 × 窗口 对比（日均 + 总额）==========
-- 之前（18 天）
WITH pre AS (
  SELECT CASE WHEN productline='web_page' THEN '网页翻译'
             WHEN productline='subtitle_f' THEN '字幕/视频翻译'
             ELSE '未归类' END AS feat,
         sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
  FROM immdata.token_used_aw
  WHERE userid=6515557 AND recordtype='capture'
    AND timestamp >= '2026-10-01 16:00:00' AND timestamp < '2026-10-19 16:00:00'
  GROUP BY 1),
cur AS (
  SELECT CASE WHEN productline='web_page' THEN '网页翻译'
             WHEN productline='subtitle_f' THEN '字幕/视频翻译'
             ELSE '未归类' END AS feat,
         sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
  FROM immdata.token_used_aw
  WHERE userid=6515557 AND recordtype='capture'
    AND timestamp >= '2026-10-21 16:00:00' AND timestamp < '2026-10-30 16:00:00'
  GROUP BY 1)
SELECT COALESCE(p.feat,c.feat) AS feat,
       p.tok AS pre_total, c.tok AS cur_total,
       round(p.tok/18.0) AS pre_avg_day, round(c.tok/9.0) AS cur_avg_day,
       round(c.tok/9.0 / NULLIF(p.tok/18.0,0), 2) AS avg_day_mult
FROM pre p FULL OUTER JOIN cur c ON p.feat=c.feat
ORDER BY COALESCE(p.tok,c.tok) DESC;

-- ========== 4) 全十月 计费来源按日（看 10/20 切换）==========
SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') AS bj_day,
       countername,
       sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid=6515557 AND recordtype='capture'
  AND timestamp >= '2026-09-30 16:00:00' AND timestamp < '2026-10-31 16:00:00'
GROUP BY 1,2 ORDER BY 1,2;
