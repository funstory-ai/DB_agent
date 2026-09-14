# -*- coding: utf-8 -*-
"""T018 paywall AB：按观察日 asof 追加归档（不覆盖历史）。

用法:
  python scripts/t018_paywall_ab_snapshot.py              # 刷到今天（北京日）
  python scripts/t018_paywall_ab_snapshot.py --asof 2026-09-04

产出:
  docs/tasks/paywall_ab_archive/INDEX.md
  docs/tasks/paywall_ab_archive/asof_YYYYMMDD.md
  output/paywall_ab/snapshots_history.csv   # 追加，永不删行
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs" / "tasks" / "paywall_ab_archive"
OUT_DIR = ROOT / "output" / "paywall_ab"
HISTORY_CSV = OUT_DIR / "snapshots_history.csv"

BJ = timezone(timedelta(hours=8))
BEH_START = "2026-08-20 16:00:00"  # 实验日起 UTC

CSV_FIELDS = [
    "asof_bj",
    "pulled_at_bj",
    "slice",
    "install_start",
    "install_end_excl",
    "exp_group",
    "new_devices",
    "registered_devices",
    "register_rate_pct",
    "checkout_3d",
    "checkout_3d_pct",
    "trial_3d",
    "trial_3d_pct",
    "paid_3d",
    "paid_3d_pct",
    "paid_7d",
    "paid_7d_pct",
    "reg_wall",
    "reg_wall_pct",
    "pay_wall",
    "pay_wall_pct",
    "note",
]


def bj_day_to_utc_end_excl(d: date) -> str:
    """北京日 d 的次日 00:00 = UTC 当天 16:00，作为观察窗右开。"""
    return f"{d.isoformat()} 16:00:00"


def funnel_sql(
    install_start: str,
    install_end_excl: str,
    beh_start_utc: str,
    beh_end_excl_utc: str,
    label: str,
) -> str:
    return f"""
