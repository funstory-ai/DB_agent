-- T067 登录赠 token 误发全员：10 号前后模型日消耗
-- 主表：immdata.token_used_aw；recordtype=capture
-- 北京自然日：timestamp 为 UTC，日标签 = to_date(date_add(hour, 8, timestamp))
-- 窗：北京 2026-10-03 00:00 ～ 2026-10-13 00:00（含 10-12；不含未结束的 10-13）
-- 注意：UTC 日 2026-10-06、2026-10-10 整段 0 行（未同步，不是用量变少）
-- 反映到北京日：6 日 08:00 后、7 日 00:00-08:00、10 日 08:00 后、11 日 00:00-08:00 都缺
-- token = inputusage + outputusage
-- 赠送试用（简中）落在 resourcename='auto' AND actualresourceid='babelfast'
-- 任务：docs/tasks/query_gift_token_model_daily_20261013.md

SELECT
  to_date(date_add(hour, 8, timestamp)) AS d_bj,
  resourcename,
  actualresourceid,
  sum(coalesce(inputusage, 0)) AS input_tokens,
  sum(coalesce(outputusage, 0)) AS output_tokens,
  sum(coalesce(inputusage, 0) + coalesce(outputusage, 0)) AS tokens,
  count(DISTINCT userid) AS users_n,
  count(*) AS rows_n
FROM immdata.token_used_aw
WHERE timestamp >= '2026-10-02 16:00:00'
  AND timestamp < '2026-10-12 16:00:00'
  AND recordtype = 'capture'
GROUP BY 1, 2, 3
ORDER BY 1, tokens DESC;
