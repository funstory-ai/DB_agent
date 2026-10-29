-- T080 看板预览：按「真实模型」看翻译时长与报错率 —— 【仅探查·勿挂板】
-- 任务：docs/tasks/dashboard_translate_model_latency_error_20261021.md
--
-- 口径要点
--   1. 维度用【顶层 translation_service】（已归一化，69 值），不要用 ex_char_arg1（含随机后缀，22268 值）
--   2. 【禁止】用 WHERE ex_int_arg3>0 筛行：失败行缺耗时 5.35% vs 成功行 0.14%，
--      筛行会系统性漏失败样本、把报错率算低。改用条件聚合。
--   3. 翻译时长主指标 = ex_int_arg3（请求耗时，不含并发闸门/批次排队）；
--      ex_int_arg2 端到端含页面侧开销，作副指标。
--   4. 报错率分母 = 全量事件（success+failure），skip 因未上报不在内。
--
-- 模型映射来源：F:\extension default_config.json（commit 5ba7d8c / 2026-10-20，git pull 失败）
-- ⚠️ 该映射是「当前配置快照」，套到历史日会失真，待确认是否落 dim 表

SELECT
  CASE
    WHEN translation_service = 'openai-pro'        THEN 'gpt-6-luna'
    WHEN translation_service = 'openai-max'        THEN 'gpt-6.1-sol'
    WHEN translation_service = 'deepseek-pro'      THEN 'DeepSeek-V4.1-Flash'
    WHEN translation_service = 'gemini-pro'        THEN 'gemini-3-flash-preview'
    WHEN translation_service = 'gemini-max'        THEN 'gemini-3.1-pro-preview'
    WHEN translation_service = 'claude-pro'        THEN 'claude-haiku-5-5'
    WHEN translation_service = 'qwen-pro'          THEN 'qwen3.5-plus'
    WHEN translation_service = 'qwen-max'          THEN 'qwen3-max-preview'
    WHEN translation_service = 'zhipu-pro'         THEN 'GLM-4.7'
    WHEN translation_service = 'zhipu-air-pro'     THEN 'glm-4.5-air'
    WHEN translation_service = 'zhipu-max'         THEN 'glm-5.2'
    WHEN translation_service = 'zhipu-free'        THEN 'glm-4-flash-250414'
    WHEN translation_service = 'kimi-max'          THEN 'kimi-k2.6'
    WHEN translation_service = 'grok-pro'          THEN 'grok-4-3'
    WHEN translation_service = 'hunyuan-pro'       THEN 'hunyuan-2.0-instruct'
    WHEN translation_service = 'qwen-mt-pro'       THEN 'qwen-mt-plus'
    WHEN translation_service = 'plamo-pro'         THEN 'plamo-3.0-prime'
    WHEN translation_service = 'siliconcloud-free' THEN 'THUDM/GLM-4-9B-0414'
    WHEN translation_service = 'deepl-pro'         THEN 'DeepL(非LLM)'
    WHEN translation_service = 'babelfast-pro'     THEN 'babelfast(自研/无定义)'
    WHEN translation_service = 'claude-max'        THEN 'claude-max(无定义)'
    WHEN translation_service = 'trial-pro'         THEN 'trial(服务端注入/unknown)'
    WHEN translation_service = 'free-model'        THEN 'free-model(服务端混池)'
    WHEN translation_service = 'google-free'       THEN 'google-free(非LLM)'
    WHEN translation_service = 'bing-free'         THEN 'bing-free(非LLM)'
    ELSE '[未认领] ' || translation_service
  END AS real_model,
  translation_service,
  count(*) AS events,
  count_if(ex_char_arg2 = 'failure') AS failures,
  round(100.0 * count_if(ex_char_arg2 = 'failure') / count(*), 2) AS err_pct,
  count_if(ex_int_arg3 > 0) AS n_with_req_ms,
  round(quantile_cont(0.50)(CASE WHEN ex_int_arg3 > 0 THEN ex_int_arg3 END)) AS req_p50_ms,
  round(quantile_cont(0.95)(CASE WHEN ex_int_arg3 > 0 THEN ex_int_arg3 END)) AS req_p95_ms,
  round(quantile_cont(0.50)(CASE WHEN ex_int_arg2 > 0 THEN ex_int_arg2 END)) AS total_p50_ms
FROM immdata.user_behaviour
WHERE created_ts >= '2026-10-18' AND created_ts < '2026-10-21'
  AND event_name = 'track_translate_page_data'
  AND translation_service IN (
    'openai-pro','openai-max','deepseek-pro','gemini-pro','gemini-max',
    'claude-pro','claude-max','qwen-pro','qwen-max','zhipu-pro','zhipu-max',
    'zhipu-air-pro','kimi-max','grok-pro','hunyuan-pro','qwen-mt-pro','plamo-pro',
    'trial-pro','babelfast-pro','deepl-pro','openai-custom','deepseek-custom',
    'siliconcloud-free','zhipu-free','free-model','google-free','bing-free'
  )
GROUP BY 1, 2
ORDER BY events DESC
