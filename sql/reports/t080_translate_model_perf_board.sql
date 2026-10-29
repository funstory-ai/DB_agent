-- =============================================================================
-- T080 网页翻译：各 -pro/-max 模型「翻译时长」与「报错率」 —— Superset 挂板 SQL
-- 规范大类：dashboard
-- 任务文档：docs/tasks/dashboard_translate_model_latency_error_20261021.md
-- 写仓前置：须先跑 sql/reports/t080_translate_model_perf_etl.sql（中间表 + TASK）
--   注：ETL 日表 grain 已改为 dt_bj × translation_service（2026-10-22）
--
-- 本文件每段自带标注：
--   【可挂 Superset】  = 生产 Dataset 用这段
--   【仅探查·勿挂板】  = 对账/排错用，禁止当生产 Dataset
--
-- Superset 操作提醒（改完 SQL 必须做）：Edit SQL → SAVE → COLUMNS 标签 → SYNC COLUMNS FROM SOURCE → 再 SAVE
-- （「Refresh」不是刷新页面；列变了必须 SYNC COLUMNS，只改 WHERE 则可只 SAVE）
--
-- ══════════════════════════════════════════════════════════════════════════
-- 口径收窄（2026-10-22 调整）：只展示 -pro / -max 官方档位，label = 服务 key
-- ──────────────────────────────────────────────────────────────────────────
-- 规则（展示层过滤，底层日表仍保留全量）：
--   1) (translation_service LIKE '%-pro' OR translation_service LIKE '%-max')
--       取官方专业/旗舰档位：deepseek-pro / openai-max / gemini-pro / claude-max …
--       -pro/-max 全部来自插件官方配置，无用户随机后缀，label 干净，可直接展示。
--   2) translation_service <> 'trial-pro'
--        trial-pro 是「免费试用额度通道」(model_group=trial)，非付费模型档位、
--        无具体模型定义，且占近 30 日约 5% 流量。若要纳入试用通道，删此条件即可。
--   3) 近 30 日 events >= 500（量级门槛，冷启动延迟；要跟踪新模型放量可调小/删）
--
-- ⚠️ 两个 Dataset 必须用同一套规则，否则同源两图口径不一致。
--   底层中间表 imm_translate_model_daily_perf（grain = dt_bj × translation_service）
--   保留全量（含 personal API），本文件只在展示层过滤。
--   日表改服务粒度后，SELECT 里把 translation_service 别名成 model_label，
--   故 Superset 里 Series / 分组字段仍是「model_label」，无需改图配置。
-- ══════════════════════════════════════════════════════════════════════════


-- =============================================================================
-- ds_translate_model_perf_day —— 【可挂 Superset】
-- 按日折线数据集；grain = dt_bj × translation_service（每行唯一）
-- dt_bj 在 Superset 里务必标 Temporal
-- 滚动窗 -90 天（P029：禁止写死日期上界）
--
-- 为什么要用 mainstream 这个 CTE 而不是直接写 row-level 条件：
--   日表单行只有「当天」的量。若按当日 events >= 500 过滤，一个近 30 日有 5 万条的
--   服务在单日只有 ~1600 条没问题，但更小一点的服务会被间歇性滤掉，导致折线断断续续。
--   统一用「近 30 日总量」判定是否主流，再回捞这些 label 的全部日期，折线才连续。
-- =============================================================================
WITH mainstream AS (
  SELECT translation_service
  FROM immdata.imm_translate_model_daily_perf
  WHERE dt_bj >= add_days(date(add_hours(now(), 8)), -30)
    AND dt_bj <  date(add_hours(now(), 8))
    AND (translation_service LIKE '%-pro' OR translation_service LIKE '%-max')
    AND translation_service <> 'trial-pro'          -- 排除免费试用通道；要保留则删此行
  GROUP BY translation_service
  HAVING sum(events) >= 500                         -- 量级门槛
)
SELECT
  d.dt_bj,
  d.translation_service                   AS model_label,   -- 新 label = 服务 key（deepseek-pro / openai-max …）
  d.model_group,
  d.real_model,
  d.events,
  d.failure_events,
  -- 失败原因 8 桶（互斥且穷尽，恒等于 failure_events；图 7 与表格用）
  d.fail_network,
  d.fail_timeout,
  d.fail_auth,
  d.fail_quota,
  d.fail_provider,
  d.fail_invalid_resp,
  d.fail_render,
  d.fail_other,
  d.error_rate,
  d.req_ms_cnt,
  d.req_ms_sum,
  d.req_ms_avg,
  d.req_ms_p50,
  d.req_ms_p95,
  d.total_ms_cnt,
  d.total_ms_sum,
  d.total_ms_avg,
  d.total_ms_p50,
  d.total_ms_p95,
  d.failure_missing_ms
