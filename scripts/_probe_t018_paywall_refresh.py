# -*- coding: utf-8 -*-
"""T018 paywall AB refresh: last cohort week + through today."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query


def funnel_sql(
    install_start: str,
    install_end_excl: str,
    beh_start_utc: str,
    beh_end_excl_utc: str,
    label: str,
) -> str:
    """install_day in [start, end_excl); behaviour/deviceinfo windows in UTC."""
    return f"""
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
    WHERE created_ts >= '{beh_start_utc}'
      AND created_ts < '{beh_end_excl_utc}'
      AND event_name = 'translate_page'
      AND ab_tag IS NOT NULL
      AND length(trim(ab_tag)) = 1
      AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
      AND (
        version >= '1.32.6'
        OR version LIKE '1.33.%'
        OR version LIKE '1.34.%'
        OR version LIKE '1.35.%'
        OR version LIKE '1.36.%'
      )
      AND install_day >= '{install_start}'
      AND install_day < '{install_end_excl}'
  ) x
  WHERE rn = 1
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
             AND d.installtime >= '{beh_start_utc}'
             AND d.installtime < '{beh_end_excl_utc}'
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
        WHEN d.installtime >= '{beh_start_utc}'
         AND d.installtime < '{beh_end_excl_utc}'
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
    AND createtime >= '{beh_start_utc}'
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
    AND o.createtime >= '{beh_start_utc}'
),
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
    max(CASE WHEN ck.createtime >= c.anchor_ts
              AND ck.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS checkout_3d,
    max(CASE WHEN ck.createtime >= c.anchor_ts
              AND ck.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS checkout_7d,
    max(CASE WHEN o.is_trial = 1 AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS trial_3d,
    max(CASE WHEN o.is_trial = 1 AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS trial_7d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS paid_3d,
    max(CASE WHEN o.is_paid = 1 AND old.device_id IS NULL
              AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 7) THEN 1 ELSE 0 END) AS paid_7d
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
   AND b.created_ts < '{beh_end_excl_utc}'
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
   AND b.created_ts < '{beh_end_excl_utc}'
   AND b.event_name = 'user_need_pro'
   AND b.trigger = 'freeUsageLimitModal'
  GROUP BY 1
)
SELECT
  '{label}' AS slice,
  c.exp_group,
  count(DISTINCT c.device_id) AS new_devices,
  count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) AS registered_devices,
  round(
    count(DISTINCT CASE WHEN c.userid IS NOT NULL THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS register_rate_pct,
  count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) AS checkout_3d,
  round(
    count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS checkout_3d_pct,
  count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) AS trial_3d,
  round(
    count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS trial_3d_pct,
  count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) AS paid_3d,
  round(
    count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS paid_3d_pct,
  count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) AS paid_7d,
  round(
    count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS paid_7d_pct,
  count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) AS reg_wall,
  round(
    count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS reg_wall_pct,
  count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) AS pay_wall,
  round(
    count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0),
    2
  ) AS pay_wall_pct
FROM cohort_devices c
LEFT JOIN cohort_funnel cf ON cf.device_id = c.device_id
LEFT JOIN reg_wall rw ON rw.device_id = c.device_id
LEFT JOIN pay_wall pw ON pw.device_id = c.device_id
GROUP BY 1, 2
ORDER BY 2
"""


def show(title: str, sql: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print(cols, flush=True)
    for r in rows:
        print(r, flush=True)


# 观察截止：北京 2026-09-04 结束 = UTC 2026-09-04 16:00
OBS_END = "2026-09-04 16:00:00"
BEH_START = "2026-08-20 16:00:00"

# 1) 原 cohort（搁置时口径：08-21～08-28），转化/触墙窗已拉到今天 → 7d 已跑满
show(
    "1 last-week cohort 08-21~08-28 (obs through 09-04)",
    funnel_sql("2026-08-21", "2026-08-29", BEH_START, OBS_END, "cohort_0821_0828"),
)

# 2) 扩到今天：install_day 到 09-04（含）；近几天 7d 未满窗
show(
    "2 through-today cohort 08-21~09-04 (obs through 09-04)",
    funnel_sql("2026-08-21", "2026-09-05", BEH_START, OBS_END, "cohort_0821_0904"),
)

# 3) 近一周新装（08-29～09-04）单独看增量
show(
    "3 recent week install 08-29~09-04",
    funnel_sql("2026-08-29", "2026-09-05", BEH_START, OBS_END, "cohort_0829_0904"),
)
