-- =============================================================================
-- 付费墙监测：Superset Virtual Dataset（最终挂板 SQL · 读中间表）
-- 任务：docs/tasks/dashboard_paywall_roi_20260817.md
-- 规范：P022；勿 Jinja；比率用 SUM(分子)/SUM(分母)
-- 只读库：money_window 禁止 WITH（用嵌套 SELECT + CROSS JOIN 窗长）；
--   勿写 SELECT * FROM ( WITH ... ) —— Superset 再包一层会 Fatal
--
-- 写仓定稿（无 patch 依赖）：
--   sql/reports/task6_paywall_daily_etl.sql  — first_device / kpi / dim + TASK
--   sql/reports/task6_paywall_wide_etl.sql   — wide_hit / wide_paywall_rate + TASK
--
-- 【数据集清单】
--   A. kpi 对账/加项：ds_paywall_kpi_volume | hit_rate | funnel | paid_ndays
--      | revenue | refund | money_window | expected | window
--   B. 挂板主读：ds_paywall_wide_cohort | money_window | hit | paywall_rate
--   Part2 金额：ds_paywall_wide_money_window / ds_paywall_kpi_money_window
--     （window_days 单选 Filter；勿跨窗 SUM）
-- 作废 ds_paywall_dim_* / ds_paywall_wide_wall_kind 已删除
-- =============================================================================


-- ---------------------------------------------------------------------------
-- A. kpi 对账 / 加项
-- ---------------------------------------------------------------------------

-- 数据集名：ds_paywall_kpi_volume
-- 用途：规模 · 按日（DAU / 当日硬墙 / 注册墙 / 首次 cohort）
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  dau,
  paywall_uv,
  register_wall_uv,
  first_paywall_uv,
  first_paywall_userid_cnt
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_hit_rate
-- 用途：触墙率 · 按日（日率画线；近窗比率见 ds_paywall_kpi_window）
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  dau,
  paywall_uv,
  first_paywall_uv,
  paywall_rate,
  first_paywall_rate
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_funnel
-- 用途：首次硬墙后 30 天漏斗（userid）
-- 建议图：Mixed — Bar=checkout/trial/paid；Line=paid_rate 右轴
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  first_paywall_userid_cnt,
  checkout_users,
  trial_users,
  paid_users,
  checkout_rate,
  trial_rate,
  paid_rate
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_paid_ndays
-- 用途：触墙后 N 日付费人数 / D4·D7 付费率
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  first_paywall_userid_cnt,
  d1_paid_users,
  d4_paid_users,
  d7_paid_users,
  d14_paid_users,
  d30_paid_users,
  d4_pay_rate,
  d7_pay_rate
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_revenue
-- 用途：Part2 · 触墙后 N 天收入 CNY + ARPU/ARPPU（无 Filter；总数）
-- 口径：finished 且 amountpaid>0；CNY；不算退款（退款见 ds_paywall_kpi_refund）
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  first_paywall_uv,
  first_paywall_userid_cnt,
  paid_users,
  d1_revenue_cny,
  d4_revenue_cny,
  d7_revenue_cny,
  d14_revenue_cny,
  d30_revenue_cny,
  arpu_30d,
  arppu_30d,
  rev_per_paywall_user_30d
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_refund
-- 用途：Part2 · 触墙后 N 天内成交、后整单退款的金额/人数（无 Filter；总数）
-- 归因：orderstatus='refunded' 且 createtime ∈ [首次触墙, +N天)；金额同收入折算
-- 前置：写仓跑 task6_paywall_refund_kpi_patch.sql 后读 kpi；未跑前可用下方注释备选
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  d1_refund_users,
  d4_refund_users,
  d7_refund_users,
  d14_refund_users,
  d30_refund_users,
  d1_refund_cny,
  d4_refund_cny,
  d7_refund_cny,
  d14_refund_cny,
  d30_refund_cny
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;



