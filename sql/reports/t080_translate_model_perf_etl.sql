-- =============================================================================
-- T080 网页翻译：各真实模型的「翻译时长」与「报错率」 —— 写仓 ETL（最终完整版）
-- 规范大类：dashboard
-- 任务文档：docs/tasks/dashboard_translate_model_latency_error_20261021.md
-- 本查数仓库只读；本文件交给写仓同学执行，勿在只读账号跑
--
-- 产出物：
--   1) dim 表   immdata.imm_translate_model_map        translation_service → 真实模型（手工维护）
--   2) 日表     immdata.imm_translate_model_daily_perf grain = dt_bj × translation_service
--   3) 日更 TASK update_imm_translate_model_daily_perf
--
-- 口径要点（改口径前先看任务文档，勿只看 SQL）：
--   1. 维度用【顶层 translation_service】（已归一化），禁止用 ex_char_arg1（含 2.2 万随机后缀）
--   2. 【禁止】用 WHERE ex_int_arg3 > 0 筛行：失败行缺耗时 5.35% vs 成功行 0.14%，
--      筛行会系统性漏失败样本、把报错率算低（实测免费档 0.61%→0.46%）。
--      本 ETL 取全量行，耗时指标只在该列 >0 时计入（条件聚合），报错率取全量行。
--   3. 翻译时长主指标 = ex_int_arg3 请求耗时（不含并发闸门/批次排队）
--   4. 报错率分母 = 全量已上报事件；skip（缓存命中）不上报，故不是「全量翻译失败率」
--   5. 分位数不可跨日再聚合：日表存当日 p50/p95（仅供按日折线逐点读）；
--      近窗汇总用 SUM(req_ms_sum)/SUM(req_ms_cnt) 加权均值，禁止 AVG(req_ms_p50)
--
-- 涉及规范：P017（禁止 WHERE 套函数再过滤时间列）、P019（抽日对账）、
--           P022（board 不得直查 user_behaviour 90d，须中间表）、
--           P027/P030（对账看 ratio≈1）、P028（TASK 须 BEGIN…END）、P035（cron 六段）
-- =============================================================================


-- =============================================================================
-- §0 清理旧对象（幂等；重复跑全文也安全）
-- =============================================================================
ALTER TASK IF EXISTS update_imm_translate_model_daily_perf SUSPEND;
DROP TASK IF EXISTS update_imm_translate_model_daily_perf;
DROP TABLE IF EXISTS immdata.imm_translate_model_daily_perf;
DROP TABLE IF EXISTS immdata.imm_translate_model_map;


-- =============================================================================
-- §1 dim 表：translation_service → 真实模型（手工维护）
--
-- 数据来源：F:\extension default_config.json 的 translationServices[*].model
--           （本地 commit 5ba7d8c / 2026-10-20；git pull 报 502，未拉最新）
-- ⚠️ 这是「当前配置快照」。模型会随版本换（今天 openai-pro=gpt-6-luna）。
--    套到历史日会失真。模型改名后：① UPDATE 本表 ② 重跑受影响区间的日表（见 §5.4）
-- 维护规则：新增/改名改本表即可，不必改 ETL 正文；查不到的服务 → model_label = '[未映射] '+服务名
-- =============================================================================
CREATE TABLE immdata.imm_translate_model_map (
  translation_service VARCHAR,   -- 顶层已归一化服务 key（唯一）
  real_model          VARCHAR,   -- 真实模型名（NULL = 插件配置查不到）
  model_group         VARCHAR,   -- pro / max / free / trial / custom / builtin
  remark              VARCHAR,   -- 来源与说明
  update_time         TIMESTAMP
);

INSERT INTO immdata.imm_translate_model_map
  (translation_service, real_model, model_group, remark, update_time)
