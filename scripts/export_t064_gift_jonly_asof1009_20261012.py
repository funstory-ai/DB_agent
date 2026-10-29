# -*- coding: utf-8 -*-
"""T064 旧版 j-only：asof=2026-10-09（扩量前），含 P042；不混入 10-10 起 50% 流量。"""
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
SQL_PATH = (
    ROOT
    / "sql"
    / "reports"
    / "query_login_ai_quota_gift_weekly_ge1332_jonly_asof1009_20261012.sql"
)
OUT_XLSX = (
    ROOT
    / "output"
    / "login_ai_quota_gift"
    / "gift_weekly_p034_dual_ge1332_jonly_asof1009_20261012.xlsx"
)
ASOF = "2026-10-09"
AGG_SLICE = "aggregate_0922_1009"
VERSION_NOTE = "激活行语义化 version>=1.33.2（商店发版起；P040）"
GROUPS = ("A", "B", "C", "I", "J")
SCOPES = (
    ("A_all", "口径A·全量P034"),
    ("B_excl_old_acct", "口径B·剔老号(ACCT<激活-1天)"),
)
SLICE_LABEL = {
    "natural_week_0922_0927": "09/22–27（发版后）",
    "natural_week_0928_1004": "09/28自然周",
    "natural_week_1005_1009": "10/05–09（扩量前截断）",
    AGG_SLICE: "汇总（09-22～10-09·扩量前）",
}
AGG_START = "2026-09-22"
AGG_END_EXCL = "2026-10-10"
AGG_END_INCL = date_cls(2026, 10, 9)


def _rate(pct_val):
    if pct_val is None:
        return None
    return float(pct_val) / 100.0


def _end_incl(end_excl: str):
    return date_cls.fromisoformat(end_excl) - timedelta(days=1)


