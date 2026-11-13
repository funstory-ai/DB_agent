# -*- coding: utf-8 -*-
"""T111：Tab2（浏览页）移动端 7 指标 + 平台登录引导漏斗（canonical）。

同一分析只保留这一份脚本：刷新时改 --end / --days，覆盖输出，不新增 dated 副本。
定稿 SQL 在 sql/reports/query_tab2_mobile_metrics_20261112.sql（按 -- @Q_xxx 分段），
本脚本只做「取数 + 精确口径计算 + 出 Excel」，口径说明写在任务文档。

交付时须带 WF_TASK=T111（wf 状态机要求已过 sampled）：
    WF_TASK=T111 python scripts/export_tab2_mobile_metrics.py
抽样阶段用 --dry-run（只打印关键数字、不写文件，绕开交付门禁的写文件动作）：
    python scripts/export_tab2_mobile_metrics.py --dry-run
"""
from __future__ import annotations

import argparse
import bisect
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import get_cursor, query  # noqa: E402

# ---- wf 硬门禁：交付前必须过抽样（设 WF_TASK 时强制） ----
if os.environ.get("WF_TASK"):
    import wf as _wf

    _wf.require(os.environ["WF_TASK"], "sampled")

SQL_FILE = ROOT / "sql" / "reports" / "query_tab2_mobile_metrics_20261112.sql"

EVENTS = (
    "app_tab2_enter", "home_show",
    "app_feed_browse_duration", "app_feed_detail_enter", "app_feed_card_impression",
    "tab2_login_card_impression", "tab2_login_cta_click", "tab2_login_card_close",
    "tab2_login_card_logggedin", "tab2_login_card_swipe",
    "login", "sign_up",
    "billing_subscribe_success", "billing_upgrade_success", "billing_purchase_success_detail",
)
FEED_EVENTS = ("app_feed_browse_duration", "app_feed_detail_enter", "app_feed_card_impression")
FUNNEL_EVENTS = (
    "tab2_login_card_impression", "tab2_login_cta_click", "tab2_login_card_close",
    "tab2_login_card_logggedin", "tab2_login_card_swipe", "login", "sign_up",
)
CARD_EVENTS = (
    "tab2_login_card_impression", "tab2_login_cta_click", "tab2_login_card_close",
    "tab2_login_card_logggedin", "tab2_login_card_swipe",
)
BILLING_EVENTS = (
    "billing_subscribe_success", "billing_upgrade_success", "billing_purchase_success_detail",
)
LOSS_EVENTS = ("tab2_login_card_close", "tab2_login_card_logggedin", "tab2_login_card_swipe")
TAB2 = "app_tab2_enter"
HOME = "home_show"
RETENTION_KS = (1, 3, 7)
PAY_DAYS = 14           # 首用日 D..D+13
STEP_WINDOW = timedelta(minutes=30)
PAIR_WINDOW = timedelta(seconds=5)   # detail_enter -> duration 配对窗口


def sql_list(items):
    return ", ".join("'" + x + "'" for x in items)


def q(sql: str, retries: int = 6):
    """带指数退避重试（覆盖 OSS AccessDenied 等瞬态）。"""
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} ({d:.0f}s): {str(e)[:120]}", flush=True)
            time.sleep(d)
            d *= 2


def stream(sql: str, chunk: int = 50000, retries: int = 6):
    """流式读取大结果集，避免 fetchall OOM；execute 失败时整条重试。"""
    d = 2.0
    cur = None
    for i in range(retries):
        try:
            cur = get_cursor()
            cur.execute(sql)
            break
        except Exception as e:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if i == retries - 1:
                raise
            print(f"  stream retry {i + 1} ({d:.0f}s): {str(e)[:120]}", flush=True)
            time.sleep(d)
            d *= 2
            cur = None
    try:
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            for r in rows:
                yield tuple(r.values()) if hasattr(r, "values") else tuple(r)
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass


def load_queries(w0: str, w1: str, prior: str, hist: str) -> dict:
    text = SQL_FILE.read_text(encoding="utf-8")
    parts = {}
    cur_name, buf = None, []
    for line in text.splitlines():
        if line.startswith("-- @Q_"):
            if cur_name:
                parts[cur_name] = "\n".join(buf).strip()
            cur_name, buf = "Q_" + line.strip().split("@Q_", 1)[1], []
        elif cur_name:
            buf.append(line)
    if cur_name:
        parts[cur_name] = "\n".join(buf).strip()
    rep = {
        "@W0@": w0, "@W1@": w1, "@PRIOR@": prior, "@HIST@": hist,
        "@EVENTS@": sql_list(EVENTS),
        "@SUBJ_EVENTS@": sql_list(EVENTS),
        "@FEED_EVENTS@": sql_list(FEED_EVENTS),
        "@FUNNEL_EVENTS@": sql_list(FUNNEL_EVENTS),
        "@CARD_EVENTS@": sql_list(CARD_EVENTS),
    }
    out = {}
    for k, v in parts.items():
        for a, b in rep.items():
            v = v.replace(a, b)
        out[k] = v
    return out


def pct(sorted_vals, p: float):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 1)


def rate(n, d):
    return round(100.0 * n / d, 2) if d else None


def strip_json_str(v):
    return (v or "").strip('"') if isinstance(v, str) else None


