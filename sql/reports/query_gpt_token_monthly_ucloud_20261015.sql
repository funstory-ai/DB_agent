-- T073 GPT token：含 UCloud / 不含 UCloud
-- 主表: immdata.token_used_aw
-- GPT: actualresourceid LIKE 'gpt-%'（连字符是字面量；% 才是通配）
-- 窗: 北京 [2025-01-01, 2026-10-16) = UTC [2024-12-31 16:00, 2026-10-15 16:00)
-- 早于有数的月份不会出行。10 月只到查询日。
-- 10 月只到查询日。capture only。按日输出，月汇总在本地加总。

SELECT
  to_date(date_add(hour, 8, timestamp)) AS d_bj,
  providername,
  sum(inputusage) AS in_tok,
  sum(outputusage) AS out_tok
FROM immdata.token_used_aw
WHERE timestamp >= '2024-12-31 16:00:00'
  AND timestamp < '2026-10-15 16:00:00'
  AND recordtype = 'capture'
  AND actualresourceid LIKE 'gpt-%'
GROUP BY 1, 2
ORDER BY 1, 2;
