-- 付费墙 A/B/C/D 实验汇总（query）v3
-- 任务：docs/tasks/query_paywall_ab_20260821.md
--
-- 口径修正（相对 v1）：
--   分母 = 埋点侧新装 device（首条 translate + ab_tag + 版本 + install_day 窗）
--   deviceinfo 仅 LEFT JOIN 补 userid；禁止 INNER JOIN 把未注册踢出分母
--   主率：checkout/试用/付费 / 新装 device（完整漏斗，含未注册）
--   辅率：同指标 / 已关联 userid（注册后转化）
--   另报：注册率 = 有 userid 的 device / 新装 device
-- v3 付费分子：剔除老客续费
--   1) ordertype = iospay_renew 不计付费
--   2) anchor 之前已有 finished 订单的 userid，其付费不计（老客）
--
-- cohort：北京 2026-08-21～08-28 新装（behaviour.install_day）+ 版本 >= 1.32.6
-- 分组：A=a,b,c | B=d,e,f | C=g,h | D=i,j
-- 转化窗锚点：COALESCE(deviceinfo.installtime, 首条 translate created_ts)

WITH cohort_beh AS (
  SELECT
    device_id,
    ab_tag,
    first_ts,
    install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i', 'j') THEN 'D'
    END AS exp_group
  FROM (
    SELECT
      device_id,
      ab_tag,
      created_ts AS first_ts,
      install_day,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-20 16:00:00'
      AND created_ts < '2026-08-29 16:00:00'
      AND event_name = 'translate_page'
      AND ab_tag IS NOT NULL
      AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        version >= '1.32.6'
        OR version LIKE '1.33.%'
        OR version LIKE '1.34.%'
      )
      AND install_day >= '2026-08-21'
      AND install_day < '2026-08-29'
  ) x
  WHERE rn = 1
),
-- 每设备取一条 deviceinfo：优先有 userid、installtime 落在实验安装窗
di AS (
  SELECT
    device_id,
    userid,
    installtime
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
             AND d.installtime >= '2026-08-20 16:00:00'
             AND d.installtime < '2026-08-29 16:00:00'
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
cohort_devices AS (
  SELECT
    b.device_id,
    b.exp_group,
    b.ab_tag,
    b.first_ts,
    b.install_day,
    d.userid,
    COALESCE(
      CASE
        WHEN d.installtime >= '2026-08-20 16:00:00'
         AND d.installtime < '2026-08-29 16:00:00'
        THEN d.installtime
      END,
      b.first_ts
    ) AS anchor_ts
  FROM cohort_beh b
  LEFT JOIN di d ON d.device_id = b.device_id
),
checkout AS (
  SELECT userid, createtime
  FROM immdata.imt_checkoutsession
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND createtime >= '2026-08-20 16:00:00'
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
      THEN 1
      ELSE 0
    END AS is_trial,
    -- 付费：task6 权益，但剔除 iospay_renew（续费）
    CASE
      WHEN o.orderstatus = 'finished'
       AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
       AND (
         COALESCE(o.amountpaid, 0) > 0
         OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
         OR lower(COALESCE(o.ordertype, '')) = 'code'
       )
      THEN 1
      ELSE 0
    END AS is_paid
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.userid IS NOT NULL
    AND o.createtime >= '2026-08-20 16:00:00'
),
-- 老客：anchor 之前已有 finished 订单 → 其付费不计入新装转化
old_customer_device AS (
  SELECT DISTINCT c.device_id
  FROM cohort_devices c
  INNER JOIN immdata.imt_subscriptiongoodsorder o
    ON o.userid = c.userid
   AND COALESCE(o.isdeleted, 0) = 0
   AND o.orderstatus = 'finished'
   AND o.createtime < c.anchor_ts
  WHERE c.userid IS NOT NULL
),
cohort_funnel AS (
  SELECT
    c.device_id,
    c.userid,
    max(
      CASE
        WHEN ck.createtime >= c.anchor_ts
         AND ck.createtime < add_days(c.anchor_ts, 3)
        THEN 1 ELSE 0
      END
    ) AS checkout_3d,
    max(
      CASE
        WHEN ck.createtime >= c.anchor_ts
         AND ck.createtime < add_days(c.anchor_ts, 7)
        THEN 1 ELSE 0
      END
    ) AS checkout_7d,
    max(
      CASE
        WHEN o.is_trial = 1
         AND o.createtime >= c.anchor_ts
         AND o.createtime < add_days(c.anchor_ts, 3)
        THEN 1 ELSE 0
      END
    ) AS trial_3d,
    max(
      CASE
        WHEN o.is_trial = 1
         AND o.createtime >= c.anchor_ts
         AND o.createtime < add_days(c.anchor_ts, 7)
        THEN 1 ELSE 0
      END
    ) AS trial_7d,
    max(
      CASE
        WHEN o.is_paid = 1
         AND old.device_id IS NULL
         AND o.createtime >= c.anchor_ts
         AND o.createtime < add_days(c.anchor_ts, 3)
        THEN 1 ELSE 0
      END
    ) AS paid_3d,
    max(
      CASE
        WHEN o.is_paid = 1
         AND old.device_id IS NULL
         AND o.createtime >= c.anchor_ts
         AND o.createtime < add_days(c.anchor_ts, 7)
        THEN 1 ELSE 0
      END
    ) AS paid_7d
  FROM cohort_devices c
  LEFT JOIN checkout ck ON ck.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN orders o ON o.userid = c.userid AND c.userid IS NOT NULL
  LEFT JOIN old_customer_device old ON old.device_id = c.device_id
  GROUP BY 1, 2
),
reg_wall AS (
  SELECT c.device_id, max(1) AS hit_reg_wall
  FROM cohort_devices c
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = c.device_id
   AND b.created_ts >= c.anchor_ts
   AND b.created_ts < '2026-08-29 16:00:00'
   AND b.event_name = 'user_need_pro'
   AND b.trigger = 'unregisteredUsageLimitModal'
  GROUP BY 1
),
pay_wall AS (
  SELECT c.device_id, max(1) AS hit_pay_wall
  FROM cohort_devices c
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = c.device_id
   AND b.created_ts >= c.anchor_ts
   AND b.created_ts < '2026-08-29 16:00:00'
   AND b.event_name = 'user_need_pro'
   AND b.trigger = 'freeUsageLimitModal'
  GROUP BY 1
)
SELECT
  c.exp_group,
  count(DISTINCT c.device_id) AS new_devices,
  count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) AS registered_devices,
  count(DISTINCT c.userid) AS linked_userids,
  round(
    count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS register_rate_pct,
  -- 完整漏斗：分母 = 新装 device
  count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) AS checkout_3d_devices,
  round(
    count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS checkout_3d_of_device_pct,
  count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) AS trial_3d_devices,
  round(
    count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS trial_3d_of_device_pct,
  count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) AS paid_3d_devices,
  round(
    count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS paid_3d_of_device_pct,
  count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) AS paid_7d_devices,
  round(
    count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS paid_7d_of_device_pct,
  -- 注册后转化：分母 = linked userid
  count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.userid END) AS checkout_3d_users,
  round(
    count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.userid END) * 100.0
      / nullif(count(DISTINCT c.userid), 0),
    2
  ) AS checkout_3d_of_userid_pct,
  count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.userid END) AS trial_3d_users,
  round(
    count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.userid END) * 100.0
      / nullif(count(DISTINCT c.userid), 0),
    2
  ) AS trial_3d_of_userid_pct,
  count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.userid END) AS paid_3d_users,
  round(
    count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.userid END) * 100.0
      / nullif(count(DISTINCT c.userid), 0),
    2
  ) AS paid_3d_of_userid_pct,
  count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.userid END) AS paid_7d_users,
  round(
    count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.userid END) * 100.0
      / nullif(count(DISTINCT c.userid), 0),
    2
  ) AS paid_7d_of_userid_pct,
  count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) AS reg_wall_devices,
  round(
    count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS reg_wall_rate_pct,
  count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) AS pay_wall_devices,
  round(
    count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS pay_wall_rate_pct
FROM cohort_devices c
LEFT JOIN cohort_funnel cf ON cf.device_id = c.device_id
LEFT JOIN reg_wall rw ON rw.device_id = c.device_id
LEFT JOIN pay_wall pw ON pw.device_id = c.device_id
GROUP BY 1
ORDER BY 1;

-- 主看：register_rate / *_of_device_pct（完整漏斗）
-- 辅看：*_of_userid_pct（注册后转化，对应旧版口径）
-- 付费分子已剔除：iospay_renew + anchor 前已有 finished 订单的老客（v3）
-- install_day 为埋点字段，可能有噪声（P003）；未注册设备无 deviceinfo.installtime，锚点回退首条 translate
