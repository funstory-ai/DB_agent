# -*- coding: utf-8 -*-
"""T061 asof=2026-10-10 · ≥1.32.6 + 剔老号 + 7d/累计触墙率 → Excel + 归档。"""
from __future__ import annotations

import csv
import sys
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    ROOT / "sql" / "reports" / "query_paywall_ab_longterm_ver_excl_old_hit_20261010.sql"
)
OUT_XLSX = (
    ROOT
    / "output"
    / "paywall_ab"
    / "paywall_ab_longterm_ver1326_excl_old_hit_20261010.xlsx"
)
ARCHIVE = ROOT / "docs" / "tasks" / "paywall_ab_archive"
HISTORY_CSV = ROOT / "output" / "paywall_ab" / "snapshots_history.csv"
BJ = timezone(timedelta(hours=8))
ASOF = "2026-10-10"
AGG_SLICE = "aggregate_0821_1010"
OBS_END_UTC = "2026-10-10 16:00:00"

FROZEN_W1 = [
    ("A", 48232, 0.2770, 0.0140, 0.0051, 0.0011, 0.0020, 0.0022, 0.1475, 0.0286),
    ("B", 38521, 0.2277, 0.0129, 0.0039, 0.0008, 0.0015, 0.0017, 0.0009, 0.0468),
    ("C", 31730, 0.2344, 0.0121, 0.0043, 0.0009, 0.0014, 0.0015, 0.0442, 0.0083),
    ("D", 34817, 0.2169, 0.0123, 0.0044, 0.0012, 0.0016, 0.0018, 0.0018, 0.0004),
]

SLICE_LABEL = {
    "natural_week_0821_0823_partial": "08/17自然周（实验起）",
    "natural_week_0824_0830": "08/24自然周",
    "natural_week_0831_0906": "08/31自然周",
    "natural_week_0907_0913": "09/07自然周",
    "natural_week_0914_0920": "09/14自然周",
    "natural_week_0921_0927": "09/21自然周",
    "natural_week_0928_1004": "09/28自然周",
    "natural_week_1005_partial": "10/05自然周（本周）",
    AGG_SLICE: "汇总（08-21～10-10）",
}


def _rate(pct_val):
    if pct_val is None:
        return None
    return float(pct_val) / 100.0


def _install_end_inclusive(end_excl: str):
    return date_cls.fromisoformat(end_excl) - timedelta(days=1)


def run() -> list[dict]:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print("querying...", flush=True)
    cols, rows = query(sql)
    out = [dict(zip(cols, r)) for r in rows]
    for d in out:
        print(
            d["slice"],
            d["exp_group"],
            "n=",
            d["new_devices"],
            "paid=",
            d["paid_to_asof_pct"],
            "wall7d=",
            d["wall_hit_7d_pct"],
            "wall=",
            d["wall_hit_to_asof_pct"],
            flush=True,
        )
    return out