FROM immdata.imm_translate_model_daily_perf d
WHERE d.dt_bj >= add_days(date(add_hours(now(), 8)), -90)
  AND d.translation_service IN (SELECT translation_service FROM mainstream);


-- =============================================================================
-- ds_translate_model_perf_window —— 【可挂 Superset】
-- 近 30 天窗口汇总，无 dt_bj → 只能给 Big Number / Table，禁止画按日折线
-- 比率与均值一律 SUM/SUM，禁止 AVG(日率) 或 AVG(req_ms_p50)
-- ⚠️ 本表给不出「近窗 p95」：分位数不可跨日再聚合。
--    worst_day_p95_30d 是「近 30 天里最差的单日 p95」，不是 30 天整体 p95
-- 三条规则与 day Dataset 保持一致
-- =============================================================================
SELECT
  translation_service                   AS model_label,
  model_group,
  sum(events)                              AS events_30d,
  sum(failure_events)                      AS failure_30d,
  -- 失败原因 8 桶（互斥且穷尽，恒等于 failure_30d）
  sum(fail_network)                        AS fail_network_30d,
  sum(fail_timeout)                        AS fail_timeout_30d,
  sum(fail_auth)                           AS fail_auth_30d,
  sum(fail_quota)                          AS fail_quota_30d,
  sum(fail_provider)                       AS fail_provider_30d,
  sum(fail_invalid_resp)                   AS fail_invalid_resp_30d,
  sum(fail_render)                         AS fail_render_30d,
  sum(fail_other)                          AS fail_other_30d,
  -- 分母保护：events_30d 不会为 0（有行才有组），但防御性加上
  CASE WHEN sum(events) > 0
       THEN sum(failure_events) * 1.0 / sum(events) END AS error_rate_30d,
  sum(req_ms_cnt)                          AS req_ms_cnt_30d,
  sum(req_ms_sum)                          AS req_ms_sum_30d,
  -- ⚠️ 分母可能为 0：某些服务整窗内一条 request_ms 都没有（纯失败或极低量），
  --    此时返回 NULL（Superset 显示空），不要返回 0（0 会被误读成「耗时 0ms」）
  CASE WHEN sum(req_ms_cnt) > 0
       THEN sum(req_ms_sum) * 1.0 / sum(req_ms_cnt) END AS avg_req_ms_30d,
  sum(total_ms_cnt)                          AS total_ms_cnt_30d,
  sum(total_ms_sum)                          AS total_ms_sum_30d,
  CASE WHEN sum(total_ms_cnt) > 0
       THEN sum(total_ms_sum) * 1.0 / sum(total_ms_cnt) END AS avg_total_ms_30d,
  max(total_ms_p95)                          AS worst_day_p95_total_30d,
  max(req_ms_p95)                          AS worst_day_p95_30d,
  max(dt_bj)                               AS last_day
FROM immdata.imm_translate_model_daily_perf
WHERE dt_bj >= add_days(date(add_hours(now(), 8)), -30)
  AND dt_bj <  date(add_hours(now(), 8))
  AND (translation_service LIKE '%-pro' OR translation_service LIKE '%-max')
  AND translation_service <> 'trial-pro'          -- 排除免费试用通道；要保留则删此行
GROUP BY translation_service, model_group
HAVING sum(events) >= 500;                       -- 量级门槛


-- =============================================================================
-- ds_translate_model_perf_recon —— 【仅探查·勿挂板】
-- 抽日对账用（P019/P027/P030）：日表 SUM 与 user_behaviour 直查对照，ratio 须 ≈1.000
-- 注意：对账必须用【未过滤】的全量日表，否则 ratio 会小于 1 而误判 ETL 丢数
-- 用前把下面 4 处的日期换成待测的北京日（dt_bj 当天 + 次日）
-- =============================================================================
-- SELECT
--   (SELECT sum(events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-19') AS tbl_events,
--   (SELECT count(*) FROM immdata.user_behaviour
--     WHERE created_ts >= add_hours(to_date('2026-10-19'), -8)
--       AND created_ts <  add_hours(to_date('2026-10-20'), -8)
--       AND event_name = 'track_translate_page_data')                                          AS raw_events,
--   (SELECT sum(failure_events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-19') AS tbl_fail,
--   (SELECT count_if(ex_char_arg2 = 'failure') FROM immdata.user_behaviour
--     WHERE created_ts >= add_hours(to_date('2026-10-19'), -8)
--       AND created_ts <  add_hours(to_date('2026-10-20'), -8)
--       AND event_name = 'track_translate_page_data')                                          AS raw_fail;
