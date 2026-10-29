-- =============================================================================
-- T080 补丁：日表增加「失败原因」拆分列（8 个桶）
-- 规范大类：dashboard
-- 任务文档：docs/tasks/dashboard_translate_model_latency_error_20261021.md
-- 本查数仓库只读；本文件交给写仓同学执行，勿在只读账号跑
--
-- ═══ 为什么要有这个补丁 ═══
-- 看板挂出来后，DeepSeek-V4.1-Flash 近 30 日报错率 8.54% 被质疑「过高不合理」。
-- 排查发现失败构成分成完全不同的两类：
--   · deepseek / babelfast / deepl  → 82~90% 是 network_error（客户端网络，非服务端故障）
--   · openai / gemini / qwen        → 50~69% 是 http_429 限流
-- 现日表只有 failure_events 总数，看不出构成 → 无法区分「网络差」还是「服务挂」。
-- 故按 ex_char_arg5（first_visible_failure_reason）拆 8 个桶落列。
--
-- ═══ 执行要点 ═══
--   · 单文件 §0→§4 一次跑完；重复跑全文幂等
--   · 只重建【日表 + TASK】，dim 表 imm_translate_model_map 不动
--   · 日表是 user_behaviour 的派生聚合，DROP 重建无数据损失（90 天回填约 65 秒）
--   · 必须先 SUSPEND 再 DROP，否则 TASK 会指向被删的表
--   · 跑完务必做 §4 验收，尤其是 §4.3「原因合计 = failure_events」
--
-- 涉及规范：P017（禁止 WHERE 套函数再过滤时间列）、P019/P027/P030（抽日对账）、
--           P028（TASK 须 BEGIN…END）、P035（cron 六段含秒）
-- =============================================================================


-- =============================================================================
-- §0 停 TASK 并删旧表（幂等）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_translate_model_daily_perf SUSPEND;
DROP TASK IF EXISTS update_imm_translate_model_daily_perf;
DROP TABLE IF EXISTS immdata.imm_translate_model_daily_perf;


-- =============================================================================
-- §1 重建日表（新增 8 个失败原因列）
-- grain = dt_bj × model_label（不变）
--
-- 失败原因取自 ex_char_arg5 = first_visible_failure_reason，
-- 插件枚举见 src/analytics/first_visible_translation.ts：
--   network_error / timeout / auth_error / quota_or_rate_limit /
--   provider_error / invalid_response / render_error / unknown
-- 前 7 个各一列，其余（含 unknown、NULL）归入 fail_other，
-- 保证 8 列之和恒等于 failure_events（§4.3 验收）。
--
-- ⚠️ 实测当前 fail_timeout 与 fail_other 恒为 0（插件未产出 timeout reason），
--    保留这两列是为了 schema 完整，将来插件改了不用再改表。
-- =============================================================================
CREATE TABLE immdata.imm_translate_model_daily_perf (
  dt_bj              DATE,      -- 北京自然日
  model_label        VARCHAR,   -- 展示名：real_model，查不到时为 '[未映射] '+服务名
  model_group        VARCHAR,   -- 取优先级最高的档位；看板 Filter 用
  groups_all         VARCHAR,   -- 该模型涉及的全部档位（'|' 分隔，备查）
  real_model         VARCHAR,   -- 真实模型名（未映射为 NULL）
  src_service        VARCHAR,   -- 来源服务；多服务聚合时为 '(多服务)'
  svc_cnt            BIGINT,    -- 映射到该 model_label 的服务数
  events             BIGINT,    -- 全量事件数（success+failure）＝ 报错率分母
  failure_events     BIGINT,    -- ex_char_arg2='failure'（＝ 下面 8 列之和）

  fail_network       BIGINT,    -- network_error      ：客户端网络（failed to fetch / ERR_* / 断网）
  fail_timeout       BIGINT,    -- timeout            ：超时（当前实测恒 0）
  fail_auth          BIGINT,    -- auth_error         ：401/403，鉴权失效（如 zhipu-air-pro 天天全败）
  fail_quota         BIGINT,    -- quota_or_rate_limit：429 限流（openai/gemini/qwen 主因）
  fail_provider      BIGINT,    -- provider_error     ：5xx 服务端故障
  fail_invalid_resp  BIGINT,    -- invalid_response   ：响应收到但解析不了（8-13 尖峰即此类）
  fail_render        BIGINT,    -- render_error       ：渲染阶段失败
  fail_other         BIGINT,    -- 其余（unknown / NULL）；当前实测恒 0

  error_rate         DOUBLE,    -- failure_events/events（日率；跨日须 SUM/SUM，勿 AVG）
  req_ms_cnt         BIGINT,    -- 有请求耗时的行数（ex_int_arg3>0）＝ 耗时分母
  req_ms_sum         BIGINT,    -- request_ms 合计 → 近窗均值用 SUM/SUM
  req_ms_avg         DOUBLE,    -- 当日均值（仅供核对；跨日用 SUM/SUM）
  req_ms_p50         DOUBLE,    -- 当日请求耗时中位数（ms）
  req_ms_p95         DOUBLE,    -- 当日请求耗时 p95（ms）
  failure_missing_ms BIGINT,    -- failure 且无 request_ms 的行数（观测数据质量，非故障）
  update_time        TIMESTAMP
);