def write_xlsx(rows: list[dict]) -> Path:
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    wb = Workbook()

    weekly = [r for r in rows if r["slice_type"] == "weekly"]
    by_slice: dict[str, dict] = {}
    for r in weekly:
        by_slice.setdefault(r["slice"], {"meta": r, "g": {}})
        by_slice[r["slice"]]["g"][r["exp_group"]] = r
    agg = {r["exp_group"]: r for r in rows if r["slice_type"] == "aggregate"}
    slice_order = sorted(by_slice.keys(), key=lambda s: by_slice[s]["meta"]["cohort_no"])

    ws = wb.active
    ws.title = "转化总览"
    ws["A1"] = "付费墙 A/B/C/D · 版本≥1.32.6（语义化）+ 剔老号 · 含触墙率"
    ws["A1"].font = bold
    ws["A2"] = (
        f"asof={ASOF}；P040≥1.32.6 + P039 剔老号。"
        "触墙=user_need_pro+freeUsageLimitModal；7d=激活后7日内；累计=激活至asof。"
        "对照新付费墙「登录弹窗%」用累计触墙率。"
    )

    ws["A5"] = "累计付费对照（第一期定稿 vs 截至今日汇总）"
    ws["A5"].font = bold
    for i, h in enumerate(["实验组", "第一期累计付费率", "截至今日累计付费率", "差值（百分点）"], 1):
        ws.cell(6, i, h).font = bold
    for i, g in enumerate("ABCD"):
        r = 7 + i
        ws.cell(r, 1, g)
        ws.cell(r, 2, f"=H{15+i}")
        ws.cell(r, 2).number_format = pct_fmt
        ws.cell(r, 3, f"=H{24+i}")
        ws.cell(r, 3).number_format = pct_fmt
        ws.cell(r, 4, f"=(C{r}-B{r})*100")

    ws["A12"] = "第一期定稿"
    ws["A12"].font = bold
    ws["A13"] = (
        "安装日 2026-08-21 至 2026-08-28；**更早旧口径冻结**（无 is_new_user_today 的 translate 进组）；"
        "勿与下方 P034 激活分母横比"
    )
    funnel_h = [
        "实验组", "新装设备", "注册率", "3d checkout", "3d 试用",
        "3d 付费", "7d 付费", "累计付费", "注册墙", "付费墙",
    ]
    for i, h in enumerate(funnel_h, 1):
        ws.cell(14, i, h).font = bold
    for i, (g, n, rr, c, t, p3, p7, pa, rw, pw) in enumerate(FROZEN_W1):
        r = 15 + i
        for col, v in enumerate([g, n, rr, c, t, p3, p7, pa, rw, pw], 1):
            cell = ws.cell(r, col, v)
            if col >= 3:
                cell.number_format = pct_fmt

    ws["A21"] = "截至今日汇总"
    ws["A21"].font = bold
    ws["A22"] = (
        f"激活日 2026-08-21 至 {ASOF}；**P034 激活 × P040≥1.32.6 × P039 剔老号**；"
        "注册/checkout/试用/3d·7d·累计付费本次刷新；墙未重算；留存=translate_page 周表"
    )
    for i, h in enumerate(funnel_h, 1):
        ws.cell(23, i, h).font = bold
    ws.cell(23, 2, "激活设备")
    ws.cell(14, 2, "新装设备(旧)")
    for i, g in enumerate("ABCD"):
        r = 24 + i
        a = agg[g]
        vals = [
            g,
            int(a["new_devices"]),
            _rate(a["register_rate_pct"]),
            _rate(a["checkout_3d_pct"]),
            _rate(a["trial_3d_pct"]),
            _rate(a["paid_3d_pct"]),
            _rate(a["paid_7d_pct"]),
            _rate(a["paid_to_asof_pct"]),
            None,
            _rate(a["wall_hit_to_asof_pct"]),
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(r, col, v)
            if col >= 3 and v is not None:
                cell.number_format = pct_fmt

    ws["A29"] = (
        "说明：自然周按周一至周日切分；各周完整漏斗 + 留存在「周同期群」页。"
        "留存未满窗单元格为空。"
    )

    ws2 = wb.create_sheet("口径与补算")
    ws2["A1"] = "口径（P040 版本 + P039 剔老号 + 触墙）"
    ws2["A1"].font = bold
    notes = [
        ("实验分组", "A=a/b/c；B=d/e/f；C=g/h；D=i/j", "T018"),
        ("分母/激活", "translate_page + is_new_user_today='1' + ab_tag + 语义化≥1.32.6 + 剔老号", "P034/P040/P039"),
        ("版本（P040）", "语义化 ≥1.32.6；含 1.32.10+；禁止字符串 >=", "T048/P040"),
        ("老号（P039）", "imt_userinfo.createtime < first_ts - 1 天", "P039"),
        ("触墙", "user_need_pro+freeUsageLimitModal；7d触墙率/触墙率÷激活；可比新墙登录弹窗%", "T057/T046"),
        ("今日汇总", f"激活北京日 ≥ 2026-08-21 且 < 2026-10-11", f"{ASOF} 刷新"),
        ("付费", "finished 且现金/onetime/code；排除 iospay_renew 与锚点前老客", "T018 v3"),
        ("周留存", "仅 translate_page；W0=激活周；未满空；分母=激活 device", "1a/2a/3b/4a"),
        ("需求", "T061 周刷 asof=2026-10-10；口径同 T057", "本次"),
    ]
    ws2["A5"] = "项目"
    ws2["B5"] = "内容"
    ws2["C5"] = "来源"
    for c in ("A5", "B5", "C5"):
        ws2[c].font = bold
    for i, (a, b, c) in enumerate(notes, 6):
        ws2.cell(i, 1, a)
        ws2.cell(i, 2, b)
        ws2.cell(i, 3, c)

    ws3 = wb.create_sheet("周同期群")
    ws3["A1"] = "付费墙实验周同期群（ver≥1.32.6 + 剔老号 + 触墙）"
    ws3["A1"].font = bold
    ws3["A2"] = (
        f"转化分母=P034 激活 × P040 × P039；按自然周切分；"
        f"末尾加 W1～W4 留存 + 7d触墙率/触墙率（空=未满留存）；asof={ASOF}"
    )

    ws3["A5"] = "周同期群累计付费率"
    ws3["A5"].font = bold
    for i, h in enumerate(["同期群", "安装开始", "安装结束", "成熟状态", "A", "B", "C", "D"], 1):
        ws3.cell(6, i, h).font = bold

    detail_start = 15
    n_weekly = len(slice_order)
    agg_start = detail_start + n_weekly * 4 + 2

    for si, sk in enumerate(slice_order):
        meta = by_slice[sk]["meta"]
        r = 7 + si
        ws3.cell(r, 1, SLICE_LABEL.get(sk, sk))
        ws3.cell(r, 2, date_cls.fromisoformat(meta["install_start"]))
        ws3.cell(r, 3, _install_end_inclusive(meta["install_end_excl"]))
        ws3.cell(r, 4, meta["maturity_status"])
        base = detail_start + si * 4
        for j, _g in enumerate("ABCD"):
            cell = ws3.cell(r, 5 + j, f"=M{base + j}")
            cell.number_format = pct_fmt
    mat_agg_row = 7 + n_weekly
    ws3.cell(mat_agg_row, 1, SLICE_LABEL[AGG_SLICE])
    ws3.cell(mat_agg_row, 2, date_cls(2026, 8, 21))
    ws3.cell(mat_agg_row, 3, date_cls(2026, 10, 10))
    ws3.cell(mat_agg_row, 4, "混合成熟度")
    for j, _g in enumerate("ABCD"):
        cell = ws3.cell(mat_agg_row, 5 + j, f"=M{agg_start + j}")
        cell.number_format = pct_fmt

    ws3["A13"] = "周同期群明细"
    ws3["A13"].font = bold
    detail_h = [
        "同期群", "安装开始", "安装结束", "成熟状态", "实验组", "激活设备",
        "注册率", "3d checkout", "3d 试用", "3d 付费", "7d 付费",
        "累计付费人数", "累计付费率",
        "W1留存", "W2留存", "W3留存", "W4留存",
        "7d触墙率", "触墙率",
    ]
    for i, h in enumerate(detail_h, 1):
        ws3.cell(14, i, h).font = bold

    def write_detail_row(r, label, meta_install_start, meta_end_excl, maturity, rec):
        ws3.cell(r, 1, label)
        ws3.cell(r, 2, date_cls.fromisoformat(meta_install_start))
        ws3.cell(r, 3, _install_end_inclusive(meta_end_excl))
        ws3.cell(r, 4, maturity)
        ws3.cell(r, 5, rec["exp_group"])
        ws3.cell(r, 6, int(rec["new_devices"]))
        for col, key in enumerate(
            ["register_rate_pct", "checkout_3d_pct", "trial_3d_pct",
             "paid_3d_pct", "paid_7d_pct"],
            7,
        ):
            cell = ws3.cell(r, col, _rate(rec[key]))
            cell.number_format = pct_fmt
        ws3.cell(r, 12, int(rec["paid_to_asof"]))
        cell = ws3.cell(r, 13, f"=L{r}/F{r}")
        cell.number_format = pct_fmt
        for col, key in enumerate(
            ["ret_w1_pct", "ret_w2_pct", "ret_w3_pct", "ret_w4_pct"], 14
        ):
            v = rec[key]
            if v is None:
                ws3.cell(r, col, None)
            else:
                cell = ws3.cell(r, col, _rate(v))
                cell.number_format = pct_fmt
        for col, key in enumerate(
            ["wall_hit_7d_pct", "wall_hit_to_asof_pct"], 18
        ):
            cell = ws3.cell(r, col, _rate(rec[key]))
            cell.number_format = pct_fmt

    ri = detail_start
    for sk in slice_order:
        meta = by_slice[sk]["meta"]
        for g in "ABCD":
            write_detail_row(
                ri,
                SLICE_LABEL.get(sk, sk),
                meta["install_start"],
                meta["install_end_excl"],
                meta["maturity_status"],
                by_slice[sk]["g"][g],
            )
            ri += 1

    ri = agg_start
    for g in "ABCD":
        write_detail_row(
            ri,
            SLICE_LABEL[AGG_SLICE],
            "2026-08-21",
            "2026-10-11",
            "混合成熟度",
            agg[g],
        )
        ri += 1

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    print(f"wrote {OUT_XLSX}", flush=True)
    return OUT_XLSX


def write_archive(rows: list[dict]) -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE / f"asof_{ASOF.replace('-', '')}.md"
    if path.exists():
        path = ARCHIVE / f"asof_{ASOF.replace('-', '')}_{datetime.now(BJ).strftime('%H%M')}.md"

    lines = [
        f"# 付费墙 AB 快照 · 观察截止北京 {ASOF}",
        "",
        f"- **拉取时间（北京）**: {datetime.now(BJ).strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **观察窗右开（UTC）**: `{OBS_END_UTC}`",
        f"- **口径**: P034 激活 × P040 语义化≥1.32.6 × P039 剔老号 + 硬墙触墙；周留存 1a/2a/3b/4a",
        f"- **SQL**: `sql/reports/query_paywall_ab_longterm_ver_excl_old_hit_20261010.sql`",
        f"- **Excel**: `output/paywall_ab/paywall_ab_longterm_ver1326_excl_old_hit_20261010.xlsx`",
        f"- **需求**: T061（T057 周刷恢复）",
        "",
        "## 累计付费（自然周）",
        "",
        "| 同期群 | 成熟度 | A | B | C | D |",
        "|--------|--------|--:|--:|--:|--:|",
    ]
    weekly = sorted(
        [r for r in rows if r["slice_type"] == "weekly"],
        key=lambda x: (x["cohort_no"], x["exp_group"]),
    )
    by_slice: dict[str, dict] = {}
    for r in weekly:
        by_slice.setdefault(r["slice"], {"meta": r, "g": {}})
        by_slice[r["slice"]]["g"][r["exp_group"]] = r
    for sk in sorted(by_slice, key=lambda s: by_slice[s]["meta"]["cohort_no"]):
        m = by_slice[sk]["meta"]
        g = by_slice[sk]["g"]
        lines.append(
            f"| {SLICE_LABEL[sk]} | {m['maturity_status']} | "
            f"**{g['A']['paid_to_asof_pct']}%** | **{g['B']['paid_to_asof_pct']}%** | "
            f"**{g['C']['paid_to_asof_pct']}%** | **{g['D']['paid_to_asof_pct']}%** |"
        )
    agg = {r["exp_group"]: r for r in rows if r["slice_type"] == "aggregate"}
    if agg:
        lines.append(
            f"| 汇总 | 混合 | **{agg['A']['paid_to_asof_pct']}%** | **{agg['B']['paid_to_asof_pct']}%** | "
            f"**{agg['C']['paid_to_asof_pct']}%** | **{agg['D']['paid_to_asof_pct']}%** |"
        )

    lines += [
        "",
        "## 触墙率（自然周 · 7d / 累计）",
        "",
        "| 同期群 | A 7d | A 累计 | B 7d | B 累计 | C 7d | C 累计 | D 7d | D 累计 |",
        "|--------|-----:|-------:|-----:|-------:|-----:|-------:|-----:|-------:|",
    ]
    for sk in sorted(by_slice, key=lambda s: by_slice[s]["meta"]["cohort_no"]):
        g = by_slice[sk]["g"]
        lines.append(
            f"| {SLICE_LABEL[sk]} | "
            f"**{g['A']['wall_hit_7d_pct']}%** | **{g['A']['wall_hit_to_asof_pct']}%** | "
            f"**{g['B']['wall_hit_7d_pct']}%** | **{g['B']['wall_hit_to_asof_pct']}%** | "
            f"**{g['C']['wall_hit_7d_pct']}%** | **{g['C']['wall_hit_to_asof_pct']}%** | "
            f"**{g['D']['wall_hit_7d_pct']}%** | **{g['D']['wall_hit_to_asof_pct']}%** |"
        )
    if agg:
        lines.append(
            f"| 汇总 | "
            f"**{agg['A']['wall_hit_7d_pct']}%** | **{agg['A']['wall_hit_to_asof_pct']}%** | "
            f"**{agg['B']['wall_hit_7d_pct']}%** | **{agg['B']['wall_hit_to_asof_pct']}%** | "
            f"**{agg['C']['wall_hit_7d_pct']}%** | **{agg['C']['wall_hit_to_asof_pct']}%** | "
            f"**{agg['D']['wall_hit_7d_pct']}%** | **{agg['D']['wall_hit_to_asof_pct']}%** |"
        )

    lines += [
        "",
        "## 周留存 W1～W4（未满为空）",
        "",
        "| 同期群 | 组 | 激活 | W1% | W2% | W3% | W4% |",
        "|--------|----|-----:|----:|----:|----:|----:|",
    ]
    for sk in sorted(by_slice, key=lambda s: by_slice[s]["meta"]["cohort_no"]):
        for grp in "ABCD":
            r = by_slice[sk]["g"][grp]

            def fmt(v):
                return "—" if v is None else f"{v}%"

            lines.append(
                f"| {SLICE_LABEL[sk]} | {grp} | {int(r['new_devices']):,} | "
                f"{fmt(r['ret_w1_pct'])} | {fmt(r['ret_w2_pct'])} | "
                f"{fmt(r['ret_w3_pct'])} | {fmt(r['ret_w4_pct'])} |"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    files = sorted(ARCHIVE.glob("asof_*.md"), reverse=True)
    idx = [
        "# 付费墙 AB 观察快照索引（T018）",
        "",
        "每期（按观察日 asof）单独留档，**不覆盖**。",
        "",
        "| 观察截止（北京）| 文件 |",
        "|----------------|------|",
    ]
    for p in files:
        if p.name == "INDEX.md":
            continue
        idx.append(f"| `{p.stem}` | [{p.name}]({p.name}) |")
    (ARCHIVE / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"archive {path}", flush=True)

    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "asof_bj", "pulled_at_bj", "slice", "install_start", "install_end_excl",
        "exp_group", "new_devices", "register_rate_pct", "paid_to_asof_pct",
        "ret_w1_pct", "ret_w2_pct", "ret_w3_pct", "ret_w4_pct", "note",
    ]
    write_header = not HISTORY_CSV.exists()
    pulled = datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")
    with HISTORY_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "asof_bj": ASOF,
                    "pulled_at_bj": pulled,
                    "slice": r["slice"],
                    "install_start": r["install_start"],
                    "install_end_excl": r["install_end_excl"],
                    "exp_group": r["exp_group"],
                    "new_devices": r["new_devices"],
                    "register_rate_pct": r["register_rate_pct"],
                    "paid_to_asof_pct": r["paid_to_asof_pct"],
                    "ret_w1_pct": r["ret_w1_pct"],
                    "ret_w2_pct": r["ret_w2_pct"],
                    "ret_w3_pct": r["ret_w3_pct"],
                    "ret_w4_pct": r["ret_w4_pct"],
                    "note": "ver1326_excl_old_hit_P034_20261010",
                }
            )


