-- =============================================================================
-- 付费墙监测：日汇总中间表 + 增量 TASK（写仓最终定稿 · 整段执行）
-- 规范大类：dashboard；P022 / P023 / P008 / P013 / P016 / P024
-- 任务：docs/tasks/dashboard_paywall_roi_20260817.md
-- 本查数仓库只读，勿在只读账号执行本文件
--
-- 本文件为最终写仓脚本：含 first_device / daily_kpi（含退款列）+ TASK；dim 已废弃（2026-08-27）。
-- 自包含，不依赖任何 *_patch.sql / *_fix.sql。
-- 宽表见 sql/reports/task6_paywall_wide_etl.sql。
--
-- 金额禁止 checkout 与 orders 同层双 LEFT JOIN（会笛卡尔放大 SUM）；
--   KPI 均用 base(+chk)+ord：人数分 CTE；金额/退款只 join orders。
--
-- 口径摘要：
--   付费硬墙 = user_need_pro AND trigger='freeUsageLimitModal'
--   首次触墙：自 2026-05-07（北京）起设备首次硬墙（非终身全局）
--   DAU = 当日 translate_page 设备 UV
--   试用 = finished + amountpaid=0 + 非 onetime* + 非 code（P013）
--   付费人数 = finished + (amountpaid>0 | onetime* | code)（P024）
--   收入 CNY = amountpaid * exchangerate / 100（仅 amountpaid>0；不算退款）
--   退款 CNY = orderstatus='refunded' 且 amountpaid>0；createtime 在触墙后 N 天内（整单）
--   金额窗：首次触墙后 1/4/7/14/30 天（时间戳）
--   基准预期付费：简中 first_uv×1.08% + 其他×0.89%
--   lang_bucket：优先 imm_device_native_language，无则回退 interface_language
--   实验 A/B/C/D：imm_paywall_exp_group_map 上线后填；日维先出 ab_tag
--   维表展开用 UNION ALL（宽表见 wide_etl.sql）
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0) 清除旧版（重建前先跑）
-- -----------------------------------------------------------------------------
ALTER TASK IF EXISTS update_imm_paywall_first_device SUSPEND;
ALTER TASK IF EXISTS update_imm_paywall_daily_kpi SUSPEND;

DROP TASK IF EXISTS update_imm_paywall_first_device;
DROP TASK IF EXISTS update_imm_paywall_daily_kpi;

DROP TABLE IF EXISTS immdata.imm_paywall_daily_kpi;
DROP TABLE IF EXISTS immdata.imm_paywall_first_device;
DROP TABLE IF EXISTS immdata.imm_paywall_exp_group_map;


-- -----------------------------------------------------------------------------
-- 1) 建表
-- -----------------------------------------------------------------------------

-- 实验 ab_tag → A/B/C/D（下周上线后由写仓 INSERT；未填时 exp_group 为空）
CREATE TABLE immdata.imm_paywall_exp_group_map (
  ab_tag VARCHAR,
  exp_group VARCHAR,   -- A / B / C / D
  start_dt DATE,
  end_dt DATE,         -- NULL=仍生效
  note VARCHAR,
  update_time TIMESTAMP
);

-- 设备首次付费硬墙（回填窗内）
CREATE TABLE immdata.imm_paywall_first_device (
  device_id VARCHAR,
  first_paywall_ts TIMESTAMP,
  first_paywall_dt_bj DATE,
  userid BIGINT,                 -- COALESCE(触墙时 ex_int_arg1, deviceinfo.userid)
  userid_from_event BIGINT,      -- 触墙行 ex_int_arg1
  userid_from_device BIGINT,     -- imt_deviceinfo
  ab_tag VARCHAR,                -- 清洗后 a-j / other
  exp_group VARCHAR,             -- 映射表；可空
  platform_type VARCHAR,
  os_name VARCHAR,
  interface_language VARCHAR,
  lang_bucket VARCHAR,           -- zh_cn | other（基准预期用）
  campaign VARCHAR,
  install_from VARCHAR,
  update_time TIMESTAMP
);

