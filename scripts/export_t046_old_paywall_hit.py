# -*- coding: utf-8 -*-
"""T046: old hard-paywall 7d hit rate on P034+P039 activate, T018 weeks."""
from __future__ import annotations

import sys
from datetime import date as date_cls
from datetime import timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql/reports/query_old_paywall_new_user_hit_rate_20260930.sql"
OUT_XLSX = ROOT / "output/paywall_ab/old_paywall_new_user_hit_7d_20260930.xlsx"

SLICE_LABEL = {
    "natural_week_0821_0823_partial": "08/17自然周（实验起）",
    "natural_week_0824_0830": "08/24自然周",
    "natural_week_0831_0906": "08/31自然周",
    "natural_week_0907_0913": "09/07自然周",
    "natural_week_0914_0920": "09/14自然周",
    "natural_week_0921_0927": "09/21自然周",
    "natural_week_0928_partial": "09/28自然周（本周）",
    "aggregate_0821_0928": "汇总（08-21～09-28）",
}
GROUPS_ABCD = ("A", "B", "C", "D")
GROUPS_IJ = ("I", "J")


def _rate(pct_val):
    if pct_val is None:
        return None
    return float(pct_val) / 100.0


def _end_incl(end_excl: str):
    return date_cls.fromisoformat(end_excl) - timedelta(days=1)


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print("querying...", flush=True)
    cols, rows = query(sql)
    out = [dict(zip(cols, r)) for r in rows]
    for r in out:
        if r["slice_type"] == "aggregate":
            print(
                r["group_kind"],
                r["group_key"],
                "n=", r["activate_uv"],
                "hit=", r["wall_hit_7d_pct"],
                "mature_hit=", r["wall_hit_7d_pct_mature"],
                flush=True,
            )

    wb = Workbook()
    bold = Font(bold=True)
    pct_fmt = "0.00%"

    # ---- 总览 ABCD ----
    ws = wb.active
    ws.title = "总览_ABCD"
    ws["A1"] = "旧版付费硬墙 · 新用户 7 日触墙率（T046）"
    ws["A1"].font = bold
    ws["A2"] = (
        "分母=P034激活 + P039剔老号（createtime<激活−1天）；"
        "分子=激活后7日内 user_need_pro+freeUsageLimitModal；"
        "周切片同 T018；obs 至 2026-09-30。"
        "率列为百分比，分母=激活设备。"
    )
    ws["A3"] = (
        "【未熟说明】wall_hit_7d_pct 含未满7d观察的激活；"
        "wall_hit_7d_pct_mature 仅 act+7d≤obs 的设备。"
        "D 含 j（新赠送墙），旧硬墙触达会被拉低 → 见「总览_IJ」。"
    )

    agg_abcd = {
        r["group_key"]: r
        for r in out
        if r["slice_type"] == "aggregate" and r["group_kind"] == "ABCD"
    }
    hdr = [
        "实验组", "激活(剔老号)", "7d触墙UV", "7d触墙率%",
        "激活(7d已满)", "7d触墙UV(已满)", "7d触墙率%(已满分母)",
    ]
    for i, h in enumerate(hdr, 1):
        ws.cell(5, i, h).font = bold
    for i, g in enumerate(GROUPS_ABCD):
        a = agg_abcd[g]
        r = 6 + i
        vals = [
            g,
            int(a["activate_uv"]),
            int(a["wall_hit_7d_uv"]),
            _rate(a["wall_hit_7d_pct"]),
            int(a["activate_uv_mature7d"]),
            int(a["wall_hit_7d_uv_mature"]),
            _rate(a["wall_hit_7d_pct_mature"]),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c, v)
            if c in (4, 7) and v is not None:
                cell.number_format = pct_fmt

    # ---- 总览 IJ ----
    ws2 = wb.create_sheet("总览_IJ")
    ws2["A1"] = "D 组内 I vs J · 旧硬墙 7 日触墙率"
    ws2["A1"].font = bold
    ws2["A2"] = "I=旧墙对照；J=loginAiQuotaGift（通常关旧硬墙）。分母同 P034+P039。"
    agg_ij = {
        r["group_key"]: r
        for r in out
        if r["slice_type"] == "aggregate" and r["group_kind"] == "IJ"
    }
    for i, h in enumerate(hdr, 1):
        ws2.cell(4, i, h).font = bold
    for i, g in enumerate(GROUPS_IJ):
        a = agg_ij[g]
        r = 5 + i
        vals = [
            g,
            int(a["activate_uv"]),
            int(a["wall_hit_7d_uv"]),
            _rate(a["wall_hit_7d_pct"]),
            int(a["activate_uv_mature7d"]),
            int(a["wall_hit_7d_uv_mature"]),
            _rate(a["wall_hit_7d_pct_mature"]),
        ]
        for c, v in enumerate(vals, 1):
            cell = ws2.cell(r, c, v)
            if c in (4, 7) and v is not None:
                cell.number_format = pct_fmt

    # ---- 周明细 ----
    def write_week_sheet(title: str, kind: str, groups: tuple[str, ...]) -> None:
        w = wb.create_sheet(title)
        w["A1"] = title
        w["A1"].font = bold
        w["A2"] = "明细：激活÷7d触墙；率%=÷激活；成熟列仅满7d观察窗。"
        detail_h = [
            "同期群", "安装开始", "安装结束", "成熟状态", "组",
            "激活", "7d触墙UV", "7d触墙率%",
            "激活(已满7d)", "触墙UV(已满)", "触墙率%(已满)",
        ]
        for i, h in enumerate(detail_h, 1):
            w.cell(4, i, h).font = bold
        weekly = [
            r for r in out
            if r["slice_type"] == "weekly" and r["group_kind"] == kind
        ]
        by_slice: dict[str, dict] = {}
        for r in weekly:
            by_slice.setdefault(r["slice"], {"meta": r, "g": {}})
            by_slice[r["slice"]]["g"][r["group_key"]] = r
        slice_order = sorted(
            by_slice.keys(), key=lambda s: by_slice[s]["meta"]["cohort_no"]
        )
        ri = 5
        for sk in slice_order:
            meta = by_slice[sk]["meta"]
            for g in groups:
                rec = by_slice[sk]["g"][g]
                w.cell(ri, 1, SLICE_LABEL.get(sk, sk))
                w.cell(ri, 2, date_cls.fromisoformat(meta["install_start"]))
                w.cell(ri, 3, _end_incl(meta["install_end_excl"]))
                w.cell(ri, 4, meta["maturity_status"])
                w.cell(ri, 5, g)
                w.cell(ri, 6, int(rec["activate_uv"]))
                w.cell(ri, 7, int(rec["wall_hit_7d_uv"]))
                cell = w.cell(ri, 8, _rate(rec["wall_hit_7d_pct"]))
                cell.number_format = pct_fmt
                w.cell(ri, 9, int(rec["activate_uv_mature7d"]))
                w.cell(ri, 10, int(rec["wall_hit_7d_uv_mature"]))
                cell = w.cell(ri, 11, _rate(rec["wall_hit_7d_pct_mature"]))
                if cell.value is not None:
                    cell.number_format = pct_fmt
                ri += 1
        # aggregate rows
        ri += 1
        w.cell(ri, 1, "汇总").font = bold
        ri += 1
        agg = {
            r["group_key"]: r
            for r in out
            if r["slice_type"] == "aggregate" and r["group_kind"] == kind
        }
        for g in groups:
            rec = agg[g]
            w.cell(ri, 1, SLICE_LABEL["aggregate_0821_0928"])
            w.cell(ri, 2, date_cls(2026, 8, 21))
            w.cell(ri, 3, date_cls(2026, 9, 28))
            w.cell(ri, 4, "混合成熟度")
            w.cell(ri, 5, g)
            w.cell(ri, 6, int(rec["activate_uv"]))
            w.cell(ri, 7, int(rec["wall_hit_7d_uv"]))
            cell = w.cell(ri, 8, _rate(rec["wall_hit_7d_pct"]))
            cell.number_format = pct_fmt
            w.cell(ri, 9, int(rec["activate_uv_mature7d"]))
            w.cell(ri, 10, int(rec["wall_hit_7d_uv_mature"]))
            cell = w.cell(ri, 11, _rate(rec["wall_hit_7d_pct_mature"]))
            if cell.value is not None:
                cell.number_format = pct_fmt
            ri += 1

    write_week_sheet("周明细_ABCD", "ABCD", GROUPS_ABCD)
    write_week_sheet("周明细_IJ", "IJ", GROUPS_IJ)

    ws3 = wb.create_sheet("口径")
    ws3["A1"] = "口径"
    ws3["A1"].font = bold
    notes = [
        ("墙", "user_need_pro + trigger=freeUsageLimitModal（仅硬墙）"),
        ("分母", "P034 激活 + P039 剔老号（userid.createtime < first_ts−1天）"),
        ("userid来源", "deviceinfo ∪ 激活行 ex_int_arg1"),
        ("分子", "同设备激活后 7 日内曾触硬墙"),
        ("分组", "A=a/b/c；B=d/e/f；C=g/h；D=i/j；另附 I/J"),
        ("周", "同 T018 asof=09-28 切片；激活窗右开 09-28 16:00 UTC"),
        ("obs", "墙事件至 2026-09-30 16:00 UTC；近周 7d 未熟见 mature 列"),
        ("百分比", "触墙率%=触墙UV÷激活；mature 列÷已满7d激活"),
    ]
    for i, (a, b) in enumerate(notes, 3):
        ws3.cell(i, 1, a)
        ws3.cell(i, 2, b)

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    print(f"wrote {OUT_XLSX}", flush=True)

    # sample: weekly sum == agg for A
    ok = True
    for kind, groups in (("ABCD", GROUPS_ABCD), ("IJ", GROUPS_IJ)):
        weekly = [r for r in out if r["slice_type"] == "weekly" and r["group_kind"] == kind]
        agg = {
            r["group_key"]: r
            for r in out
            if r["slice_type"] == "aggregate" and r["group_kind"] == kind
        }
        for g in groups:
            s = sum(int(r["activate_uv"]) for r in weekly if r["group_key"] == g)
            a = int(agg[g]["activate_uv"])
            if s != a:
                print(f"FAIL sum {kind}/{g} weekly={s} agg={a}")
                ok = False
    # A should have higher hard-wall hit than J on mature if gift replaces wall
    if float(agg_ij["J"]["wall_hit_7d_pct"]) > float(agg_abcd["A"]["wall_hit_7d_pct"]):
        print("WARN: J hard-wall hit > A (unexpected if gift replaces wall)", flush=True)
    print(f"【抽样复核】周加总=汇总；结论={'通过' if ok else '不通过'}", flush=True)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