def sample_validate(rows: list[dict]) -> None:
    """成熟度门闩 + 周人数加总（last_closed=2026-09-28；不重扫 behaviour）。"""
    print("\n【抽样复核】成熟度门闩+人数加总...", flush=True)

    weekly = [r for r in rows if r["slice_type"] == "weekly"]
    agg = {r["exp_group"]: r for r in rows if r["slice_type"] == "aggregate"}
    w817 = [r for r in rows if r["slice"] == "natural_week_0821_0823_partial"]
    w824 = [r for r in rows if r["slice"] == "natural_week_0824_0830"]
    w831 = [r for r in rows if r["slice"] == "natural_week_0831_0906"]
    w907 = [r for r in rows if r["slice"] == "natural_week_0907_0913"]
    w914 = [r for r in rows if r["slice"] == "natural_week_0914_0920"]
    w921 = [r for r in rows if r["slice"] == "natural_week_0921_0927"]
    w928 = [r for r in rows if r["slice"] == "natural_week_0928_1004"]
    w1005 = [r for r in rows if r["slice"] == "natural_week_1005_partial"]
    ok = True

    # last_closed_week_start = 2026-09-28
    for r in w817 + w824 + w831:
        if any(r[k] is None for k in ("ret_w1_pct", "ret_w2_pct", "ret_w3_pct", "ret_w4_pct")):
            print("FAIL: early weeks should have W1+W2+W3+W4", r["slice"], r["exp_group"])
            ok = False
    for r in w907:
        if r["ret_w1_pct"] is None or r["ret_w2_pct"] is None or r["ret_w3_pct"] is None:
            print("FAIL: 09/07 should have W1+W2+W3", r)
            ok = False
        if r["ret_w4_pct"] is not None:
            print("FAIL: 09/07 W4 should be empty", r)
            ok = False
    for r in w914:
        if r["ret_w1_pct"] is None or r["ret_w2_pct"] is None:
            print("FAIL: 09/14 should have W1+W2", r)
            ok = False
        if r["ret_w3_pct"] is not None:
            print("FAIL: 09/14 W3 should be empty", r)
            ok = False
    for r in w921:
        if r["ret_w1_pct"] is None:
            print("FAIL: 09/21 should have W1", r)
            ok = False
        if r["ret_w2_pct"] is not None:
            print("FAIL: 09/21 W2 should be empty", r)
            ok = False
    for r in w928 + w1005:
        if r["ret_w1_pct"] is not None:
            print("FAIL: 09/28/10/05 W1 should be empty", r)
            ok = False
    for g in "ABCD":
        s = sum(int(r["new_devices"]) for r in weekly if r["exp_group"] == g)
        a = int(agg[g]["new_devices"]) if agg else -1
        if s != a:
            print(f"FAIL: new_devices sum {g} weekly={s} agg={a}")
            ok = False
    print(
        f"【抽样复核】成熟度门闩+人数加总；结论={'通过' if ok else '不通过'}",
        flush=True,
    )
    if not ok:
        raise SystemExit(1)


