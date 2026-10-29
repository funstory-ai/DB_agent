-- =============================================================================
-- T025：BabelDoc 首次使用周 → W1～W4 留存
-- 规范大类：dashboard；口径对齐插件业务留存（首次周 + W1～W4）
-- 任务：docs/tasks/dashboard_translate_weekly_retention_20260831.md
-- 业务口径：docs/norms/translate_biz.md（babeldoc 节）
-- 本查数仓库只读，勿在只读账号执行
--
-- 与插件业务留存差异（已确认 2026-09-03）：
--   · 源表：imm_babel_doc_record（不走 user_behaviour / 周事件表）
--   · 主体：userid（非 device_id）
--   · 活跃定义：useddate 所在自然周有记录
--   · 周切分与周表一致：只含**已闭合周**
--     week_start < 北京本周一（同 update_imm_device_event_by_utf8_week）
--   · 含未满窗 cohort；源尚无的 Wn → 0
--
-- 若表已存在、只改闭合周：逻辑已并入本文件；重跑本文件或 TASK 即可。
-- 整文件一次跑完：建表 → 回填 → TASK → RESUME
-- =============================================================================


-- =============================================================================
-- §0 重建表 / TASK（幂等）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_babeldoc_firstuse_weekly_retention SUSPEND;
DROP TASK IF EXISTS update_imm_babeldoc_firstuse_weekly_retention;
DROP TABLE IF EXISTS immdata.imm_babeldoc_firstuse_weekly_retention;

CREATE TABLE immdata.imm_babeldoc_firstuse_weekly_retention (
  biz_code VARCHAR,             -- 固定 babeldoc
  biz_name VARCHAR,             -- BabelDoc
  cohort_week_start DATE,       -- 首次使用周（周一）
  cohort_users BIGINT,          -- 分母（userid）
  ret_w1_users BIGINT,
  ret_w2_users BIGINT,
  ret_w3_users BIGINT,
  ret_w4_users BIGINT,
  w1_retention_rate DOUBLE,
  w2_retention_rate DOUBLE,
  w3_retention_rate DOUBLE,
  w4_retention_rate DOUBLE,
  update_time TIMESTAMP
);


-- =============================================================================
-- §1 全量回填
-- =============================================================================
INSERT INTO immdata.imm_babeldoc_firstuse_weekly_retention
WITH act AS (
  SELECT
    userid,
    to_start_of_week(useddate, 1) AS week_start
  FROM immdata.imm_babel_doc_record
  WHERE userid IS NOT NULL
    AND userid <> ''
    -- 已闭合周：与周表一致（北京本周一之前）
    AND to_start_of_week(useddate, 1) < to_start_of_week(date(add_hours(now(), 8)), 1)
  GROUP BY 1, 2
),
firsts AS (
  SELECT userid, min(week_start) AS first_week
  FROM act
  GROUP BY 1
),
labeled AS (
  SELECT
    f.first_week,
    f.userid,
    max(CASE WHEN a.week_start = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
    max(CASE WHEN a.week_start = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
    max(CASE WHEN a.week_start = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
    max(CASE WHEN a.week_start = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
  FROM firsts f
  LEFT JOIN act a
    ON a.userid = f.userid
   AND a.week_start >= date_add(day, 7, f.first_week)
   AND a.week_start <= date_add(day, 28, f.first_week)
  GROUP BY 1, 2
)
SELECT
  'babeldoc' AS biz_code,
  'BabelDoc' AS biz_name,
  first_week AS cohort_week_start,
  count(*) AS cohort_users,
  sum(r1) AS ret_w1_users,
  sum(r2) AS ret_w2_users,
  sum(r3) AS ret_w3_users,
  sum(r4) AS ret_w4_users,
  sum(r1) * 1.0 / count(*) AS w1_retention_rate,
  sum(r2) * 1.0 / count(*) AS w2_retention_rate,
  sum(r3) * 1.0 / count(*) AS w3_retention_rate,
  sum(r4) * 1.0 / count(*) AS w4_retention_rate,
  now() AS update_time
FROM labeled
GROUP BY 1, 2, 3;


-- =============================================================================
-- §2 周更 TASK（周一 10:30 上海；与分业务留存同落后于上游周表；全量重算；P028 / P035）
-- =============================================================================
CREATE TASK update_imm_babeldoc_firstuse_weekly_retention
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 30 10 * * 1' 'Asia/Shanghai'
AS BEGIN
  DELETE FROM immdata.imm_babeldoc_firstuse_weekly_retention;
  INSERT INTO immdata.imm_babeldoc_firstuse_weekly_retention
  WITH act AS (
    SELECT
      userid,
      to_start_of_week(useddate, 1) AS week_start
    FROM immdata.imm_babel_doc_record
    WHERE userid IS NOT NULL
      AND userid <> ''
      AND to_start_of_week(useddate, 1) < to_start_of_week(date(add_hours(now(), 8)), 1)
    GROUP BY 1, 2
  ),
  firsts AS (
    SELECT userid, min(week_start) AS first_week
    FROM act
    GROUP BY 1
  ),
  labeled AS (
    SELECT
      f.first_week,
      f.userid,
      max(CASE WHEN a.week_start = date_add(day, 7, f.first_week) THEN 1 ELSE 0 END) AS r1,
      max(CASE WHEN a.week_start = date_add(day, 14, f.first_week) THEN 1 ELSE 0 END) AS r2,
      max(CASE WHEN a.week_start = date_add(day, 21, f.first_week) THEN 1 ELSE 0 END) AS r3,
      max(CASE WHEN a.week_start = date_add(day, 28, f.first_week) THEN 1 ELSE 0 END) AS r4
    FROM firsts f
    LEFT JOIN act a
      ON a.userid = f.userid
     AND a.week_start >= date_add(day, 7, f.first_week)
     AND a.week_start <= date_add(day, 28, f.first_week)
    GROUP BY 1, 2
  )
  SELECT
    'babeldoc',
    'BabelDoc',
    first_week,
    count(*),
    sum(r1), sum(r2), sum(r3), sum(r4),
    sum(r1) * 1.0 / count(*),
    sum(r2) * 1.0 / count(*),
    sum(r3) * 1.0 / count(*),
    sum(r4) * 1.0 / count(*),
    now()
  FROM labeled
  GROUP BY 1, 2, 3;
END;

ALTER TASK update_imm_babeldoc_firstuse_weekly_retention RESUME;


-- =============================================================================
-- §3 验收（只读）
-- =============================================================================
-- SELECT max(cohort_week_start) AS max_c,
--   (SELECT max(week_start_day) FROM immdata.imm_device_event_by_utf8_week) AS week_max
-- FROM immdata.imm_babeldoc_firstuse_weekly_retention;
-- -- 期望 max_c = week_max（当前约 2026-08-24）
;