-- 按「首次触墙北京日」的 cohort KPI + 当日 DAU / 当日触墙
CREATE TABLE immdata.imm_paywall_daily_kpi (
  dt_bj DATE,
  -- 分母 / 当日曝光
  dau BIGINT,
  paywall_uv BIGINT,             -- 当日任意硬墙设备 UV（非仅首次）
  register_wall_uv BIGINT,       -- 当日未登录限额墙（B 组参考）
  -- 首次硬墙 cohort（主漏斗）
  first_paywall_uv BIGINT,
  first_paywall_userid_cnt BIGINT,
  first_paywall_uv_zh_cn BIGINT,
  first_paywall_uv_other BIGINT,
  expected_paid_users DOUBLE,    -- 基准预期付费
  -- 触墙后 30 天漏斗（userid）
  checkout_users BIGINT,
  trial_users BIGINT,
  paid_users BIGINT,
  -- 触墙后 N 日付费人数 / 收入 CNY
  d1_paid_users BIGINT,
  d4_paid_users BIGINT,
  d7_paid_users BIGINT,
  d14_paid_users BIGINT,
  d30_paid_users BIGINT,
  d1_revenue_cny DOUBLE,
  d4_revenue_cny DOUBLE,
  d7_revenue_cny DOUBLE,
  d14_revenue_cny DOUBLE,
  d30_revenue_cny DOUBLE,
  -- 触墙后 N 天内成交、后整单退（orderstatus=refunded；不扣收入）
  d1_refund_users BIGINT,
  d4_refund_users BIGINT,
  d7_refund_users BIGINT,
  d14_refund_users BIGINT,
  d30_refund_users BIGINT,
  d1_refund_cny DOUBLE,
  d4_refund_cny DOUBLE,
  d7_refund_cny DOUBLE,
  d14_refund_cny DOUBLE,
  d30_refund_cny DOUBLE,
  -- 率（日粒度；窗口率看板用 SUM 分子/SUM 分母）
  paywall_rate DOUBLE,           -- paywall_uv / dau
  first_paywall_rate DOUBLE,     -- first_paywall_uv / dau
  checkout_rate DOUBLE,          -- checkout / first_paywall_userid_cnt
  trial_rate DOUBLE,
  paid_rate DOUBLE,              -- paid / first_paywall_userid_cnt
  d4_pay_rate DOUBLE,
  d7_pay_rate DOUBLE,
  arpu_30d DOUBLE,               -- d30_revenue / first_paywall_uv
  arppu_30d DOUBLE,              -- d30_revenue / paid_users
  rev_per_paywall_user_30d DOUBLE,
  update_time TIMESTAMP
);



-- -----------------------------------------------------------------------------
-- 2) 全量回填：首次硬墙设备（自 2026-05-07 北京 00:00）
--    UTC 下界 = 2026-05-06 16:00:00
-- -----------------------------------------------------------------------------
REPLACE INTO immdata.imm_paywall_first_device
(
  device_id, first_paywall_ts, first_paywall_dt_bj,
  userid, userid_from_event, userid_from_device,
  ab_tag, exp_group,
  platform_type, os_name, interface_language, lang_bucket,
  campaign, install_from, update_time
)
ON (device_id)
WITH wall AS (
  SELECT
    device_id,
    created_ts,
    ex_int_arg1 AS userid_from_event,
    CASE
      WHEN ab_tag IS NOT NULL
       AND LENGTH(TRIM(ab_tag)) = 1
       AND LOWER(TRIM(ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(ab_tag))
      ELSE 'other'
    END AS ab_tag,
    platform_type,
    os_name,
    interface_language,
    campaign,
    install_from,
    ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY created_ts ASC) AS rn
  FROM immdata.user_behaviour
  WHERE event_name = 'user_need_pro'
    AND trigger = 'freeUsageLimitModal'
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= '2026-05-06 16:00:00'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
),
first_row AS (
  SELECT * FROM wall WHERE rn = 1
),
dev AS (
  SELECT deviceid, MAX(userid) AS userid_from_device
  FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND deviceid IS NOT NULL AND deviceid <> ''
  GROUP BY deviceid
)
SELECT
  f.device_id,
  f.created_ts AS first_paywall_ts,
  CAST(DATEADD(hour, 8, f.created_ts) AS DATE) AS first_paywall_dt_bj,
  COALESCE(f.userid_from_event, d.userid_from_device) AS userid,
  f.userid_from_event,
  d.userid_from_device,
  f.ab_tag,
  m.exp_group,
  f.platform_type,
  f.os_name,
  f.interface_language,
  CASE
    WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, ''))
           IN ('zh-cn', 'zh', 'zh-hans')
      OR LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, '')) LIKE 'zh-cn%'
      OR LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, '')) LIKE 'zh_cn%'
    THEN 'zh_cn'
    ELSE 'other'
  END AS lang_bucket,
  f.campaign,
  f.install_from,
  NOW() AS update_time
FROM first_row f
LEFT JOIN dev d ON d.deviceid = f.device_id
LEFT JOIN immdata.imm_device_native_language n
  ON n.device_id = f.device_id
