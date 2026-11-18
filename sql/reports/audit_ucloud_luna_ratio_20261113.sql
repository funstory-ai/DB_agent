-- T115  UCloud luna 8/9/10 月异常占比与倍率一致性核对 —— 抽样 SQL
-- 用途：① 复核 9/10 月 luna 逐日真实用量与「打满 max_tokens」分布；② 按北京月对拍 T105 月合计
-- 我方：immdata.token_used_aw，UCloud capture；北京日 = date_add(hour,8,timestamp)
-- 粗 UTC 窗 [2026-08-31 16:00, 2026-11-01 16:00) 对应北京 2026-09-01 ~ 2026-11-01，保分区裁剪
-- 8 月不重跑全量（沿用 T105/T106 已验收结果）；账单侧逐日形态见任务文档「抽样复核」

-- @Q_DAILY  逐日请求数 / input / output / 单请求上限分布
SELECT
  to_date(date_add(hour, 8, timestamp))                              AS bj_date,
  actualresourceid                                                   AS model,
  COUNT(*)                                                           AS n_rows,
  SUM(inputusage)                                                    AS inp,
  SUM(outputusage)                                                   AS outp,
  MAX(outputusage)                                                   AS max_out,
  SUM(CASE WHEN outputusage >= 65536  THEN 1 ELSE 0 END)            AS n_ge65536,
  SUM(CASE WHEN outputusage >= 128000 THEN 1 ELSE 0 END)            AS n_ge128000
FROM immdata.token_used_aw
WHERE providername = 'UCloud'
  AND recordtype  = 'capture'
  AND timestamp  >= '2026-08-31 16:00:00'
  AND timestamp  <  '2026-11-01 16:00:00'
  AND actualresourceid IN ('gpt-5.6-luna', 'gpt-6-luna')
GROUP BY bj_date, model
ORDER BY bj_date, model;

-- @Q_MONTH  按北京月对拍 output/_t105_db_monthly.csv 的 9/10 月 luna 合计（P044）
SELECT
  substr(to_string(date_add(hour, 8, timestamp)), 1, 7)              AS bj_month,
  actualresourceid                                                   AS model,
  COUNT(*)                                                           AS n_rows,
  SUM(inputusage)                                                    AS inp,
  SUM(outputusage)                                                   AS outp
FROM immdata.token_used_aw
WHERE providername = 'UCloud'
  AND recordtype  = 'capture'
  AND timestamp  >= '2026-08-31 16:00:00'
  AND timestamp  <  '2026-11-01 16:00:00'
  AND actualresourceid IN ('gpt-5.6-luna', 'gpt-6-luna')
GROUP BY bj_month, model
ORDER BY bj_month, model;