-- =============================================================================
-- §2 全量回填：近 90 个完整北京日
-- 时间边界用 created_ts 常量（P017）
-- 预判：约 65 秒（14 天实测 10.2s 线性外推）
-- =============================================================================
INSERT INTO immdata.imm_translate_model_daily_perf
WITH src AS (
  SELECT
    DATE(add_hours(created_ts, 8))             AS dt_bj,
    COALESCE(translation_service, '(unknown)') AS translation_service,
    ex_char_arg2                               AS result_flag,
    ex_char_arg5                               AS failure_reason,
    ex_int_arg3                                AS request_ms
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -90), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
    AND event_name = 'track_translate_page_data'
),
mapped AS (
  SELECT
    s.dt_bj,
    s.translation_service,
    d.real_model,
    COALESCE(d.model_group, 'unknown')                          AS model_group,
    COALESCE(d.real_model, '[未映射] ' || s.translation_service) AS model_label,
    s.result_flag,
    s.failure_reason,
    s.request_ms
  FROM src s
  LEFT JOIN immdata.imm_translate_model_map d
    ON d.translation_service = s.translation_service
)
SELECT
  dt_bj,
  model_label,
  CASE
    WHEN count_if(model_group = 'max')     > 0 THEN 'max'
    WHEN count_if(model_group = 'pro')     > 0 THEN 'pro'
    WHEN count_if(model_group = 'trial')   > 0 THEN 'trial'
    WHEN count_if(model_group = 'free')    > 0 THEN 'free'
    WHEN count_if(model_group = 'custom')  > 0 THEN 'custom'
    WHEN count_if(model_group = 'builtin') > 0 THEN 'builtin'
    ELSE 'unknown'
  END                                                       AS model_group,
  array_to_string(array_sort(array_agg(DISTINCT model_group)), '|') AS groups_all,
  min(real_model)                                           AS real_model,
  CASE WHEN count(DISTINCT translation_service) = 1
       THEN min(translation_service) ELSE '(多服务)' END     AS src_service,
  count(DISTINCT translation_service)                       AS svc_cnt,
  count(*)                                                  AS events,
  count_if(result_flag = 'failure')                         AS failure_events,
  -- ↓↓↓ 失败原因 8 桶（互斥且穷尽，恒等于 failure_events）↓↓↓
  count_if(failure_reason = 'network_error')                AS fail_network,
  count_if(failure_reason = 'timeout')                      AS fail_timeout,
  count_if(failure_reason = 'auth_error')                   AS fail_auth,
  count_if(failure_reason = 'quota_or_rate_limit')          AS fail_quota,
  count_if(failure_reason = 'provider_error')               AS fail_provider,
  count_if(failure_reason = 'invalid_response')             AS fail_invalid_resp,
  count_if(failure_reason = 'render_error')                 AS fail_render,
  count_if(result_flag = 'failure'
           AND (failure_reason IS NULL
                OR failure_reason NOT IN ('network_error','timeout','auth_error',
                    'quota_or_rate_limit','provider_error','invalid_response','render_error')))
                                                            AS fail_other,
  count_if(result_flag = 'failure') * 1.0 / count(*)        AS error_rate,
  count_if(request_ms > 0)                                  AS req_ms_cnt,
  sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END)  AS req_ms_sum,
  CASE WHEN count_if(request_ms > 0) > 0
       THEN sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END) * 1.0
            / count_if(request_ms > 0)
  END                                                       AS req_ms_avg,
  quantile_cont(0.50)(CASE WHEN request_ms > 0 THEN request_ms END) AS req_ms_p50,
  quantile_cont(0.95)(CASE WHEN request_ms > 0 THEN request_ms END) AS req_ms_p95,
  count_if(result_flag = 'failure' AND (request_ms IS NULL OR request_ms <= 0)) AS failure_missing_ms,
  now()
