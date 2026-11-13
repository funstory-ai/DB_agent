-- T104 单用户额度消耗分析：4776466@qq.com -> immdata.imt_userinfo.id = 5993459
-- 窗口：账号全历史（2026-05 起）~ 2026-11-09；重点 2026-10~11（消耗异常期）
-- 主表：immdata.token_used_aw（AW 账单，billing-ledger 落表）
-- 口径：recordtype='capture'；token=inputusage+outputusage；额度归属看 countername（权威）
--       user_subs_ai_token_used_count_v2 = Pro 月订阅 AI 额度（实测 20M/月硬上限）；
--       user_ai_package_used_count = 买的流量包（2026-06-16 购 10M）。
-- 用户自述：使用电子书（EPUB）翻译 -> 与"10 月海量固定 ~5.6K 小段 Qwen/GLM 请求"签名一致。
-- 注意（P043 数据质量）：本账号 token 记录按对账日批量写入，token_used_aw.timestamp / imm_token_used.dates
--       只落在少数归并日（9 月全在 09-18、11 月全在 11-07、10 月 7 天），逐日/逐小时不可信；
--       月度总量、计数器归属、单请求特征、功能维度、user_behaviour 真实事件时间 可靠。
-- 复用脚本：scripts/export_user_token_qq4776466_20261109.py

-- 0) 账号定位
-- SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') ct, isdeleted
-- FROM immdata.imt_userinfo WHERE email='4776466@qq.com';   -- -> 5993459
-- SELECT DISTINCT userid, count(*) n FROM immdata.imt_subscriptiongoodsorder WHERE useremail='4776466@qq.com' GROUP BY 1;
-- SELECT DISTINCT userid, count(*) n FROM immdata.imt_deviceinfo WHERE useremail='4776466@qq.com' GROUP BY 1;

-- 1) 账号画像 + 订阅/套餐
SELECT id, accounttype, to_char(createtime,'%Y-%m-%d') ct, isdeleted
FROM immdata.imt_userinfo WHERE id=5993459;

SELECT to_char(createtime,'%Y-%m-%d %H:%M') d, subscriptiontype, membership,
  orderstatus, ordertype, amountpaid, subscriptionday,
  substring(subscriptiongoodssnap, position('OpenAITokenQuota' in subscriptiongoodssnap), 40) snap_quota
FROM immdata.imt_subscriptiongoodsorder WHERE userid=5993459 ORDER BY createtime;

-- 2) 逐月 token 总量（全历史）
SELECT to_char(timestamp,'%Y-%m') ym, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
GROUP BY 1 ORDER BY 1;

-- 3) 逐月 额度归属 countername（看 Pro 上限 vs 流量包溢出）
SELECT to_char(timestamp,'%Y-%m') ym, countername, count(*) n,
  sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
GROUP BY 1,2 ORDER BY 1,2;

-- 4) 单请求体量 按月（input/output avg/median/p99/max）—— 识别"电子书分段"签名
SELECT to_char(timestamp,'%Y-%m') ym, count(*) n,
  round(avg(coalesce(inputusage,0)),0) avg_in, median(coalesce(inputusage,0)) med_in,
  quantile(0.99)(coalesce(inputusage,0)) p99_in, max(coalesce(inputusage,0)) max_in,
  round(avg(coalesce(outputusage,0)),0) avg_out, max(coalesce(outputusage,0)) max_out
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
  AND timestamp>='2026-05-01 00:00:00' AND timestamp<'2026-11-10 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 5) productline 总额（本账号功能标签几乎全 'unknow'，仅 5 月 web_page）
SELECT productline, count(*) n, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture' GROUP BY 1 ORDER BY tok DESC;

-- 6) 10 月（异常期）模型/资源构成
SELECT actualresourceid, providername, count(*) n, sum(coalesce(inputusage,0)) inp, sum(coalesce(outputusage,0)) outp
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
  AND timestamp>='2026-10-01 00:00:00' AND timestamp<'2026-11-01 00:00:00'
GROUP BY 1,2 ORDER BY n DESC LIMIT 20;

-- 7) 10 月 input 直方图（验证固定 ~5.6K 分段签名）
SELECT CASE WHEN inputusage<1000 THEN 'a:<1k' WHEN inputusage<3000 THEN 'b:1-3k'
  WHEN inputusage<5000 THEN 'c:3-5k' WHEN inputusage<6000 THEN 'd:5-6k'
  WHEN inputusage<7000 THEN 'e:6-7k' WHEN inputusage<10000 THEN 'f:7-10k' ELSE 'g:>=10k' END bucket, count(*) n
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
  AND timestamp>='2026-10-01 00:00:00' AND timestamp<'2026-11-01 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 8) 自动化签名：(businessid,actionid) 唯一性（排除"同请求重发"）
SELECT to_char(timestamp,'%Y-%m') ym, count(*) total,
  count(DISTINCT (businessid||'|'||actionid)) distinct_pairs
FROM immdata.token_used_aw WHERE userid=5993459 AND recordtype='capture'
  AND timestamp>='2026-05-01 00:00:00' AND timestamp<'2026-11-10 00:00:00'
GROUP BY 1 ORDER BY 1;

-- 9) 排名基准（窗口 2026-10-01~2026-11-10 全量活跃用户）
WITH u AS (SELECT userid, sum(coalesce(inputusage,0)+coalesce(outputusage,0)) tok
  FROM immdata.token_used_aw WHERE timestamp>='2026-10-01 00:00:00' AND timestamp<'2026-11-10 00:00:00' AND recordtype='capture' GROUP BY 1)
SELECT (SELECT count(*) FROM u WHERE tok>=(SELECT tok FROM u WHERE userid=5993459)) rank_no,
       (SELECT count(*) FROM u) total_users, (SELECT tok FROM u WHERE userid=5993459) this_tok;

-- 10) user_behaviour 真实事件时间：两活跃设备 事件类型×月（看"消耗 vs 真实翻译行为"是否对得上）
--     设备经 imt_deviceinfo(userid=5993459) 取：73a45934... / v13BVU7F... / XFLj8cFI...(休眠)
SELECT to_char(created_ts,'%Y-%m') ym, event_name, count(*) n
FROM immdata.user_behaviour WHERE device_id='73a4593449dfc9d9cf7bd7b2405ff0e6404dc267fe47218d11a344f35ac294d8'
  AND created_ts>='2026-03-01 00:00:00' AND created_ts<'2026-11-10 00:00:00'
GROUP BY 1,2 ORDER BY 1,3 DESC;
SELECT to_char(created_ts,'%Y-%m') ym, event_name, count(*) n
FROM immdata.user_behaviour WHERE device_id='v13BVU7FqE08SpntBL5rQkQ74KRMvnVLsQi67NvIribHencwaYOjOuV50RNtYorg'
  AND created_ts>='2026-08-01 00:00:00' AND created_ts<'2026-11-10 00:00:00'
GROUP BY 1,2 ORDER BY 1,3 DESC;
