-- chenghuili19991115@gmail.com (userid=626306)
-- DeepSeek 明细：2026-08-22 ~ 2026-08-24
-- 表：immdata.token_used_aw；resourcename='deepseek'

SELECT
  timestamp,
  userid,
  providername,
  productline,
  categoryname,
  resourcename,
  actualresourceid,
  recordtype,
  usageunit,
  coalesce(inputusage, 0) AS inputusage,
  coalesce(cachedinputusage, 0) AS cachedinputusage,
  coalesce(outputusage, 0) AS outputusage,
  coalesce(inputusage, 0) + coalesce(cachedinputusage, 0) + coalesce(outputusage, 0) AS total_tokens,
  delta,
  businessid,
  actionid,
  clientip
FROM immdata.token_used_aw
WHERE userid = 626306
  AND resourcename = 'deepseek'
  AND timestamp >= '2026-08-22'
  AND timestamp < '2026-08-25'
ORDER BY timestamp;