LEFT JOIN immdata.imm_paywall_exp_group_map m
  ON m.ab_tag = f.ab_tag
 AND f.created_ts >= CAST(m.start_dt AS TIMESTAMP)
 AND (m.end_dt IS NULL OR f.created_ts < DATEADD(day, 1, CAST(m.end_dt AS TIMESTAMP)));


-- -----------------------------------------------------------------------------
-- 3) 全量回填：daily_kpi（首次触墙日 cohort + 当日 DAU/触墙；含退款；金额无 fanout）
-- -----------------------------------------------------------------------------
REPLACE INTO immdata.imm_paywall_daily_kpi
(
  dt_bj, dau, paywall_uv, register_wall_uv,
  first_paywall_uv, first_paywall_userid_cnt,
  first_paywall_uv_zh_cn, first_paywall_uv_other, expected_paid_users,
  checkout_users, trial_users, paid_users,
  d1_paid_users, d4_paid_users, d7_paid_users, d14_paid_users, d30_paid_users,
  d1_revenue_cny, d4_revenue_cny, d7_revenue_cny, d14_revenue_cny, d30_revenue_cny,
  d1_refund_users, d4_refund_users, d7_refund_users, d14_refund_users, d30_refund_users,
  d1_refund_cny, d4_refund_cny, d7_refund_cny, d14_refund_cny, d30_refund_cny,
  paywall_rate, first_paywall_rate,
  checkout_rate, trial_rate, paid_rate, d4_pay_rate, d7_pay_rate,
  arpu_30d, arppu_30d, rev_per_paywall_user_30d, update_time
)
ON (dt_bj)
WITH dau_day AS (
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    COUNT(DISTINCT device_id) AS dau
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= '2026-05-06 16:00:00'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1
),
same_day_wall AS (
  SELECT
    CAST(DATEADD(hour, 8, created_ts) AS DATE) AS dt_bj,
    COUNT(DISTINCT CASE
      WHEN trigger = 'freeUsageLimitModal' THEN device_id END) AS paywall_uv,
    COUNT(DISTINCT CASE
      WHEN trigger = 'unregisteredUsageLimitModal' THEN device_id END) AS register_wall_uv
  FROM immdata.user_behaviour
  WHERE event_name = 'user_need_pro'
    AND trigger IN ('freeUsageLimitModal', 'unregisteredUsageLimitModal')
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= '2026-05-06 16:00:00'
    AND created_ts < add_hours(date(add_hours(now(), 8)), -8)
  GROUP BY 1
),
orders AS (
  SELECT
    o.userid,
    o.createtime,
    CASE
      WHEN COALESCE(o.amountpaid, 0) <= 0 THEN 0.0
      WHEN UPPER(COALESCE(o.currency, '')) IN ('CNY', 'RMB') THEN o.amountpaid / 100.0
      ELSE o.amountpaid * COALESCE(er.exchangerate, 0) / 100.0
    END AS amount_cny,
    CASE
      WHEN o.orderstatus = 'finished'
       AND COALESCE(o.amountpaid, 0) = 0
       AND COALESCE(CAST(o.subscriptiongoodssnap AS STRING), '')
           NOT LIKE '%"SubscriptionType":"onetime%'
       AND LOWER(COALESCE(o.ordertype, '')) <> 'code'
      THEN 1 ELSE 0
    END AS is_trial,
    CASE
      WHEN o.orderstatus = 'finished'
       AND (
         COALESCE(o.amountpaid, 0) > 0
         OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
         OR LOWER(COALESCE(o.ordertype, '')) = 'code'
       )
      THEN 1 ELSE 0
    END AS is_paid,
    CASE
      WHEN o.orderstatus = 'refunded' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0
    END AS is_refund
  FROM immdata.imt_subscriptiongoodsorder o
  LEFT JOIN immdata.exchangerates er
    ON UPPER(COALESCE(o.currency, '')) = UPPER(COALESCE(er.currency, ''))
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.userid IS NOT NULL
    AND o.createtime >= '2026-05-06 16:00:00'
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= '2026-05-06 16:00:00'
),
base AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT f.device_id) AS first_paywall_uv,
    COUNT(DISTINCT f.userid) AS first_paywall_userid_cnt,
    COUNT(DISTINCT CASE WHEN f.lang_bucket = 'zh_cn' THEN f.device_id END) AS first_paywall_uv_zh_cn,
    COUNT(DISTINCT CASE WHEN f.lang_bucket = 'other' THEN f.device_id END) AS first_paywall_uv_other
  FROM immdata.imm_paywall_first_device f
  GROUP BY f.first_paywall_dt_bj
),
chk AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT CASE
      WHEN c.userid IS NOT NULL
       AND c.createtime >= f.first_paywall_ts
       AND c.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN c.userid END) AS checkout_users
  FROM immdata.imm_paywall_first_device f
  LEFT JOIN checkout c ON c.userid = f.userid
  GROUP BY f.first_paywall_dt_bj
),
ord AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT CASE
      WHEN o.is_trial = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS trial_users,
    COUNT(DISTINCT CASE
      WHEN o.is_paid = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.userid END) AS d1_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.userid END) AS d4_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.userid END) AS d7_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.userid END) AS d14_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.userid END) AS d30_paid_users,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d30_revenue_cny,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.userid END) AS d1_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.userid END) AS d4_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.userid END) AS d7_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.userid END) AS d14_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.userid END) AS d30_refund_users,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d30_refund_cny
  FROM immdata.imm_paywall_first_device f
  LEFT JOIN orders o ON o.userid = f.userid
  GROUP BY f.first_paywall_dt_bj
),
cohort AS (
  SELECT
    b.dt_bj,
    b.first_paywall_uv,
    b.first_paywall_userid_cnt,
    b.first_paywall_uv_zh_cn,
    b.first_paywall_uv_other,
    COALESCE(c.checkout_users, 0) AS checkout_users,
    COALESCE(o.trial_users, 0) AS trial_users,
    COALESCE(o.paid_users, 0) AS paid_users,
    COALESCE(o.d1_paid_users, 0) AS d1_paid_users,
    COALESCE(o.d4_paid_users, 0) AS d4_paid_users,
    COALESCE(o.d7_paid_users, 0) AS d7_paid_users,
    COALESCE(o.d14_paid_users, 0) AS d14_paid_users,
    COALESCE(o.d30_paid_users, 0) AS d30_paid_users,
    COALESCE(o.d1_revenue_cny, 0) AS d1_revenue_cny,
    COALESCE(o.d4_revenue_cny, 0) AS d4_revenue_cny,
    COALESCE(o.d7_revenue_cny, 0) AS d7_revenue_cny,
    COALESCE(o.d14_revenue_cny, 0) AS d14_revenue_cny,
    COALESCE(o.d30_revenue_cny, 0) AS d30_revenue_cny,
    COALESCE(o.d1_refund_users, 0) AS d1_refund_users,
    COALESCE(o.d4_refund_users, 0) AS d4_refund_users,
    COALESCE(o.d7_refund_users, 0) AS d7_refund_users,
    COALESCE(o.d14_refund_users, 0) AS d14_refund_users,
    COALESCE(o.d30_refund_users, 0) AS d30_refund_users,
    COALESCE(o.d1_refund_cny, 0) AS d1_refund_cny,
    COALESCE(o.d4_refund_cny, 0) AS d4_refund_cny,
    COALESCE(o.d7_refund_cny, 0) AS d7_refund_cny,
    COALESCE(o.d14_refund_cny, 0) AS d14_refund_cny,
    COALESCE(o.d30_refund_cny, 0) AS d30_refund_cny
  FROM base b
  LEFT JOIN chk c ON c.dt_bj = b.dt_bj
  LEFT JOIN ord o ON o.dt_bj = b.dt_bj
)
SELECT
  COALESCE(c.dt_bj, d.dt_bj, s.dt_bj) AS dt_bj,
  COALESCE(d.dau, 0) AS dau,
  COALESCE(s.paywall_uv, 0) AS paywall_uv,
  COALESCE(s.register_wall_uv, 0) AS register_wall_uv,
  COALESCE(c.first_paywall_uv, 0) AS first_paywall_uv,
  COALESCE(c.first_paywall_userid_cnt, 0) AS first_paywall_userid_cnt,
  COALESCE(c.first_paywall_uv_zh_cn, 0) AS first_paywall_uv_zh_cn,
  COALESCE(c.first_paywall_uv_other, 0) AS first_paywall_uv_other,
  COALESCE(c.first_paywall_uv_zh_cn, 0) * 0.0108
    + COALESCE(c.first_paywall_uv_other, 0) * 0.0089 AS expected_paid_users,
  COALESCE(c.checkout_users, 0) AS checkout_users,
  COALESCE(c.trial_users, 0) AS trial_users,
  COALESCE(c.paid_users, 0) AS paid_users,
  COALESCE(c.d1_paid_users, 0) AS d1_paid_users,
  COALESCE(c.d4_paid_users, 0) AS d4_paid_users,
  COALESCE(c.d7_paid_users, 0) AS d7_paid_users,
  COALESCE(c.d14_paid_users, 0) AS d14_paid_users,
  COALESCE(c.d30_paid_users, 0) AS d30_paid_users,
  COALESCE(c.d1_revenue_cny, 0) AS d1_revenue_cny,
  COALESCE(c.d4_revenue_cny, 0) AS d4_revenue_cny,
  COALESCE(c.d7_revenue_cny, 0) AS d7_revenue_cny,
  COALESCE(c.d14_revenue_cny, 0) AS d14_revenue_cny,
  COALESCE(c.d30_revenue_cny, 0) AS d30_revenue_cny,
  COALESCE(c.d1_refund_users, 0) AS d1_refund_users,
  COALESCE(c.d4_refund_users, 0) AS d4_refund_users,
  COALESCE(c.d7_refund_users, 0) AS d7_refund_users,
  COALESCE(c.d14_refund_users, 0) AS d14_refund_users,
  COALESCE(c.d30_refund_users, 0) AS d30_refund_users,
  COALESCE(c.d1_refund_cny, 0) AS d1_refund_cny,
  COALESCE(c.d4_refund_cny, 0) AS d4_refund_cny,
  COALESCE(c.d7_refund_cny, 0) AS d7_refund_cny,
  COALESCE(c.d14_refund_cny, 0) AS d14_refund_cny,
  COALESCE(c.d30_refund_cny, 0) AS d30_refund_cny,
  COALESCE(s.paywall_uv, 0) * 1.0 / NULLIF(COALESCE(d.dau, 0), 0) AS paywall_rate,
  COALESCE(c.first_paywall_uv, 0) * 1.0 / NULLIF(COALESCE(d.dau, 0), 0) AS first_paywall_rate,
  COALESCE(c.checkout_users, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_userid_cnt, 0), 0) AS checkout_rate,
  COALESCE(c.trial_users, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_userid_cnt, 0), 0) AS trial_rate,
  COALESCE(c.paid_users, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_userid_cnt, 0), 0) AS paid_rate,
  COALESCE(c.d4_paid_users, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_userid_cnt, 0), 0) AS d4_pay_rate,
  COALESCE(c.d7_paid_users, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_userid_cnt, 0), 0) AS d7_pay_rate,
  COALESCE(c.d30_revenue_cny, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_uv, 0), 0) AS arpu_30d,
  COALESCE(c.d30_revenue_cny, 0) * 1.0
    / NULLIF(COALESCE(c.paid_users, 0), 0) AS arppu_30d,
  COALESCE(c.d30_revenue_cny, 0) * 1.0
    / NULLIF(COALESCE(c.first_paywall_uv, 0), 0) AS rev_per_paywall_user_30d,
  NOW() AS update_time
