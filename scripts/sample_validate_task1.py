"""Task1-ONLY sample validation (试用未付费 + 五类翻译次数).

其它任务勿复用本脚本的「翻译分层」标准（见 docs/sample_validation.md / P019）。
已知性能债：当前会全量建分层池，后续应改为从已有 Excel 抽 userid。
默认只打印对话用结论，不写抽样文件。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

N = 20  # 默认；可用命令行覆盖
SEED = 20260813

# 与 v3 相同的事件口径
EVENT_FILTER = """
  (
    (b.event_name = 'translate_page' AND b.page_type IN ('html', 'pdfReader', 'pdfProReader'))
    OR b.event_name IN (
      'translate_video_subtitle',
      'translate_image',
      'translate_image_client',
      'translate_manga'
    )
  )
"""


def cohort_pool_sql() -> str:
    return f"""
    WITH trial_90d AS (
      SELECT DISTINCT userid
      FROM immdata.imt_subscriptiongoodsorder
      WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
        AND COALESCE(amountpaid,0)=0
        AND createtime >= DATEADD(day,-90,NOW()) AND userid IS NOT NULL
            AND (
              subscriptiongoodssnap IS NULL
              OR CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%"SubscriptionType":"onetime%'
            )
    ),
    paid_ever AS (
      SELECT DISTINCT userid FROM immdata.imt_subscriptiongoodsorder
      WHERE COALESCE(isdeleted,0)=0 AND orderstatus='finished'
        AND COALESCE(amountpaid,0)>0
    ),
    cohort AS (
      SELECT t.userid FROM trial_90d t
      LEFT JOIN paid_ever p ON t.userid=p.userid WHERE p.userid IS NULL
    ),
    device_user_cnt AS (
      SELECT deviceid, COUNT(DISTINCT userid) AS users_on_device
      FROM immdata.imt_deviceinfo
      WHERE COALESCE(isdeleted,0)=0 AND userid IS NOT NULL
        AND deviceid IS NOT NULL AND deviceid <> ''
      GROUP BY deviceid
    ),
    user_devices AS (
      SELECT DISTINCT c.userid, d.deviceid
      FROM cohort c
      INNER JOIN immdata.imt_deviceinfo d
        ON c.userid=d.userid AND COALESCE(d.isdeleted,0)=0
       AND d.deviceid IS NOT NULL AND d.deviceid <> ''
    ),
    user_share AS (
      SELECT ud.userid,
             COUNT(DISTINCT ud.deviceid) AS device_cnt,
             MAX(duc.users_on_device) AS max_users_on_any_device
      FROM user_devices ud
      INNER JOIN device_user_cnt duc ON ud.deviceid=duc.deviceid
      GROUP BY ud.userid
    ),
    devices AS (SELECT DISTINCT deviceid FROM user_devices),
    beh AS (
      SELECT
        b.device_id,
        SUM(CASE WHEN b.event_name='translate_page' AND b.page_type='html' THEN 1 ELSE 0 END) AS web_cnt,
        SUM(CASE WHEN b.event_name='translate_video_subtitle' THEN 1 ELSE 0 END) AS video_cnt,
        SUM(CASE WHEN b.event_name IN ('translate_image','translate_image_client') THEN 1 ELSE 0 END) AS image_cnt,
        SUM(CASE WHEN b.event_name='translate_manga' THEN 1 ELSE 0 END) AS manga_cnt,
        SUM(CASE WHEN b.event_name='translate_page' AND b.page_type IN ('pdfReader','pdfProReader') THEN 1 ELSE 0 END) AS pdf_cnt
      FROM immdata.user_behaviour b
      INNER JOIN devices d ON b.device_id=d.deviceid
      WHERE b.created_ts >= DATEADD(day,-90,NOW()) AND b.created_ts < NOW()
        AND {EVENT_FILTER}
      GROUP BY b.device_id
    ),
    user_tr AS (
      SELECT
        ud.userid,
        SUM(COALESCE(beh.web_cnt,0)) AS web_cnt,
        SUM(COALESCE(beh.video_cnt,0)) AS video_cnt,
        SUM(COALESCE(beh.image_cnt,0)) AS image_cnt,
        SUM(COALESCE(beh.manga_cnt,0)) AS manga_cnt,
        SUM(COALESCE(beh.pdf_cnt,0)) AS pdf_cnt
      FROM user_devices ud
      LEFT JOIN beh ON ud.deviceid=beh.device_id
      GROUP BY ud.userid
    )
    SELECT
      us.userid,
      us.device_cnt,
      us.max_users_on_any_device,
      COALESCE(tr.web_cnt,0) AS web_cnt,
      COALESCE(tr.video_cnt,0) AS video_cnt,
      COALESCE(tr.image_cnt,0) AS image_cnt,
      COALESCE(tr.manga_cnt,0) AS manga_cnt,
      COALESCE(tr.pdf_cnt,0) AS pdf_cnt,
      COALESCE(tr.web_cnt,0)+COALESCE(tr.video_cnt,0)+COALESCE(tr.image_cnt,0)
        +COALESCE(tr.manga_cnt,0)+COALESCE(tr.pdf_cnt,0) AS total_cnt
    FROM user_share us
    LEFT JOIN user_tr tr ON us.userid=tr.userid
    """


def _sql_str(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _user_devices(userid: int) -> list[str]:
    sql = f"""
    SELECT DISTINCT deviceid
    FROM immdata.imt_deviceinfo
    WHERE COALESCE(isdeleted,0)=0
      AND userid = {int(userid)}
      AND deviceid IS NOT NULL AND deviceid <> ''
    """
    _, rows = query(sql)
    return [str(r[0]) for r in rows]


def _device_share(deviceid: str) -> int:
    sql = f"""
    SELECT COUNT(DISTINCT userid)
    FROM immdata.imt_deviceinfo
    WHERE COALESCE(isdeleted,0)=0
      AND userid IS NOT NULL
      AND deviceid = {_sql_str(deviceid)}
    """
    _, rows = query(sql)
    return int(rows[0][0]) if rows else 0


def _count_device_beh(deviceid: str) -> tuple[int, int, int, int, int]:
    """Independent path: equality on one device_id (avoids IN-subquery OOM)."""
    # 分事件类型 COUNT，降低单次聚合内存；与报表五类口径一致
    specs = [
        ("web", "event_name='translate_page' AND page_type='html'"),
        ("video", "event_name='translate_video_subtitle'"),
        ("image", "event_name IN ('translate_image','translate_image_client')"),
        ("manga", "event_name='translate_manga'"),
        ("pdf", "event_name='translate_page' AND page_type IN ('pdfReader','pdfProReader')"),
    ]
    out = []
    for _, cond in specs:
        sql = f"""
        SELECT COUNT(*)
        FROM immdata.user_behaviour
        WHERE created_ts >= DATEADD(day,-90,NOW()) AND created_ts < NOW()
          AND device_id = {_sql_str(deviceid)}
          AND ({cond})
        """
        _, rows = query(sql)
        out.append(int(rows[0][0]) if rows else 0)
    return tuple(out)  # type: ignore[return-value]


def recount_and_detail(userids: list[int]):
    """Per-user / per-device independent recount; cache shared-device counts."""
    beh_cache: dict[str, tuple[int, int, int, int, int]] = {}
    share_cache: dict[str, int] = {}
    audit_rows = []  # userid, device_cnt, max_share, web..pdf, total
    detail_rows = []  # userid, deviceid, share, web..pdf, total

    for uid in userids:
        devices = _user_devices(uid)
        print(f"  recount userid={uid} devices={len(devices)}", flush=True)
        sums = [0, 0, 0, 0, 0]
        max_share = 0
        for did in devices:
            if did not in share_cache:
                share_cache[did] = _device_share(did)
            share = share_cache[did]
            max_share = max(max_share, share)
            if did not in beh_cache:
                print(f"    device={did[:12]}... share={share} counting...", flush=True)
                beh_cache[did] = _count_device_beh(did)
            w, v, i, m, p = beh_cache[did]
            sums[0] += w
            sums[1] += v
            sums[2] += i
            sums[3] += m
            sums[4] += p
            detail_rows.append((uid, did, share, w, v, i, m, p, w + v + i + m + p))
        total = sum(sums)
        audit_rows.append(
            (uid, len(devices), max_share, sums[0], sums[1], sums[2], sums[3], sums[4], total)
        )
    return audit_rows, detail_rows


def stratified_sample(rows: list, n: int, seed: int) -> list:
    """rows: userid, device_cnt, max_share, web,video,image,manga,pdf,total"""
    rng = random.Random(seed)

    def pick(pool, k, label):
        if not pool:
            return []
        k = min(k, len(pool))
        chosen = rng.sample(pool, k)
        return [(r, label) for r in chosen]

    exclusive_pos = [r for r in rows if int(r[2]) == 1 and int(r[8]) > 0]
    mild = [r for r in rows if 2 <= int(r[2]) <= 5 and int(r[8]) > 0]
    heavy = [r for r in rows if int(r[2]) >= 100 and int(r[8]) > 0]
    zero = [r for r in rows if int(r[8]) == 0]

    # 8 + 5 + 4 + 3 = 20
    plan = [
        (exclusive_pos, 8, "独占有翻译"),
        (mild, 5, "轻度共享2-5有翻译"),
        (heavy, 4, "重度共享>=100有翻译"),
        (zero, 3, "有设备零翻译"),
    ]
    out = []
    for pool, k, label in plan:
        out.extend(pick(pool, k, label))

    # 若不足 N，从剩余补齐
    have = {int(r[0]) for r, _ in out}
    rest = [r for r in rows if int(r[0]) not in have]
    while len(out) < n and rest:
        r = rng.choice(rest)
        rest.remove(r)
        out.append((r, "补齐随机"))
    return out[:n]


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=N)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args()

    print("Loading cohort pool (report口径)...", flush=True)
    cols, rows = query(cohort_pool_sql())
    print(f"pool_size={len(rows)}", flush=True)

    sample = stratified_sample(rows, args.n, args.seed)
    print(f"sampled={len(sample)}", flush=True)
    for r, label in sample:
        print(f"  {label}: userid={r[0]} total={r[8]} max_share={r[2]}", flush=True)

    userids = [int(r[0]) for r, _ in sample]
    report_map = {
        int(r[0]): {
            "label": label,
            "device_cnt": int(r[1]),
            "max_share": int(r[2]),
            "web": int(r[3]),
            "video": int(r[4]),
            "image": int(r[5]),
            "manga": int(r[6]),
            "pdf": int(r[7]),
            "total": int(r[8]),
        }
        for r, label in sample
    }

    print("Independent recount (per-user / per-device)...", flush=True)
    audit_rows, _detail = recount_and_detail(userids)
    audit_map = {int(r[0]): r for r in audit_rows}

    # compare
    results = []
    mismatch = 0
    for uid in userids:
        rep = report_map[uid]
        aud = audit_map.get(uid)
        if aud is None:
            ok = False
            audit_vals = (None,) * 8
        else:
            audit_vals = (
                int(aud[1]),
                int(aud[2]),
                int(aud[3]),
                int(aud[4]),
                int(aud[5]),
                int(aud[6]),
                int(aud[7]),
                int(aud[8]),
            )
            ok = (
                audit_vals[2] == rep["web"]
                and audit_vals[3] == rep["video"]
                and audit_vals[4] == rep["image"]
                and audit_vals[5] == rep["manga"]
                and audit_vals[6] == rep["pdf"]
                and audit_vals[7] == rep["total"]
            )
        if not ok:
            mismatch += 1
        results.append((uid, rep, audit_vals, ok))

    print(
        f"【抽样复核】任务=task1翻译次数；N={args.n} "
        f"一致={args.n - mismatch}/{args.n} "
        f"结论={'通过' if mismatch == 0 else '不通过'}",
        flush=True,
    )
    if mismatch:
        print("不一致/异常：", flush=True)
        for uid, rep, aud, ok in results:
            if not ok:
                print(
                    f"  userid={uid} label={rep['label']} "
                    f"report_total={rep['total']} audit_total={aud[7]} "
                    f"report=({rep['web']},{rep['video']},{rep['image']},{rep['manga']},{rep['pdf']}) "
                    f"audit=({aud[2]},{aud[3]},{aud[4]},{aud[5]},{aud[6]})",
                    flush=True,
                )
    else:
        print("不一致/异常：无", flush=True)


if __name__ == "__main__":
    main()
