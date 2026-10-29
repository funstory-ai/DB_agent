-- =============================================================================
-- T078  without_fb 任务改点 + 一次性补数
-- 规范大类：anomaly
-- 本文件交给写仓执行。本仓只读账号不要跑。
--
-- 根因：
--   update_imm_user_target_lan_stats          21:00 UTC（北京 05:00）写累计
--   update_imm_device_native_language_without_fb 原 20:00 UTC，比累计早 1 小时
--   当天第一次带目标语翻译的设备，对累计表时还没有行，内连接被丢掉。
--   之后没再译，就一直不在 without_fb。界面语兜底的人本来就不该进这张表。
--
-- 执行顺序：
--   1) §1 补数。赶在累计任务没在跑的时候（21:00 UTC 那一阵避开）。
--      现在这样的白天可以跑：累计已含到北京昨天。
--   2) §2 换任务。新时刻 22:30 UTC = 北京 06:30，在累计之后、和主母语任务（22:00 UTC）错开。
--   3) §3 验收：缺行应为 0。北京「今天」只译一次的人，要等当晚新任务跑完才进来。
--
-- 逻辑除了时刻，日更 SQL 与线上任务相同（仍只收目标语，不用界面语）。
-- 补数按当前累计表对齐：没有的设备补上；已有设备的目标语、次数、更早的安装日一并补齐。
-- 安装日取主表 imm_device_native_language.install_day，不扫 user_behaviour 全历史。
-- =============================================================================


-- -----------------------------------------------------------------------------
-- §0 补数前看缺多少（只读，可单独跑）
-- -----------------------------------------------------------------------------
-- SELECT COUNT(*) AS stats_devices_missing_from_without_fb
-- FROM (
--   SELECT device_id
--   FROM (
--     SELECT
--       device_id,
--       ROW_NUMBER() OVER (
--         PARTITION BY device_id
--         ORDER BY cnt DESC, update_time DESC, target_language
--       ) AS rn
--     FROM immdata.imm_user_target_lan_stats
--     WHERE target_language IS NOT NULL
--       AND target_language <> ''
--   ) s
--   WHERE rn = 1
-- ) top
-- LEFT JOIN immdata.imm_device_native_language_without_fb fb
--   ON top.device_id = fb.device_id
-- WHERE fb.device_id IS NULL;


-- -----------------------------------------------------------------------------
-- §1 一次性补数
-- -----------------------------------------------------------------------------
REPLACE INTO immdata.imm_device_native_language_without_fb (
  device_id, native_language, cnt, update_time, install_day
) ON (device_id)
SELECT
  x.device_id,
  x.target_language AS native_language,
  x.cnt,
  NOW() AS update_time,
  CASE
    WHEN old.install_day IS NULL THEN lang.install_day
    WHEN lang.install_day IS NULL THEN old.install_day
    WHEN lang.install_day < old.install_day THEN lang.install_day
    ELSE old.install_day
  END AS install_day
FROM (
  SELECT device_id, target_language, cnt
  FROM (
    SELECT
      device_id,
      target_language,
      cnt,
      ROW_NUMBER() OVER (
        PARTITION BY device_id
        ORDER BY cnt DESC, update_time DESC, target_language
      ) AS rn
    FROM immdata.imm_user_target_lan_stats
    WHERE target_language IS NOT NULL
      AND target_language <> ''
  ) ranked
  WHERE rn = 1
) x
LEFT JOIN immdata.imm_device_native_language_without_fb AS old
  ON x.device_id = old.device_id
LEFT JOIN immdata.imm_device_native_language AS lang
  ON x.device_id = lang.device_id
WHERE old.device_id IS NULL
   OR COALESCE(old.native_language, '') <> x.target_language
   OR COALESCE(old.cnt, -1) <> COALESCE(x.cnt, -1)
   OR (
     lang.install_day IS NOT NULL
     AND (old.install_day IS NULL OR lang.install_day < old.install_day)
   );


-- -----------------------------------------------------------------------------
-- §2 改自动任务：20:00 UTC → 22:30 UTC
--    语句本体与线上一致，只改时刻。
-- -----------------------------------------------------------------------------
ALTER TASK IF EXISTS update_imm_device_native_language_without_fb SUSPEND;
DROP TASK IF EXISTS update_imm_device_native_language_without_fb;

CREATE TASK update_imm_device_native_language_without_fb
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 30 22 * * *' 'UTC'
COMMENT = '设备母语（仅目标语，无界面语兜底）。须在 update_imm_user_target_lan_stats（21:00 UTC）之后'
AS
REPLACE INTO immdata.imm_device_native_language_without_fb (
  device_id, native_language, cnt, update_time, install_day
) ON (device_id)
SELECT
  x1.device_id,
  x1.target_language AS native_language,
  x1.cnt,
  NOW() AS update_time,
  CASE
    WHEN old.install_day IS NULL THEN inst.install_day
    WHEN inst.install_day IS NULL THEN old.install_day
    WHEN inst.install_day < old.install_day THEN inst.install_day
    ELSE old.install_day
  END AS install_day
FROM (
  SELECT device_id, target_language, cnt
  FROM (
    SELECT
      s.device_id,
      s.target_language,
      s.cnt,
      ROW_NUMBER() OVER (
        PARTITION BY s.device_id
        ORDER BY s.cnt DESC, s.update_time DESC, s.target_language
      ) AS rn
    FROM immdata.imm_user_target_lan_stats AS s
    INNER JOIN (
      SELECT DISTINCT device_id
      FROM immdata.user_behaviour
      WHERE event_name = 'translate_page'
        AND target_language IS NOT NULL
        AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
        AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
    ) AS d
      USING (device_id)
  ) AS t
  WHERE rn = 1
) AS x1
LEFT OUTER JOIN immdata.imm_device_native_language_without_fb AS old
  USING (device_id)
LEFT OUTER JOIN (
  SELECT
    device_id,
    MIN(TO_DATE(install_day, '%Y-%m-%d')) AS install_day
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
    AND install_day IS NOT NULL
    AND REGEXP_LIKE(install_day, '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') = 1
  GROUP BY device_id
) AS inst
  USING (device_id)
WHERE old.install_day IS NULL
   OR inst.install_day IS NOT NULL AND inst.install_day < old.install_day
   OR (
     old.device_id IS NULL
     OR COALESCE(old.native_language, '') <> COALESCE(x1.target_language, '')
     OR COALESCE(old.cnt, -1) <> COALESCE(x1.cnt, -1)
   );

ALTER TASK update_imm_device_native_language_without_fb RESUME;


-- -----------------------------------------------------------------------------
-- §3 补数后验收（只读）。缺行应为 0。
--    把 §0 那条 SELECT 再跑一遍即可。
-- -----------------------------------------------------------------------------