FROM cohort c
FULL OUTER JOIN dau_day d ON d.dt_bj = c.dt_bj
FULL OUTER JOIN same_day_wall s ON s.dt_bj = COALESCE(c.dt_bj, d.dt_bj);


-- -----------------------------------------------------------------------------
-- 5) 日更 TASK
-- -----------------------------------------------------------------------------

-- 5.1 昨日新首次硬墙设备（已存在则不覆盖）
DROP TASK IF EXISTS update_imm_paywall_first_device;
CREATE TASK IF NOT EXISTS update_imm_paywall_first_device
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 20 21 * * *' 'UTC'
COMMENT = '付费墙：昨日新首次硬墙设备写入 first_device'
AS
INSERT INTO immdata.imm_paywall_first_device
(
  device_id, first_paywall_ts, first_paywall_dt_bj,
  userid, userid_from_event, userid_from_device,
  ab_tag, exp_group,
  platform_type, os_name, interface_language, lang_bucket,
  campaign, install_from, update_time
)
WITH wall AS (
  SELECT
    device_id,
    created_ts,
    ex_int_arg1 AS userid_from_event,
    CASE
      WHEN ab_tag IS NOT NULL
       AND LENGTH(TRIM(ab_tag)) = 1
       AND LOWER(TRIM(ab_tag)) BETWEEN 'a' AND 'j'
      THEN LOWER(TRIM(ab_tag))
      ELSE 'other'
    END AS ab_tag,
    platform_type,
    os_name,
    interface_language,
    campaign,
    install_from,
    ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY created_ts ASC) AS rn
  FROM immdata.user_behaviour
  WHERE event_name = 'user_need_pro'
    AND trigger = 'freeUsageLimitModal'
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
),
first_row AS (
  SELECT w.*
  FROM wall w
  LEFT JOIN immdata.imm_paywall_first_device e ON e.device_id = w.device_id
  WHERE w.rn = 1
    AND e.device_id IS NULL
),
dev AS (
  SELECT deviceid, MAX(userid) AS userid_from_device
  FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND deviceid IS NOT NULL AND deviceid <> ''
  GROUP BY deviceid
)
SELECT
  f.device_id,
  f.created_ts,
  CAST(DATEADD(hour, 8, f.created_ts) AS DATE),
  COALESCE(f.userid_from_event, d.userid_from_device),
  f.userid_from_event,
  d.userid_from_device,
  f.ab_tag,
  m.exp_group,
  f.platform_type,
  f.os_name,
  f.interface_language,
  CASE
    WHEN LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, ''))
           IN ('zh-cn', 'zh', 'zh-hans')
      OR LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, '')) LIKE 'zh-cn%'
      OR LOWER(COALESCE(NULLIF(n.native_language, ''), f.interface_language, '')) LIKE 'zh_cn%'
    THEN 'zh_cn'
    ELSE 'other'
  END,
  f.campaign,
  f.install_from,
  NOW()
