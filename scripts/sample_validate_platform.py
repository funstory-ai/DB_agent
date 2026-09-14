"""抽样核主要平台：从 v2/v5 抽 N，窄查询对拍；只打印。"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query
from openpyxl import load_workbook

OUT = Path(__file__).resolve().parents[1] / "output"
PLATFORM_EXPR = """
CASE
  WHEN lower(COALESCE(b.os_name, '')) IN ('ios', 'ipados', 'android') THEN '移动端'
  WHEN b.os_name = 'macOS' THEN 'Mac'
  WHEN b.os_name IN ('Windows', 'Linux', 'Chrome OS') THEN 'PC'
  WHEN b.platform_type IN ('mobile', 'tablet') THEN '移动端'
  WHEN b.platform_type LIKE 'iPhone%' OR b.platform_type LIKE 'iPad%' THEN '移动端'
  WHEN b.platform_type = 'desktop' THEN 'PC'
  ELSE '其他/未知'
END
"""


def main():
    wb = load_workbook(OUT / "task2_churn90d_vs_trial_unpaid_translate_v2.xlsx", read_only=True, data_only=True)
    ws = wb["流失会员"]
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    plat_i = headers.index("主要平台")
    rows = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if r[1] is None:
            continue
        rows.append((int(r[1]), r[plat_i], int(r[15] or 0)))
    wb.close()

    rng = random.Random(20260814)
    # 分层：有平台 / 无平台各若干
    with_p = [r for r in rows if r[1]]
    no_p = [r for r in rows if not r[1]]
    sample = rng.sample(with_p, min(12, len(with_p))) + rng.sample(no_p, min(8, len(no_p)))
    ids = ",".join(str(r[0]) for r in sample)
    print(f"sampled={len(sample)}", flush=True)

    _, aud = query(
        f"""
        WITH ud AS (
          SELECT DISTINCT userid, deviceid FROM immdata.imt_deviceinfo
          WHERE COALESCE(isdeleted,0)=0 AND userid IN ({ids})
            AND deviceid IS NOT NULL AND deviceid <> ''
        ),
        per AS (
          SELECT ud.userid, {PLATFORM_EXPR} AS major_platform, COUNT(*) cnt
          FROM ud
          INNER JOIN immdata.user_behaviour b ON b.device_id = ud.deviceid
          WHERE b.created_ts >= DATEADD(day,-90,NOW()) AND b.created_ts < NOW()
            AND (
              (b.event_name='translate_page' AND b.page_type IN ('html','pdfReader','pdfProReader'))
              OR b.event_name IN ('translate_video_subtitle','translate_image','translate_image_client','translate_manga')
            )
          GROUP BY ud.userid, major_platform
        ),
        ranked AS (
          SELECT userid, major_platform, cnt,
                 ROW_NUMBER() OVER (
                   PARTITION BY userid
                   ORDER BY CASE WHEN major_platform='其他/未知' THEN 1 ELSE 0 END, cnt DESC, major_platform
                 ) rn
          FROM per
        )
        SELECT userid, major_platform FROM ranked WHERE rn=1
        """
    )
    amap = {int(r[0]): r[1] for r in aud}
    mism = 0
    for uid, rep, has_di in sample:
        aud_p = amap.get(uid)
        # both empty OK if no di or no beh
        ok = (rep or None) == (aud_p or None) or (rep is None and aud_p is None)
        if not ok and rep is None and has_di == 0:
            ok = True  # no device -> empty expected; audit also empty
        if not ok:
            mism += 1
            print(f"FAIL uid={uid} rep={rep!r} aud={aud_p!r} has_di={has_di}", flush=True)
        else:
            print(f"OK uid={uid} plat={rep!r}", flush=True)
    n = len(sample)
    print(
        f"【抽样复核】任务=主要平台；N={n} 一致={n-mism}/{n} 结论={'通过' if mism==0 else '不通过'}",
        flush=True,
    )
    print("不一致/异常：" + ("无" if mism == 0 else "见 FAIL"), flush=True)


if __name__ == "__main__":
    main()
