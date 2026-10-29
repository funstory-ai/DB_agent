-- T094 单用户月度 token 消耗：kjzkg84ctb@privaterelay.appleid.com (userid=609408)
-- 口径：用户选定「每月 token 消耗量」。主体 = imt_userinfo.id = 609408（账号级，非设备）。
-- 数据来源：token_used_aw（明细，≈2026-03-02 起有数）/ imm_token_used（日汇总，≈2025-09-30 起有数）。
-- 成功扣费行：recordtype='capture'；token = inputusage + outputusage。
-- 注：本账号在两表均为 0 行（见下方验证）；下表按月汇总，2026-01-27 起。

-- 0) 全局零值确认（无时间过滤）
SELECT 'token_used_aw' AS src, count(*) AS n
FROM immdata.token_used_aw WHERE userid = 609408
UNION ALL
SELECT 'imm_token_used' AS src, count(*) AS n
FROM immdata.imm_token_used WHERE userid = 609408;

-- 1) 按月 token 消耗（明细表，2026-01-27 起）
SELECT
  to_char(timestamp, '%Y-%m') AS month,
  count(*) AS n_records,
  sum(coalesce(inputusage,0) + coalesce(outputusage,0)) AS tokens
FROM immdata.token_used_aw
WHERE userid = 609408
  AND timestamp >= '2026-01-27 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 2) 同口径日汇总表（2026-01-27 起）
SELECT
  to_char(dates, '%Y-%m') AS month,
  count(*) AS n_days,
  sum(coalesce(openai,0)+coalesce(deepl,0)+coalesce(deepseek,0)+coalesce(gemini,0)
     +coalesce(claude,0)+coalesce(bigmodel,0)+coalesce(babel_doc,0)+coalesce(qwen3,0)) AS tokens
FROM immdata.imm_token_used
WHERE userid = 609408
  AND dates >= '2026-01-27 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 3) 账号背景：订阅时间线（解释为何 token 近 0）
SELECT to_char(createtime, '%Y-%m-%d') AS pay_date, amountpaid, subscriptiontype, membership, membertype
FROM immdata.imt_subscriptiongoodsorder
WHERE userid = 609408 AND amountpaid > 0
ORDER BY createtime;
