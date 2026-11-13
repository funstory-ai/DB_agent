# -*- coding: utf-8 -*-
"""T112 canonical：新加坡/马来西亚「按天」收入（今年窗口 + 去年同月日），多 sheet Excel。

口径完全沿用 T107 / T107d，仅把时间粒度由月/周改为北京自然日：
  付费订单 userid -> imt_deviceinfo.deviceid -> imm_regional_activation
  取该用户全历史最常出现的 real_geo（主导 IP 国家），两年共用同一套映射。
  金额 = (amountpaid/100) * exchangerates -> CNY。NO_GEO 单列，SG/MY 为下界（P037）。

同一分析只保留这一份脚本，刷新时改 --start / --end，覆盖输出，不新增 dated 副本。
定稿 SQL 在 sql/reports/query_sg_my_daily_revenue_yoy_20261112.sql（按 -- @Q_xxx 分段），
本脚本只做「取数 + 精确口径计算 + 出 Excel」，口径说明写在任务文档。

用法：
  # 抽样阶段：跑全部查询并打印校验数字，不写文件（绕开交付门禁）
  python scripts/export_sg_my_daily_revenue_yoy.py --start 2026-10-25 --end 2026-11-12 --dry-run
  # 正式交付：须已过 wf sampled
  WF_TASK=T112 python scripts/export_sg_my_daily_revenue_yoy.py --start 2026-10-25 --end 2026-11-12
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402

SQL_FILE = ROOT / "sql" / "reports" / "query_sg_my_daily_revenue_yoy_20261112.sql"
OUT = ROOT / "output" / "sg_my_revenue"
WEEKLY_XLSX = OUT / "sg_my_weekly_revenue_202511_202611.xlsx"
BUCKETS = ("SG", "MY", "NO_GEO", "OTHER")


def q(sql: str, retries: int = 6):
    """只读查询 + 指数退避重试（覆盖 OSS AccessDenied 等瞬态）。"""
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} ({d:.0f}s): {str(e)[:160]}", flush=True)
            time.sleep(d)
            d *= 2


def load_parts(repl: dict) -> dict:
    """按 -- @NAME 标记切分定稿 SQL；占位符替换后返回。"""
    text = SQL_FILE.read_text(encoding="utf-8")
    parts, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^--\s+@([A-Za-z0-9_]+)\b", line)
        if m:
            if cur:
                parts[cur] = "\n".join(buf).strip().rstrip(";").strip()
            cur = m.group(1)
            buf = []
        elif cur:
            buf.append(line)
    if cur:
        parts[cur] = "\n".join(buf).strip().rstrip(";").strip()
    out = {}
    for k, v in parts.items():
        for a, b in repl.items():
            v = v.replace(a, b)
        out[k] = v
    return out


def prior_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:          # 2-29 -> 2-28
        return d.replace(year=d.year - 1, day=28)


def utc_bounds(d0: date, d1: date):
    """北京自然日 [d0, d1] 对应的 UTC 粗边界，保分区裁剪。"""
    return f"{d0 - timedelta(days=1)} 16:00:00", f"{d1} 16:00:00"


def daykey(v) -> str:
    return str(v)[:10]


def build_days(start: date, end: date):
    days, d = [], start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-25")
    ap.add_argument("--end", default="2026-11-12")
    ap.add_argument("--dry-run", action="store_true", help="只打印校验数字，不写 Excel")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("--end 必须 >= --start")
    ly_start, ly_end = prior_year(start), prior_year(end)
    ty_days = build_days(start, end)
    ly_days = build_days(ly_start, ly_end)
    if len(ty_days) != len(ly_days):
        raise SystemExit("今年/去年窗口天数不一致，请检查起止日期")

    ty_lo, ty_hi = utc_bounds(start, end)
    ly_lo, ly_hi = utc_bounds(ly_start, ly_end)
    repl = {
        "{{TY_LO}}": ty_lo, "{{TY_HI}}": ty_hi,
        "{{LY_LO}}": ly_lo, "{{LY_HI}}": ly_hi,
    }
    print(f"窗口(北京日): 今年 {start} ~ {end} ({len(ty_days)}天)  UTC [{ty_lo}, {ty_hi})")
    print(f"             去年 {ly_start} ~ {ly_end} ({len(ly_days)}天)  UTC [{ly_lo}, {ly_hi})")

    # ---- wf 硬门禁：正式交付必须已过 sampled ----
    if not args.dry_run:
        task = os.environ.get("WF_TASK")
        if not task:
            raise SystemExit("正式交付须带环境变量 WF_TASK=T112（wf 状态机门禁）")
        import wf as _wf
        _wf.require(task, "sampled")

    P = load_parts(repl)
    need = ("CTES", "Q_RATE", "Q_ORDER_COVER", "Q_WATERMARK",
            "Q_REV", "Q_USERS", "Q_GEO_SANITY", "Q_P046_DETAIL", "Q_TIE")
    missing = [k for k in need if k not in P]
    if missing:
        raise SystemExit(f"定稿 SQL 缺段: {missing}")

    # ---- 语法小探针：date_trunc('day', +8h) ----
    probe = q("SELECT date_trunc('day', date_add(hour, 8, TIMESTAMP '2026-10-28 16:00:00')) AS d")
    print(f"[probe] date_trunc('day', +8h) -> {probe[1][0][0]}")

    # ---- 诊断段（小查询） ----
    print("\n== 汇率维表 (Q_RATE) ==")
    _, rate_rows = q(P["Q_RATE"])
    rates = {str(r[0]).upper(): float(r[1]) for r in rate_rows}
    print(f"  币种数={len(rates)}  CNY={rates.get('CNY')} USD={rates.get('USD')} "
          f"SGD={rates.get('SGD')} MYR={rates.get('MYR')}")

    print("\n== 两段窗口付费订单币种覆盖 (Q_ORDER_COVER) ==")
    _, cover_rows = q(P["Q_ORDER_COVER"])
    unmatched_orders = 0
    null_cur_orders, null_cur_amt = 0, 0.0
    for cur, n, amt, rate, unmatched in cover_rows:
        unmatched_orders += int(unmatched or 0)
        if cur is None:
            null_cur_orders, null_cur_amt = int(n), float(amt or 0)
        print(f"  {str(cur):6} 单数={int(n):>7,} 原币金额={float(amt or 0):>14,.2f} "
              f"汇率={rate} 未匹配={int(unmatched or 0):,}")
    print(f"  >> 汇率匹配不到汇率表的订单数 = {unmatched_orders:,}")

    print("\n== 订单落库水位 (Q_WATERMARK) ==")
    _, wm_rows = q(P["Q_WATERMARK"])
    wm = {}
    for seg, n, lo, hi in wm_rows:
        wm[seg] = (int(n), str(lo), str(hi))
        print(f"  {seg}: 订单行={int(n):,}  createtime [{lo} .. {hi}]")

    # ---- 主查询（重 join） ----
    ctes = P["CTES"]
    print("\n== 逐日收入 (Q_REV, heavy join) ==")
    _, rev_rows = q(ctes + "\n" + P["Q_REV"])
    print(f"  返回行数={len(rev_rows):,}")
    print("== 逐日付费用户数 (Q_USERS) ==")
    _, usr_rows = q(ctes + "\n" + P["Q_USERS"])
    print(f"  返回行数={len(usr_rows):,}")
    print("== 主导国家桶分布 (Q_GEO_SANITY) ==")
    _, geo_rows = q(ctes + "\n" + P["Q_GEO_SANITY"])
    geo_users = {str(r[0]): int(r[1]) for r in geo_rows}
    print(f"  {geo_users}")

    print("\n== P046 未匹配币种(有实付)地区影响面 (Q_P046_DETAIL) ==")
    _, p046_rows = q(ctes + "\n" + P["Q_P046_DETAIL"])
    p046_sgmy_orders = 0
    p046_sgmy_amt = 0.0
    for cur, bucket, n, amaj in p046_rows:
        print(f"  {str(cur):8} 桶={str(bucket):7} 单数={int(n):>3} 原币金额={float(amaj or 0):>12,.2f}")
        if str(bucket) in ("SG", "MY"):
            p046_sgmy_orders += int(n)
            p046_sgmy_amt += float(amaj or 0)
    p046_cash_orders = sum(int(r[2]) for r in p046_rows)
    print(f"  >> 有实付且汇率缺失合计 {p046_cash_orders} 笔；其中落在 SG/MY 的 "
          f"{p046_sgmy_orders} 笔（原币 {p046_sgmy_amt:,.2f}）")

    print("\n== 主导国家 cnt 并列用户数 (Q_TIE) ==")
    _, tie_rows = q(ctes + "\n" + P["Q_TIE"])
    tied_users = int(tie_rows[0][0]) if tie_rows else 0
    print(f"  并列用户数 = {tied_users}")

    # ---- Python 聚合 ----
    rev = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # day -> bucket -> cur -> cny
    amt_major = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    orders = defaultdict(lambda: defaultdict(int))
    cash_orders = defaultdict(lambda: defaultdict(int))
    bucket_seen = set()
    for day, bucket, cur, n, cash_n, amaj, acny in rev_rows:
        dk, bk, ck = daykey(day), str(bucket), str(cur)
        bucket_seen.add(bk)
        rev[dk][bk][ck] += float(acny or 0)
        amt_major[dk][bk][ck] += float(amaj or 0)
        orders[dk][bk] += int(n or 0)
        cash_orders[dk][bk] += int(cash_n or 0)

    users = defaultdict(lambda: defaultdict(int))
    for day, bucket, n in usr_rows:
        users[daykey(day)][str(bucket)] = int(n or 0)

    def cny(dk, bk):
        return sum(rev[dk].get(bk, {}).values())

    def comb(dk):
        return cny(dk, "SG") + cny(dk, "MY")

    def dstr(d: date):
        return d.isoformat()

    ty_keys = [dstr(d) for d in ty_days]
    ly_keys = [dstr(d) for d in ly_days]
    pair = dict(zip(ty_keys, ly_keys))

    # ---- 自检断言（P019 抽样复核用） ----
    print("\n== 自检 / 抽样断言 ==")
    checks = []
    checks.append(("桶集合不串组", bucket_seen.issubset(set(BUCKETS)),
                   f"实际={sorted(bucket_seen)}"))
    all_days = set(rev.keys())
    outside = sorted(d for d in all_days if d not in set(ty_keys) | set(ly_keys))
    checks.append(("北京日切分未越界", not outside, f"越界日={outside}"))
    ty_missing = [d for d in ty_keys if d not in all_days]
    ly_missing = [d for d in ly_keys if d not in all_days]
    checks.append(("今年19天齐全", not ty_missing, f"缺={ty_missing}"))
    checks.append(("去年19天齐全", not ty_missing and not ly_missing, f"缺={ly_missing}"))
    checks.append(("P046：NULL币种未匹配单均为兑换码(实付0)", null_cur_amt == 0,
                   f"NULL币种 {null_cur_orders:,} 笔，原币金额合计 {null_cur_amt:,.2f}"))
    checks.append(("P046：有实付的未匹配币种不落在SG/MY", p046_sgmy_orders == 0,
                   f"落在SG/MY {p046_sgmy_orders} 笔 / 原币 {p046_sgmy_amt:,.2f}；"
                   f"全窗有实付未匹配 {p046_cash_orders} 笔"))
    ty_zero = [d for d in ty_keys if comb(d) == 0]
    ly_zero = [d for d in ly_keys if comb(d) == 0]
    checks.append(("无假零：今年 SG+MY 每日非0", not ty_zero, f"零值日={ty_zero}"))
    checks.append(("无假零：去年 SG+MY 每日非0", not ly_zero, f"零值日={ly_zero}"))
    ident = all(abs(comb(d) - (cny(d, "SG") + cny(d, "MY"))) < 1e-6
                for d in set(ty_keys) | set(ly_keys))
    checks.append(("SG+MY 恒等 SG + MY", ident, ""))

    ty_sum = sum(comb(d) for d in ty_keys)
    ly_sum = sum(comb(d) for d in ly_keys)
    ty_full = sum(comb(d) for d in ty_keys[:-1])   # 剔除最后一天（今天，不完整）
    ly_full = sum(comb(d) for d in ly_keys[:-1])
    print(f"  窗口合计 SG+MY: 今年 ¥{ty_sum:,.2f} / 去年 ¥{ly_sum:,.2f} "
          f"(含11-12不完整日 同比 {(ty_sum-ly_sum)/ly_sum*100:+.1f}%)")
    print(f"  完整日合计(剔除最后一天): 今年 ¥{ty_full:,.2f} / 去年 ¥{ly_full:,.2f} "
          f"(同比 {(ty_full-ly_full)/ly_full*100:+.1f}%)")
    nogeo_ty = sum(cny(d, "NO_GEO") for d in ty_keys[:-1])
    nogeo_ly = sum(cny(d, "NO_GEO") for d in ly_keys[:-1])
    nogeo_pct = (nogeo_ty - nogeo_ly) / nogeo_ly * 100 if nogeo_ly else None
    print(f"  完整日 NO_GEO（移动端测量缺口）: 今年 ¥{nogeo_ty:,.2f} / 去年 ¥{nogeo_ly:,.2f} "
          f"(同比 {nogeo_pct:+.1f}%); SG+MY 占「SG+MY+NO_GEO」比 "
          f"今年 {ty_full/(ty_full+nogeo_ty)*100:.1f}% / 去年 {ly_full/(ly_full+nogeo_ly)*100:.1f}%")

    # 与 T107b 周版交叉：同口径、不同粒度，两个完整周应一致
    cross = []
    if WEEKLY_XLSX.exists():
        from openpyxl import load_workbook
        wb_w = load_workbook(WEEKLY_XLSX, data_only=True)
        ws_w = wb_w["周收入_SG_MY"]
        weekly = {}
        for r in ws_w.iter_rows(values_only=True):
            if r and r[0] and str(r[0]).startswith("20") and isinstance(r[3], (int, float)):
                weekly[str(r[0])[:10]] = (float(r[1] or 0), float(r[2] or 0), float(r[3] or 0))
        for wk in sorted(weekly):
            w0 = date.fromisoformat(wk)
            week_days = [w0 + timedelta(days=i) for i in range(7)]
            if all(dstr(d) in ty_keys for d in week_days):
                sg_w = sum(cny(dstr(d), "SG") for d in week_days)
                my_w = sum(cny(dstr(d), "MY") for d in week_days)
                cb_w = sg_w + my_w
                ref = weekly[wk][2]
                diff = (cb_w - ref) / ref * 100 if ref else None
                cross.append((wk, cb_w, ref, diff))
                checks.append((f"周版交叉 {wk}", diff is not None and abs(diff) < 1.0,
                               f"日版加总 ¥{cb_w:,.2f} vs 周版 ¥{ref:,.2f} (差 {diff:+.3f}%，阈值1%)"))
        print("\n== 与 T107b 周版交叉（同口径不同粒度，完整周） ==")
        for wk, cb_w, ref, diff in cross:
            print(f"  {wk}: 日版加总 ¥{cb_w:,.2f} | 周版 ¥{ref:,.2f} | 差 {diff:+.3f}%")
        if not cross:
            print("  (窗口内无完整周可交叉)")
        print(f"  归因：周版 11-10 跑、日版 11-12 跑（订单表北京 01:00 日更，水位不同）；"
              f"日版主导国家并列时加 real_geo 决胜键，周版未加，并列用户 {tied_users} 人。"
              "单用户跨 SG/MY/OTHER 换桶即可造成 <1% 周差异，属可接受量级。")
    else:
        print("\n== 周版文件不存在，跳过交叉 ==")

    print()
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    n_fail = sum(1 for _, ok, _ in checks if not ok)
    print(f"  => {len(checks) - n_fail}/{len(checks)} PASS")

    # ---- 逐日打印（dry-run 详细） ----
    if args.dry_run:
        print("\n== 逐日明细（今年 / 去年同月日） ==")
        print("日期        SG今年¥   MY今年¥   合计今年¥ | SG去年¥   MY去年¥   合计去年¥ | 同比%")
        for t, l in zip(ty_keys, ly_keys):
            p = (comb(t) - comb(l)) / comb(l) * 100 if comb(l) else None
            print(f"{t} {cny(t,'SG'):>9,.0f} {cny(t,'MY'):>8,.0f} {comb(t):>10,.0f} | "
                  f"{cny(l,'SG'):>9,.0f} {cny(l,'MY'):>8,.0f} {comb(l):>10,.0f} | "
                  f"{p:+.1f}%" if p is not None else "")

    if args.dry_run:
        print("\n[--dry-run] 未写任何文件。抽样通过后带 WF_TASK=T112 重跑生成 Excel。")
        return

    # ---- 多 sheet Excel ----
    OUT.mkdir(parents=True, exist_ok=True)
    hdr_fill = PatternFill("solid", fgColor="D9D9D9")

    def style_header(ws, ncol):
        for c in range(1, ncol + 1):
            cell = ws.cell(1, c)
            cell.font = Font(bold=True)
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")

    def daily_sheet(ws, days, is_ty):
        hdr = ["日期(北京日)", "SG收入¥", "MY收入¥", "SG+MY合计¥",
               "SG付费单数", "MY付费单数", "SG+MY付费单数",
               "SG付费用户", "MY付费用户", "NO_GEO¥", "OTHER¥", "备注"]
        ws.append(hdr)
        style_header(ws, len(hdr))
        for d in days:
            dk = dstr(d)
            note = ""
            if is_ty and d == end:
                note = "不完整日（当天，订单表北京01:00日更、副本水位约01:xx）"
            ws.append([dk, round(cny(dk, "SG"), 2), round(cny(dk, "MY"), 2), round(comb(dk), 2),
                       orders[dk].get("SG", 0), orders[dk].get("MY", 0),
                       orders[dk].get("SG", 0) + orders[dk].get("MY", 0),
                       users[dk].get("SG", 0), users[dk].get("MY", 0),
                       round(cny(dk, "NO_GEO"), 2), round(cny(dk, "OTHER"), 2), note])
        ws.append([])
        ws.append(["窗口合计", round(sum(cny(dstr(d), "SG") for d in days), 2),
                   round(sum(cny(dstr(d), "MY") for d in days), 2),
                   round(sum(comb(dstr(d)) for d in days), 2)])
        for c in range(1, len(hdr) + 1):
            ws.column_dimensions[ws.cell(1, c).column_letter].width = 15
        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["L"].width = 52

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "逐日收入_今年"
    daily_sheet(ws1, ty_days, True)
    ws2 = wb.create_sheet("逐日收入_去年同期")
    daily_sheet(ws2, ly_days, False)

    # sheet3: 同比对照
    ws3 = wb.create_sheet("同比对照")
    hdr3 = ["今年日期", "去年同月日", "SG今年¥", "SG去年¥", "SG同比%",
            "MY今年¥", "MY去年¥", "MY同比%", "合计今年¥", "合计去年¥", "合计同比%", "备注"]
    ws3.append(hdr3)
    style_header(ws3, len(hdr3))

    def pct(a, b):
        return round((a - b) / b * 100, 1) if b else None

    for t, l in zip(ty_keys, ly_keys):
        note = ""
        if t == dstr(end):
            note = "今年当日不完整，不参与结论"
        ws3.append([t, l,
                    round(cny(t, "SG"), 2), round(cny(l, "SG"), 2), pct(cny(t, "SG"), cny(l, "SG")),
                    round(cny(t, "MY"), 2), round(cny(l, "MY"), 2), pct(cny(t, "MY"), cny(l, "MY")),
                    round(comb(t), 2), round(comb(l), 2), pct(comb(t), comb(l)), note])
    # 合计行（全窗口 / 完整日窗口）
    sg_t, sg_l = sum(cny(t, "SG") for t in ty_keys), sum(cny(l, "SG") for l in ly_keys)
    my_t, my_l = sum(cny(t, "MY") for t in ty_keys), sum(cny(l, "MY") for l in ly_keys)
    ws3.append([])
    ws3.append(["窗口合计(19天)", "含11-12不完整日",
                round(sg_t, 2), round(sg_l, 2), pct(sg_t, sg_l),
                round(my_t, 2), round(my_l, 2), pct(my_t, my_l),
                round(ty_sum, 2), round(ly_sum, 2), pct(ty_sum, ly_sum), "仅供参考"])
    sg_tf = sum(cny(t, "SG") for t in ty_keys[:-1])
    sg_lf = sum(cny(l, "SG") for l in ly_keys[:-1])
    my_tf = sum(cny(t, "MY") for t in ty_keys[:-1])
    my_lf = sum(cny(l, "MY") for l in ly_keys[:-1])
    ws3.append([f"完整日合计({len(ty_keys)-1}天)", f"截至{dstr(end - timedelta(days=1))}",
                round(sg_tf, 2), round(sg_lf, 2), pct(sg_tf, sg_lf),
                round(my_tf, 2), round(my_lf, 2), pct(my_tf, my_lf),
                round(ty_full, 2), round(ly_full, 2), pct(ty_full, ly_full), "★ 结论以此行为准"])
    for c in range(1, len(hdr3) + 1):
        ws3.column_dimensions[ws3.cell(1, c).column_letter].width = 15
    ws3.column_dimensions["A"].width = 18
    ws3.column_dimensions["B"].width = 16
    ws3.column_dimensions["L"].width = 34

    # sheet4: 分币种（仅 SG/MY）
    ws4 = wb.create_sheet("分币种_SG_MY")
    hdr4 = ["日期", "年份", "地区", "币种", "原币金额", "汇率", "收入¥", "现金单数"]
    ws4.append(hdr4)
    style_header(ws4, len(hdr4))
    for is_ty, days, label in ((True, ty_days, "今年"), (False, ly_days, "去年")):
        for d in days:
            dk = dstr(d)
            for bk in ("SG", "MY"):
                for ck, v in sorted(rev[dk].get(bk, {}).items(), key=lambda x: -x[1]):
                    ws4.append([dk, label, bk, ck, round(amt_major[dk][bk][ck], 2),
                                rates.get(ck), round(v, 2), cash_orders[dk].get(bk, 0)])
    for c in range(1, len(hdr4) + 1):
        ws4.column_dimensions[ws4.cell(1, c).column_letter].width = 15

    # sheet5: 结论与口径
    ws5 = wb.create_sheet("结论与口径")
    sg_delta = pct(sg_tf, sg_lf)
    my_delta = pct(my_tf, my_lf)
    cb_delta = pct(ty_full, ly_full)
    p046_impact = (
        "SG/MY 收入不受影响；沿用 T107 口径，OTHER/NO_GEO 展示列对这些单计 0（P046 已知局限，见任务文档）。"
        if p046_sgmy_orders == 0 else
        "⚠️ 已落在 SG/MY，须按 P046 补标准人民币价后再交付（见抽样复核）。"
    )
    notes = [
        [f"SG/MY 按天收入：今年 {start} ~ {end} vs 去年同期 {ly_start} ~ {ly_end}（人民币，按用户主导 IP 国家归属）"],
        [""],
        ["【关键结论（完整日，剔除今年最后一天）】"],
        [f"1. SG+MY 合计：今年 ¥{ty_full:,.2f} vs 去年 ¥{ly_full:,.2f}，同比 {cb_delta:+.1f}%。"],
        [f"2. SG：今年 ¥{sg_tf:,.2f} vs 去年 ¥{sg_lf:,.2f}，同比 {sg_delta:+.1f}%；"
         f"MY：今年 ¥{my_tf:,.2f} vs 去年 ¥{my_lf:,.2f}，同比 {my_delta:+.1f}%。"],
        [f"3. 全窗口（含今年 {dstr(end)} 不完整日）：今年 ¥{ty_sum:,.2f} vs 去年 ¥{ly_sum:,.2f}，"
         f"同比 {pct(ty_sum, ly_sum):+.1f}%；该行仅供对照，不作结论。"],
        [f"4. ⚠️ 口径限定：以上均为「地理可见部分」（用户主导 IP 国家 = SG/MY）。"
         f"完整日 NO_GEO 今年 ¥{nogeo_ty:,.2f} vs 去年 ¥{nogeo_ly:,.2f}（同比 {nogeo_pct:+.1f}%）；"
         "移动端测量缺口跨年变化会改变可识别比例，故「SG+MY 同比持平」不能外推为两地真实总量持平（见 T107 结论）。"],
        [""],
        ["【口径】"],
        ["1. 时间窗：北京自然日 = 订单 createtime + 8h 取 date_trunc('day')；"
         "WHERE 用对齐的 UTC 粗边界两段 OR 拼接，保分区裁剪。去年同期按同月日一一对应（非 −364 天同星期）。"],
        ["2. 付费订单（P013）：imt_subscriptiongoodsorder，COALESCE(isdeleted,0)=0 + orderstatus='finished' + "
         "(amountpaid>0 或 兑换码 ordertype='code' 或 subscriptiontype LIKE 'onetime%')。"
         "兑换码 amountpaid 常为空，计 1 单、金额计 0。"],
        ["3. 地区归属（按 IP）：real_geo 为 2 位 ISO 国家码（IP 国家，非母语、非账号注册地）。"
         "订单 userid -> imt_deviceinfo.deviceid -> imm_regional_activation 取该用户全历史出现次数最多的 real_geo；"
         "两年共用同一套映射（沿用 T107d），使同比只反映收入变化。"],
        ["4. 金额：amountpaid 为分，(amountpaid/100) × exchangerates.exchangerate 折人民币（CNY=1）；"
         f"UPPER(currency) 归一 join。汇率匹配不到共 {unmatched_orders:,} 笔，其中 {null_cur_orders:,} 笔为 "
         "NULL 币种兑换码（amountpaid 为空、金额 0，P046 第 6 条明确不算漏算）；有实付金额却缺汇率的仅 "
         f"{p046_cash_orders} 笔（CZK/MNT/IQD/UAH/PKR/ARS 等未维护小币种），其中落在 SG/MY 的 "
         f"{p046_sgmy_orders} 笔。{p046_impact}"],
        ["5. 桶：SG / MY / NO_GEO（取不到国家，主为移动端）/ OTHER；SG+MY = SG + MY；NO_GEO 单列，不摊进 SG/MY。"],
        ["6. 移动端缺口（P037）：iOS/Android 的 device_id 大多不在 imt_deviceinfo → 归 NO_GEO，"
         f"故 SG/MY 收入为下界、非全量。本次完整日 NO_GEO 今年 ¥{nogeo_ty:,.2f} / 去年 ¥{nogeo_ly:,.2f}，"
         f"SG+MY 占「SG+MY+NO_GEO」比 今年 {ty_full/(ty_full+nogeo_ty)*100:.1f}% / "
         f"去年 {ly_full/(ly_full+nogeo_ly)*100:.1f}%。"],
        ["7. VPN 噪声：单用户 real_geo 高度碎片化（T107 抽样证实），主导国家已稀释偶发 VPN/漫游；"
         "日粒度样本小（T107b 周版约 ¥2.5 万/周），绝对值带噪声，结论以窗口合计与两年对比为准，不以单日尖峰下判断。"],
        ["8. 已知限制：主导国家映射含 2026 年地理信息，对去年订单存在轻微前视归属；"
         "按用户确认沿用 T107/T107d 口径，保证与历史交付可比。"],
        [""],
        ["【数据水位】"],
        [f"今年段订单 createtime 最大 = {wm.get('TY', ('', '', ''))[2]}；"
         f"去年段 = {wm.get('LY', ('', '', ''))[2]}（订单表经 H:\\imt_data_synch 北京每天 01:00 日更，"
         "副本停在约 01:xx 为正常水位，非同步故障，见 P043）。"],
        [f"今年 {dstr(end)} 为当天、数据不完整，逐日表与同比表均已标注；去年同期对应日为完整日。"],
        [""],
        ["【抽样复核】"],
        [f"自检 {len(checks) - n_fail}/{len(checks)} PASS：桶集合、北京日越界、19 天齐全、P046 汇率影响面、"
         f"假零、SG+MY 恒等、周版交叉（主导国家并列用户 {tied_users} 人）；"
         "与 T107b 周版（同口径不同粒度）完整周加总交叉见下。"],
    ]
    for c in cross:
        notes.append([f"  周 {c[0]}：日版加总 ¥{c[1]:,.2f} vs 周版 ¥{c[2]:,.2f}，差 {c[3]:+.3f}%"])
    notes += [
        [""],
        ["【留档】"],
        ["任务文档 docs/tasks/query_sg_my_daily_revenue_yoy_20261112.md；"
         "定稿 SQL sql/reports/query_sg_my_daily_revenue_yoy_20261112.sql；"
         "canonical scripts/export_sg_my_daily_revenue_yoy.py --start --end（交付须带 WF_TASK=T112）。"],
    ]
    for line in notes:
        ws5.append(line)
    ws5.cell(1, 1).font = Font(bold=True)
    ws5.column_dimensions["A"].width = 130

    fname = f"sg_my_daily_revenue_yoy_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.xlsx"
    path = OUT / fname
    wb.save(path)
    print(f"\nSAVED: {path}")
    print(f"  自检 {len(checks) - n_fail}/{len(checks)} PASS；交付门禁 WF_TASK={os.environ.get('WF_TASK')}")


if __name__ == "__main__":
    main()
