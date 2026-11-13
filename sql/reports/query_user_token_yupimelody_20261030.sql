-- T096 单用户额度消耗分析：yupimelody24@gmail.com (userid=6515557)
-- 窗口 2026-10-22 ~ 2026-10-30（10-30 当日明细尚未同步，截至 10-30 16:09 无 10-30 数据）。
-- 口径：账号级主体 P018-D；额度消耗 = token_used_aw inputusage+outputusage，扣费行 recordtype='capture'。
-- 日序列以 imm_token_used（日汇总，较完整、已回补 10-26）为准；token_used_aw 作交叉校验。
-- 关键校准：token_used_aw（百亿级明细）对 10-26 存在 ETL 滞后缺失，日汇总 imm_token_used 有该日 0.93M，故无真实断更。

-- 0) 账号定位（email 在订单/设备表，订单与设备一致指向 6515557）
SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') AS createtime, isdeleted
FROM immdata.imt_userinfo WHERE id = 6515557;

SELECT userid, useremail, amountpaid, subscriptiontype, membership, to_char(createtime,'%Y-%m-%d') AS d
FROM immdata.imt_subscriptiongoodsorder WHERE useremail = 'yupimelody24@gmail.com' ORDER BY createtime;

-- 1) 日消耗（imm_token_used 日汇总，主序列）
SELECT to_char(dates,'%Y-%m-%d') AS day,
  coalesce(openai,0)+coalesce(deepl,0)+coalesce(deepseek,0)+coalesce(gemini,0)
 +coalesce(claude,0)+coalesce(bigmodel,0)+coalesce(babel_doc,0)+coalesce(qwen3,0)
 +coalesce(doubao,0)+coalesce(pics,0)+coalesce(asr_audio,0)+coalesce(comics,0)
 +coalesce(math_pix,0)+coalesce(openai_gpt_41,0)+coalesce(gemini_25_pro_preview,0)
 +coalesce(claude4,0)+coalesce(novice_ai,0)+coalesce(qwen_plus,0)+coalesce(kimi_k2_0905,0)
 +coalesce(bigmodel45air,0)+coalesce(novice_pro_pdf,0)+coalesce(novice_asr_audio,0) AS tok
FROM immdata.imm_token_used
WHERE userid = 6515557 AND dates >= '2026-10-22' AND dates < '2026-10-31'
ORDER BY 1;

-- 2) 日消耗交叉校验（token_used_aw 明细，对时间列范围过滤）
SELECT to_char(timestamp,'%Y-%m-%d') AS day, count(*) AS n,
  sum(coalesce(inputusage,0)) AS inp, sum(coalesce(outputusage,0)) AS outp,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture'
GROUP BY 1 ORDER BY 1;

-- 3) 按模型 Provider / 产品线
SELECT providername, count(*) AS n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture'
GROUP BY 1 ORDER BY tok DESC;

SELECT productline, categoryname, count(*) AS n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture'
GROUP BY 1,2 ORDER BY tok DESC;

-- 4) 时段分布 + 请求体量（判自动化）
SELECT to_char(timestamp,'%H') AS hr, count(*) AS n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture'
GROUP BY 1 ORDER BY 1;

SELECT count(*) AS n, round(avg(coalesce(inputusage,0)+coalesce(outputusage,0)),0) AS avg_tok,
  max(coalesce(inputusage,0)+coalesce(outputusage,0)) AS max_tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture';

-- 5) 对比基准（窗口内全量活跃用户）
SELECT count(DISTINCT userid) AS active_users,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS total_tok
FROM immdata.token_used_aw
WHERE timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00' AND recordtype = 'capture';

WITH u AS (
  SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
  FROM immdata.token_used_aw
  WHERE timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00' AND recordtype = 'capture'
  GROUP BY 1)
SELECT count(*) AS users_ge FROM u WHERE tok >= (SELECT tok FROM u WHERE userid = 6515557);

-- ============================================================================
-- 6) 额度归属（权威口径，来自 AW 账单 token_used_aw.countername）
--    user_subs_ai_token_used_count_v2 = Pro 月订阅 AI 额度；user_ai_package_used_count = 买的流量包
--    直接回答「扣的是 Pro 还是流量包」——这是初版漏看的归属列。
-- ============================================================================

-- 6a) 窗口 10/22-10/30 内按计数器（归属）拆分
SELECT countername, count(*) AS n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok
FROM immdata.token_used_aw
WHERE userid = 6515557 AND timestamp >= '2026-10-22 00:00:00' AND timestamp < '2026-10-31 00:00:00'
  AND recordtype = 'capture'
GROUP BY 1 ORDER BY tok DESC;

-- 6b) 10 月按日 归属切换点（可见 10/20 由 Pro 月额度切到流量包）
SELECT to_char(timestamp,'%Y-%m-%d') AS day,
  sum(CASE WHEN countername='user_subs_ai_token_used_count_v2' THEN coalesce(inputusage,0)+coalesce(outputusage,0) ELSE 0 END) AS subs_ai_tok,
  sum(CASE WHEN countername='user_ai_package_used_count'       THEN coalesce(inputusage,0)+coalesce(outputusage,0) ELSE 0 END) AS pkg_ai_tok,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS total_tok,
  count(*) AS n
FROM immdata.token_used_aw
WHERE userid = 6515557 AND recordtype='capture'
  AND timestamp >= '2026-10-01' AND timestamp < '2026-11-01'
GROUP BY 1 ORDER BY 1;

-- 6c) 全账号历史全部计数器（确认 Pro 月额度 6/26-10/20 有量、10/20 后停）
SELECT countername, count(*) AS n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) AS tok,
  min(to_char(timestamp,'%Y-%m-%d')) AS first_d, max(to_char(timestamp,'%Y-%m-%d')) AS last_d,
  count(DISTINCT to_char(timestamp,'%Y-%m-%d')) AS active_days
FROM immdata.token_used_aw
WHERE userid = 6515557 AND recordtype='capture'
GROUP BY 1 ORDER BY first_d;

-- 6d) 系统性排查：全局 Pro 月额度计数器 10/15-10/25 是否也下降（若否，则为本账号额度耗尽，非全站故障）
SELECT to_char(timestamp,'%Y-%m-%d') AS day,
  sum(CASE WHEN countername='user_subs_ai_token_used_count_v2' THEN 1 ELSE 0 END) AS subs_rows,
  count(DISTINCT CASE WHEN countername='user_subs_ai_token_used_count_v2' THEN userid END) AS subs_users
FROM immdata.token_used_aw
WHERE recordtype='capture' AND countername='user_subs_ai_token_used_count_v2'
  AND timestamp >= '2026-10-15' AND timestamp < '2026-10-26'
GROUP BY 1 ORDER BY 1;

-- 6e) 订阅/套餐（确认 10/02 续费 finished、覆盖到 ~11/02；两包 OpenAITokenQuota）
SELECT to_char(createtime,'%Y-%m-%d %H:%M') AS d, subscriptiontype, membership, orderstatus,
  ordertype, amountpaid, subscriptionday,
  substring(subscriptiongoodssnap, position('OpenAITokenQuota' in subscriptiongoodssnap), 40) AS snap_quota
FROM immdata.imt_subscriptiongoodsorder
WHERE userid = 6515557 AND COALESCE(isdeleted,0)=0 ORDER BY createtime;