FROM first_row f
LEFT JOIN dev d ON d.deviceid = f.device_id
LEFT JOIN immdata.imm_device_native_language n
  ON n.device_id = f.device_id
LEFT JOIN immdata.imm_paywall_exp_group_map m
  ON m.ab_tag = f.ab_tag
 AND f.created_ts >= CAST(m.start_dt AS TIMESTAMP)
 AND (m.end_dt IS NULL OR f.created_ts < DATEADD(day, 1, CAST(m.end_dt AS TIMESTAMP)));


-- 5.2 刷新近 31 个首次触墙日的 KPI（转化窗滚动）+ 昨日 DAU/当日触墙
-- 金额：base + chk + ord（orders-only SUM，防 checkout fanout）
DROP TASK IF EXISTS update_imm_paywall_daily_kpi;

CREATE TASK update_imm_paywall_daily_kpi
WAREHOUSE = 'write'
SCHEDULE = USING CRON '0 30 21 * * *' 'UTC'
COMMENT = '付费墙：近31日 cohort KPI（退款+金额无 checkout 放大）'
AS
REPLACE INTO immdata.imm_paywall_daily_kpi
(
  dt_bj, dau, paywall_uv, register_wall_uv,
  first_paywall_uv, first_paywall_userid_cnt,
  first_paywall_uv_zh_cn, first_paywall_uv_other, expected_paid_users,
  checkout_users, trial_users, paid_users,
  d1_paid_users, d4_paid_users, d7_paid_users, d14_paid_users, d30_paid_users,
  d1_revenue_cny, d4_revenue_cny, d7_revenue_cny, d14_revenue_cny, d30_revenue_cny,
  d1_refund_users, d4_refund_users, d7_refund_users, d14_refund_users, d30_refund_users,
  d1_refund_cny, d4_refund_cny, d7_refund_cny, d14_refund_cny, d30_refund_cny,
  paywall_rate, first_paywall_rate,
  checkout_rate, trial_rate, paid_rate, d4_pay_rate, d7_pay_rate,
  arpu_30d, arppu_30d, rev_per_paywall_user_30d, update_time
)
ON (dt_bj)
WITH y_bj AS (
  SELECT add_days(date(add_hours(now(), 8)), -1) AS y
),
dau_y AS (
  SELECT COUNT(DISTINCT device_id) AS dau
  FROM immdata.user_behaviour
  WHERE event_name = 'translate_page'
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
),
same_day_y AS (
  SELECT
    COUNT(DISTINCT CASE WHEN trigger = 'freeUsageLimitModal' THEN device_id END) AS paywall_uv,
    COUNT(DISTINCT CASE WHEN trigger = 'unregisteredUsageLimitModal' THEN device_id END) AS register_wall_uv
  FROM immdata.user_behaviour
  WHERE event_name = 'user_need_pro'
    AND trigger IN ('freeUsageLimitModal', 'unregisteredUsageLimitModal')
    AND device_id IS NOT NULL AND device_id <> ''
    AND created_ts >= add_hours(add_days(date(add_hours(now(), 8)), -1), -8)
    AND created_ts <  add_hours(date(add_hours(now(), 8)), -8)
),
orders AS (
  SELECT
    o.userid,
    o.createtime,
    CASE
      WHEN COALESCE(o.amountpaid, 0) <= 0 THEN 0.0
      WHEN UPPER(COALESCE(o.currency, '')) IN ('CNY', 'RMB') THEN o.amountpaid / 100.0
      ELSE o.amountpaid * COALESCE(er.exchangerate, 0) / 100.0
    END AS amount_cny,
    CASE
      WHEN o.orderstatus = 'finished'
       AND COALESCE(o.amountpaid, 0) = 0
       AND COALESCE(CAST(o.subscriptiongoodssnap AS STRING), '')
           NOT LIKE '%"SubscriptionType":"onetime%'
       AND LOWER(COALESCE(o.ordertype, '')) <> 'code'
      THEN 1 ELSE 0
    END AS is_trial,
    CASE
      WHEN o.orderstatus = 'finished'
       AND (
         COALESCE(o.amountpaid, 0) > 0
         OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
         OR LOWER(COALESCE(o.ordertype, '')) = 'code'
       )
      THEN 1 ELSE 0
    END AS is_paid,
    CASE
      WHEN o.orderstatus = 'refunded' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0
    END AS is_refund
  FROM immdata.imt_subscriptiongoodsorder o
  LEFT JOIN immdata.exchangerates er
    ON UPPER(COALESCE(o.currency, '')) = UPPER(COALESCE(er.currency, ''))
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.userid IS NOT NULL
    AND o.createtime >= DATEADD(day, -62, add_hours(date(add_hours(now(), 8)), -8))
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= DATEADD(day, -62, add_hours(date(add_hours(now(), 8)), -8))
),
base AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT f.device_id) AS first_paywall_uv,
    COUNT(DISTINCT f.userid) AS first_paywall_userid_cnt,
    COUNT(DISTINCT CASE WHEN f.lang_bucket = 'zh_cn' THEN f.device_id END) AS first_paywall_uv_zh_cn,
    COUNT(DISTINCT CASE WHEN f.lang_bucket = 'other' THEN f.device_id END) AS first_paywall_uv_other
  FROM immdata.imm_paywall_first_device f
  CROSS JOIN y_bj y
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -30, y.y)
    AND f.first_paywall_dt_bj <= y.y
  GROUP BY f.first_paywall_dt_bj
),
chk AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT CASE
      WHEN c.userid IS NOT NULL
       AND c.createtime >= f.first_paywall_ts
       AND c.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN c.userid END) AS checkout_users
  FROM immdata.imm_paywall_first_device f
  CROSS JOIN y_bj y
  LEFT JOIN checkout c ON c.userid = f.userid
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -30, y.y)
    AND f.first_paywall_dt_bj <= y.y
  GROUP BY f.first_paywall_dt_bj
),
ord AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(DISTINCT CASE
      WHEN o.is_trial = 1 AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS trial_users,
    COUNT(DISTINCT CASE
      WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.userid END) AS d1_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.userid END) AS d4_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.userid END) AS d7_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.userid END) AS d14_paid_users,
    COUNT(DISTINCT CASE WHEN o.is_paid = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.userid END) AS d30_paid_users,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_revenue_cny,
    SUM(CASE WHEN o.is_paid = 1 AND o.amount_cny > 0 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d30_revenue_cny,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.userid END) AS d1_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.userid END) AS d4_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.userid END) AS d7_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.userid END) AS d14_refund_users,
    COUNT(DISTINCT CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.userid END) AS d30_refund_users,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_refund_cny,
    SUM(CASE WHEN o.is_refund = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 30, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d30_refund_cny
  FROM immdata.imm_paywall_first_device f
  CROSS JOIN y_bj y
  LEFT JOIN orders o ON o.userid = f.userid
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -30, y.y)
    AND f.first_paywall_dt_bj <= y.y
  GROUP BY f.first_paywall_dt_bj
),
cohort AS (
  SELECT
    b.dt_bj,
    b.first_paywall_uv,
    b.first_paywall_userid_cnt,
    b.first_paywall_uv_zh_cn,
    b.first_paywall_uv_other,
    COALESCE(c.checkout_users, 0) AS checkout_users,
    COALESCE(o.trial_users, 0) AS trial_users,
    COALESCE(o.paid_users, 0) AS paid_users,
    COALESCE(o.d1_paid_users, 0) AS d1_paid_users,
    COALESCE(o.d4_paid_users, 0) AS d4_paid_users,
    COALESCE(o.d7_paid_users, 0) AS d7_paid_users,
    COALESCE(o.d14_paid_users, 0) AS d14_paid_users,
    COALESCE(o.d30_paid_users, 0) AS d30_paid_users,
    COALESCE(o.d1_revenue_cny, 0) AS d1_revenue_cny,
    COALESCE(o.d4_revenue_cny, 0) AS d4_revenue_cny,
    COALESCE(o.d7_revenue_cny, 0) AS d7_revenue_cny,
    COALESCE(o.d14_revenue_cny, 0) AS d14_revenue_cny,
    COALESCE(o.d30_revenue_cny, 0) AS d30_revenue_cny,
    COALESCE(o.d1_refund_users, 0) AS d1_refund_users,
    COALESCE(o.d4_refund_users, 0) AS d4_refund_users,
    COALESCE(o.d7_refund_users, 0) AS d7_refund_users,
    COALESCE(o.d14_refund_users, 0) AS d14_refund_users,
    COALESCE(o.d30_refund_users, 0) AS d30_refund_users,
    COALESCE(o.d1_refund_cny, 0) AS d1_refund_cny,
    COALESCE(o.d4_refund_cny, 0) AS d4_refund_cny,
    COALESCE(o.d7_refund_cny, 0) AS d7_refund_cny,
    COALESCE(o.d14_refund_cny, 0) AS d14_refund_cny,
    COALESCE(o.d30_refund_cny, 0) AS d30_refund_cny
  FROM base b
  LEFT JOIN chk c ON c.dt_bj = b.dt_bj
  LEFT JOIN ord o ON o.dt_bj = b.dt_bj
)
SELECT
  c.dt_bj,
  CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT dau FROM dau_y)
       ELSE COALESCE((SELECT k.dau FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
  END,
  CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT paywall_uv FROM same_day_y)
       ELSE COALESCE((SELECT k.paywall_uv FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
  END,
  CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT register_wall_uv FROM same_day_y)
       ELSE COALESCE((SELECT k.register_wall_uv FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
  END,
  c.first_paywall_uv,
  c.first_paywall_userid_cnt,
  c.first_paywall_uv_zh_cn,
  c.first_paywall_uv_other,
  c.first_paywall_uv_zh_cn * 0.0108 + c.first_paywall_uv_other * 0.0089,
  c.checkout_users,
  c.trial_users,
  c.paid_users,
  c.d1_paid_users,
  c.d4_paid_users,
  c.d7_paid_users,
  c.d14_paid_users,
  c.d30_paid_users,
  c.d1_revenue_cny,
  c.d4_revenue_cny,
  c.d7_revenue_cny,
  c.d14_revenue_cny,
  c.d30_revenue_cny,
  c.d1_refund_users,
  c.d4_refund_users,
  c.d7_refund_users,
  c.d14_refund_users,
  c.d30_refund_users,
  c.d1_refund_cny,
  c.d4_refund_cny,
  c.d7_refund_cny,
  c.d14_refund_cny,
  c.d30_refund_cny,
  (CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT paywall_uv FROM same_day_y)
        ELSE COALESCE((SELECT k.paywall_uv FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
   END) * 1.0
    / NULLIF(CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT dau FROM dau_y)
                  ELSE COALESCE((SELECT k.dau FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
             END, 0),
  c.first_paywall_uv * 1.0
    / NULLIF(CASE WHEN c.dt_bj = (SELECT y FROM y_bj) THEN (SELECT dau FROM dau_y)
                  ELSE COALESCE((SELECT k.dau FROM immdata.imm_paywall_daily_kpi k WHERE k.dt_bj = c.dt_bj), 0)
             END, 0),
  c.checkout_users * 1.0 / NULLIF(c.first_paywall_userid_cnt, 0),
  c.trial_users * 1.0 / NULLIF(c.first_paywall_userid_cnt, 0),
  c.paid_users * 1.0 / NULLIF(c.first_paywall_userid_cnt, 0),
  c.d4_paid_users * 1.0 / NULLIF(c.first_paywall_userid_cnt, 0),
  c.d7_paid_users * 1.0 / NULLIF(c.first_paywall_userid_cnt, 0),
  c.d30_revenue_cny * 1.0 / NULLIF(c.first_paywall_uv, 0),
  c.d30_revenue_cny * 1.0 / NULLIF(c.paid_users, 0),
  c.d30_revenue_cny * 1.0 / NULLIF(c.first_paywall_uv, 0),
  NOW()
FROM cohort c;


ALTER TASK IF EXISTS update_imm_paywall_first_device RESUME;
ALTER TASK IF EXISTS update_imm_paywall_daily_kpi RESUME;


-- -----------------------------------------------------------------------------
-- 6) 实验映射（写仓在下周分流确定后执行示例）
-- -----------------------------------------------------------------------------
-- INSERT INTO immdata.imm_paywall_exp_group_map (ab_tag, exp_group, start_dt, end_dt, note, update_time)
-- VALUES
--   ('a', 'A', '2026-08-25', NULL, '当前方案', NOW()),
--   ('b', 'B', '2026-08-25', NULL, '取消注册墙', NOW()),
--   ('c', 'C', '2026-08-25', NULL, '激活后7日不触墙', NOW()),
--   ('d', 'D', '2026-08-25', NULL, '激活后14日不触墙', NOW());
-- 然后：UPDATE first_device.exp_group；或重跑 first_device 回填段 + kpi。
