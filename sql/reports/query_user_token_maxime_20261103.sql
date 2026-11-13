-- T102 · 单用户功能使用 / EPUB 消费异常核查
-- 主体：maximefouquet33@gmail.com -> userid=7154600
-- 窗口：2026-09-01 ~ 2026-11-04（首次用量 9/26，数据截至 11/02）
-- 主表：immdata.token_used_aw（AW 账单，billing-ledger 落表）
-- 口径：recordtype='capture'；token=inputusage+outputusage；北京自然日 to_char(date_add(hour,8,timestamp),'%Y-%m-%d')
--       功能维度=productline；WHERE 用粗 UTC 范围保分区裁剪，日精度在 SELECT/GROUP BY 做
-- 复用脚本：scripts/export_user_token_maxime_20261103.py（产出 output/user_token_maxime_20261103.xlsx）

-- 0) 定位账号（email 在 imt_userinfo 命中；订单/设备表反查备用）
-- SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') ct, isdeleted
-- FROM immdata.imt_userinfo WHERE email='maximefouquet33@gmail.com';           -- -> 7154600
-- SELECT DISTINCT userid, count(*) n FROM immdata.imt_subscriptiongoodsorder WHERE useremail='maximefouquet33@gmail.com' GROUP BY 1;
-- SELECT DISTINCT userid, count(*) n FROM immdata.imt_deviceinfo WHERE useremail='maximefouquet33@gmail.com' GROUP BY 1;

-- 1) 账号画像 + 订阅/套餐
SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') ct, isdeleted
FROM immdata.imt_userinfo WHERE id=7154600;

SELECT to_char(createtime,'%Y-%m-%d %H:%M') d, subscriptiontype, membership,
  orderstatus, ordertype, amountpaid, subscriptionday,
  substring(subscriptiongoodssnap, position('OpenAITokenQuota' in subscriptiongoodssnap), 40) snap_quota
FROM immdata.imt_subscriptiongoodsorder WHERE userid=7154600 ORDER BY createtime;

-- 2) 功能维度（productline）总额 —— 核心"功能使用情况"
SELECT productline, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00'
GROUP BY 1 ORDER BY tok DESC;

-- 3) 每日×功能 矩阵（北京自然日）
SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, productline,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00'
GROUP BY 1,2 ORDER BY 1,2;

-- 4) 额度归属 countername（看是否走流量包 / 订阅）
SELECT countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00'
GROUP BY 1 ORDER BY tok DESC;

-- 5) EPUB 专项：单请求 input 随时间（异常核心：文本段是否变大）
SELECT to_char(date_add(hour,8,timestamp),'%Y-%m-%d') d, count(*) n,
  round(avg(coalesce(inputusage,0)),0) avg_in, round(avg(coalesce(outputusage,0)),0) avg_out,
  round(avg(coalesce(inputusage,0)+coalesce(outputusage,0)),0) avg_tot,
  max(coalesce(inputusage,0)) max_in
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture' AND productline='epub'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 6) EPUB 整体单请求分布（看是否有固定大 input=系统提示重复计入）
SELECT count(*) n, round(avg(coalesce(inputusage,0)),1) avg_in,
  round(avg(coalesce(outputusage,0)),1) avg_out,
  max(coalesce(inputusage,0)) max_in, median(coalesce(inputusage,0)) med_in,
  quantile(0.99)(coalesce(inputusage,0)) p99_in
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture' AND productline='epub'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00';

-- 7) EPUB 重复计费检测（businessid,actionid 唯一性 → 重试/续翻是否重复计）
SELECT count(*) total, count(DISTINCT (businessid||'|'||actionid)) distinct_pairs,
  sum(CASE WHEN cnt>1 THEN 1 ELSE 0 END) pairs_repeated, max(cnt) max_repeat
FROM (SELECT businessid, actionid, count(*) cnt
  FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture' AND productline='epub'
    AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00' GROUP BY 1,2) t;

-- 8) EPUB 模型分布（actualresourceid）
SELECT actualresourceid, providername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=7154600 AND recordtype='capture' AND productline='epub'
  AND timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00'
GROUP BY 1,2 ORDER BY tok DESC LIMIT 25;

-- 9) 排名基准（窗口内 token 消耗量级）
WITH u AS (SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
  FROM immdata.token_used_aw WHERE timestamp>='2026-09-01 00:00:00' AND timestamp<'2026-11-04 00:00:00' AND recordtype='capture' GROUP BY 1)
SELECT (SELECT count(*) FROM u WHERE tok>=(SELECT tok FROM u WHERE userid=7154600)) rank_no,
       (SELECT count(*) FROM u) total_users,
       (SELECT tok FROM u WHERE userid=7154600) this_tok;
