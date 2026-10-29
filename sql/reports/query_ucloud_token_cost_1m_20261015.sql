-- T071 UCloud 近一个月 token 估成本
-- 主表: immdata.token_used_aw（docs/tables/immdata/token_used_aw.md）
-- 窗: 北京 [2026-09-15, 2026-10-16) = UTC timestamp [2026-09-14 16:00, 2026-10-15 16:00)
-- 过滤: providername='UCloud' AND recordtype='capture'
-- 单价 USD/1M，按 actualresourceid（勿 join tmp_model_price.resourcename）：
--   gpt-6-luna / gpt-6-sol / gpt-6.1-sol：OpenAI 短上下文标价 × 0.8
--     （8 月账单对 gpt-5.6-luna/terra 恰为标价 8 折：0.20→0.16，1.20→0.96，2→1.6，12→9.6）
--     标价：luna 0.10/0.50，sol 与 6.1-sol 2/10
--   gpt-5.6-luna 0.16/0.96，terra 1.6/9.6，gpt-5.4 1.5/9，gpt-5-mini 0.15/1.2（8 月账单）
--   kimi-k2.6 等无 UCloud 账单价，usd_est 留空
-- 已知: 8 月 gpt-5.6-luna output 约为账单的 1/3（T042/T059）；本结果是 AW 估成本

SELECT
  actualresourceid,
  resourcename,
  sum(inputusage) AS in_tok,
  sum(cachedinputusage) AS cache_tok,
  sum(outputusage) AS out_tok,
  count(*) AS n_rows,
  CASE actualresourceid
    WHEN 'gpt-6-luna' THEN sum(inputusage) / 1e6 * 0.08 + sum(outputusage) / 1e6 * 0.40
    WHEN 'gpt-6-sol' THEN sum(inputusage) / 1e6 * 1.60 + sum(outputusage) / 1e6 * 8.00
    WHEN 'gpt-6.1-sol' THEN sum(inputusage) / 1e6 * 1.60 + sum(outputusage) / 1e6 * 8.00
    WHEN 'gpt-5.6-luna' THEN sum(inputusage) / 1e6 * 0.16 + sum(outputusage) / 1e6 * 0.96
    WHEN 'gpt-5.6-terra' THEN sum(inputusage) / 1e6 * 1.6 + sum(outputusage) / 1e6 * 9.6
    WHEN 'gpt-5.4' THEN sum(inputusage) / 1e6 * 1.5 + sum(outputusage) / 1e6 * 9
    WHEN 'gpt-5-mini' THEN sum(inputusage) / 1e6 * 0.15 + sum(outputusage) / 1e6 * 1.2
    ELSE NULL
  END AS usd_est
FROM immdata.token_used_aw
WHERE timestamp >= '2026-09-14 16:00:00'
  AND timestamp < '2026-10-15 16:00:00'
  AND recordtype = 'capture'
  AND providername = 'UCloud'
GROUP BY 1, 2
ORDER BY in_tok + out_tok DESC;
