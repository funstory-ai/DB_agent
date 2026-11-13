-- T105 | 2026-11-09 | 逐月 luna 输入输出比 + 账单侧 output 多计损失
-- 我方权威账本 immdata.token_used_aw；与 UCloud 账单 out/in 对照。
-- 口径：providername='UCloud' AND recordtype='capture'；北京日 = date_add(hour,8,timestamp)。
-- ⚠️ WHERE 只用粗 UTC timestamp 保分区裁剪，绝不在 WHERE 里写 to_date(date_add(...))（全表扫被 kill）。
-- ⚠️ 「服务」= productline；providername 是上游供应商。cachedinputusage 恒 0（已折进 inputusage），不参与 out/in。
-- 供应商侧账单解析见 scripts/_t105_supplier.py；对照与金额折算见 scripts/_t105_report.py。

-- Q1 逐北京月 × UCloud 模型（含 luna 两代与其它对照模型）
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       actualresourceid                              AS model,
       count(*)                                      AS n_rows,
       SUM(inputusage)                               AS inp,
       SUM(cachedinputusage)                         AS cinp,
       SUM(outputusage)                              AS outp
FROM immdata.token_used_aw
WHERE providername = 'UCloud'
  AND recordtype   = 'capture'
  AND timestamp   >= '2026-05-31 16:00:00'   -- 北京 2026-06-01 00:00
  AND timestamp    < '2026-11-10 16:00:00'   -- 北京 2026-11-11 00:00（查询日 11-09，留余量）
GROUP BY bj_month, model
ORDER BY bj_month, model;

-- Q2 luna 逐北京日（与账单小时桶按日对齐，避免账期/自然月错配）
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM-DD') AS bj,
       actualresourceid                                 AS model,
       count(*)                                        AS n_rows,
       SUM(inputusage)                                 AS inp,
       SUM(outputusage)                                AS outp
FROM immdata.token_used_aw
WHERE providername = 'UCloud'
  AND recordtype   = 'capture'
  AND timestamp   >= '2026-07-31 16:00:00'
  AND timestamp    < '2026-11-10 16:00:00'
  AND lower(actualresourceid) LIKE '%luna%'
GROUP BY bj, model
ORDER BY bj, model;

-- 结果摘要（2026-11-09 实跑）
-- 我方 luna out/in：8月 0.2022 (gpt-5.6-luna) | 9月 0.2383 | 10月 0.2530 | 11月(至11/09) 0.2813 (gpt-6-luna)
-- 账单 8月 luna out/in = 0.6087（我方 3.01 倍），input 151.79亿 vs 151.62亿 仅差 0.11%
-- 8月 output 差额 61.73亿 token × $0.9604/百万 = $5,928.69 多计（≈¥42,094）
-- 星图 10/06~11/05 同窗口差额 2.06亿 × $0.3800/百万 = $78.15
-- 累计已证实 $6,006.83 ≈ ¥42,649；9 月账单缺失未计入