def main() -> None:
    rows = run()
    write_xlsx(rows)
    write_archive(rows)
    print("\n=== 累计付费% / 触墙% by week (ver+excl_old+hit) ===", flush=True)
    weeks = [
        "natural_week_0824_0830",
        "natural_week_0831_0906",
        "natural_week_0907_0913",
        "natural_week_0914_0920",
        "natural_week_0921_0927",
        "natural_week_0928_1004",
        "natural_week_1005_partial",
        AGG_SLICE,
    ]
    print(
        f"{'slice':28} "
        f"{'Ap':>6} {'Aw':>6} {'Bp':>6} {'Bw':>6} {'Cp':>6} {'Cw':>6} {'Dp':>6} {'Dw':>6}",
        flush=True,
    )
    for sl in weeks:
        vals = {}
        ns = {}
        for g in "ABCD":
            r = next(x for x in rows if x["slice"] == sl and x["exp_group"] == g)
            vals[g] = (
                float(r["paid_to_asof_pct"]),
                float(r["wall_hit_to_asof_pct"]),
            )
            ns[g] = int(r["new_devices"])
        print(
            f"{sl:28} "
            f"{vals['A'][0]:5.3f}% {vals['A'][1]:5.2f}% "
            f"{vals['B'][0]:5.3f}% {vals['B'][1]:5.2f}% "
            f"{vals['C'][0]:5.3f}% {vals['C'][1]:5.2f}% "
            f"{vals['D'][0]:5.3f}% {vals['D'][1]:5.2f}%",
            flush=True,
        )
        if sl == AGG_SLICE:
            print(
                f"{'n_agg':28} {ns['A']:7d} {ns['B']:7d} {ns['C']:7d} {ns['D']:7d}",
                flush=True,
            )
    sample_validate(rows)
    agg = {r["exp_group"]: r for r in rows if r["slice_type"] == "aggregate"}
    for g in "AB":
        if float(agg[g]["wall_hit_7d_pct"]) <= 0:
            raise SystemExit(f"FAIL {g} 7d触墙应为正")
    for g in "CD":
        if float(agg[g]["wall_hit_7d_pct"]) > 0.5:
            raise SystemExit(
                f"FAIL {g} 7d触墙应接近0，got {agg[g]['wall_hit_7d_pct']}"
            )
    print("wall sample OK: A/B>0, C/D~0", flush=True)


if __name__ == "__main__":
    main()
