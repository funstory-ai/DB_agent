-- T109 · 单用户额度使用核查
-- 主体: userid = 5339075 (email 70764498@qq.com 反查核对)
-- 窗口: 北京日 2026-10-06 ~ 2026-11-06 (含两端)
-- 粗 UTC 预过滤保分区裁剪: 北京日 D 00:00 = UTC D-1 16:00; 北京日 11-07 00:00 = UTC 11-06 16:00
-- 权威账本: immdata.token_used_aw; 额度归属看 countername

-- 1) email <-> userid 对应性核对
SELECT id, email, createtime
FROM immdata.imt_userinfo
WHERE id = 5339075 OR email = '70764498@qq.com';

SELECT useremail, userid
FROM immdata.imt_subscriptiongoodsorder
WHERE useremail = '70764498@qq.com' OR userid = 5339075
LIMIT 20;

SELECT useremail, userid, deviceid
FROM immdata.imt_deviceinfo
WHERE useremail = '70764498@qq.com' OR userid = 5339075
LIMIT 20;

-- 2) 窗口内额度消耗按天 × 额度类型明细
SELECT
  date(date_add(hour, 8, timestamp)) AS bj_day,
  countername,
  recordtype,
  COUNT(*)                              AS req_cnt,
  SUM(inputusage)                       AS input_tok,
  SUM(outputusage)                      AS output_tok,
  SUM(inputusage + outputusage)         AS total_tok
FROM immdata.token_used_aw
WHERE userid = 5339075
  AND timestamp >= '2026-10-05 16:00:00'
  AND timestamp <  '2026-11-06 16:00:00'
  AND date(date_add(hour, 8, timestamp)) BETWEEN '2026-10-06' AND '2026-11-06'
GROUP BY bj_day, countername, recordtype
ORDER BY bj_day, countername, recordtype;

-- 3) 窗口内按额度类型汇总
SELECT
  countername,
  COUNT(*)                      AS req_cnt,
  SUM(inputusage + outputusage) AS total_tok
FROM immdata.token_used_aw
WHERE userid = 5339075
  AND timestamp >= '2026-10-05 16:00:00'
  AND timestamp <  '2026-11-06 16:00:00'
  AND date(date_add(hour, 8, timestamp)) BETWEEN '2026-10-06' AND '2026-11-06'
GROUP BY countername
ORDER BY total_tok DESC;
