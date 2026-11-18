"""T128 Stripe 主动取消 × 行为对照组分析（只读）。

核心：流失组 vs 对照组按锚点日同日 1:1 配对，在同一绝对日期窗口比行为强度，
排除 T127 发现的"相对天覆盖率上升=全局时间趋势假象"。

输入缓存：churn_q1.json / control_map.json / all_cancel_uids.json / churn_subs.json
输出：stripe_churn_control_20261118.xlsx
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402

OUT = ROOT / "output" / "stripe_behavior"
LO, HI = "2026-10-19", "2026-11-17"
PRE, POST = 14, 14  # 锚点前后观察窗（自然日）


def parse_day(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def behavior(uids: set[int]) -> dict:
    """返回 uid -> {date: [events_all,page,subtitle,error,pricing]}"""
    if not uids:
        return {}
    sql = f"""SELECT ex_int_arg1 AS userid, to_date(date_add(hour,8,created_ts)) AS bj_day,
      count(*) AS ev,
      count_if(event_name='translate_page') AS page,
      count_if(event_name='translate_video_subtitle') AS sub,
      count_if(event_name='error_modal_show') AS err,
      count_if(event_name IN ('go_pricing_page','pricing_purchase_btn_click','shell_pricing_activity_modal_show')) AS pricing
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-09-15 16:00:00' AND created_ts < '2026-11-19 16:00:00'
      AND ex_int_arg1 IN ({','.join(str(u) for u in uids)})
    GROUP BY ex_int_arg1, to_date(date_add(hour,8,created_ts))"""
    c, r = query(sql)
    out = defaultdict(dict)
    for row in r:
        d = dict(zip(c, row))
        out[int(d["userid"])][parse_day(d["bj_day"])] = [
            d["ev"] or 0, d["page"] or 0, d["sub"] or 0, d["err"] or 0, d["pricing"] or 0]
    return out


def window_stats(beh: dict, pairs: list, side: str) -> dict:
    """side='pre' → [T0-PRE, T0-1]; 'post' → [T0+1, T0+POST]。
    返回按组的人均强度（分母=该组在该窗有行为者）+ 有行为天数 + 覆盖率。"""
    offs = range(-PRE, 0) if side == "pre" else range(1, POST + 1)
    acc = {g: {"n": 0, "cover": 0, "sum": [0]*5, "days": 0} for g in ("churn", "ctrl")}
    for grp, uid, t0 in pairs:
        a = acc[grp]; n_day = 0; s = [0]*5
        for off in offs:
            v = beh.get(uid, {}).get(t0 + timedelta(days=off))
            if v and v[0] > 0:
                n_day += 1
                for i in range(5):
                    s[i] += v[i]
        a["n"] += 1
        if n_day > 0:
            a["cover"] += 1
            a["days"] += n_day
            for i in range(5):
                a["sum"][i] += s[i]
    out = {}
    for g, a in acc.items():
        c = a["cover"] or 1
        out[g] = {
            "users": a["n"], "active_users": a["cover"],
            "coverage_pct": round(100*a["cover"]/a["n"], 1) if a["n"] else 0,
            "avg_active_days": round(a["days"]/c, 1),
            "ev": round(a["sum"][0]/c, 1), "page": round(a["sum"][1]/c, 1),
            "sub": round(a["sum"][2]/c, 1), "err": round(a["sum"][3]/c, 2),
            "pricing": round(a["sum"][4]/c, 2),
        }
    return out


def main() -> None:
    # 流失组：主动取消 uid + 最后取消日 T0（复用 T127 口径）
    q1 = json.load(open(OUT / "churn_q1.json", encoding="utf-8"))
    inv2uid = {r[0]: r[1] for r in q1["rows"] if r[1]}
    subs = json.load(open(OUT / "churn_subs.json", encoding="utf-8"))
    active = [s for s in subs if s.get("reason") == "cancellation_requested"
              and s.get("canceled_bj") and LO <= s["canceled_bj"] <= HI]
    uid_t0: dict[int, date] = {}
    for s in active:
        uid = inv2uid.get(s["latest_invoice"])
        if not uid:
            continue
        d = date.fromisoformat(s["canceled_bj"])
        if uid not in uid_t0 or d > uid_t0[uid]:
            uid_t0[uid] = d
    print("churn users:", len(uid_t0))

    # 对照组：实付 invoice uid，排除任何已取消 uid
    cmap = json.load(open(OUT / "control_map.json", encoding="utf-8"))
    inv2uid_all = {k: v for k, v in cmap["inv2uid"].items()}
    inv2day = cmap["inv2day"]
    all_cancel = set(json.load(open(OUT / "all_cancel_uids.json", encoding="utf-8")))
    # 每个候选 uid 取窗口内最早实付日作锚点
    ctrl_anchor: dict[int, date] = {}
    for inv, uid in inv2uid_all.items():
        uid = int(uid)
        if uid in all_cancel or uid in uid_t0:
            continue
        d = date.fromisoformat(inv2day[inv])
        if not (LO <= inv2day[inv] <= HI):
            continue
        if uid not in ctrl_anchor or d < ctrl_anchor[uid]:
            ctrl_anchor[uid] = d
    print("control users:", len(ctrl_anchor))

    # 按锚点日同日 1:1 配对
    ctrl_by_day = defaultdict(list)
    for uid, d in ctrl_anchor.items():
        ctrl_by_day[d].append(uid)
    churn_by_day = defaultdict(list)
    for uid, d in uid_t0.items():
        churn_by_day[d].append(uid)
    pairs = []
    unmatched = 0
    for d, cul in sorted(churn_by_day.items()):
        pool = ctrl_by_day.get(d, [])
        for i, uid in enumerate(cul):
            if i < len(pool):
                pairs.append(("churn", uid, d))
                pairs.append(("ctrl", pool[i], d))
            else:
                unmatched += 1
    print("paired days:", len(churn_by_day), "pairs:", len(pairs)//2, "unmatched churn:", unmatched)

    pair_uids = {uid for _, uid, _ in pairs}
    beh = behavior(pair_uids)
    pre = window_stats(beh, pairs, "pre")
    post = window_stats(beh, pairs, "post")
    print("PRE :", pre)
    print("POST:", post)

    # 全窗口（不受 1:1 配对限制）的组级对比做稳健性校验
    allpairs = [("churn", u, d) for u, d in uid_t0.items()]
    for u, d in ctrl_anchor.items():
        allpairs.append(("ctrl", u, d))
    beh_all = behavior({u for _, u, _ in allpairs})
    pre_all = window_stats(beh_all, allpairs, "pre")
    print("PRE-ALL:", pre_all)

    # ---- Excel ----
    wb = Workbook(); ws = wb.active; ws.title = "结论"
    ws.append(["T128 主动取消 vs 对照组（锚点日同日配对）"])
    ws["A1"].font = Font(bold=True)
    for r in [
        ["流失组用户", len(uid_t0)], ["对照组候选", len(ctrl_anchor)],
        ["配对成功", len(pairs)//2], ["未配对流失用户", unmatched],
        ["观察窗", f"前{PRE}天 / 后{POST}天"],
        ["配对方式", "锚点日（北京日）同日 1:1；控制日期分布以排除时间趋势假象"],
        ["对照组定义", "窗口内 Stripe 实付 invoice 的 userid，排除全部 6,398 个已取消用户"],
    ]:
        ws.append(r)

    def sheet(name, stat1, stat2):
        w = wb.create_sheet(name)
        hdr = ["指标", "流失组", "对照组", "差异(流失-对照)"]
        w.append(hdr)
        for cell in w[1]:
            cell.font = Font(bold=True); cell.fill = PatternFill("solid", fgColor="DDEBF7")
        keys = [("样本用户","users"),("有行为用户","active_users"),("有行为占比%","coverage_pct"),
                ("人均有行为天数","avg_active_days"),("人均总事件","ev"),("人均翻译页","page"),
                ("人均字幕","sub"),("人均错误弹窗","err"),("人均定价页访问","pricing")]
        for label, k in keys:
            a, b = stat1[k], stat2[k]
            diff = round(a-b, 2) if isinstance(a,(int,float)) and isinstance(b,(int,float)) else ""
            w.append([label, a, b, diff])
        w.freeze_panes = "A2"

    sheet("取消前14天_配对", pre["churn"], pre["ctrl"])
    sheet("取消后14天_配对", post["churn"], post["ctrl"])
    sheet("取消前14天_全量", pre_all["churn"], pre_all["ctrl"])

    path = OUT / "stripe_churn_control_20261118.xlsx"
    wb.save(path)
    print("saved:", path)
    json.dump({"pre": pre, "post": post, "pre_all": pre_all,
               "n_churn": len(uid_t0), "n_ctrl": len(ctrl_anchor),
               "n_pairs": len(pairs)//2},
              open(OUT / "churn_control_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