# --------------------------------------------------------------------------
# Excel 输出助手：每个 block = (标题, 表头, 行列表)；比例列一律写百分数数值（xx.xx）
# --------------------------------------------------------------------------
def write_sheet(wb: Workbook, name: str, blocks):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    widths = {}
    r = 1
    for title, headers, rows in blocks:
        if title:
            c = ws.cell(row=r, column=1, value=title)
            c.font = Font(bold=True, size=12)
            r += 1
        if headers:
            for j, h in enumerate(headers, 1):
                c = ws.cell(row=r, column=j, value=h)
                c.font = Font(bold=True)
                c.alignment = Alignment(vertical="center", wrap_text=True)
                widths[j] = max(widths.get(j, 8), min(38, max(10, len(str(h)) * 1.7)))
            r += 1
        for row in rows:
            for j, v in enumerate(row, 1):
                c = ws.cell(row=r, column=j, value=v)
                if isinstance(v, str) and len(v) > 40:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                widths[j] = max(widths.get(j, 8), min(38, max(10, len(str(v or "")) * 1.3)))
            r += 1
        r += 2
    for j, w in widths.items():
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
    return ws


def add_summary(wb, lines):
    ws = wb.create_sheet("说明与摘要", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 108
    r = 1
    for k, v in lines:
        a = ws.cell(row=r, column=1, value=k)
        a.font = Font(bold=True)
        a.alignment = Alignment(vertical="top")
        b = ws.cell(row=r, column=2, value=v)
        b.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default="2026-11-12", help="北京日窗口右开边界 YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=30, help="窗口天数")
    ap.add_argument("--dry-run", action="store_true", help="只打印关键数字，不写 Excel")
    args = ap.parse_args()

    end = date.fromisoformat(args.end)
    start = end - timedelta(days=args.days)
    end_day = end - timedelta(days=1)
    days = [start + timedelta(days=i) for i in range(args.days)]
    day_ord = {d: i for i, d in enumerate(days)}
    w0 = (datetime.combine(start, datetime.min.time()) - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    w1 = (datetime.combine(end, datetime.min.time()) - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    prior = "2026-03-01 00:00:00"
    hist = "2026-07-31 16:00:00"
    print(f"[窗口] 北京日 {start} ~ {end_day}（{args.days} 天），UTC {w0} ~ {w1}", flush=True)

    Q = load_queries(w0, w1, prior, hist)
    print("[DB] Q_COUNTS ...", flush=True)
    _, counts_rows = q(Q["Q_COUNTS"])
    counts_com = Counter()
    counts_all = Counter()
    counts_by_ed = Counter()
    for d, ev, ed, c in counts_rows:
        counts_all[(ev, d)] += c
        counts_by_ed[(ev, ed)] += c
        if ed == "com":
            counts_com[(ev, d)] += c

    print("[DB] Q_SUBJECT_DAYS ...", flush=True)
    subj_rows = [tuple(r) for r in stream(Q["Q_SUBJECT_DAYS"])]
    uid_map = {}
    uid_variants = defaultdict(set)
    for d, ev, dev, uid, ed in subj_rows:
        if uid and uid > 0:
            uid_variants[dev].add(uid)
            if dev not in uid_map or uid < uid_map[dev]:
                uid_map[dev] = uid

    def subj_of(dev, uid):
        if uid and uid > 0:
            return "u" + str(uid)
        if dev in uid_map:
            return "u" + str(uid_map[dev])
        return "d" + str(dev)

    sets_com = defaultdict(set)
    sets_all = defaultdict(set)
    dev_com = defaultdict(set)
    dev_all = defaultdict(set)
    for d, ev, dev, uid, ed in subj_rows:
        s = subj_of(dev, uid)
        sets_all[(ev, d)].add(s)
        dev_all[ev].add(dev)
        if ed == "com":
            sets_com[(ev, d)].add(s)
            dev_com[ev].add(dev)
    print(f"       {len(subj_rows)} 行；设备→账号映射 {len(uid_map)} 台；多账号设备 "
          f"{sum(1 for v in uid_variants.values() if len(v) > 1)} 台", flush=True)

    print("[DB] Q_FEED ...", flush=True)
    dur_by_dev = defaultdict(list)
    det_by_dev = defaultdict(list)
    dur_values = []
    dur_by_day = defaultdict(list)
    viewed_dist = Counter()
    trigger_dist = Counter()
    imp_week_events = Counter()
    imp_week_devs = defaultdict(set)
    feed_rows_com = Counter()
    feed_rows_all = Counter()
    sid = 0
    for dev, uid, ed, ev, ts, d, dm, vc, tt in stream(Q["Q_FEED"]):
        feed_rows_all[ev] += 1
        if ed != "com":
            continue
        feed_rows_com[ev] += 1
        if ev == "app_feed_browse_duration":
            sid += 1
            dur_by_dev[dev].append((ts, d, dm, vc, sid))
            if dm is not None and dm >= 0:
                dur_values.append(int(dm))
                dur_by_day[d].append(int(dm))
            if vc is not None:
                viewed_dist[min(int(vc), 10) if vc >= 0 else -1] += 1
        elif ev == "app_feed_detail_enter":
            t = strip_json_str(tt)
            det_by_dev[dev].append((ts, t))
            trigger_dist[t or "(空)"] += 1
        else:  # app_feed_card_impression
            wk = (d - timedelta(days=d.weekday())).isoformat()
            imp_week_events[wk] += 1
            imp_week_devs[wk].add(dev)

    sess_total = Counter()
    sess_hit = Counter()
    sess_tap = Counter()
    sess_scroll = Counter()
    assigned = unassigned = 0
    for dev, durs in dur_by_dev.items():
        durs.sort(key=lambda x: x[0])
        ends = [x[0] for x in durs]
        dets = sorted(det_by_dev.get(dev, []), key=lambda x: x[0])
        owner = defaultdict(list)
        for ts, t in dets:
            i = bisect.bisect_left(ends, ts)
            if i < len(durs) and durs[i][0] - ts <= PAIR_WINDOW:
                owner[i].append(t)
                assigned += 1
            else:
                unassigned += 1
        for x in durs:
            sess_total[x[1]] += 1
        for i, ts_set in owner.items():
            d = durs[i][1]
            sess_hit[d] += 1
            kinds = set(ts_set)
            if "tap" in kinds:
                sess_tap[d] += 1
            if "scroll" in kinds:
                sess_scroll[d] += 1
    sv = sorted(dur_values)
    print(f"       duration 会话 {len(dur_values)} / detail {sum(len(v) for v in det_by_dev.values())}"
          f"；配对成功 {assigned}、未配对 {unassigned}", flush=True)

    print("[DB] Q_FUNNEL ...", flush=True)
    timeline = defaultdict(lambda: defaultdict(list))
    funnel_month_users = defaultdict(set)
    loss_events_month = defaultdict(lambda: defaultdict(list))
    for dev, uid, ed, ev, ts, d in stream(Q["Q_FUNNEL"]):
        if ed != "com":
            continue
        s = subj_of(dev, uid)
        bj = ts + timedelta(hours=8)
        m = bj.strftime("%Y-%m")
        timeline[s][ev].append((ts, m))
        if ev == "tab2_login_card_impression":
            funnel_month_users[m].add(s)
        if ev in LOSS_EVENTS:
            loss_events_month[m][ev].append((s, ts))

    print("[DB] Q_PRIOR（首用左删失回看）...", flush=True)
    prior_subjects = set()
    prior_devices = set()
    for dev, uid in stream(Q["Q_PRIOR"]):
        prior_devices.add(dev)
        prior_subjects.add(subj_of(dev, uid))
        prior_subjects.add("d" + str(dev))
    print(f"       主窗前用过 Tab2 的设备 {len(prior_devices)}", flush=True)

    print("[DB] Q_HIST（卡片事件历史月度）...", flush=True)
    _, hist_rows = q(Q["Q_HIST"])
    print("[DB] Q_ENTRY（Tab2 进入方式）...", flush=True)
    _, entry_rows_raw = q(Q["Q_ENTRY"])
    entry_rows = []
    for et, c, uv in entry_rows_raw:
        entry_rows.append([strip_json_str(et) or "(空)", c, uv])

    # ---------------- 指标 1/2 ----------------
    sheet1 = []
    for d in days:
        t2 = len(sets_com[(TAB2, d)])
        t2ev = counts_com[(TAB2, d)]
        app_com = len(sets_com[(HOME, d)])
        app_all = len(sets_all[(HOME, d)])
        sheet1.append([d.isoformat(), t2ev, t2, round(t2ev / t2, 2) if t2 else None,
                       app_com, rate(t2, app_com), app_all, rate(t2, app_all)])
    tot_t2ev = sum(r[1] for r in sheet1)
    tot_t2 = sum(r[2] for r in sheet1)
    avg_app_com = sum(r[4] for r in sheet1) / len(sheet1)
    avg_app_all = sum(r[6] for r in sheet1) / len(sheet1)
    avg_t2 = tot_t2 / len(sheet1)
    sheet1.append(["合计/均值", tot_t2ev, tot_t2, round(tot_t2ev / tot_t2, 2) if tot_t2 else None,
                   round(avg_app_com, 1), rate(avg_t2, avg_app_com),
                   round(avg_app_all, 1), rate(avg_t2, avg_app_all)])

    # ---------------- 指标 3 ----------------
    p50_all, p90_all, p99_all = pct(sv, .5), pct(sv, .9), pct(sv, .99)
    # 极端长会话（>1h，疑似后台挂起）不影响 P50/P90；另给剔除后的敏感性对照
    sv_trim = [x for x in sv if x <= 3600000]
    dur_block = [
        ["全窗", len(sv), p50_all, p90_all, p99_all, sv[0] if sv else None,
         sv[-1] if sv else None, round(p50_all / 1000, 2) if p50_all else None,
         round(p90_all / 1000, 2) if p90_all else None],
        [f"全窗(剔除>1h 异常长会话 {len(sv) - len(sv_trim)} 条)", len(sv_trim),
         pct(sv_trim, .5), pct(sv_trim, .9), pct(sv_trim, .99),
         sv_trim[0] if sv_trim else None, sv_trim[-1] if sv_trim else None,
         round(pct(sv_trim, .5) / 1000, 2) if sv_trim else None,
         round(pct(sv_trim, .9) / 1000, 2) if sv_trim else None],
    ]
    dur_daily = []
    for d in days:
        v = sorted(dur_by_day[d])
        dur_daily.append([d.isoformat(), len(v), pct(v, .5), pct(v, .9),
                          round(pct(v, .5) / 1000, 2) if v else None,
                          round(pct(v, .9) / 1000, 2) if v else None])
    buckets = [(0, 1000), (1000, 5000), (5000, 10000), (10000, 30000),
               (30000, 60000), (60000, 300000), (300000, 10 ** 12)]
    labels = ["<1s", "1~5s", "5~10s", "10~30s", "30~60s", "1~5min", ">5min"]
    bucket_rows = []
    for (lo, hi), lab in zip(buckets, labels):
        n = sum(1 for x in sv if lo <= x < hi)
        bucket_rows.append([lab, n, rate(n, len(sv))])
    viewed_rows = []
    tot_vc = sum(viewed_dist.values())
    for k in sorted(viewed_dist):
        lab = "10+" if k == 10 else ("(负/异常)" if k < 0 else str(k))
        viewed_rows.append([lab, viewed_dist[k], rate(viewed_dist[k], tot_vc)])

    # ---------------- 指标 4 ----------------
    sheet3 = []
    for d in days:
        n = sess_total[d]
        h = sess_hit[d]
        sheet3.append([d.isoformat(), n, h, rate(h, n), sess_tap[d], rate(sess_tap[d], n),
                       sess_scroll[d], rate(sess_scroll[d], n),
                       counts_com[("app_feed_card_impression", d)]])
    n_all = sum(sess_total[d] for d in days)
    h_all = sum(sess_hit[d] for d in days)
    sheet3.append(["合计", n_all, h_all, rate(h_all, n_all),
                   sum(sess_tap.values()), rate(sum(sess_tap.values()), n_all),
                   sum(sess_scroll.values()), rate(sum(sess_scroll.values()), n_all),
                   sum(counts_com[("app_feed_card_impression", d)] for d in days)])

    # ---------------- 指标 5 ----------------
    def mature(d, k):
        return d + timedelta(days=k) <= end_day

    sheet4 = []
    for d in days:
        cohort = sets_com[(TAB2, d)]
        row = [d.isoformat(), len(cohort)]
        for k in RETENTION_KS:
            if mature(d, k):
                n = len(cohort & sets_com[(TAB2, d + timedelta(days=k))])
                row += [n, rate(n, len(cohort))]
            else:
                row += [None, None]
        row.append("D+7 已成熟" if mature(d, 7) else "D+7 未成熟（留空）")
        sheet4.append(row)
    sum4 = ["成熟 cohort 合计", 0] + [0, None] * len(RETENTION_KS) + [""]
    for d in days:
        if not mature(d, 7):
            continue
        cohort = sets_com[(TAB2, d)]
        sum4[1] += len(cohort)
        for j, k in enumerate(RETENTION_KS):
            sum4[2 + 2 * j] += len(cohort & sets_com[(TAB2, d + timedelta(days=k))])
    for j in range(len(RETENTION_KS)):
        sum4[3 + 2 * j] = rate(sum4[2 + 2 * j], sum4[1])
    sheet4.append(sum4)

    # ---------------- 指标 6 ----------------
    sheet5 = []
    for d in days:
        allu = sets_com[(HOME, d)]
        used = allu & sets_com[(TAB2, d)]
        notused = allu - used
        row = [d.isoformat(), len(allu), len(used), len(notused)]
        for k in RETENTION_KS:
            if mature(d, k):
                tgt = sets_com[(HOME, d + timedelta(days=k))]
                for g in (allu, used, notused):
                    n = len(g & tgt)
                    row += [n, rate(n, len(g))]
            else:
                row += [None] * 6
        sheet5.append(row)
    sum5 = ["成熟 cohort 合计", 0, 0, 0] + [0, None] * (3 * len(RETENTION_KS))
    for d in days:
        if not mature(d, 7):
            continue
        allu = sets_com[(HOME, d)]
        used = allu & sets_com[(TAB2, d)]
        notused = allu - used
        groups = (allu, used, notused)
        for gi, g in enumerate(groups):
            sum5[1 + gi] += len(g)
        for j, k in enumerate(RETENTION_KS):
            tgt = sets_com[(HOME, d + timedelta(days=k))]
            for gi, g in enumerate(groups):
                sum5[4 + 6 * j + 2 * gi] += len(g & tgt)
    for j in range(len(RETENTION_KS)):
        for gi in range(3):
            pos = 5 + 6 * j + 2 * gi
            sum5[pos] = rate(sum5[pos - 1], sum5[1 + gi])
    sheet5.append(sum5)

    # ---------------- 指标 7 ----------------
    tab2_first = {}
    for d in days:
        for s in sets_com[(TAB2, d)]:
            if s not in tab2_first:
                tab2_first[s] = d
    tab2_any = set(tab2_first)
    billing_by_day = defaultdict(set)
    for d in days:
        for ev in BILLING_EVENTS:
            billing_by_day[d] |= sets_com[(ev, d)]
    sheet6 = []
    pay_days_ok = [d for d in days if d + timedelta(days=PAY_DAYS - 1) <= end_day]
    for d in days:
        if d not in pay_days_ok:
            sheet6.append([d.isoformat(), None, None, None, None, None, None, None, None, None,
                           "14 天窗未成熟（留空）"])
            continue
        a = {s for s in sets_com[(TAB2, d)]
             if tab2_first.get(s) == d and s not in prior_subjects}
        b = {s for s in sets_com[(HOME, d)] if s not in tab2_any and s not in prior_subjects}
        paid = set()
        for x in range(PAY_DAYS):
            paid |= billing_by_day[d + timedelta(days=x)]
        ap, bp = len(a & paid), len(b & paid)
        ra, rb = rate(ap, len(a)), rate(bp, len(b))
        sheet6.append([d.isoformat(), len(a), rate(sum(1 for s in a if s.startswith("u")), len(a)),
                       ap, ra, len(b), rate(sum(1 for s in b if s.startswith("u")), len(b)),
                       bp, rb, round(ra / rb, 2) if (ra is not None and rb) else None, "D..D+13 已成熟"])
    sum6 = ["成熟 cohort 合计", 0, None, 0, None, 0, None, 0, None, None, ""]
    for row in sheet6:
        if row[1] is None:
            continue
        for i in (1, 3, 5, 7):
            sum6[i] += row[i]
    for i, den in ((4, 1), (8, 5)):
        sum6[i] = rate(sum6[i - 1], sum6[den])
    sum6[2] = round(sum((r[2] or 0) for r in sheet6 if r[1] is not None) / max(1, len(pay_days_ok)), 2)
    sum6[6] = round(sum((r[6] or 0) for r in sheet6 if r[1] is not None) / max(1, len(pay_days_ok)), 2)
    sum6[9] = round(sum6[4] / sum6[8], 2) if (sum6[4] is not None and sum6[8]) else None
    sheet6.append(sum6)

    # 结构诊断：Tab2 cohort 本身的 App 级留存远低于全体活跃用户，
    # 说明「使用者组」以一次性/新进设备为主，付费对照的组间差不能解读为 Tab2 的因果效果。
    diag_rows = []
    for k in RETENTION_KS:
        ds = [d for d in days if mature(d, k)]
        t2c = sum(len(sets_com[(TAB2, d)]) for d in ds)
        allc = sum(len(sets_com[(HOME, d)]) for d in ds)
        t2r = sum(len(sets_com[(TAB2, d)] & sets_com[(HOME, d + timedelta(days=k))]) for d in ds)
        allr = sum(len(sets_com[(HOME, d)] & sets_com[(HOME, d + timedelta(days=k))]) for d in ds)
        diag_rows.append([f"D+{k}", t2c, t2r, rate(t2r, t2c), allc, allr, rate(allr, allc)])

    # ---------------- 指标 8：登录引导漏斗 ----------------
    def within(src, tgt, window):
        """src 中任一时刻到 tgt 中任一时刻，间隔 [0, window] 即命中。"""
        for a in src:
            i = bisect.bisect_left(tgt, a)
            if i < len(tgt) and tgt[i] - a <= window:
                return True
        return False

    sheet7_main = []
    sheet7_loss = []
    for m in sorted(funnel_month_users):
        users = funnel_month_users[m]
        s2, s3 = set(), set()
        for s in users:
            imps = sorted(t for t, mm in timeline[s]["tab2_login_card_impression"] if mm == m)
            ctas = sorted(t for t, mm in timeline[s]["tab2_login_cta_click"] if mm == m)
            logins = sorted(t for t, mm in (timeline[s]["login"] + timeline[s]["sign_up"]) if mm == m)
            if not imps:
                continue
            qual_ctas = [c for c in ctas if any(0 <= (c - i).total_seconds() <= 1800 for i in imps)]
            if qual_ctas:
                s2.add(s)
                if within(qual_ctas, logins, STEP_WINDOW):
                    s3.add(s)
        n1, n2, n3 = len(users), len(s2), len(s3)
        sheet7_main.append([m, n1, n2, rate(n2, n1), n3, rate(n3, n1), rate(n3, n2)])
        for ev in LOSS_EVENTS:
            rows = loss_events_month[m].get(ev, [])
            ppl = {x[0] for x in rows}
            near = 0
            for s, ts in rows:
                imps = [t for t, mm in timeline[s]["tab2_login_card_impression"] if mm == m]
                if any(0 <= (ts - t).total_seconds() <= 1800 for t in imps):
                    near += 1
            sheet7_loss.append([m, ev, len(rows), len(ppl), rate(len(ppl), n1), near])

    hist_map = defaultdict(dict)
    for ym, ev, c, uv in hist_rows:
        hist_map[ym][ev] = (c, uv)
    sheet7_hist = []
    for ym in sorted(hist_map):
        for ev in FUNNEL_EVENTS:
            c, uv = hist_map[ym].get(ev, (0, 0))
            sheet7_hist.append([ym, ev, c, uv])

    # ---------------- Sheet 8：口径体检 ----------------
    ev_rows = []
    for ev in EVENTS:
        c_all = sum(v for (e2, _), v in counts_by_ed.items() if e2 == ev)
        subs = set()
        for d in days:
            subs |= sets_com[(ev, d)]
        ev_rows.append([ev, counts_by_ed[(ev, "com")], c_all,
                        len(dev_com[ev]), len(subs),
                        rate(sum(1 for s in subs if s.startswith("u")), len(subs)),
                        counts_by_ed[(ev, "cn")], counts_by_ed[(ev, "(null)")]])
    identity_rows = [
        ["窗口内出现过的设备（主口径 com）", len(set().union(*dev_com.values())) if dev_com else 0],
        ["能映射到 userid 的设备", len(uid_map)],
        ["设备→账号映射覆盖率(%)", rate(len(uid_map), len(set().union(*dev_com.values())) if dev_com else 0)],
        ["挂了 >1 个 userid 的设备", sum(1 for v in uid_variants.values() if len(v) > 1)],
        ["主窗前用过 Tab2 的设备（首用左删失）", len(prior_devices)],
        ["detail→duration 配对成功 / 未配对", f"{assigned} / {unassigned}"],
    ]
    trigger_rows = [[k, v, rate(v, sum(trigger_dist.values()))] for k, v in trigger_dist.most_common()]
    imp_rows = []
    for wk in sorted(imp_week_events):
        imp_rows.append([wk, imp_week_events[wk], len(imp_week_devs[wk]),
                         round(imp_week_events[wk] / len(imp_week_devs[wk]), 2) if imp_week_devs[wk] else None])

    # ---------------- 组装 Excel ----------------
    wb = Workbook()
    wb.remove(wb.active)
    summary = [
        ("任务 / 口径", "T111 Tab2 浏览页移动端指标与登录引导漏斗；规范大类 query；全部基于现有埋点，仅国际版（ex_char_arg10='com'）"),
        ("时间窗", f"北京自然日 {start} ~ {end_day}（{args.days} 天）；UTC 粗过滤 {w0} ~ {w1}；数据水位到 2026-11-11"),
        ("去重主体", "有账号归 userid（行内 ex_int_arg1>0，或同窗同设备任意事件映射到的 min userid），无账号用 device_id（P018-D/E）。移动端按 P037 只用埋点 device_id，不 JOIN imt_deviceinfo"),
        ("① Tab2 日活", f"窗口日均 {round(avg_t2, 1)} 人；占国际版 App 日活（home_show {round(avg_app_com,1)}）{rate(avg_t2, avg_app_com)}%；占含国内版/未标版本的全版 App 日活（{round(avg_app_all,1)}）{rate(avg_t2, avg_app_all)}%"),
        ("② 人均进入次数", f"全窗 {round(tot_t2ev / tot_t2, 2) if tot_t2 else None} 次/人/日"),
        ("③ 会均时长", f"duration_ms 精确 P50={p50_all}ms（{round(p50_all/1000,2) if p50_all else None}s）/ P90={p90_all}ms（{round(p90_all/1000,2) if p90_all else None}s）；1 条事件=1 会话，未用均值。最大 {sv[-1] if sv else None}ms（约 45h，疑似后台挂起）；剔除 >1h 的 {len(sv)-len(sv_trim)} 条后 P50={pct(sv_trim,.5)}ms / P90={pct(sv_trim,.9)}ms，结论不变，见 Sheet2"),
        ("④ 内容点击率", f"全窗 {rate(h_all, n_all)}%（{h_all}/{n_all} 会话含 detail_enter）；tap 主动点击 {rate(sum(sess_tap.values()), n_all)}%；scroll 是滚动自动进全屏，不算主动探索"),
        ("⑤ Tab2 使用留存", f"D+7 成熟 cohort 合计 {sum4[2+2*2]} / {sum4[1]} = {sum4[3+2*2]}%（D+1/D+3/D+7 见 Sheet4；未成熟留空）"),
        ("⑥ 使用者 vs 全体留存", f"D+7 用过 Tab2 组 {sum5[4+6*2+2*1+1]}%、未用过组 {sum5[4+6*2+2*2+1]}%、全体 {sum5[4+6*2+1]}%（App 级 home_show，见 Sheet5）"),
        ("⑦ 付费率对照", f"首用 Tab2 后 14 天付费率 {sum6[4]}% vs 从未使用者 {sum6[8]}%，比值 {sum6[9]}（仅成熟 cohort）。⚠️ 两组人群结构不可比：使用者组多为新进/一次性设备，未使用者组以存量老用户为主，此差值**不能**解读为 Tab2 提升付费；见 Sheet6 结构诊断（P043）"),
        ("结构诊断（证据）", f"Tab2 cohort 的 App 级 D+7 留存 {diag_rows[2][3]}%，全体活跃 {diag_rows[2][6]}%；独立复核 cohort 10-20（设备级）：Tab2 cohort D+7 仍活跃 287/4532=6.33%，全体活跃 2836/12504=22.68%，Tab2 D+7 复用 98/4532=2.16%。Tab2 D+7 低主要是 cohort 本身流失，不是留存用户不再用 Tab2"),
        ("2.1 登录引导漏斗", "用户级 3 步：impression → CTA → login/sign_up；相邻步 ≤30 分钟；按月汇总。注意库内真实事件名是 tab2_login_cta_click（文档写 tab2_login_card_cta_click），详见 Sheet7"),
        ("事件名修正", "实测 tab2_login_card_cta_click 在库内 0 条，实际为 tab2_login_cta_click；tab2_login_card_logggedin（三个 g）库内拼写一致"),
        ("未做（需求明确）", "2.2 内容探索会话级漏斗、2.3 Tab2 归因付费漏斗（billing 的 from 无 Tab2）、分平台（X/Reddit/YouTube）、子 Tab 分布、问卷漏斗分母"),
        ("注意①", "viewed_card_count 只在会话开始/切子 Tab 按 URL 去重计「当前卡」，横滑与进详情都不算，实测多为 0~4，不当浏览卡片数用；分布见 Sheet2"),
        ("注意②", "app_feed_card_impression 在 App 进程内去重、跨会话不重置，会随使用周期「耗尽」，转化率自然衰减是口径现象不是产品下滑；逐周量见 Sheet8，本任务不做 impression 漏斗；横截面若要分析须限「版本上线后首个会话」"),
        ("注意③", "trigger_type=scroll 不是滑动切卡，而是滚动内容时自动进全屏详情；主动探索只看 tap，Sheet3 已拆开"),
        ("注意④", "付费按「首次使用 Tab2 之后」方向算（D..D+13），没有倒过来算「付费用户的 Tab2 使用率」；首用判定回看 2026-03-17（该事件最早出现日）"),
        ("移动端缺口 P037", "android/iOS/iPadOS 的埋点 device_id 大部分不在 imt_deviceinfo（历史实测命中率约 13%），本任务全程用埋点 ID；无账号设备不可能产生 billing 成功事件，故付费两组都列了「有账号主体占比」以暴露选择偏差"),
        ("Tab2 日活解读", f"app_tab2_enter 的 entry_type：app_open（打开 App 即落在 Tab2，被动进入）{dict((r[0], r[1]) for r in entry_rows).get('app_open', 0)} 条事件 / {dict((r[0], r[2]) for r in entry_rows).get('app_open', 0)} 台，tab_switch（主动切 Tab）{dict((r[0], r[1]) for r in entry_rows).get('tab_switch', 0)} 条 / {dict((r[0], r[2]) for r in entry_rows).get('tab_switch', 0)} 台；日活口径包含被动进入，不宜直接当作「主动使用 Tab2 的人数」"),
        ("付费口径限制", "billing_*_success 是埋点成功事件，不是订单，无金额、无法区分首购/续费；使用者与未使用者活跃度/登录率不同，此对照仅描述性，不能证明 Tab2 提升付费"),
        ("留存成熟度", f"D+1 只报 D≤{end_day - timedelta(days=1)}、D+3 只报 D≤{end_day - timedelta(days=3)}、D+7 只报 D≤{end_day - timedelta(days=7)}；14 天付费只报 D≤{end_day - timedelta(days=13)}，未成熟一律留空不写 0（P045/P019）"),
        ("会话归属法", "每条 app_feed_detail_enter 按同设备配对到其后 ≤5 秒内最早的一条 app_feed_browse_duration，一条 detail 只归一个会话；实测 11-09 配对率 97.1%，配对时延中位 0.44 秒；impression 不参与漏斗"),
    ]
    add_summary(wb, summary)

    write_sheet(wb, "1_日活与人均", [(
        "① Tab2 日活 / ② 人均进入次数（主口径：国际版 com；全版分母仅作参考）",
        ["北京日", "Tab2进入事件数", "Tab2日活(去重用户)", "人均进入次数", "国际版App日活(home_show)",
         "占国际版活跃(%)", "全版App日活(含国内/未标)", "占全版活跃(%)"], sheet1)])

    write_sheet(wb, "2_时长与浏览深度", [
        ("③ 会均时长：app_feed_browse_duration.duration_ms 精确分位（1 事件 = 1 会话，不用均值）",
         ["范围", "有效时长事件数", "P50(ms)", "P90(ms)", "P99(ms)", "最小(ms)", "最大(ms)", "P50(秒)", "P90(秒)"], dur_block),
        ("逐日 P50 / P90", ["北京日", "会话数", "P50(ms)", "P90(ms)", "P50(秒)", "P90(秒)"], dur_daily),
        ("时长分桶分布（全窗）", ["区间", "会话数", "占比(%)"], bucket_rows),
        ("注意①：viewed_card_count 分布（口径很窄，仅会话开始/切子 Tab 计当前卡，非浏览卡片数）",
         ["viewed_card_count", "会话数", "占比(%)"], viewed_rows),
    ])

    write_sheet(wb, "3_内容点击率", [(
        "④ 内容点击率 = 含 app_feed_detail_enter 的会话 ÷ app_feed_browse_duration 会话数（不做 2.2 漏斗）",
        ["北京日", "会话数(duration事件)", "含detail会话数", "内容点击率(%)", "tap会话数", "tap点击率(%)",
         "scroll会话数", "scroll率(%)", "impression事件数(仅参考)"], sheet3)])

    write_sheet(wb, "4_Tab2使用留存", [(
        "⑤ Tab2 使用留存：当日进过 Tab2 的用户，D+k 当日再次触发 app_tab2_enter（精确当日）",
        ["首用/cohort日", "cohort用户数", "D+1人数", "D+1留存(%)", "D+3人数", "D+3留存(%)",
         "D+7人数", "D+7留存(%)", "成熟度"], sheet4)])

    write_sheet(wb, "5_使用者vs全体留存", [(
        "⑥ 当日 App 活跃用户（home_show）按当日是否用过 Tab2 分组，比 App 级留存（home_show, D+1/D+3/D+7）",
        ["北京日", "全体活跃", "用过Tab2", "未用过Tab2",
         "全体D+1", "全体D+1(%)", "用过D+1", "用过D+1(%)", "未用D+1", "未用D+1(%)",
         "全体D+3", "全体D+3(%)", "用过D+3", "用过D+3(%)", "未用D+3", "未用D+3(%)",
         "全体D+7", "全体D+7(%)", "用过D+7", "用过D+7(%)", "未用D+7", "未用D+7(%)"], sheet5)])

    write_sheet(wb, "6_付费率对照", [
        ("⑦ 首次使用 Tab2 后 14 天（D..D+13）内发生 billing_*_success 的用户占比 vs 从未使用者（同锚点日、同国际版）",
         ["首用日D", "使用者人数", "使用者有账号(%)", "使用者14d付费人数", "使用者付费率(%)",
          "未使用者人数", "未使用者有账号(%)", "未使用者14d付费人数", "未使用者付费率(%)",
          "率比(使用者/未使用者)", "成熟度"], sheet6),
        ("结构诊断：Tab2 使用 cohort 本身的 App 级留存（home_show）远低于全体活跃用户",
         ["回访日", "Tab2 cohort人数", "Tab2 cohort仍活跃", "Tab2 cohort App留存(%)",
          "全体活跃人数", "全体仍活跃", "全体 App留存(%)"], diag_rows),
        ("解读边界（P043）", ["项", "说明"], [
            ["不能当因果", "使用者组是「首次使用 Tab2」的人，多为新进/一次性设备；未使用者组是存量活跃老用户，其 14 天内 billing 多为续费。两组人群结构不可比，率比只作描述"],
            ["证据", "上表显示 Tab2 cohort 的 App 级留存显著低于全体活跃；独立复核（cohort 10-20，设备级）Tab2 cohort D+7 仍活跃 287/4532=6.33%，全体活跃 2836/12504=22.68%，Tab2 D+7 复用仅 98/4532=2.16%"],
            ["方向", "本表严格按「首次使用 Tab2 → 之后 14 天」计算，没有倒过来算「付费用户的 Tab2 使用率」"],
            ["限制", "billing_*_success 是埋点成功事件、无金额、无法区分首购/续费；无账号设备不可能进付费分子，两组另列有账号主体占比"],
        ]),
    ])

    write_sheet(wb, "7_登录引导漏斗", [
        ("2.1 平台登录引导漏斗（用户级 3 步，相邻步 ≤30 分钟，按月汇总；平台维度不支持）",
         ["北京月", "有曝光用户", "CTA用户", "CTA率(%)", "login/sign_up成功用户", "成功率(对曝光,%)", "成功率(对CTA,%)"], sheet7_main),
        ("流失口单独统计（close=永久不展示 / logggedin=暂不登录3天冷却 / swipe=滑走3天冷却）",
         ["北京月", "流失事件", "事件数", "去重用户", "占曝光用户(%)", "曝光后30分钟内事件数"], sheet7_loss),
        ("补充参考：卡片 5 事件 + login/sign_up 历史月度总量（2026-08 起，不参与 30 天主口径）",
         ["北京月", "事件", "事件数", "去重设备"], sheet7_hist),
        ("事件名修正", ["说明", "内容"], [
            ["文档写法", "tab2_login_card_cta_click（库内 0 条）"],
            ["库内实际", "tab2_login_cta_click（10-01~11-11 共 79 条）"],
            ["其余 4 个", "tab2_login_card_impression / close / logggedin / swipe 与文档一致；logggedin 库内即三个 g"],
        ]),
    ])

    write_sheet(wb, "8_埋点口径体检", [
        ("事件总量与主体（主窗 30 天；com = 国际版；主体按 userid 优先归并）",
         ["事件", "com事件数", "全版本事件数", "com去重设备", "com去重主体", "有账号主体(%)", "cn事件数", "版本标记空"], ev_rows),
        ("身份与配对质量", ["项", "值"], identity_rows),
        ("Tab2 进入方式（app_open = 打开 App 即落在 Tab2，属被动进入；tab_switch = 主动切 Tab）",
         ["entry_type", "事件数", "去重设备"], entry_rows),
        ("注意③：app_feed_detail_enter.trigger_type 分布", ["trigger_type", "事件数", "占比(%)"], trigger_rows),
        ("注意②：app_feed_card_impression 逐周衰减（进程内去重，跨会话不重置）",
         ["周(北京周一)", "impression事件数", "去重设备", "人均事件数"], imp_rows),
        ("移动端缺口与不做项", ["项", "说明"], [
            ["P037", "移动端 device_id 大部分不在 imt_deviceinfo（历史短窗实测命中率约 13%）；本任务不 JOIN 设备表，身份以埋点 device_id + ex_int_arg1 为准"],
            ["付费埋点", "billing_*_success 无金额、无法区分首购/续费；from 枚举无 Tab2 取值，WebView 内购买统一记 imt_plugin，故 2.3 付费漏斗做不了"],
            ["平台维度", "登录引导事件无 platform 参数，X / Reddit / YouTube 拆不开"],
            ["子 Tab", "子 Tab 切换无埋点，Social / Articles / Videos 分布做不了"],
            ["问卷", "问卷无曝光事件，问卷漏斗分母做不了"],
            ["2.2 内容漏斗", "impression 在 App 进程内去重，第二次会话后有 detail 无 impression，分子分母对不上；本任务改用 duration_ms + viewed_card_count 分布"],
        ]),
    ])

    print("\n=== 关键数字（dry-run 核对用） ===", flush=True)
    print(f"Tab2 日均 UV={avg_t2:.1f}, 国际版 App 日均 UV={avg_app_com:.1f}, 占比={rate(avg_t2, avg_app_com)}%")
    print(f"人均进入次数={tot_t2ev / tot_t2:.2f}")
    print(f"duration P50={p50_all}ms P90={p90_all}ms P99={p99_all}ms, 会话={len(sv)}")
    print(f"内容点击率={rate(h_all, n_all)}% ({h_all}/{n_all}), tap={rate(sum(sess_tap.values()), n_all)}%")
    print(f"Tab2 D+7 成熟合计={sum4[2+2*2]}/{sum4[1]}={sum4[3+2*2]}%")
    print(f"使用者/未使用者 14d 付费率={sum6[4]}% / {sum6[8]}%, 比值={sum6[9]}")
    print("结构诊断(Tab2 cohort vs 全体 App 留存):", diag_rows)
    print("使用者vs全体 D+7 合计: 全体", sum5[16], sum5[17], "用过", sum5[18], sum5[19], "未用", sum5[20], sum5[21])
    print("Tab2 进入方式:", entry_rows)
    print("登录引导漏斗:", sheet7_main, flush=True)

    if args.dry_run:
        print("\n[dry-run] 未写 Excel。", flush=True)
        return

    out = ROOT / "output" / f"tab2_mobile_metrics_{end.strftime('%Y%m%d')}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"\n[交付] {out}", flush=True)


if __name__ == "__main__":
    main()
