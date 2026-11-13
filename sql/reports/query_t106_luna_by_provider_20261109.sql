-- T106 | 2026-11-09 | 全供应商 luna 逐月用量与输入输出比
-- 需求：用户澄清 T105 的真实意图 —— 之前把 UCloud 流量切走了，我方平均输入输出比 0.2~0.25，
--       想确认「其他供应商的 luna 模型是否也有 8 月 UCloud 账单 0.6087 的 3 倍问题」。
-- 与 T105 的关键差别：T105 限 providername='UCloud'；本次**不限供应商**，按 provider × 北京月 × 模型拆开。
-- ⚠️ WHERE 只用粗 UTC timestamp 保分区裁剪；北京月切分放 SELECT 表达式里。
-- ⚠️ luna 用 lower(actualresourceid) LIKE '%luna%'，覆盖 gpt-5.6-luna / gpt-6-luna 两代。

-- Q1 各供应商 luna 逐月（含 recordtype，本窗实测全部为 capture）
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       coalesce(providername,'(NULL)')              AS provider,
       coalesce(actualresourceid,'(NULL)')          AS model,
       coalesce(recordtype,'(NULL)')                AS rtype,
       count(*)                                    AS n_rows,
       SUM(inputusage)                             AS inp,
       SUM(outputusage)                            AS outp
FROM immdata.token_used_aw
WHERE timestamp >= '2025-12-31 16:00:00'   -- 北京 2026-01-01（实测 luna 自 8/5 才有量）
  AND timestamp  < '2026-11-10 16:00:00'
  AND lower(actualresourceid) LIKE '%luna%'
GROUP BY bj_month, provider, model, rtype
ORDER BY bj_month, provider, model, rtype;

-- Q2 全模型基线：各供应商 × 月 的总 input/output，用于验证「平均 0.2~0.25」并算 luna 份额
--    基线计算时排除 output 恒 0 的 DeepL-LB / DeepL-Pro / Internal / Unknown（非 LLM 通道，只记 input）
SELECT to_char(date_add(hour,8,timestamp),'YYYY-MM') AS bj_month,
       coalesce(providername,'(NULL)')              AS provider,
       count(*)                                    AS n_rows,
       SUM(inputusage)                             AS inp,
       SUM(outputusage)                            AS outp
FROM immdata.token_used_aw
WHERE timestamp >= '2025-12-31 16:00:00'
  AND timestamp  < '2026-11-10 16:00:00'
  AND recordtype = 'capture'
GROUP BY bj_month, provider
ORDER BY bj_month, provider;

-- 结果摘要（2026-11-09 实跑，out/in = SUM(output)/SUM(input)）
-- 逐月 luna 总量：8月 162.29亿in/32.86亿out=0.2025 | 9月 202.88/46.14=0.2274
--                10月 209.89/57.16=0.2723 | 11月(至11/09) 50.24/14.57=0.2900
-- 全模型 LLM 基线：0.2059 / 0.2281 / 0.2717 / 0.2823 —— 与 luna 几乎重合（差 -0.0034~+0.0077）
-- 8 月同模型跨供应商：UCloud 我方 0.2022 | OneRouter 0.1967 | OpenRouter 0.2353
--                     UCloud【账单】0.6087 = 基线的 2.96 倍（唯一异常）
-- 10 月：OneRouter 0.2839 / OpenAI 0.2783 / UCloud 0.2530；11 月：0.2930 / 0.2825 / 0.2813
-- UCloud 占 luna input 份额：93.4% → 15.8% → 35.2% → 8.3%
-- 结论：luna 模型本身没有 3 倍问题，各家一致且等于全平台平均；0.6087 是 UCloud 账单侧独有。
-- 限制：本地无 OneRouter/OpenAI 对账单，只能证明模型侧正常，不能证明它们账单也正常。
