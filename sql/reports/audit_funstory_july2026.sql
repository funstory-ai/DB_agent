-- Funstory 2026-07 vs token_used_aw（UCloud / AW翻译Key 主对账）
-- 账单：Funstory.ai Limited 7月份账单（20260701-20260801）.xlsx
-- 单价：gpt-5-mini 0.15/1.2；gpt-5.4 1.5/9（USD per 1M tokens）

-- 1) gpt-5.4 UCloud（AW翻译路径主缺口）
SELECT
  sum(inputusage) AS aw_in,
  sum(outputusage) AS aw_out,
  count(*) AS aw_rows,
  sum(inputusage) / 1e6 * 1.5 + sum(outputusage) / 1e6 * 9 AS aw_usd_est
FROM immdata.token_used_aw
WHERE timestamp >= '2026-07-01' AND timestamp < '2026-08-01'
  AND recordtype = 'capture'
  AND resourcename = 'openai_gpt_41'
  AND actualresourceid = 'gpt-5.4'
  AND providername = 'UCloud';
-- 2026-07 实测：aw_usd_est ≈ 2023.25；Funstory AW Key 账单 ≈ 2229.52；缺口 ≈ 206（~9.3%）

-- 2) gpt-5-mini UCloud（AW翻译Key，基本对齐）
SELECT
  sum(inputusage) AS aw_in,
  sum(outputusage) AS aw_out,
  count(*) AS aw_rows,
  sum(inputusage) / 1e6 * 0.15 + sum(outputusage) / 1e6 * 1.2 AS aw_usd_est
FROM immdata.token_used_aw
WHERE timestamp >= '2026-07-01' AND timestamp < '2026-08-01'
  AND recordtype = 'capture'
  AND resourcename = 'openai'
  AND providername = 'UCloud';
-- 2026-07 实测：aw_usd_est ≈ 6524.86；Funstory AW Key 账单 ≈ 6631.01；缺口 ≈ 106（~1.6%）

-- 3) gpt-5.4 按日（对照 Funstory 明细「交易生效时间 UTC+8」的 date）
SELECT
  date(timestamp) AS d,
  sum(inputusage) / 1e6 AS aw_in_M,
  sum(outputusage) / 1e6 AS aw_out_M,
  count(*) AS aw_rows,
  sum(inputusage) / 1e6 * 1.5 + sum(outputusage) / 1e6 * 9 AS aw_usd_est
FROM immdata.token_used_aw
WHERE timestamp >= '2026-07-01' AND timestamp < '2026-08-01'
  AND recordtype = 'capture'
  AND resourcename = 'openai_gpt_41'
  AND actualresourceid = 'gpt-5.4'
  AND providername = 'UCloud'
GROUP BY 1
ORDER BY 1;