WITH cohort_beh AS (
  SELECT
    device_id, ab_tag, first_ts, install_day,
    CASE
      WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
      WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
      WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
      WHEN lower(trim(ab_tag)) IN ('i', 'j') THEN 'D'
    END AS exp_group
  FROM (
    SELECT
      device_id, ab_tag, created_ts AS first_ts, install_day,
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
      d.deviceid AS device_id, d.userid, d.installtime,
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
    b.device_id, b.exp_group, b.ab_tag, b.first_ts, b.install_day, d.userid,
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
    o.userid, o.createtime,
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
    c.device_id, c.userid,
    max(CASE WHEN ck.createtime >= c.anchor_ts
              AND ck.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS checkout_3d,
    max(CASE WHEN o.is_trial = 1 AND o.createtime >= c.anchor_ts
              AND o.createtime < add_days(c.anchor_ts, 3) THEN 1 ELSE 0 END) AS trial_3d,
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
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS register_rate_pct,
  count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) AS checkout_3d,
  round(
    count(DISTINCT CASE WHEN cf.checkout_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS checkout_3d_pct,
  count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) AS trial_3d,
  round(
    count(DISTINCT CASE WHEN cf.trial_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS trial_3d_pct,
  count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) AS paid_3d,
  round(
    count(DISTINCT CASE WHEN cf.paid_3d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_3d_pct,
  count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) AS paid_7d,
  round(
    count(DISTINCT CASE WHEN cf.paid_7d = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS paid_7d_pct,
  count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) AS reg_wall,
  round(
    count(DISTINCT CASE WHEN rw.hit_reg_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS reg_wall_pct,
  count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) AS pay_wall,
  round(
    count(DISTINCT CASE WHEN pw.hit_pay_wall = 1 THEN c.device_id END) * 100.0
      / nullif(count(DISTINCT c.device_id), 0), 2
  ) AS pay_wall_pct
FROM cohort_devices c
LEFT JOIN cohort_funnel cf ON cf.device_id = c.device_id
LEFT JOIN reg_wall rw ON rw.device_id = c.device_id
LEFT JOIN pay_wall pw ON pw.device_id = c.device_id
GROUP BY 1, 2
ORDER BY 2
"""


def append_history(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not HISTORY_CSV.exists()
    with HISTORY_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def rows_to_md_table(rows: list[dict]) -> str:
    headers = [
        "组", "新装", "注册率", "3d checkout", "3d 试用", "3d 付费",
        "7d 付费", "注册墙", "付费墙",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|----|" + "|".join(["-----:"] * (len(headers) - 1)) + "|",
    ]
    for r in sorted(rows, key=lambda x: x["exp_group"]):
        lines.append(
            "| {g} | {n:,} | {rr}% | {c}% | {t}% | {p3}% | **{p7}%** | {rw}% | {pw}% |".format(
                g=r["exp_group"],
                n=int(r["new_devices"]),
                rr=r["register_rate_pct"],
                c=r["checkout_3d_pct"],
                t=r["trial_3d_pct"],
                p3=r["paid_3d_pct"],
                p7=r["paid_7d_pct"],
                rw=r["reg_wall_pct"],
                pw=r["pay_wall_pct"],
            )
        )
    return "\n".join(lines)


def write_asof_md(
    asof: date,
    pulled_at: str,
    obs_end: str,
    slices: list[tuple[str, str, str, str, list[dict]]],
) -> Path:
    """slices: (title, install_start, install_end_excl, note, rows)"""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE / f"asof_{asof.strftime('%Y%m%d')}.md"
    # 同日多次拉取：加时间后缀，不覆盖
    if path.exists():
        path = ARCHIVE / f"asof_{asof.strftime('%Y%m%d')}_{datetime.now(BJ).strftime('%H%M')}.md"

    parts = [
        f"# 付费墙 AB 快照 · 观察截止北京 {asof.isoformat()}",
        "",
        f"- **拉取时间（北京）**: {pulled_at}",
        f"- **观察窗右开（UTC）**: `{obs_end}`",
        f"- **口径**: T018 v3（device 完整漏斗；付费剔 renew+老客）",
        f"- **定稿 SQL**: `sql/reports/query_paywall_ab_20260821.sql`",
        f"- **历史长表**: `output/paywall_ab/snapshots_history.csv`",
        "",
    ]
    for title, inst0, inst1, note, rows in slices:
        parts.append(f"## {title}")
        parts.append("")
        parts.append(f"- install_day: `{inst0}` ≤ d < `{inst1}`")
        if note:
            parts.append(f"- 注: {note}")
        parts.append("")
        parts.append(rows_to_md_table(rows))
        parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def update_index() -> None:
    files = sorted(ARCHIVE.glob("asof_*.md"), reverse=True)
    lines = [
        "# 付费墙 AB 观察快照索引（T018）",
        "",
        "每期（按观察日 asof）单独留档，**不覆盖**。长表追加：`output/paywall_ab/snapshots_history.csv`。",
        "",
        "| 观察截止（北京）| 文件 |",
        "|----------------|------|",
    ]
    for p in files:
        stem = p.stem  # asof_YYYYMMDD or asof_YYYYMMDD_HHMM
        lines.append(f"| `{stem}` | [{p.name}]({p.name}) |")
    lines.append("")
    (ARCHIVE / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def freeze_first_pull_20260904() -> None:
    """把任务文档里已确认的第一期数写入归档（若尚未写入）。"""
    marker = ARCHIVE / "asof_20260904.md"
    if marker.exists():
        print("skip freeze: asof_20260904.md already exists", flush=True)
        return

    # 与 docs/tasks/query_paywall_ab_20260821.md §①②③ 一致
    frozen = {
        "cohort_0821_0828": [
            ("A", 48232, 27.70, 1.40, 0.51, 0.11, 0.20, 14.75, 2.86),
            ("B", 38521, 22.77, 1.29, 0.39, 0.08, 0.15, 0.09, 4.68),
            ("C", 31730, 23.44, 1.21, 0.43, 0.09, 0.14, 4.42, 0.83),
            ("D", 34817, 21.69, 1.23, 0.44, 0.12, 0.16, 0.18, 0.04),
        ],
        "cohort_0821_0904": [
            ("A", 87035, 26.82, 1.37, 0.47, 0.11, 0.17, 13.32, 2.40),
            ("B", 68749, 23.01, 1.29, 0.42, 0.08, 0.14, 0.07, 4.07),
            ("C", 56872, 22.89, 1.22, 0.44, 0.09, 0.12, 2.49, 0.46),
            ("D", 62619, 21.89, 1.26, 0.46, 0.10, 0.13, 0.12, 0.02),
        ],
        "cohort_0829_0904": [
            ("A", 38859, 25.70, 1.35, 0.44, 0.11, None, 11.54, 1.83),
            ("B", 30270, 23.29, 1.27, 0.46, 0.08, None, 0.05, 3.28),
            ("C", 25173, 22.18, 1.20, 0.43, 0.08, None, 0.04, 0.0),
            ("D", 27852, 22.11, 1.29, 0.47, 0.07, None, 0.05, 0.0),
        ],
    }
    slice_meta = {
        "cohort_0821_0828": ("2026-08-21", "2026-08-29", "上周 cohort，7d 已满（第一期定稿）"),
        "cohort_0821_0904": ("2026-08-21", "2026-09-05", "扩到 asof；近几天 7d 未满"),
        "cohort_0829_0904": ("2026-08-29", "2026-09-05", "近一周增量；7d 未满故表中 7d 付费以文档为准可空"),
    }
    pulled_at = "2026-09-04（任务文档第一期定稿，冻结入库）"
    asof = date(2026, 9, 4)
    hist_rows: list[dict] = []
    md_slices: list[tuple[str, str, str, str, list[dict]]] = []

    for label, triples in frozen.items():
        inst0, inst1, note = slice_meta[label]
        rows = []
        for g, n, rr, c, t, p3, p7, rw, pw in triples:
            row = {
                "asof_bj": asof.isoformat(),
                "pulled_at_bj": pulled_at,
                "slice": label,
                "install_start": inst0,
                "install_end_excl": inst1,
                "exp_group": g,
                "new_devices": n,
                "registered_devices": "",
                "register_rate_pct": rr,
                "checkout_3d": "",
                "checkout_3d_pct": c,
                "trial_3d": "",
                "trial_3d_pct": t,
                "paid_3d": "",
                "paid_3d_pct": p3,
                "paid_7d": "",
                "paid_7d_pct": p7 if p7 is not None else "",
                "reg_wall": "",
                "reg_wall_pct": rw,
                "pay_wall": "",
                "pay_wall_pct": pw,
                "note": "frozen_from_task_doc_v3",
            }
            hist_rows.append(row)
            rows.append(row)
        title = {
            "cohort_0821_0828": "① 上周 cohort (08-21~08-28)",
            "cohort_0821_0904": "② 扩到 asof (08-21~09-04)",
            "cohort_0829_0904": "③ 近一周增量 (08-29~09-04)",
        }[label]
        md_slices.append((title, inst0, inst1, note, rows))

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    # 直接写固定文件名（首次冻结）
    path = ARCHIVE / "asof_20260904.md"
    parts = [
        f"# 付费墙 AB 快照 · 观察截止北京 {asof.isoformat()}",
        "",
        f"- **拉取时间（北京）**: {pulled_at}",
        f"- **观察窗右开（UTC）**: `2026-09-04 16:00:00`",
        f"- **口径**: T018 v3（device 完整漏斗；付费剔 renew+老客）",
        f"- **来源**: 任务文档第一期定稿，冻结保留，禁止覆盖改数",
        "",
    ]
    for title, inst0, inst1, note, rows in md_slices:
        parts.append(f"## {title}")
        parts.append("")
        parts.append(f"- install_day: `{inst0}` ≤ d < `{inst1}`")
        parts.append(f"- 注: {note}")
        parts.append("")
        parts.append(rows_to_md_table(rows))
        parts.append("")
    path.write_text("\n".join(parts), encoding="utf-8")
    append_history(hist_rows)
    print(f"froze {path}", flush=True)


def run_live(asof: date) -> None:
    obs_end = bj_day_to_utc_end_excl(asof)
    # install 扩到 asof 当日（含）：end_excl = asof+1
    inst_end = (asof + timedelta(days=1)).isoformat()
    # 上周 cohort：与第一期定稿对齐 —— install 08-21～08-28（右开 08-29，共 8 个北京日）
    # 其后按同样 8 日窗滚动；成熟条件：窗末日 + 7d <= asof
    week0_start = date(2026, 8, 21)
    wave_len = 8  # 与 asof_20260904 定稿一致
    mature_weeks: list[tuple[date, date]] = []
    ws = week0_start
    while True:
        we = ws + timedelta(days=wave_len)  # end excl
        last_install = we - timedelta(days=1)
        if last_install + timedelta(days=7) <= asof:
            mature_weeks.append((ws, we))
            ws = we
        else:
            break
    if not mature_weeks:
        mature_weeks = [(week0_start, week0_start + timedelta(days=wave_len))]

    last_mature = mature_weeks[-1]
    # 近一周：asof-6 ~ asof（含）共 7 日
    recent_start = asof - timedelta(days=6)

    pulled_at = datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")
    specs = [
        (
            f"① 最近已满 7d 的 install 周 ({last_mature[0]}~{last_mature[1]-timedelta(days=1)})",
            last_mature[0].isoformat(),
            last_mature[1].isoformat(),
            f"cohort_{last_mature[0].strftime('%m%d')}_{last_mature[1].strftime('%m%d')}",
            "7d 付费窗已跑满（对该周末日安装而言）",
        ),
        (
            f"② 扩到今天 (2026-08-21~{asof.isoformat()})",
            "2026-08-21",
            inst_end,
            f"cohort_0821_{asof.strftime('%m%d')}",
            "近几天安装 7d 未满，paid_7d 会偏低",
        ),
        (
            f"③ 近一周新装 ({recent_start}~{asof.isoformat()})",
            recent_start.isoformat(),
            inst_end,
            f"cohort_{recent_start.strftime('%m%d')}_{asof.strftime('%m%d')}",
            "增量窗；7d 多半未满",
        ),
    ]

    md_slices = []
    hist_rows: list[dict] = []
    for title, i0, i1, label, note in specs:
        print(f"\n>>> querying {label} ...", flush=True)
        cols, raw = query(funnel_sql(i0, i1, BEH_START, obs_end, label))
        rows = []
        for r in raw:
            d = dict(zip(cols, r))
            row = {
                "asof_bj": asof.isoformat(),
                "pulled_at_bj": pulled_at,
                "slice": label,
                "install_start": i0,
                "install_end_excl": i1,
                "exp_group": d["exp_group"],
                "new_devices": d["new_devices"],
                "registered_devices": d["registered_devices"],
                "register_rate_pct": d["register_rate_pct"],
                "checkout_3d": d["checkout_3d"],
                "checkout_3d_pct": d["checkout_3d_pct"],
                "trial_3d": d["trial_3d"],
                "trial_3d_pct": d["trial_3d_pct"],
                "paid_3d": d["paid_3d"],
                "paid_3d_pct": d["paid_3d_pct"],
                "paid_7d": d["paid_7d"],
                "paid_7d_pct": d["paid_7d_pct"],
                "reg_wall": d["reg_wall"],
                "reg_wall_pct": d["reg_wall_pct"],
                "pay_wall": d["pay_wall"],
                "pay_wall_pct": d["pay_wall_pct"],
                "note": note,
            }
            rows.append(row)
            hist_rows.append(row)
            print(d, flush=True)
        md_slices.append((title, i0, i1, note, rows))

    path = write_asof_md(asof, pulled_at, obs_end, md_slices)
    append_history(hist_rows)
    update_index()
    print(f"\nwrote {path}", flush=True)
    print(f"appended {len(hist_rows)} rows -> {HISTORY_CSV}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None, help="北京观察截止日 YYYY-MM-DD，默认今天")
    ap.add_argument("--skip-freeze", action="store_true")
    args = ap.parse_args()
    if not args.skip_freeze:
        freeze_first_pull_20260904()
        update_index()
    if args.asof:
        asof = date.fromisoformat(args.asof)
    else:
        asof = datetime.now(BJ).date()
    run_live(asof)


if __name__ == "__main__":
    main()
