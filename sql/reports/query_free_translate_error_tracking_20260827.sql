-- 探查：free-model 网页翻译失败原因分布（track_translate_page_data）
-- 任务：docs/tasks/query_free_translate_error_tracking_20260827.md
-- 短窗示例；正式分析请收窄 created_ts

SELECT
  ex_char_arg1 AS translation_service,
  ex_char_arg2 AS first_visible_result,
  ex_char_arg4 AS failure_code,
  ex_char_arg5 AS failure_reason,
  ex_char_arg6 AS failure_stage,
  count(*) AS cnt
FROM immdata.user_behaviour
WHERE created_ts >= '2026-08-20'
  AND created_ts < '2026-08-27'
  AND event_name = 'track_translate_page_data'
  AND ex_char_arg1 = 'free-model'
  AND ex_char_arg2 = 'failure'
GROUP BY 1, 2, 3, 4, 5
ORDER BY cnt DESC;

-- 网络 vs 服务粗分（陈琦口径参考）
-- network → 国内端点兜底；service/provider → 谷歌/服务兜底
