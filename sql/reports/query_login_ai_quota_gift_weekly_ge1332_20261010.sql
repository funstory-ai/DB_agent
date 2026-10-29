-- T062 / T060 登录赠送额度：P034 激活自然周漏斗（A/B/C/I/J）+ gift
-- **P040 语义化 version >= 1.33.2** + 双口径；**新增：耗尽去付费 → 付费**（条件转化÷去付费UV）
-- asof 北京 2026-10-10；任务：docs/tasks/query_login_ai_quota_gift_exhausted_pay_20261010.md

WITH slice_specs AS (
  SELECT 'natural_week_0922_0927' AS slice, 'weekly' AS slice_type, 1 AS cohort_no,
         '2026-09-22' AS install_start, '2026-09-28' AS install_end_excl,
         '发版后至周日（6天）' AS maturity_status, DATE '2026-09-21' AS cohort_week_start
  UNION ALL
  SELECT 'natural_week_0928_1004', 'weekly', 2,
         '2026-09-28', '2026-10-05', '完整自然周（7天）', DATE '2026-09-28'
  UNION ALL
  SELECT 'natural_week_1005_partial', 'weekly', 3,
         '2026-10-05', '2026-10-11', '本周不满（6天）', DATE '2026-10-05'
  UNION ALL
  SELECT 'aggregate_0922_1010', 'aggregate', 99,
         '2026-09-22', '2026-10-11', '混合成熟度', NULL
),
params AS (
  SELECT
    DATE '2026-10-10' AS asof_bj,
    DATE '2026-09-28' AS last_closed_week_start,
    '2026-09-21 16:00:00' AS beh_start_utc,
    '2026-10-10 16:00:00' AS obs_end_utc
),
cohort_beh AS (
  SELECT
    device_id,
    ab_tag,
    first_ts,
    act_uid,
    install_day,
    to_start_of_week(to_date(install_day), 1) AS install_week_start,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
      WHEN lower(trim(ab_tag)) = 'i' THEN 'I'
      WHEN lower(trim(ab_tag)) = 'j' THEN 'J'
    END AS exp_group
  FROM (
    SELECT
      device_id,
      ab_tag,
      created_ts AS first_ts,
      TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
      -- 激活日 = 首条「当日新用户翻译」北京自然日（P034 激活）
      CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-09-21 16:00:00'
      AND created_ts < '2026-10-10 16:00:00'
      AND event_name = 'translate_page'
      AND is_new_user_today = '1'
      AND ab_tag IS NOT NULL
      AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        TRY_CAST(split_part(version, '.', 1) AS INT) > 1
        OR (
          TRY_CAST(split_part(version, '.', 1) AS INT) = 1
          AND (
            TRY_CAST(split_part(version, '.', 2) AS INT) > 33
            OR (
              TRY_CAST(split_part(version, '.', 2) AS INT) = 33
              AND TRY_CAST(split_part(version, '.', 3) AS INT) >= 2
            )
          )
        )
      )
  ) x
  WHERE rn = 1
    AND install_day >= '2026-09-22'
    AND install_day < '2026-10-11'
),
di AS (
  SELECT device_id, userid, installtime
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      d.installtime,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY
          CASE
            WHEN d.userid IS NOT NULL
             AND d.installtime >= '2026-09-21 16:00:00'
             AND d.installtime < '2026-10-10 16:00:00'
            THEN 0
            WHEN d.userid IS NOT NULL THEN 1
            ELSE 2
          END,
          d.installtime
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM cohort_beh) c
      ON c.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0
      AND d.installtime > '1970-01-02'
  ) t
  WHERE rn = 1
),
base_devices AS (
  SELECT
    b.device_id,
    b.exp_group,
    b.ab_tag,
    b.first_ts,
    b.act_uid,
    b.install_day,
    b.install_week_start,
    d.userid,
    COALESCE(
      CASE
        WHEN d.installtime >= '2026-09-21 16:00:00'
         AND d.installtime < '2026-10-10 16:00:00'
        THEN d.installtime
      END,
      b.first_ts
    ) AS anchor_ts
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
claim_uid AS (
  SELECT
    g.device_id,
    min(TRY_CAST(g.ex_int_arg1 AS BIGINT)) AS claim_uid
  FROM immdata.user_behaviour g
  INNER JOIN (SELECT DISTINCT device_id FROM base_devices) b
    ON b.device_id = g.device_id
  WHERE g.created_ts >= '2026-09-21 16:00:00'
    AND g.created_ts < '2026-10-10 16:00:00'
    AND g.event_name = 'login_ai_quota_gift_claim_success'
    AND g.ex_int_arg1 IS NOT NULL
  GROUP BY 1
),
uid_candidates AS (
  SELECT device_id, userid AS uid, first_ts
  FROM base_devices
  WHERE userid IS NOT NULL
  UNION
  SELECT device_id, act_uid AS uid, first_ts
  FROM base_devices
  WHERE act_uid IS NOT NULL
  UNION
  SELECT b.device_id, c.claim_uid AS uid, b.first_ts
  FROM base_devices b
  INNER JOIN claim_uid c ON c.device_id = b.device_id
  WHERE c.claim_uid IS NOT NULL
),
old_acct_device AS (
  -- 老号：账号创建早于激活超过 1 天（缓冲内视为同会话/延迟，不算老号）
  SELECT DISTINCT u.device_id
  FROM uid_candidates u
  INNER JOIN immdata.imt_userinfo ui
    ON ui.id = u.uid
   AND COALESCE(ui.isdeleted, 0) = 0
  WHERE ui.createtime < date_add(day, -1, u.first_ts)
),
metric_scopes AS (
  SELECT 'A_all' AS metric_scope
  UNION ALL
  SELECT 'B_excl_old_acct' AS metric_scope
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= '2026-09-21 16:00:00'
    AND createtime < '2026-10-10 16:00:00'
),
orders AS (
  SELECT
    o.userid,
    o.createtime,
    CASE
      WHEN o.orderstatus = 'finished'
       AND COALESCE(o.amountpaid, 0) = 0
       AND COALESCE(CAST(o.subscriptiongoodssnap AS STRING), '')
           NOT LIKE '%"SubscriptionType":"onetime%'
       AND lower(COALESCE(o.ordertype, '')) <> 'code'
      THEN 1 ELSE 0
    END AS is_trial,
    CASE
      WHEN o.orderstatus = 'finished'
       AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
       AND (
         COALESCE(o.amountpaid, 0) > 0
         OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
         OR lower(COALESCE(o.ordertype, '')) = 'code'
       )
      THEN 1 ELSE 0
    END AS is_paid
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.userid IS NOT NULL
    AND o.createtime >= '2026-09-21 16:00:00'
    AND o.createtime < '2026-10-10 16:00:00'
),
old_customer_device AS (
  SELECT DISTINCT c.device_id
  FROM base_devices c
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid
   AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished'
   AND o.createtime < c.anchor_ts
  WHERE c.userid IS NOT NULL
),
device_funnel AS (
  SELECT
    c.device_id,
    max(CASE WHEN ck.createtime >= c.anchor_ts
              AND ck.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS checkout_3d,
    max(CASE WHEN o.is_trial = 1
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS trial_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS paid_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS paid_7d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < '2026-10-10 16:00:00' THEN 1 ELSE 0 END) AS paid_to_asof
  FROM base_devices c
  LEFT JOIN checkout ck ON ck.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN orders o ON o.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN old_customer_device old ON old.device_id = c.device_id
  GROUP BY 1
),
-- 周活跃：仅 translate_page；收窄到可能作为 W1～W4 的已闭合周（<= last_closed_week_start）
week_active AS (
  SELECT DISTINCT w.device_id, w.week_start_day
  FROM immdata.imm_device_event_by_utf8_week w
  INNER JOIN (SELECT DISTINCT device_id FROM base_devices) d
    ON d.device_id = w.device_id
  WHERE w.event_name = 'translate_page'
    AND w.week_start_day >= DATE '2026-09-21'
    AND w.week_start_day <= DATE '2026-09-28'
),
device_ret AS (
  SELECT
    c.device_id,
    c.install_week_start AS w0,
    max(CASE WHEN a.week_start_day = date_add(day, 7, c.install_week_start) THEN 1 ELSE 0 END) AS r1,
    max(CASE WHEN a.week_start_day = date_add(day, 14, c.install_week_start) THEN 1 ELSE 0 END) AS r2,
    max(CASE WHEN a.week_start_day = date_add(day, 21, c.install_week_start) THEN 1 ELSE 0 END) AS r3,
    max(CASE WHEN a.week_start_day = date_add(day, 28, c.install_week_start) THEN 1 ELSE 0 END) AS r4
  FROM base_devices c
  LEFT JOIN week_active a
    ON a.device_id = c.device_id
   AND a.week_start_day >= date_add(day, 7, c.install_week_start)
   AND a.week_start_day <= date_add(day, 28, c.install_week_start)
  GROUP BY 1, 2
),
cohort_slices AS (
  SELECT
    ms.metric_scope,
    s.slice,
    s.slice_type,
    s.cohort_no,
    s.install_start,
    s.install_end_excl,
    s.maturity_status,
    s.cohort_week_start,
    c.device_id,
    c.userid,
    c.exp_group,
    c.install_week_start
  FROM base_devices c
  INNER JOIN slice_specs s
    ON c.install_day >= s.install_start
   AND c.install_day < s.install_end_excl
  CROSS JOIN metric_scopes ms
  LEFT JOIN old_acct_device oa ON oa.device_id = c.device_id
  WHERE ms.metric_scope = 'A_all'
     OR (ms.metric_scope = 'B_excl_old_acct' AND oa.device_id IS NULL)
),
gift_hit AS (
  SELECT
    g.device_id,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_show' THEN 1 ELSE 0 END) AS login_show,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_primary_click' THEN 1 ELSE 0 END) AS login_click,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_close' THEN 1 ELSE 0 END) AS login_close,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_claim_success' THEN 1 ELSE 0 END) AS claim,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_show' THEN 1 ELSE 0 END) AS exhausted_show,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_primary_click' THEN 1 ELSE 0 END) AS exhausted_pay,
    max(CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_close' THEN 1 ELSE 0 END) AS exhausted_close,
    min(CASE
          WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_primary_click'
          THEN g.created_ts
        END) AS exhausted_pay_first_ts
  FROM immdata.user_behaviour g
  INNER JOIN (SELECT DISTINCT device_id FROM base_devices) b
    ON b.device_id = g.device_id
  WHERE g.created_ts >= '2026-09-21 16:00:00'
    AND g.created_ts < '2026-10-10 16:00:00'
    AND g.event_name IN (
      'login_ai_quota_gift_login_modal_show',
      'login_ai_quota_gift_login_modal_primary_click',
      'login_ai_quota_gift_login_modal_close',
      'login_ai_quota_gift_claim_success',
      'login_ai_quota_gift_exhausted_modal_show',
      'login_ai_quota_gift_exhausted_modal_primary_click',
      'login_ai_quota_gift_exhausted_modal_close'
    )
  GROUP BY 1
),
-- 耗尽「去付费」→付费（条件转化分子；P042：订单 createtime 可相对点击前放宽 1 天，消化落库时差）
exhausted_pay_then_paid AS (
  SELECT DISTINCT gh.device_id
  FROM gift_hit gh
  INNER JOIN base_devices b ON b.device_id = gh.device_id
  INNER JOIN orders o
    ON o.userid = b.userid
   AND o.is_paid = 1
   AND o.createtime >= date_add(day, -1, gh.exhausted_pay_first_ts)
   AND o.createtime < '2026-10-10 16:00:00'
  LEFT JOIN old_customer_device old ON old.device_id = b.device_id
  WHERE gh.exhausted_pay = 1
    AND b.userid IS NOT NULL
    AND old.device_id IS NULL
),
p AS (SELECT * FROM params)
SELECT
  c.metric_scope,
  c.slice,
  c.slice_type,
  c.cohort_no,
  c.install_start,
  c.install_end_excl,
  c.maturity_status,
  c.cohort_week_start,
  c.exp_group,
  count(DISTINCT c.device_id) AS new_devices,
  count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) AS registered_devices,
  round(
    count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS register_rate_pct,
  count(DISTINCT CASE WHEN f.checkout_3d = 1 THEN c.device_id END) AS checkout_3d,
  round(
    count(DISTINCT CASE WHEN f.checkout_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS checkout_3d_pct,
  count(DISTINCT CASE WHEN f.trial_3d = 1 THEN c.device_id END) AS trial_3d,
  round(
    count(DISTINCT CASE WHEN f.trial_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS trial_3d_pct,
  count(DISTINCT CASE WHEN f.paid_3d = 1 THEN c.device_id END) AS paid_3d,
  round(
    count(DISTINCT CASE WHEN f.paid_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_3d_pct,
  count(DISTINCT CASE WHEN f.paid_7d = 1 THEN c.device_id END) AS paid_7d,
  round(
    count(DISTINCT CASE WHEN f.paid_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_7d_pct,
  count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN c.device_id END) AS paid_to_asof,
  round(
    count(DISTINCT CASE WHEN f.paid_to_asof = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_to_asof_pct,
  count(DISTINCT CASE WHEN gh.login_show = 1 THEN c.device_id END) AS gift_login_show,
  round(
    count(DISTINCT CASE WHEN gh.login_show = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_login_show_pct,
  count(DISTINCT CASE WHEN gh.login_click = 1 THEN c.device_id END) AS gift_login_click,
  round(
    count(DISTINCT CASE WHEN gh.login_click = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_login_click_pct,
  count(DISTINCT CASE WHEN gh.login_close = 1 THEN c.device_id END) AS gift_login_close,
  round(
    count(DISTINCT CASE WHEN gh.login_close = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_login_close_pct,
  count(DISTINCT CASE WHEN gh.claim = 1 THEN c.device_id END) AS gift_claim,
  round(
    count(DISTINCT CASE WHEN gh.claim = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_claim_pct,
  count(DISTINCT CASE WHEN gh.exhausted_show = 1 THEN c.device_id END) AS gift_exhausted_show,
  round(
    count(DISTINCT CASE WHEN gh.exhausted_show = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_exhausted_show_pct,
  count(DISTINCT CASE WHEN gh.exhausted_pay = 1 THEN c.device_id END) AS gift_exhausted_pay,
  round(
    count(DISTINCT CASE WHEN gh.exhausted_pay = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_exhausted_pay_pct,
  count(DISTINCT CASE WHEN ep.device_id IS NOT NULL THEN c.device_id END) AS gift_exhausted_pay_then_paid,
  round(
    count(DISTINCT CASE WHEN ep.device_id IS NOT NULL THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT CASE WHEN gh.exhausted_pay = 1 THEN c.device_id END), 0), 2
  ) AS gift_exhausted_pay_then_paid_pct,
  count(DISTINCT CASE WHEN gh.exhausted_close = 1 THEN c.device_id END) AS gift_exhausted_close,
  round(
    count(DISTINCT CASE WHEN gh.exhausted_close = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS gift_exhausted_close_pct,
  -- 周同期群：整窗满才给率；汇总行：只对「该设备 Wn 已闭合」的子集计率（混成熟度）
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 7, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN count(DISTINCT CASE WHEN r.r1 = 1 THEN c.device_id END)
    WHEN c.slice_type = 'aggregate'
    THEN count(DISTINCT CASE
           WHEN date_add(day, 7, r.w0) <= (SELECT last_closed_week_start FROM p)
            AND r.r1 = 1 THEN c.device_id END)
  END AS ret_w1_devices,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 7, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN round(
           count(DISTINCT CASE WHEN r.r1 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT c.device_id), 0), 2)
    WHEN c.slice_type = 'aggregate'
    THEN round(
           count(DISTINCT CASE
             WHEN date_add(day, 7, r.w0) <= (SELECT last_closed_week_start FROM p)
              AND r.r1 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT CASE
               WHEN date_add(day, 7, r.w0) <= (SELECT last_closed_week_start FROM p)
               THEN c.device_id END), 0), 2)
  END AS ret_w1_pct,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 14, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN count(DISTINCT CASE WHEN r.r2 = 1 THEN c.device_id END)
    WHEN c.slice_type = 'aggregate'
    THEN count(DISTINCT CASE
           WHEN date_add(day, 14, r.w0) <= (SELECT last_closed_week_start FROM p)
            AND r.r2 = 1 THEN c.device_id END)
  END AS ret_w2_devices,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 14, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN round(
           count(DISTINCT CASE WHEN r.r2 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT c.device_id), 0), 2)
    WHEN c.slice_type = 'aggregate'
    THEN round(
           count(DISTINCT CASE
             WHEN date_add(day, 14, r.w0) <= (SELECT last_closed_week_start FROM p)
              AND r.r2 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT CASE
               WHEN date_add(day, 14, r.w0) <= (SELECT last_closed_week_start FROM p)
               THEN c.device_id END), 0), 2)
  END AS ret_w2_pct,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 21, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN count(DISTINCT CASE WHEN r.r3 = 1 THEN c.device_id END)
    WHEN c.slice_type = 'aggregate'
    THEN count(DISTINCT CASE
           WHEN date_add(day, 21, r.w0) <= (SELECT last_closed_week_start FROM p)
            AND r.r3 = 1 THEN c.device_id END)
  END AS ret_w3_devices,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 21, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN round(
           count(DISTINCT CASE WHEN r.r3 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT c.device_id), 0), 2)
    WHEN c.slice_type = 'aggregate'
    THEN round(
           count(DISTINCT CASE
             WHEN date_add(day, 21, r.w0) <= (SELECT last_closed_week_start FROM p)
              AND r.r3 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT CASE
               WHEN date_add(day, 21, r.w0) <= (SELECT last_closed_week_start FROM p)
               THEN c.device_id END), 0), 2)
  END AS ret_w3_pct,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 28, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN count(DISTINCT CASE WHEN r.r4 = 1 THEN c.device_id END)
    WHEN c.slice_type = 'aggregate'
    THEN count(DISTINCT CASE
           WHEN date_add(day, 28, r.w0) <= (SELECT last_closed_week_start FROM p)
            AND r.r4 = 1 THEN c.device_id END)
  END AS ret_w4_devices,
  CASE
    WHEN c.slice_type = 'weekly'
     AND date_add(day, 28, c.cohort_week_start) <= (SELECT last_closed_week_start FROM p)
    THEN round(
           count(DISTINCT CASE WHEN r.r4 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT c.device_id), 0), 2)
    WHEN c.slice_type = 'aggregate'
    THEN round(
           count(DISTINCT CASE
             WHEN date_add(day, 28, r.w0) <= (SELECT last_closed_week_start FROM p)
              AND r.r4 = 1 THEN c.device_id END) * 100.0
             / nullif(count(DISTINCT CASE
               WHEN date_add(day, 28, r.w0) <= (SELECT last_closed_week_start FROM p)
               THEN c.device_id END), 0), 2)
  END AS ret_w4_pct
FROM cohort_slices c
LEFT JOIN device_funnel f ON f.device_id = c.device_id
LEFT JOIN device_ret r ON r.device_id = c.device_id
LEFT JOIN gift_hit gh ON gh.device_id = c.device_id
LEFT JOIN exhausted_pay_then_paid ep ON ep.device_id = c.device_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
ORDER BY c.metric_scope, c.cohort_no, c.exp_group;