VALUES
  ('aliyun-bailian', 'qwen-long', 'builtin', '插件配置 model', now()),
  ('aliyun-bailian-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('aliyun-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('azure-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('azure-openai-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('babel-lite-free', NULL, 'free', '免费通道，服务端混池，无模型定义', now()),
  ('babelfast', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('babelfast-pro', NULL, 'pro', '自研/服务端下发，插件配置无公开模型名', now()),
  ('baidu-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('bing', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('bing-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('bing-free', NULL, 'free', '免费通道（非LLM），服务端混池，无模型定义', now()),
  ('browser-translator', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('caiyun-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('claude-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('claude-max', NULL, 'max', '服务端下发，插件配置无公开模型名', now()),
  ('claude-pro', 'claude-haiku-5-5', 'pro', '插件配置 model', now()),
  ('custom', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('custom-ai', 'gpt-4o-mini', 'builtin', '插件配置 model', now()),
  ('custom-ai-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('custom-ai-local-1-8b', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('custom-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('deepl', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('deepl-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('deepl-pro', NULL, 'pro', 'DeepL 付费接口（非LLM），无模型名', now()),
  ('deeplx-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('deepseek', 'deepseek-flash', 'builtin', '插件配置 model', now()),
  ('deepseek-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('deepseek-pro', 'DeepSeek-V4.1-Flash', 'pro', '插件配置 model', now()),
  ('doubao', 'deepseek-v3-1-250821', 'builtin', '插件配置 model', now()),
  ('doubao-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('free-model', NULL, 'free', '免费通道，服务端混池，无模型定义', now()),
  ('gemini', 'gemini-2.5-flash', 'builtin', '插件配置 model', now()),
  ('gemini-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('gemini-max', 'gemini-3.1-pro-preview', 'max', '插件配置 model', now()),
  ('gemini-pro', 'gemini-3-flash-preview', 'pro', '插件配置 model', now()),
  ('google', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('google-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('google-free', NULL, 'free', '免费通道（非LLM），服务端混池，无模型定义', now()),
  ('grok-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('grok-pro', 'grok-4-3', 'pro', '插件配置 model', now()),
  ('groq-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('imtq-chatgpt', NULL, 'builtin', '内置/旧版通道，无模型定义', now()),
  ('imtq-chatgpt-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('kimi-max', 'kimi-k2.6', 'max', '插件配置 model', now()),
  ('lingyiwanwu-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('mimo-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('mock-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('niu-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('ollama', 'llama3.3', 'builtin', '插件配置 model', now()),
  ('ollama-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('openai', 'gpt-6-luna', 'builtin', '插件配置 model', now()),
  ('openai-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('openai-max', 'gpt-6.1-sol', 'max', '插件配置 model', now()),
  ('openai-pro', 'gpt-6-luna', 'pro', '插件配置 model', now()),
  ('openrouter', 'google/gemini-2.0-flash-001', 'builtin', '插件配置 model', now()),
  ('openrouter-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('plamo-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('plamo-pro', 'plamo-3.0-prime', 'pro', '插件配置 model', now()),
  ('qianfan2-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('qwen-mt-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('qwen-pro', 'qwen3.5-plus', 'pro', '插件配置 model', now()),
  ('siliconcloud', 'Qwen/Qwen3-8B', 'builtin', '插件配置 model', now()),
  ('siliconcloud-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('siliconcloud-free', 'THUDM/GLM-4-9B-0414', 'free', '插件配置 model', now()),
  ('tencent-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('tokenhub-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('trial-pro', NULL, 'trial', '服务端下发试用额度，无模型定义', now()),
  ('volc-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('youdao-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('youdao-ziyue-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('zhipu', 'glm-4-flash', 'builtin', '插件配置 model', now()),
  ('zhipu-air-pro', 'glm-4.5-air', 'pro', '插件配置 model', now()),
  ('zhipu-custom', NULL, 'custom', '用户自建服务，模型由用户自配', now()),
  ('zhipu-free', 'glm-4-flash-250414', 'free', '插件配置 model', now()),
  ('zhipu-max', 'glm-5.2', 'max', '插件配置 model', now()),
  ('zhipu-pro', 'GLM-4.7', 'pro', '插件配置 model', now());


-- =============================================================================
-- §2 日表
-- grain = dt_bj × translation_service  （2026-10-22 由 dt_bj × model_label 改为服务粒度）
-- ═══ 为什么改服务粒度 ═══
--   · 看板要以「-pro/-max 服务 key」当 label（deepseek-pro / openai-max …），服务粒度下
--     translation_service 即标签，无需再拼 model_label，也不会塌成 "(多服务)"。
--   · 每个 translation_service 经 dim 映射后 → 唯一 model_group / real_model（函数依赖），
--     故无需优先级 CASE、groups_all、src_service、svc_cnt。
--   · 彻底消除「同模型跨档位合并」：gpt-6-luna 不再把 builtin openai 流量并到 openai-pro。
--   · 行数仍小（约 92 服务 × 天数），Superset 秒级；SUM(events) 跨全行 = 该日总量可对账。
--   · 展示层收窄（只看 -pro/-max、排除 trial-pro）在 board SQL 做，不在本表做，保留全量。
-- =============================================================================
CREATE TABLE immdata.imm_translate_model_daily_perf (
  dt_bj              DATE,      -- 北京自然日
  translation_service VARCHAR,  -- 顶层服务 key（新 label；-pro/-max 档无随机后缀）
  model_label        VARCHAR,   -- 展示名：real_model，查不到时为 '[未映射] '+服务名
  model_group        VARCHAR,   -- 服务对应档位（pro/max/free/trial/custom/builtin/unknown）
  real_model         VARCHAR,   -- 真实模型名（未映射为 NULL）
  events             BIGINT,    -- 全量事件数（success+failure）＝ 报错率分母
  failure_events     BIGINT,    -- ex_char_arg2='failure'（＝ 下面 8 列之和）

  fail_network       BIGINT,    -- network_error      ：客户端网络（failed to fetch / ERR_* / 断网）
  fail_timeout       BIGINT,    -- timeout            ：超时（当前实测恒 0）
  fail_auth          BIGINT,    -- auth_error         ：401/403，鉴权失效
  fail_quota         BIGINT,    -- quota_or_rate_limit：429 限流
  fail_provider      BIGINT,    -- provider_error     ：5xx 服务端故障
  fail_invalid_resp  BIGINT,    -- invalid_response   ：响应收到但解析不了
  fail_render        BIGINT,    -- render_error       ：渲染阶段失败
  fail_other         BIGINT,    -- 其余（unknown / NULL）；当前实测恒 0

  error_rate         DOUBLE,    -- failure_events/events（日率；跨日须 SUM/SUM，勿 AVG）
  req_ms_cnt         BIGINT,    -- 有请求耗时的行数（ex_int_arg3>0）＝ 耗时分母
  req_ms_sum         BIGINT,    -- request_ms 合计 → 近窗均值用 SUM/SUM
  req_ms_avg         DOUBLE,    -- 当日均值（仅供核对；跨日用 SUM/SUM）
  req_ms_p50         DOUBLE,    -- 当日请求耗时中位数（ms）
  req_ms_p95         DOUBLE,    -- 当日请求耗时 p95（ms）
  total_ms_cnt       BIGINT,    -- 有总耗时的行数（ex_int_arg2>0）＝ 总耗时分母
  total_ms_sum       BIGINT,    -- total_ms 合计 → 近窗均值用 SUM/SUM
  total_ms_avg       DOUBLE,    -- 当日总耗时均值（长尾敏感，仅核对用；跨日用 SUM/SUM）
  total_ms_p50       DOUBLE,    -- 当日总耗时中位数（ms）
  total_ms_p95       DOUBLE,    -- 当日总耗时 p95（ms）
  failure_missing_ms BIGINT,    -- failure 且无 request_ms 的行数（观测数据质量，非故障）
  update_time        TIMESTAMP
);


-- =============================================================================
-- §3 全量回填：近 90 个完整北京日
-- 时间边界用 created_ts 常量（P017：禁止 WHERE 里对时间列套函数）
-- 待 DAU 口径确认后如需更长历史，改 -90 即可，重跑本文件全文（幂等）
-- =============================================================================
INSERT INTO immdata.imm_translate_model_daily_perf
WITH src AS (
  SELECT
    DATE(add_hours(created_ts, 8))                 AS dt_bj,
    COALESCE(translation_service, '(unknown)')     AS translation_service,
    ex_char_arg2                                   AS result_flag,
    ex_char_arg5                                   AS failure_reason,
    ex_int_arg3                                    AS request_ms,
    ex_int_arg2                                    AS total_ms
  FROM immdata.user_behaviour
  WHERE created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -90), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
    AND event_name = 'track_translate_page_data'
),
mapped AS (
  SELECT
    s.dt_bj,
    s.translation_service,
    COALESCE(d.real_model, '[未映射] ' || s.translation_service) AS model_label,
    COALESCE(d.model_group, 'unknown')                          AS model_group,
    d.real_model                                                AS real_model,
    s.result_flag,
    s.failure_reason,
    s.request_ms,
    s.total_ms
  FROM src s
  LEFT JOIN immdata.imm_translate_model_map d
    ON d.translation_service = s.translation_service
)
SELECT
  dt_bj,
  translation_service,
  model_label,
  model_group,
  real_model,
  count(*)                                                 AS events,
  count_if(result_flag = 'failure')                        AS failure_events,
  count_if(failure_reason = 'network_error')               AS fail_network,
  count_if(failure_reason = 'timeout')                     AS fail_timeout,
  count_if(failure_reason = 'auth_error')                  AS fail_auth,
  count_if(failure_reason = 'quota_or_rate_limit')         AS fail_quota,
  count_if(failure_reason = 'provider_error')              AS fail_provider,
  count_if(failure_reason = 'invalid_response')            AS fail_invalid_resp,
  count_if(failure_reason = 'render_error')                AS fail_render,
  count_if(result_flag = 'failure'
           AND (failure_reason IS NULL
                OR failure_reason NOT IN ('network_error','timeout','auth_error',
                    'quota_or_rate_limit','provider_error','invalid_response','render_error')))
                                                           AS fail_other,
  count_if(result_flag = 'failure') * 1.0 / count(*)       AS error_rate,
  count_if(request_ms > 0)                                 AS req_ms_cnt,
  sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END) AS req_ms_sum,
  CASE WHEN count_if(request_ms > 0) > 0
       THEN sum(CASE WHEN request_ms > 0 THEN request_ms ELSE 0 END) * 1.0
            / count_if(request_ms > 0)
  END                                                      AS req_ms_avg,
  quantile_cont(0.50)(CASE WHEN request_ms > 0 THEN request_ms END) AS req_ms_p50,
  quantile_cont(0.95)(CASE WHEN request_ms > 0 THEN request_ms END) AS req_ms_p95,
  count_if(total_ms > 0)                                  AS total_ms_cnt,
  sum(CASE WHEN total_ms > 0 THEN total_ms ELSE 0 END)    AS total_ms_sum,
  CASE WHEN count_if(total_ms > 0) > 0
       THEN sum(CASE WHEN total_ms > 0 THEN total_ms ELSE 0 END) * 1.0
            / count_if(total_ms > 0)
  END                                                     AS total_ms_avg,
  quantile_cont(0.50)(CASE WHEN total_ms > 0 THEN total_ms END) AS total_ms_p50,
  quantile_cont(0.95)(CASE WHEN total_ms > 0 THEN total_ms END) AS total_ms_p95,
  count_if(result_flag = 'failure' AND (request_ms IS NULL OR request_ms <= 0)) AS failure_missing_ms,
  now()
FROM mapped
GROUP BY dt_bj, translation_service, model_label, model_group, real_model;


-- =============================================================================
-- §4 日更 TASK
-- · 每天重跑近 3 个完整北京日：容忍埋点迟到回填，无需人工补数
-- · P028 多语句必须 AS BEGIN … END;（裸 DELETE; INSERT 会让生产只留 DELETE）
-- · P035 cron 六段含秒；上游是 user_behaviour 原始埋点，无上游调度依赖
-- · 每天 07:30 北京（此时昨日数据已完整）
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
      ex_int_arg3                                AS request_ms,
      ex_int_arg2                                AS total_ms
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
      COALESCE(d.model_group, 'unknown')                           AS model_group,
      COALESCE(d.real_model, '[未映射] ' || s.translation_service)  AS model_label,
      s.result_flag,
      s.failure_reason,
      s.request_ms,
      s.total_ms
    FROM src s
    LEFT JOIN immdata.imm_translate_model_map d
      ON d.translation_service = s.translation_service
  )
  SELECT
    dt_bj,
    translation_service,
    model_label,
    model_group,
    real_model,
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
    count_if(total_ms > 0),
    sum(CASE WHEN total_ms > 0 THEN total_ms ELSE 0 END),
    CASE WHEN count_if(total_ms > 0) > 0
         THEN sum(CASE WHEN total_ms > 0 THEN total_ms ELSE 0 END) * 1.0
              / count_if(total_ms > 0)
    END,
    quantile_cont(0.50)(CASE WHEN total_ms > 0 THEN total_ms END),
    quantile_cont(0.95)(CASE WHEN total_ms > 0 THEN total_ms END),
    count_if(result_flag = 'failure' AND (request_ms IS NULL OR request_ms <= 0)),
    now()
  FROM mapped
  GROUP BY dt_bj, translation_service, model_label, model_group, real_model;
END;

ALTER TASK update_imm_translate_model_daily_perf RESUME;


-- =============================================================================
-- §5 验收（只读，写仓同学跑完后执行对照）
-- =============================================================================

-- §5.1 新鲜度：max(dt_bj) 应 = 昨日北京日
-- SELECT max(dt_bj) AS max_day, count(DISTINCT dt_bj) AS days, count(*) AS rows
-- FROM immdata.imm_translate_model_daily_perf;

-- §5.2 grain 唯一：cnt 必须 = dist（否则整套再重跑）
-- SELECT count(*) AS cnt,
--   count(DISTINCT concat(cast(dt_bj AS string), '|', translation_service)) AS dist
-- FROM immdata.imm_translate_model_daily_perf;

-- §5.3 抽日对账（P019/P027/P030）：日表 SUM(events) 必须 = 直查 user_behaviour 行数，ratio≈1.000
-- 拿 2026-10-19、2026-10-20 两天各对一次：
-- SELECT sum(events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-19';
-- SELECT count(*) FROM immdata.user_behaviour
-- WHERE created_ts >= add_hours(to_date('2026-10-19'), -8)
--   AND created_ts <  add_hours(to_date('2026-10-20'), -8)
--   AND event_name = 'track_translate_page_data';
-- failure 同理：
-- SELECT sum(failure_events) FROM immdata.imm_translate_model_daily_perf WHERE dt_bj = '2026-10-19';
-- SELECT count_if(ex_char_arg2 = 'failure') FROM immdata.user_behaviour
-- WHERE created_ts >= add_hours(to_date('2026-10-19'), -8)
--   AND created_ts <  add_hours(to_date('2026-10-20'), -8)
--   AND event_name = 'track_translate_page_data';

-- §5.4 模型改名后的回填（改完 dim 表跑这段，勿跑全文）：
-- DELETE FROM immdata.imm_translate_model_daily_perf
-- WHERE dt_bj >= to_date('起始日') AND dt_bj <= to_date('结束日');
--   → 再把 §3 的 INSERT 拿过来改时间边界重跑该区间即可

-- §5.5 TASK 体检（P028）：definition 里必须同时见到 DELETE 和 INSERT
-- SHOW TASKS LIKE 'update_imm_translate_model_daily_perf';
;