def write_overview(ws, agg: dict, title: str, note: str) -> None:
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    ws["A1"] = title
    ws["A1"].font = bold
    ws["A2"] = note
    ws["A3"] = (
        "【分母说明】下表除「激活设备」外，其余列均为百分比，"
        "分母一律=该口径本行「激活设备」UV。"
        "去付费→付费率÷去付费人数。"
    )
    funnel_h = [
        "实验组",
        "激活设备(分母)",
        "注册率%",
        "3d checkout%",
        "3d 试用%",
        "3d 付费%",
        "7d 付费%",
        "累计付费人数(总付费)",
        "累计付费%",
        "登录弹窗%",
        "立即登录%",
        "登录关闭%",
        "领取成功%",
        "耗尽墙%",
        "耗尽去付费人数",
        "耗尽去付费%",
        "去付费后付费人数",
        "去付费→付费率%(÷去付费)",
        "耗尽关闭%",
    ]
    ws["A5"] = "汇总（除「去付费→付费率」外，率列分母=激活设备）"
    ws["A5"].font = bold
    for i, h in enumerate(funnel_h, 1):
        ws.cell(6, i, h).font = bold
    for i, g in enumerate(GROUPS):
        r = 7 + i
        a = agg[g]
        vals = [
            g,
            int(a["new_devices"]),
            _rate(a["register_rate_pct"]),
            _rate(a["checkout_3d_pct"]),
            _rate(a["trial_3d_pct"]),
            _rate(a["paid_3d_pct"]),
            _rate(a["paid_7d_pct"]),
            int(a["paid_to_asof"] or 0),
            _rate(a["paid_to_asof_pct"]),
            _rate(a["gift_login_show_pct"]),
            _rate(a["gift_login_click_pct"]),
            _rate(a["gift_login_close_pct"]),
            _rate(a["gift_claim_pct"]),
            _rate(a["gift_exhausted_show_pct"]),
            int(a["gift_exhausted_pay"] or 0),
            _rate(a["gift_exhausted_pay_pct"]),
            int(a["gift_exhausted_pay_then_paid"] or 0),
            _rate(a["gift_exhausted_pay_then_paid_pct"]),
            _rate(a["gift_exhausted_close_pct"]),
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(r, col, v)
            if col in (3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 18, 19) and v is not None:
                cell.number_format = pct_fmt


def write_weekly(ws, scope_rows: list[dict], title: str) -> None:
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    ws["A1"] = title
    ws["A1"].font = bold

    weekly = [r for r in scope_rows if r["slice_type"] == "weekly"]
    by_slice: dict[str, dict] = {}
    for r in weekly:
        by_slice.setdefault(r["slice"], {"meta": r, "g": {}})
        by_slice[r["slice"]]["g"][r["exp_group"]] = r
    agg = {r["exp_group"]: r for r in scope_rows if r["slice_type"] == "aggregate"}
    slice_order = sorted(by_slice.keys(), key=lambda s: by_slice[s]["meta"]["cohort_no"])
    n_g = len(GROUPS)

    for i, h in enumerate(
        ["同期群", "安装开始", "安装结束", "成熟状态"] + list(GROUPS), 1
    ):
        ws.cell(4, i, h).font = bold
    ws["A3"] = "累计付费率"
    ws["A3"].font = bold

    detail_start = 8 + len(slice_order)
    for si, sk in enumerate(slice_order):
        meta = by_slice[sk]["meta"]
        r = 5 + si
        ws.cell(r, 1, SLICE_LABEL.get(sk, sk))
        ws.cell(r, 2, date_cls.fromisoformat(meta["install_start"]))
        ws.cell(r, 3, _end_incl(meta["install_end_excl"]))
        ws.cell(r, 4, meta["maturity_status"])
        base = detail_start + si * n_g
        for j, _g in enumerate(GROUPS):
            cell = ws.cell(r, 5 + j, f"=M{base + j}")
            cell.number_format = pct_fmt
    mat_agg = 5 + len(slice_order)
    ws.cell(mat_agg, 1, SLICE_LABEL[AGG_SLICE])
    ws.cell(mat_agg, 2, date_cls.fromisoformat(AGG_START))
    ws.cell(mat_agg, 3, AGG_END_INCL)
    ws.cell(mat_agg, 4, "混合成熟度·扩量前")
    agg_start = detail_start + len(slice_order) * n_g + 2
    for j, _g in enumerate(GROUPS):
        cell = ws.cell(mat_agg, 5 + j, f"=M{agg_start + j}")
        cell.number_format = pct_fmt

    hdr_row = detail_start - 1
    ws.cell(hdr_row - 1, 1, "明细").font = bold
    detail_h = [
        "同期群", "安装开始", "安装结束", "成熟状态", "实验组", "激活设备(分母)",
        "注册率%", "3d checkout%", "3d 试用%", "3d 付费%", "7d 付费%",
        "累计付费人数", "累计付费率%(÷激活)",
        "W1留存%", "W2留存%", "W3留存%", "W4留存%",
        "登录弹窗UV", "登录弹窗%(÷激活)", "立即登录UV", "立即登录%(÷激活)",
        "登录关闭UV", "登录关闭%(÷激活)", "领取UV", "领取%(÷激活)",
        "耗尽墙UV", "耗尽墙%(÷激活)", "耗尽去付费UV", "耗尽去付费%(÷激活)",
        "去付费后付费人数", "去付费→付费率%(÷去付费)",
        "耗尽关闭UV", "耗尽关闭%(÷激活)",
    ]
    for i, h in enumerate(detail_h, 1):
        ws.cell(hdr_row, i, h).font = bold

    def write_detail_row(r, label, start, end_excl, maturity, rec):
        ws.cell(r, 1, label)
        ws.cell(r, 2, date_cls.fromisoformat(start))
        ws.cell(r, 3, _end_incl(end_excl))
        ws.cell(r, 4, maturity)
        ws.cell(r, 5, rec["exp_group"])
        ws.cell(r, 6, int(rec["new_devices"]))
        for col, key in enumerate(
            ["register_rate_pct", "checkout_3d_pct", "trial_3d_pct",
             "paid_3d_pct", "paid_7d_pct"],
            7,
        ):
            cell = ws.cell(r, col, _rate(rec[key]))
            cell.number_format = pct_fmt
        ws.cell(r, 12, int(rec["paid_to_asof"]))
        cell = ws.cell(r, 13, f"=L{r}/F{r}")
        cell.number_format = pct_fmt
        for col, key in enumerate(
            ["ret_w1_pct", "ret_w2_pct", "ret_w3_pct", "ret_w4_pct"], 14
        ):
            v = rec[key]
            if v is None:
                ws.cell(r, col, None)
            else:
                cell = ws.cell(r, col, _rate(v))
                cell.number_format = pct_fmt
        gift_pairs = [
            ("gift_login_show", "gift_login_show_pct"),
            ("gift_login_click", "gift_login_click_pct"),
            ("gift_login_close", "gift_login_close_pct"),
            ("gift_claim", "gift_claim_pct"),
            ("gift_exhausted_show", "gift_exhausted_show_pct"),
            ("gift_exhausted_pay", "gift_exhausted_pay_pct"),
        ]
        col = 18
        for cnt_k, pct_k in gift_pairs:
            ws.cell(r, col, int(rec[cnt_k] or 0))
            cell = ws.cell(r, col + 1, _rate(rec[pct_k]))
            cell.number_format = pct_fmt
            col += 2
        ws.cell(r, col, int(rec["gift_exhausted_pay_then_paid"] or 0))
        cell = ws.cell(r, col + 1, _rate(rec["gift_exhausted_pay_then_paid_pct"]))
        if rec["gift_exhausted_pay_then_paid_pct"] is not None:
            cell.number_format = pct_fmt
        col += 2
        ws.cell(r, col, int(rec["gift_exhausted_close"] or 0))
        cell = ws.cell(r, col + 1, _rate(rec["gift_exhausted_close_pct"]))
        cell.number_format = pct_fmt

    ri = detail_start
    for sk in slice_order:
        meta = by_slice[sk]["meta"]
        for g in GROUPS:
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
    for g in GROUPS:
        write_detail_row(
            ri,
            SLICE_LABEL[AGG_SLICE],
            AGG_START,
            AGG_END_EXCL,
            "混合成熟度·扩量前",
            agg[g],
        )
        ri += 1


def sample_validate() -> bool:
    """短窗北京 10-08：验 P039；非 j 登录弹窗应近 0（扩量前）。"""
    print("\n【抽样复核】旧版扩量前…", flush=True)
    sql_non_j = r"""
    SELECT
      count(DISTINCT CASE WHEN lower(trim(ab_tag)) BETWEEN 'a' AND 'i'
        THEN device_id END) AS non_j_show,
      count(DISTINCT CASE WHEN lower(trim(ab_tag)) = 'j'
        THEN device_id END) AS j_show
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-10-08 16:00:00' AND created_ts < '2026-10-09 16:00:00'
      AND event_name = 'login_ai_quota_gift_login_modal_show'
      AND ab_tag IS NOT NULL AND length(trim(ab_tag)) = 1
    """
    cols, rows = query(sql_non_j)
    d = dict(zip(cols, rows[0]))
    print(d, flush=True)
    ok = int(d["j_show"] or 0) > 100
    # 扩量前非 j 应远小于 j（允许个位数噪声）
    if int(d["non_j_show"] or 0) > int(d["j_show"] or 0) * 0.05:
        print("FAIL non-j gift show too high before 50% rollout")
        ok = False
    return ok


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print("querying j-only asof=10-09...", flush=True)
    cols, rows = query(sql)
    out = [dict(zip(cols, r)) for r in rows]
    by_scope: dict[str, list] = {}
    for r in out:
        by_scope.setdefault(r["metric_scope"], []).append(r)

    for scope, label in SCOPES:
        print(f"\n=== {scope} {label} ===", flush=True)
        for r in by_scope[scope]:
            if r["slice_type"] != "aggregate":
                continue
            print(
                r["exp_group"],
                "n=", r["new_devices"],
                "login%=", r["gift_login_show_pct"],
                "exh_pay=", r.get("gift_exhausted_pay"),
                "exh→paid=", r.get("gift_exhausted_pay_then_paid"),
                flush=True,
            )

    wb = Workbook()
    bold = Font(bold=True)
    scope0, label0 = SCOPES[0]
    agg0 = {r["exp_group"]: r for r in by_scope[scope0] if r["slice_type"] == "aggregate"}
    ws = wb.active
    ws.title = "总览_A全量"
    write_overview(
        ws,
        agg0,
        f"登录赠送·旧版仅j（T064）· {label0}",
        f"观察截止 asof={ASOF}（10-10 50%扩量前）；{VERSION_NOTE}；I=i对照，J=j实验。"
        "不含扩量后流量。",
    )
    scope1, label1 = SCOPES[1]
    agg1 = {r["exp_group"]: r for r in by_scope[scope1] if r["slice_type"] == "aggregate"}
    write_overview(
        wb.create_sheet("总览_B剔老号"),
        agg1,
        f"登录赠送·旧版仅j（T064）· {label1}",
        f"口径B剔老号；asof={ASOF}；扩量前截断。",
    )
    write_weekly(wb.create_sheet("周_A全量"), by_scope[scope0], f"周同期群 · {label0}")
    write_weekly(wb.create_sheet("周_B剔老号"), by_scope[scope1], f"周同期群 · {label1}")

    ws2 = wb.create_sheet("口径")
    ws2["A1"] = "口径"
    ws2["A1"].font = bold
    notes = [
        ("阶段", "旧版 j-only：config abTagNumber>8；观察/激活均 < 2026-10-10"),
        ("新版", "见 T065 / gift_*_50pct_from1010_*（Ctrl a–e vs Treat f–j）"),
        ("版本", VERSION_NOTE),
        ("口径B", "剔老号 createtime<激活-1天（P039）"),
        ("去付费→付费", "P042 订单≥点击−1天"),
        ("分组", "A=a/b/c；B=d/e/f；C=g/h；I=i；J=j"),
        ("需求", "T064"),
    ]
    for i, (a, b) in enumerate(notes, 3):
        ws2.cell(i, 1, a)
        ws2.cell(i, 2, b)

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    print(f"\nwrote {OUT_XLSX}", flush=True)

    ok = True
    for scope, _label in SCOPES:
        scope_rows = by_scope[scope]
        weekly = [r for r in scope_rows if r["slice_type"] == "weekly"]
        agg = {r["exp_group"]: r for r in scope_rows if r["slice_type"] == "aggregate"}
        for g in GROUPS:
            s = sum(int(r["new_devices"]) for r in weekly if r["exp_group"] == g)
            a = int(agg[g]["new_devices"])
            if s != a:
                print(f"FAIL {scope} sum {g} weekly={s} agg={a}")
                ok = False
        if int(agg["J"]["gift_login_show"] or 0) <= 0:
            print(f"FAIL {scope} J should have login_show")
            ok = False
        # 扩量前：A/B/C/I 登录弹窗%应接近 0
        for g in ("A", "B", "C", "I"):
            pct = float(agg[g]["gift_login_show_pct"] or 0)
            if pct > 1.0:
                print(f"FAIL {scope} {g} login_show_pct={pct} (expect ~0 pre-rollout)")
                ok = False
        j = agg["J"]
        exh = int(j["gift_exhausted_pay"] or 0)
        then_paid = int(j["gift_exhausted_pay_then_paid"] or 0)
        total_paid = int(j["paid_to_asof"] or 0)
        if then_paid > exh or then_paid > total_paid:
            print(f"FAIL {scope} J then_paid inconsistent")
            ok = False
        print(
            f"{scope} J n={j['new_devices']} login%={j['gift_login_show_pct']} "
            f"总付费={total_paid} 去付费={exh}→付费={then_paid}",
            flush=True,
        )

    # W1：09/22、09/28 应有；10/05 截断周应空
    for scope, _label in SCOPES:
        for r in by_scope[scope]:
            if r["slice"] in ("natural_week_0922_0927", "natural_week_0928_1004"):
                n = int(r["new_devices"] or 0)
                w1 = r["ret_w1_pct"]
                if w1 is None:
                    print(f"FAIL {scope} {r['slice']} should have W1")
                    ok = False
                elif n >= 500 and float(w1) <= 0:
                    print(f"FAIL {scope} {r['slice']} W1 fake zero")
                    ok = False
            if r["slice"] == "natural_week_1005_1009" and r["ret_w1_pct"] is not None:
                print(f"FAIL {scope} 1005 W1 should be empty")
                ok = False

    a_n = int(agg0["J"]["new_devices"])
    b_n = int(agg1["J"]["new_devices"])
    if b_n >= a_n:
        print(f"FAIL B should shrink vs A for J")
        ok = False

    ok = ok and sample_validate()
    print(f"【抽样复核】结论={'通过' if ok else '不通过'}", flush=True)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
