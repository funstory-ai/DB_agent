-- T081 UCloud 各模型明细（北京 2026-07-01..2026-10-22）
-- 主表: immdata.token_used_aw
-- 过滤: providername='UCloud' AND recordtype='capture'
-- 时间: 北京 [2026-07-01, 2026-10-23)  ->  timestamp UTC ['2026-06-30 16:00','2026-10-23 16:00')
--       取数按 to_date(date_add(hour,8,timestamp)) 归北京日；2026-10-22 为查询当日，不完整
-- 粒度: 北京日 × actualresourceid（真实模型）；resourcename 一并带出
-- 脱敏: 仅聚合 token 计数，不含任何 userid/设备号/IP/业务单号；可直接对外给供应商
-- 不含金额估算（仅 input/output）
-- 产物: output/ucloud_model_detail_202607_20261022.xlsx（汇总 / 按日明细 / 说明 三表）

SELECT
  to_date(date_add(hour, 8, timestamp))           AS bj_date,
  actualresourceid,
  resourcename,
  sum(inputusage)        AS in_tok,
  sum(cachedinputusage)  AS cache_tok,
  sum(outputusage)       AS out_tok,
  count(*)               AS n_rows
FROM immdata.token_used_aw
WHERE timestamp >= '2026-06-30 16:00:00'
  AND timestamp <  '2026-10-23 16:00:00'
  AND recordtype = 'capture'
  AND providername = 'UCloud'
  AND to_date(date_add(hour, 8, timestamp)) >= '2026-07-01'
  AND to_date(date_add(hour, 8, timestamp)) <= '2026-10-22'
GROUP BY 1, 2, 3
ORDER BY 1, 2;
