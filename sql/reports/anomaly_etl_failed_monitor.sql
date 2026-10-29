-- ============================================================
-- 日更 ETL 失败巡检（anomaly monitor）
-- 用途：定期查最近 N 天的自动任务失败，并高亮 OSS/权限类故障
-- 适用：只读账号即可执行（仅 SELECT system.task_history）
-- 关联任务：T086（task_run_daily_etl 自 2026-10-24 起 OSS 403 连续失败）
-- ============================================================

-- 可调参数：回溯天数
SET @lookback_days = 7;

-- 1) 最近 N 天失败任务清单（按调度时间倒序）
SELECT
    name                                                        AS task_name,
    state,
    scheduled_time,
    completed_time,
    ROUND(DATEDIFF('second', scheduled_time, completed_time)/60.0, 1) AS dur_min,
    exception_code,
    -- 命中 OSS / 权限类关键字的优先标红
    CASE
        WHEN exception_text ILIKE '%AccessDenied%' OR exception_text ILIKE '%bucket acl%'
             OR exception_text ILIKE '%OSS%' OR exception_text ILIKE '%403%'
        THEN 'OSS/PERMISSION'
        ELSE 'OTHER'
    END                                                         AS fail_class,
    LEFT(exception_text, 400)                                   AS exception_excerpt
FROM system.task_history
WHERE state = 'FAILED'
  AND scheduled_time >= DATE_SUB(NOW(), INTERVAL @lookback_days DAY)
ORDER BY scheduled_time DESC;

-- 2) 聚合视角：每个失败任务近 N 天的 成功/失败 计数
SELECT
    name              AS task_name,
    COUNT_IF(state = 'SUCCEEDED') AS n_ok,
    COUNT_IF(state = 'FAILED')    AS n_fail,
    MAX(scheduled_time)           AS last_run,
    MAX(CASE WHEN state='FAILED' THEN scheduled_time END) AS last_fail
FROM system.task_history
WHERE scheduled_time >= DATE_SUB(NOW(), INTERVAL @lookback_days DAY)
GROUP BY name
HAVING n_fail > 0
ORDER BY n_fail DESC, name;
