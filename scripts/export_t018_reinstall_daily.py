# -*- coding: utf-8 -*-
"""Daily reinstall-ish volume: P034 new install + old account (1d buffer)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

# 近 30 个北京自然日（行为窗覆盖 UTC）
SQL_DAILY = r"""
WITH act AS (
  SELECT
    device_id,
    created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS DATE) AS act_bj_day
  FROM (
    SELECT
      device_id, created_ts, ex_int_arg1,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-29 16:00:00'
      AND created_ts < '2026-09-29 16:00:00'
      AND event_name = 'translate_page'
      AND is_new_user_today = '1'
      AND (
        version >= '1.32.6'
        OR version LIKE '1.33.%'
        OR version LIKE '1.34.%'
        OR version LIKE '1.35.%'
        OR version LIKE '1.36.%'
      )
  ) t
  WHERE rn = 1
    AND CAST(to_date(add_hours(created_ts, 8)) AS DATE) >= DATE '2026-08-30'
    AND CAST(to_date(add_hours(created_ts, 8)) AS DATE) < DATE '2026-09-29'
),
di AS (
  SELECT device_id, userid
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY
          CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END,
          d.installtime
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM act) a ON a.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0
      AND d.installtime > '1970-01-02'
  ) x
  WHERE rn = 1
),
linked AS (
  SELECT
    a.act_bj_day,
    a.device_id,
    a.act_ts,
    COALESCE(d.userid, a.act_uid) AS uid
  FROM act a
  LEFT JOIN di d ON d.device_id = a.device_id
),
flagged AS (
  SELECT
    l.act_bj_day,
    l.device_id,
    l.uid,
    l.act_ts
  FROM linked l
  INNER JOIN immdata.imt_userinfo u
    ON u.id = l.uid AND COALESCE(u.isdeleted, 0) = 0
  WHERE l.uid IS NOT NULL
    AND u.createtime < date_add(day, -1, l.act_ts)
),
earliest_other AS (
  -- 账号下是否另有更早设备（更像换机/重装，而非纯账号漂移）
  SELECT
    f.act_bj_day,
    f.device_id,
    f.uid,
    max(CASE
          WHEN d.deviceid IS NOT NULL AND d.deviceid <> f.device_id
           AND COALESCE(d.installtime, d.createtime) < f.act_ts
          THEN 1 ELSE 0
        END) AS has_earlier_other_dev
  FROM flagged f
  LEFT JOIN immdata.imt_deviceinfo d
    ON d.userid = f.uid AND COALESCE(d.isdeleted, 0) = 0
  GROUP BY 1, 2, 3
)
SELECT
  a.act_bj_day,
  count(DISTINCT a.device_id) AS activate_uv,
  count(DISTINCT f.device_id) AS old_acct_device_uv,
  count(DISTINCT f.uid) AS old_acct_userid_uv,
  round(count(DISTINCT f.device_id) * 100.0 / nullif(count(DISTINCT a.device_id), 0), 2)
    AS old_acct_device_pct,
  count(DISTINCT CASE WHEN e.has_earlier_other_dev = 1 THEN f.device_id END)
    AS reinstall_like_device_uv,
  count(DISTINCT CASE WHEN e.has_earlier_other_dev = 1 THEN f.uid END)
    AS reinstall_like_userid_uv,
  round(
    count(DISTINCT CASE WHEN e.has_earlier_other_dev = 1 THEN f.device_id END) * 100.0
      / nullif(count(DISTINCT a.device_id), 0), 2
  ) AS reinstall_like_pct