-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_money_window
-- 用途：Part2 · Big Number / 无六维；窗长单选默认 30
-- 口径：userid×触墙日只留最早设备；金额 CNY
-- 禁止 WITH：Superset 保存时会再包 SELECT * FROM (...), 子查询内 CTE 会 Fatal
-- ---------------------------------------------------------------------------
SELECT
  d.dt_bj,
  d.first_paywall_userid_cnt,
  w.window_days,
  CASE w.window_days
    WHEN 1 THEN d.d1_revenue_cny
    WHEN 4 THEN d.d4_revenue_cny
    WHEN 7 THEN d.d7_revenue_cny
    WHEN 14 THEN d.d14_revenue_cny
    WHEN 30 THEN d.d30_revenue_cny
  END AS revenue_cny,
  CASE w.window_days
    WHEN 1 THEN d.d1_refund_cny
    WHEN 4 THEN d.d4_refund_cny
    WHEN 7 THEN d.d7_refund_cny
    WHEN 14 THEN d.d14_refund_cny
    WHEN 30 THEN d.d30_refund_cny
  END AS refund_cny,
  CASE w.window_days
    WHEN 1 THEN d.d1_refund_users
    WHEN 4 THEN d.d4_refund_users
    WHEN 7 THEN d.d7_refund_users
    WHEN 14 THEN d.d14_refund_users
    WHEN 30 THEN d.d30_refund_users
  END AS refund_users
FROM (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COUNT(*) AS first_paywall_userid_cnt,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
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
  FROM (
    SELECT userid, first_paywall_dt_bj, first_paywall_ts
    FROM (
      SELECT
        userid,
        first_paywall_dt_bj,
        first_paywall_ts,
        ROW_NUMBER() OVER (
          PARTITION BY userid, first_paywall_dt_bj
          ORDER BY first_paywall_ts ASC, device_id ASC
        ) AS rn
      FROM immdata.imm_paywall_first_device
      WHERE userid IS NOT NULL
        AND first_paywall_dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
    ) t
    WHERE rn = 1
  ) f
  LEFT JOIN (
    SELECT
      o.userid,
      o.createtime,
      CASE
        WHEN COALESCE(o.amountpaid, 0) <= 0 THEN 0.0
        WHEN UPPER(COALESCE(o.currency, '')) IN ('CNY', 'RMB') THEN o.amountpaid / 100.0
        ELSE o.amountpaid * COALESCE(er.exchangerate, 0) / 100.0
      END AS amount_cny,
      CASE WHEN o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_paid_amt,
      CASE WHEN o.orderstatus = 'refunded' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_refund
    FROM immdata.imt_subscriptiongoodsorder o
    LEFT JOIN immdata.exchangerates er
      ON UPPER(COALESCE(o.currency, '')) = UPPER(COALESCE(er.currency, ''))
    WHERE COALESCE(o.isdeleted, 0) = 0
      AND o.userid IS NOT NULL
      AND o.createtime >= DATEADD(hour, -8, DATEADD(day, -120, CAST(DATEADD(hour, 8, NOW()) AS DATE)))
  ) o ON o.userid = f.userid
  GROUP BY f.first_paywall_dt_bj
) d
CROSS JOIN (
  SELECT 1 AS window_days
  UNION ALL SELECT 4
  UNION ALL SELECT 7
  UNION ALL SELECT 14
  UNION ALL SELECT 30
) w


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_expected
-- 用途：基准预期付费 vs 实际（简中 1.08% / 其他 0.89%；母语分桶）
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  first_paywall_uv,
  first_paywall_uv_zh_cn,
  first_paywall_uv_other,
  expected_paid_users,
  paid_users,
  paid_users * 1.0 / NULLIF(expected_paid_users, 0) AS paid_vs_expected
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_kpi_window
-- 用途：近窗卡片（加项；无 dt_bj）
-- ---------------------------------------------------------------------------
SELECT
  SUM(first_paywall_uv) AS first_paywall_uv_sum,
  SUM(first_paywall_userid_cnt) AS first_paywall_userid_sum,
  SUM(checkout_users) * 1.0
    / NULLIF(SUM(first_paywall_userid_cnt), 0) AS checkout_rate,
  SUM(trial_users) * 1.0
    / NULLIF(SUM(first_paywall_userid_cnt), 0) AS trial_rate,
  SUM(paid_users) * 1.0
    / NULLIF(SUM(first_paywall_userid_cnt), 0) AS paid_rate_30d,
  SUM(d7_paid_users) * 1.0
    / NULLIF(SUM(first_paywall_userid_cnt), 0) AS d7_pay_rate,
  SUM(d30_revenue_cny) AS d30_revenue_cny,
  SUM(d30_revenue_cny)
    / NULLIF(SUM(first_paywall_uv), 0) AS arpu_30d,
  SUM(d30_revenue_cny)
    / NULLIF(SUM(paid_users), 0) AS arppu_30d,
  SUM(paid_users) * 1.0
    / NULLIF(SUM(expected_paid_users), 0) AS paid_vs_expected,
  SUM(paywall_uv) * 1.0
    / NULLIF(SUM(dau), 0) AS paywall_rate_note_day_uv_ratio
