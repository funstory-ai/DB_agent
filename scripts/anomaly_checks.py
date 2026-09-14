"""异常数据标准检查（可单独跑，便于审查占比）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query


def run(sql: str):
    cols, rows = query(sql)
    print("COLS", cols)
    for r in rows:
        print(r)
    return cols, rows


def check_deviceinfo_dups():
    print("\n=== P015 deviceinfo (userid,deviceid) 重复 ===")
    run(
        """
        WITH base AS (
          SELECT userid, deviceid, COUNT(*) AS cnt
          FROM immdata.imt_deviceinfo
          WHERE COALESCE(isdeleted,0)=0
            AND userid IS NOT NULL
            AND deviceid IS NOT NULL AND deviceid <> ''
          GROUP BY userid, deviceid
        )
        SELECT
          COUNT(*) AS distinct_pairs,
          SUM(CASE WHEN cnt > 1 THEN 1 ELSE 0 END) AS dup_pairs,
          ROUND(SUM(CASE WHEN cnt > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 4) AS dup_pair_pct,
          SUM(CASE WHEN cnt > 1 THEN cnt - 1 ELSE 0 END) AS extra_rows
        FROM base
        """
    )
    print("-- 举例 Top5 --")
    run(
        """
        SELECT userid, deviceid, COUNT(*) AS cnt,
               MIN(createtime) AS min_ct, MAX(createtime) AS max_ct, MIN(useremail) AS email
        FROM immdata.imt_deviceinfo
        WHERE COALESCE(isdeleted,0)=0
          AND userid IS NOT NULL AND deviceid IS NOT NULL AND deviceid <> ''
        GROUP BY userid, deviceid
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 5
        """
    )


def check_trial_unpaid_translate_tail():
    print("\n=== P014 试用未付费 × translate_page 头部 ===")
    run(
        """
        WITH trial_90d AS (
          SELECT DISTINCT userid
          FROM immdata.imt_subscriptiongoodsorder
          WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
            AND COALESCE(amountpaid,0)=0
            AND createtime >= DATEADD(day,-90,NOW()) AND userid IS NOT NULL
        ),
        paid_ever AS (
          SELECT DISTINCT userid
          FROM immdata.imt_subscriptiongoodsorder
          WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
            AND COALESCE(amountpaid,0)>0
        ),
        cohort AS (
          SELECT t.userid FROM trial_90d t
          LEFT JOIN paid_ever p ON t.userid=p.userid WHERE p.userid IS NULL
        ),
        user_devices AS (
          SELECT DISTINCT c.userid, d.deviceid
          FROM cohort c
          INNER JOIN immdata.imt_deviceinfo d
            ON c.userid=d.userid AND COALESCE(d.isdeleted,0)=0
           AND d.deviceid IS NOT NULL AND d.deviceid <> ''
        ),
        device_user_cnt AS (
          SELECT deviceid, COUNT(DISTINCT userid) AS users_on_device
          FROM user_devices GROUP BY deviceid
        ),
        devices AS (SELECT DISTINCT deviceid FROM user_devices),
        beh AS (
          SELECT b.device_id, COUNT(*) AS cnt
          FROM immdata.user_behaviour b
          INNER JOIN devices d ON b.device_id = d.deviceid
          WHERE b.created_ts >= DATEADD(day,-90,NOW())
            AND b.created_ts < NOW()
            AND b.event_name = 'translate_page'
          GROUP BY b.device_id
        ),
        user_agg AS (
          SELECT ud.userid,
                 SUM(COALESCE(beh.cnt,0)) AS translate_page_cnt,
                 MAX(duc.users_on_device) AS max_users_on_any_device
          FROM user_devices ud
          LEFT JOIN beh ON ud.deviceid = beh.device_id
          LEFT JOIN device_user_cnt duc ON ud.deviceid = duc.deviceid
          GROUP BY ud.userid
        )
        SELECT
          COUNT(*) AS users_with_device,
          SUM(CASE WHEN translate_page_cnt > 0 THEN 1 ELSE 0 END) AS with_translate,
          SUM(CASE WHEN translate_page_cnt >= 100000 THEN 1 ELSE 0 END) AS users_ge_100k,
          ROUND(
            SUM(CASE WHEN translate_page_cnt >= 100000 THEN 1 ELSE 0 END) * 100.0
            / NULLIF(SUM(CASE WHEN translate_page_cnt > 0 THEN 1 ELSE 0 END),0)
          , 4) AS pct_ge_100k_among_active,
          ROUND(
            SUM(CASE WHEN translate_page_cnt >= 100000 THEN translate_page_cnt ELSE 0 END) * 100.0
            / NULLIF(SUM(translate_page_cnt),0)
          , 2) AS pct_events_from_ge_100k,
          SUM(CASE WHEN max_users_on_any_device >= 2 THEN 1 ELSE 0 END) AS users_on_shared_device,
          ROUND(
            SUM(CASE WHEN max_users_on_any_device >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
          , 2) AS pct_on_shared_device
        FROM user_agg
        """
    )
    print("-- 高活共享设备举例 --")
    run(
        """
        WITH trial_90d AS (
          SELECT DISTINCT userid
          FROM immdata.imt_subscriptiongoodsorder
          WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
            AND COALESCE(amountpaid,0)=0
            AND createtime >= DATEADD(day,-90,NOW()) AND userid IS NOT NULL
        ),
        paid_ever AS (
          SELECT DISTINCT userid
          FROM immdata.imt_subscriptiongoodsorder
          WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
            AND COALESCE(amountpaid,0)>0
        ),
        cohort AS (
          SELECT t.userid FROM trial_90d t
          LEFT JOIN paid_ever p ON t.userid=p.userid WHERE p.userid IS NULL
        ),
        user_devices AS (
          SELECT DISTINCT c.userid, d.deviceid
          FROM cohort c
          INNER JOIN immdata.imt_deviceinfo d
            ON c.userid=d.userid AND COALESCE(d.isdeleted,0)=0
           AND d.deviceid IS NOT NULL AND d.deviceid <> ''
        ),
        devices AS (SELECT DISTINCT deviceid FROM user_devices),
        beh AS (
          SELECT b.device_id, COUNT(*) AS cnt
          FROM immdata.user_behaviour b
          INNER JOIN devices d ON b.device_id = d.deviceid
          WHERE b.created_ts >= DATEADD(day,-90,NOW())
            AND b.created_ts < NOW()
            AND b.event_name = 'translate_page'
          GROUP BY b.device_id
        )
        SELECT beh.device_id, beh.cnt AS device_cnt,
               COUNT(DISTINCT ud.userid) AS cohort_users,
               MIN(ud.userid) AS example_uid_min,
               MAX(ud.userid) AS example_uid_max
        FROM beh
        INNER JOIN user_devices ud ON beh.device_id = ud.deviceid
        WHERE beh.cnt >= 100000
        GROUP BY beh.device_id, beh.cnt
        ORDER BY cohort_users DESC, device_cnt DESC
        LIMIT 5
        """
    )


def main():
    p = argparse.ArgumentParser(description="异常数据审查检查")
    p.add_argument(
        "--check",
        choices=["all", "p015", "p014"],
        default="all",
        help="跑哪一项检查",
    )
    args = p.parse_args()
    if args.check in ("all", "p015"):
        check_deviceinfo_dups()
    if args.check in ("all", "p014"):
        check_trial_unpaid_translate_tail()


if __name__ == "__main__":
    main()