FROM mapped
GROUP BY dt_bj, model_label;


-- =============================================================================
-- §3 重建日更 TASK（列变了，definition 必须跟着换，否则每日增量不写新列）
-- · 每天重跑近 3 个完整北京日，容忍埋点迟到
-- · P028 多语句必须 AS BEGIN … END;
-- · P035 cron 六段含秒；07:30 北京
-- =============================================================================
CREATE TASK update_imm_translate_model_daily_perf
WAREHOUSE = 'default'
SCHEDULE = USING CRON '0 30 7 * * *' 'Asia/Shanghai'
AS BEGIN
  DELETE FROM immdata.imm_translate_model_daily_perf
  WHERE dt_bj >= add_days(date(add_hours(now(), 8)), -3)
    AND dt_bj <  date(add_hours(now(), 8));

  INSERT INTO immdata.imm_translate_model_daily_perf
  WITH src AS (
    SELECT
      DATE(add_hours(created_ts, 8))             AS dt_bj,
      COALESCE(translation_service, '(unknown)') AS translation_service,
      ex_char_arg2                               AS result_flag,
      ex_char_arg5                               AS failure_reason,
      ex_int_arg3                                AS request_ms
    FROM immdata.user_behaviour
    WHERE created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -3), -8)
      AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
      AND event_name = 'track_translate_page_data'
  ),
  mapped AS (
    SELECT
      s.dt_bj,
      s.translation_service,
      d.real_model,
      COALESCE(d.model_group, 'unknown')                          AS model_group,
      COALESCE(d.real_model, '[未映射] ' || s.translation_service) AS model_label,
      s.result_flag,
      s.failure_reason,
      s.request_ms
    FROM src s
    LEFT JOIN immdata.imm_translate_model_map d
      ON d.translation_service = s.translation_service
  )
  SELECT
    dt_bj,
    model_label,
    CASE
      WHEN count_if(model_group = 'max')     > 0 THEN 'max'
      WHEN count_if(model_group = 'pro')     > 0 THEN 'pro'
      WHEN count_if(model_group = 'trial')   > 0 THEN 'trial'
      WHEN count_if(model_group = 'free')    > 0 THEN 'free'
      WHEN count_if(model_group = 'custom')  > 0 THEN 'custom'
      WHEN count_if(model_group = 'builtin') > 0 THEN 'builtin'
      ELSE 'unknown'
    END,
    array_to_string(array_sort(array_agg(DISTINCT model_group)), '|'),
    min(real_model),
    CASE WHEN count(DISTINCT translation_service) = 1
         THEN min(translation_service) ELSE '(多服务)' END,
    count(DISTINCT translation_service),
    count(*),
    count_if(result_flag = 'failure'),
    count_if(failure_reason = 'network_error'),
    count_if(failure_reason = 'timeout'),
    count_if(failure_reason = 'auth_error'),
    count_if(failure_reason = 'quota_or_rate_limit'),
    count_if(failure_reason = 'provider_error'),
    count_if(failure_reason = 'invalid_response'),
    count_if(failure_reason = 'render_error'),
    count_if(result_flag = 'failure'
             AND (failure_reason IS NULL
                  OR failure_reason NOT IN ('network_error','timeout','auth_error',
                      'quota_or_rate_limit','provider_error','invalid_response','render_error'))),
    count_if(result_flag = 'failure') * 1.0 / count(*),
    count_if(request_ms > 0),
    sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END),
    CASE WHEN count_if(request_ms > 0) > 0
         THEN sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END) * 1.0
              / count_if(request_ms > 0)
    END,
    quantile_cont(0.50)(CASE WHEN request_ms > 0 THEN request_ms END),
    quantile_cont(0.95)(CASE WHEN request_ms > 0 THEN request_ms END),
    count_if(result_flag = 'failure' AND (request_ms IS NULL OR request_ms <= 0)),
    now()
  FROM mapped
  GROUP BY dt_bj, model_label;