FROM immdata.imm_paywall_daily_kpi
WHERE dt_bj >= DATEADD(day, -30, CAST(DATEADD(hour, 8, NOW()) AS DATE));


-- =============================================================================
-- B. 挂板主读：宽表（每维一列 → 六个 Dashboard Filter）
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_wide_cohort
-- 用途：cohort 漏斗 + Part2 收入/退款 · 六维 Filter（空=全量；多选=交集）
-- 粒度：每行 = dt_bj × 六维
-- 收入：finished 且 amountpaid>0 → CNY；退款：refunded 整单，createtime 在触墙后 N 天内
-- 注意：checkout 与 orders 分开聚合，禁止同层双 LEFT JOIN（金额会被放大）
-- ---------------------------------------------------------------------------
WITH orders AS (
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
    AND o.createtime >= DATEADD(hour, -8, DATEADD(day, -120, CAST(DATEADD(hour, 8, NOW()) AS DATE)))
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= DATEADD(hour, -8, DATEADD(day, -120, CAST(DATEADD(hour, 8, NOW()) AS DATE)))
),
base AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COALESCE(f.ab_tag, 'other') AS ab_tag,
    COALESCE(f.exp_group, '(unset)') AS exp_group,
    COALESCE(f.lang_bucket, 'other') AS lang_bucket,
    COALESCE(f.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(f.campaign, ''), '(null)') AS campaign,
    COALESCE(NULLIF(f.install_from, ''), '(null)') AS install_from,
    COUNT(DISTINCT f.device_id) AS first_paywall_uv,
    COUNT(DISTINCT f.userid) AS first_paywall_userid_cnt
  FROM immdata.imm_paywall_first_device f
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
chk AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COALESCE(f.ab_tag, 'other') AS ab_tag,
    COALESCE(f.exp_group, '(unset)') AS exp_group,
    COALESCE(f.lang_bucket, 'other') AS lang_bucket,
    COALESCE(f.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(f.campaign, ''), '(null)') AS campaign,
    COALESCE(NULLIF(f.install_from, ''), '(null)') AS install_from,
    COUNT(DISTINCT CASE
      WHEN c.userid IS NOT NULL
       AND c.createtime >= f.first_paywall_ts
       AND c.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN c.userid END) AS checkout_users
  FROM immdata.imm_paywall_first_device f
  LEFT JOIN checkout c ON c.userid = f.userid
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  GROUP BY 1, 2, 3, 4, 5, 6, 7
),
ord AS (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COALESCE(f.ab_tag, 'other') AS ab_tag,
    COALESCE(f.exp_group, '(unset)') AS exp_group,
    COALESCE(f.lang_bucket, 'other') AS lang_bucket,
    COALESCE(f.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(f.campaign, ''), '(null)') AS campaign,
    COALESCE(NULLIF(f.install_from, ''), '(null)') AS install_from,
    COUNT(DISTINCT CASE
      WHEN o.is_trial = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS trial_users,
    COUNT(DISTINCT CASE
      WHEN o.is_paid = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 4, f.first_paywall_ts)
      THEN o.userid END) AS d4_paid_users,
    COUNT(DISTINCT CASE
      WHEN o.is_paid = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 7, f.first_paywall_ts)
      THEN o.userid END) AS d7_paid_users,
    COUNT(DISTINCT CASE
      WHEN o.is_paid = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS paid_users,
    SUM(CASE
      WHEN o.is_paid = 1 AND COALESCE(o.amount_cny, 0) > 0
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 1, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d1_revenue_cny,
    SUM(CASE
      WHEN o.is_paid = 1 AND COALESCE(o.amount_cny, 0) > 0
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 4, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d4_revenue_cny,
    SUM(CASE
      WHEN o.is_paid = 1 AND COALESCE(o.amount_cny, 0) > 0
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 7, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d7_revenue_cny,
    SUM(CASE
      WHEN o.is_paid = 1 AND COALESCE(o.amount_cny, 0) > 0
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 14, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d14_revenue_cny,
    SUM(CASE
      WHEN o.is_paid = 1 AND COALESCE(o.amount_cny, 0) > 0
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d30_revenue_cny,
    COUNT(DISTINCT CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 1, f.first_paywall_ts)
      THEN o.userid END) AS d1_refund_users,
    COUNT(DISTINCT CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 4, f.first_paywall_ts)
      THEN o.userid END) AS d4_refund_users,
    COUNT(DISTINCT CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 7, f.first_paywall_ts)
      THEN o.userid END) AS d7_refund_users,
    COUNT(DISTINCT CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 14, f.first_paywall_ts)
      THEN o.userid END) AS d14_refund_users,
    COUNT(DISTINCT CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.userid END) AS d30_refund_users,
    SUM(CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 1, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d1_refund_cny,
    SUM(CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 4, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d4_refund_cny,
    SUM(CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 7, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d7_refund_cny,
    SUM(CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 14, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d14_refund_cny,
    SUM(CASE
      WHEN o.is_refund = 1
       AND o.createtime >= f.first_paywall_ts
       AND o.createtime < DATEADD(day, 30, f.first_paywall_ts)
      THEN o.amount_cny ELSE 0 END) AS d30_refund_cny
  FROM immdata.imm_paywall_first_device f
  LEFT JOIN orders o ON o.userid = f.userid
  WHERE f.first_paywall_dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
  GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
  b.dt_bj,
  b.ab_tag,
  b.exp_group,
  b.lang_bucket,
  b.platform_type,
  b.campaign,
  b.install_from,
  b.first_paywall_uv,
  b.first_paywall_userid_cnt,
  COALESCE(c.checkout_users, 0) AS checkout_users,
  COALESCE(o.trial_users, 0) AS trial_users,
  COALESCE(o.d4_paid_users, 0) AS d4_paid_users,
  COALESCE(o.d7_paid_users, 0) AS d7_paid_users,
  COALESCE(o.paid_users, 0) AS paid_users,
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
LEFT JOIN chk c
  ON c.dt_bj = b.dt_bj AND c.ab_tag = b.ab_tag AND c.exp_group = b.exp_group
 AND c.lang_bucket = b.lang_bucket AND c.platform_type = b.platform_type
 AND c.campaign = b.campaign AND c.install_from = b.install_from
LEFT JOIN ord o
  ON o.dt_bj = b.dt_bj AND o.ab_tag = b.ab_tag AND o.exp_group = b.exp_group
 AND o.lang_bucket = b.lang_bucket AND o.platform_type = b.platform_type
 AND o.campaign = b.campaign AND o.install_from = b.install_from
;



-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_wide_money_window
-- 用途：Part2 · 折线 + 六维 + 窗长；窗长单选默认 30
-- 口径：同 kpi_money_window；禁止 WITH
-- ---------------------------------------------------------------------------
SELECT
  d.dt_bj,
  d.ab_tag,
  d.exp_group,
  d.lang_bucket,
  d.platform_type,
  d.campaign,
  d.install_from,
  d.first_paywall_userid_cnt,
  w.window_days,
  CASE w.window_days
    WHEN 1 THEN d.d1_revenue_cny
    WHEN 4 THEN d.d4_revenue_cny
    WHEN 7 THEN d.d7_revenue_cny
    WHEN 14 THEN d.d14_revenue_cny
    WHEN 30 THEN d.d30_revenue_cny
  END AS revenue_cny,
  CASE w.window_days
    WHEN 1 THEN d.d1_refund_cny
    WHEN 4 THEN d.d4_refund_cny
    WHEN 7 THEN d.d7_refund_cny
    WHEN 14 THEN d.d14_refund_cny
    WHEN 30 THEN d.d30_refund_cny
  END AS refund_cny,
  CASE w.window_days
    WHEN 1 THEN d.d1_refund_users
    WHEN 4 THEN d.d4_refund_users
    WHEN 7 THEN d.d7_refund_users
    WHEN 14 THEN d.d14_refund_users
    WHEN 30 THEN d.d30_refund_users
  END AS refund_users
FROM (
  SELECT
    f.first_paywall_dt_bj AS dt_bj,
    COALESCE(f.ab_tag, 'other') AS ab_tag,
    COALESCE(f.exp_group, '(unset)') AS exp_group,
    COALESCE(f.lang_bucket, 'other') AS lang_bucket,
    COALESCE(f.platform_type, '(null)') AS platform_type,
    COALESCE(NULLIF(f.campaign, ''), '(null)') AS campaign,
    COALESCE(NULLIF(f.install_from, ''), '(null)') AS install_from,
    COUNT(*) AS first_paywall_userid_cnt,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 1, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d1_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 4, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d4_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 7, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d7_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
      AND o.createtime < DATEADD(day, 14, f.first_paywall_ts) THEN o.amount_cny ELSE 0 END) AS d14_revenue_cny,
    SUM(CASE WHEN o.is_paid_amt = 1 AND o.createtime >= f.first_paywall_ts
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
  FROM (
    SELECT
      userid,
      first_paywall_dt_bj,
      first_paywall_ts,
      ab_tag,
      exp_group,
      lang_bucket,
      platform_type,
      campaign,
      install_from
    FROM (
      SELECT
        userid,
        first_paywall_dt_bj,
        first_paywall_ts,
        ab_tag,
        exp_group,
        lang_bucket,
        platform_type,
        campaign,
        install_from,
        ROW_NUMBER() OVER (
          PARTITION BY userid, first_paywall_dt_bj
          ORDER BY first_paywall_ts ASC, device_id ASC
        ) AS rn
      FROM immdata.imm_paywall_first_device
      WHERE userid IS NOT NULL
        AND first_paywall_dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
    ) t
    WHERE rn = 1
  ) f
  LEFT JOIN (
    SELECT
      o.userid,
      o.createtime,
      CASE
        WHEN COALESCE(o.amountpaid, 0) <= 0 THEN 0.0
        WHEN UPPER(COALESCE(o.currency, '')) IN ('CNY', 'RMB') THEN o.amountpaid / 100.0
        ELSE o.amountpaid * COALESCE(er.exchangerate, 0) / 100.0
      END AS amount_cny,
      CASE WHEN o.orderstatus = 'finished' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_paid_amt,
      CASE WHEN o.orderstatus = 'refunded' AND COALESCE(o.amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_refund
    FROM immdata.imt_subscriptiongoodsorder o
    LEFT JOIN immdata.exchangerates er
      ON UPPER(COALESCE(o.currency, '')) = UPPER(COALESCE(er.currency, ''))
    WHERE COALESCE(o.isdeleted, 0) = 0
      AND o.userid IS NOT NULL
      AND o.createtime >= DATEADD(hour, -8, DATEADD(day, -120, CAST(DATEADD(hour, 8, NOW()) AS DATE)))
  ) o ON o.userid = f.userid
  GROUP BY
    f.first_paywall_dt_bj,
    COALESCE(f.ab_tag, 'other'),
    COALESCE(f.exp_group, '(unset)'),
    COALESCE(f.lang_bucket, 'other'),
    COALESCE(f.platform_type, '(null)'),
    COALESCE(NULLIF(f.campaign, ''), '(null)'),
    COALESCE(NULLIF(f.install_from, ''), '(null)')
) d
CROSS JOIN (
  SELECT 1 AS window_days
  UNION ALL SELECT 4
  UNION ALL SELECT 7
  UNION ALL SELECT 14
  UNION ALL SELECT 30
) w


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_wide_hit
-- 前置：写仓执行 task6_paywall_wide_etl_patch.sql → imm_paywall_daily_wide_hit
-- 用途：图1 每日触墙 · 六维 Filter
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  install_from,
  platform_type,
  campaign,
  lang_bucket,
  ab_tag,
  exp_group,
  paywall_uv
FROM immdata.imm_paywall_daily_wide_hit
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj, paywall_uv DESC;


-- ---------------------------------------------------------------------------
-- 数据集名：ds_paywall_wide_paywall_rate
-- 前置：写仓执行 task6_paywall_wide_etl_patch.sql + dedupe_fix + wide_rate_dau_patch
--       → imm_paywall_daily_wide_paywall_rate（六维 dau）
-- 用途：图8 触墙率 · Metrics = SUM(paywall_uv)/SUM(dau)
-- ---------------------------------------------------------------------------
SELECT
  dt_bj,
  install_from,
  platform_type,
  campaign,
  lang_bucket,
  ab_tag,
  exp_group,
  paywall_uv,
  dau,
  paywall_rate
FROM immdata.imm_paywall_daily_wide_paywall_rate
WHERE dt_bj >= DATEADD(day, -90, CAST(DATEADD(hour, 8, NOW()) AS DATE))
ORDER BY dt_bj, paywall_uv DESC;
