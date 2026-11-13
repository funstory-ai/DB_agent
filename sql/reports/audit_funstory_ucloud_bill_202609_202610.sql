-- T110  Funstory (推文) UCloud 9月/10月账单 vs AW 对账
-- 我方权威记录：token_used_aw，UCloud capture，按北京日聚合 input/output/cache
-- 粗 UTC 窗 [2026-08-30, 2026-11-01) 保分区裁剪；北京日 = date_add(hour,8,timestamp)
-- 9 月账单(明细 08-31~09-30 UTC+8) -> 北京月 2026-09；10 月账单(09-30~10-31) -> 北京月 2026-10
SELECT
  to_date(date_add(hour, 8, timestamp))                          AS bj_date,
  actualresourceid                                             AS model,
  SUM(inputusage)                                              AS inp,
  SUM(outputusage)                                             AS outp,
  SUM(cachedinputusage)                                        AS cache_in,
  COUNT(*)                                                     AS n_rows
FROM immdata.token_used_aw
WHERE providername = 'UCloud'
  AND recordtype  = 'capture'
  AND timestamp  >= '2026-08-30 00:00:00'
  AND timestamp  <  '2026-11-01 00:00:00'
GROUP BY bj_date, model
ORDER BY bj_date, outp DESC;
