-- Funstory 2026-08 vs token_used_aw（UCloud）
-- 账单：Funstory.ai Limited 8月份账单（20260801-20260901）.xlsx
-- 账期 UTC+8：对齐 AW 窗 [2026-07-31 16:00, 2026-08-31 16:00)
-- 折后单价（USD / 1M tokens，取自订单汇总主计费单元）：
--   gpt-5.6-luna  in 0.16 / out 0.96
--   gpt-5.6-terra in 1.6  / out 9.6
--   gpt-5.4       in 1.5  / out 9.0
--   gpt-5-mini    in 0.15 / out 1.2

-- 1) 主模型用量 + 折后估价（北京对齐窗）
SELECT
  actualresourceid,
  resourcename,
  sum(inputusage) AS aw_in,
  sum(cachedinputusage) AS aw_cache,
  sum(outputusage) AS aw_out,
  count(*) AS aw_rows,
  CASE actualresourceid
    WHEN 'gpt-5.6-luna' THEN sum(inputusage) / 1e6 * 0.16 + sum(outputusage) / 1e6 * 0.96
    WHEN 'gpt-5.6-terra' THEN sum(inputusage) / 1e6 * 1.6 + sum(outputusage) / 1e6 * 9.6
    WHEN 'gpt-5.4' THEN sum(inputusage) / 1e6 * 1.5 + sum(outputusage) / 1e6 * 9
    WHEN 'gpt-5-mini' THEN sum(inputusage) / 1e6 * 0.15 + sum(outputusage) / 1e6 * 1.2
    ELSE NULL
  END AS aw_usd_est
FROM immdata.token_used_aw
WHERE timestamp >= '2026-07-31 16:00:00'
  AND timestamp < '2026-08-31 16:00:00'
  AND recordtype = 'capture'
  AND providername = 'UCloud'
  AND actualresourceid IN ('gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.4', 'gpt-5-mini')
GROUP BY 1, 2
ORDER BY 1;

-- 账单对照（现金）：luna 11326.65 / terra 2019.56 / gpt-5.4 509.12（含中台） / mini 14.50
-- 实测：luna input≈账单、output≈账单 1/3；terra 差~7%；gpt-5.4 AW 仅覆盖 aw-测试 Key

-- 2) gpt-5.6-luna 按日（看 output 缺口是否全日性）
SELECT
  to_date(date_add(hour, 8, timestamp)) AS d_bj,
  sum(inputusage) AS aw_in,
  sum(outputusage) AS aw_out,
  sum(outputusage) * 1.0 / nullif(sum(inputusage), 0) AS out_in_ratio
FROM immdata.token_used_aw
WHERE timestamp >= '2026-07-31 16:00:00'
  AND timestamp < '2026-08-31 16:00:00'
  AND recordtype = 'capture'
  AND providername = 'UCloud'
  AND actualresourceid = 'gpt-5.6-luna'
GROUP BY 1
ORDER BY 1;