FROM act a
LEFT JOIN flagged f ON f.device_id = a.device_id AND f.act_bj_day = a.act_bj_day
LEFT JOIN earliest_other e ON e.device_id = f.device_id
GROUP BY 1
ORDER BY 1
"""

# 同一 userid 在窗内命中 ≥2 个「老号新装」设备 → 反复
SQL_REPEAT = r"""
WITH act AS (
  SELECT
    device_id,
    created_ts AS act_ts,
    TRY_CAST(ex_int_arg1 AS BIGINT) AS act_uid,
    CAST(to_date(add_hours(created_ts, 8)) AS DATE) AS act_bj_day
  FROM (
    SELECT
      device_id, created_ts, ex_int_arg1,
      row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-08-29 16:00:00'
      AND created_ts < '2026-09-29 16:00:00'
      AND event_name = 'translate_page'
      AND is_new_user_today = '1'
      AND (
        version >= '1.32.6'
        OR version LIKE '1.33.%'
        OR version LIKE '1.34.%'
        OR version LIKE '1.35.%'
        OR version LIKE '1.36.%'
      )
  ) t
  WHERE rn = 1
    AND CAST(to_date(add_hours(created_ts, 8)) AS DATE) >= DATE '2026-08-30'
    AND CAST(to_date(add_hours(created_ts, 8)) AS DATE) < DATE '2026-09-29'
),
di AS (
  SELECT device_id, userid
  FROM (
    SELECT
      d.deviceid AS device_id,
      d.userid,
      row_number() OVER (
        PARTITION BY d.deviceid
        ORDER BY CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END, d.installtime
      ) AS rn
    FROM immdata.imt_deviceinfo d
    INNER JOIN (SELECT DISTINCT device_id FROM act) a ON a.device_id = d.deviceid
    WHERE COALESCE(d.isdeleted, 0) = 0 AND d.installtime > '1970-01-02'
  ) x WHERE rn = 1
),
flagged AS (
  SELECT
    a.act_bj_day,
    a.device_id,
    COALESCE(d.userid, a.act_uid) AS uid,
    a.act_ts
  FROM act a
  LEFT JOIN di d ON d.device_id = a.device_id
  INNER JOIN immdata.imt_userinfo u
    ON u.id = COALESCE(d.userid, a.act_uid) AND COALESCE(u.isdeleted, 0) = 0
  WHERE COALESCE(d.userid, a.act_uid) IS NOT NULL
    AND u.createtime < date_add(day, -1, a.act_ts)
),
uid_dev AS (
  SELECT uid, count(DISTINCT device_id) AS n_dev, count(DISTINCT act_bj_day) AS n_days
  FROM flagged
  GROUP BY uid
)
SELECT
  count(*) AS old_acct_uids_in_window,
  sum(IF(n_dev >= 2, 1, 0)) AS uids_ge2_devices,
  sum(IF(n_dev >= 3, 1, 0)) AS uids_ge3_devices,
  sum(IF(n_days >= 2, 1, 0)) AS uids_ge2_days,
  max(n_dev) AS max_devices_per_uid,
  round(avg(n_dev), 3) AS avg_devices_per_uid
FROM uid_dev
"""


def main() -> None:
    print("=== daily P034 activate + old-acct / reinstall-like ===", flush=True)
    cols, rows = query(SQL_DAILY)
    print(
        f"{'day':12} {'act':>8} {'oldDev':>8} {'oldUid':>8} {'old%':>7} "
        f"{'reDev':>8} {'reUid':>8} {'re%':>7}",
        flush=True,
    )
    tot_act = tot_old = tot_re = 0
    for r in rows:
        d = dict(zip(cols, r))
        day = str(d["act_bj_day"])[:10]
        act = int(d["activate_uv"])
        old = int(d["old_acct_device_uv"] or 0)
        re_ = int(d["reinstall_like_device_uv"] or 0)
        tot_act += act
        tot_old += old
        tot_re += re_
        print(
            f"{day:12} {act:8d} {old:8d} {int(d['old_acct_userid_uv'] or 0):8d} "
            f"{float(d['old_acct_device_pct']):6.2f}% "
            f"{re_:8d} {int(d['reinstall_like_userid_uv'] or 0):8d} "
            f"{float(d['reinstall_like_pct']):6.2f}%",
            flush=True,
        )
    n = len(rows) or 1
    print(
        f"\n近{n}日日均: 激活={tot_act/n:.0f}, "
        f"老号新装设备={tot_old/n:.0f} ({tot_old*100/tot_act:.1f}%), "
        f"有更早设备的重装样={tot_re/n:.0f} ({tot_re*100/tot_act:.1f}%)",
        flush=True,
    )

    print("\n=== same userid multi new-install devices (window) ===", flush=True)
    cols, rows = query(SQL_REPEAT)
    print(dict(zip(cols, rows[0])), flush=True)


if __name__ == "__main__":
    main()