END;

ALTER TASK update_imm_translate_model_daily_perf RESUME;


-- =============================================================================
-- §4 验收（只读；写仓同学跑完后逐条执行对照）
-- =============================================================================

-- §4.1 新鲜度：max(dt_bj) 应 = 昨日北京日；grain 唯一：cnt 必须 = dist
-- SELECT count(*) AS cnt,
--        count(DISTINCT concat(cast(dt_bj AS string), '|', model_label)) AS dist,
--        min(dt_bj) AS min_day, max(dt_bj) AS max_day
-- FROM immdata.imm_translate_model_daily_perf;

-- §4.2 【本补丁核心】原因 8 桶之和 必须 = failure_events（差 0 才算拆对了）
-- SELECT sum(failure_events) AS total_fail,
--        sum(fail_network + fail_timeout + fail_auth + fail_quota
--            + fail_provider + fail_invalid_resp + fail_render + fail_other) AS sum_reasons,
--        sum(failure_events)
--          - sum(fail_network + fail_timeout + fail_auth + fail_quota
--                + fail_provider + fail_invalid_resp + fail_render + fail_other) AS diff
-- FROM immdata.imm_translate_model_daily_perf;
-- → diff 必须为 0

-- §4.3 抽日对账（P019/P027/P030）：日表 SUM 与 user_behaviour 直查 ratio ≈ 1.000
-- SELECT sum(events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-20';
-- SELECT count(*) FROM immdata.user_behaviour
--   WHERE created_ts >= add_hours(to_date('2026-10-20'), -8)
--     AND created_ts <  add_hours(to_date('2026-10-21'), -8)
--     AND event_name = 'track_translate_page_data';
-- SELECT sum(failure_events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-20';
-- SELECT count_if(ex_char_arg2 = 'failure') FROM immdata.user_behaviour
--   WHERE created_ts >= add_hours(to_date('2026-10-20'), -8)
--     AND created_ts <  add_hours(to_date('2026-10-21'), -8)
--     AND event_name = 'track_translate_page_data';

-- §4.4 TASK 重建检查（P028/P035）：definition 须同时含 DELETE 与 INSERT，且含新列
-- SHOW TASKS;   -- ⚠️ Databend 的 LIKE 不过滤，须在客户端侧按 name 筛
-- → 检查 definition 含 'fail_network'

-- §4.5 抽样看一眼构成是否合理（近 30 日主流模型，网络 vs 限流）
-- SELECT model_label, sum(failure_events) AS fail,
--        sum(fail_network) AS net, sum(fail_quota) AS q429,
--        sum(fail_provider) AS p5xx, sum(fail_invalid_resp) AS invalid, sum(fail_auth) AS auth
-- FROM immdata.imm_translate_model_daily_perf
-- WHERE dt_bj >= add_days(date(add_hours(now(), 8)), -30) AND dt_bj < date(add_hours(now(), 8))
--   AND model_group NOT IN ('custom','unknown')
-- GROUP BY model_label HAVING sum(events) >= 500 ORDER BY fail DESC;
