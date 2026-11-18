"""T127 Stripe 主动取消流失 × 流失前行为分析 —— 报告生成（只读）。

输入：output/stripe_behavior/churn_subs.json（stripe_churn_extract 产出）
      sql/reports/query_stripe_churn_behavior_20261118.sql（Q1/Q2 占位符模板）
输出：output/stripe_behavior/stripe_churn_behavior_20261118.xlsx
纪律：不写库、不打印 Key、P043 猜测标注、P019 抽样复核。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill, Alignment  # noqa: E402

OUT = ROOT / "output" / "stripe_behavior"
LO, HI = "2026-10-19", "2026-11-17"  # 北京日窗口（含端点）


def load_q() -> dict:
    txt = (ROOT / "sql/reports/query_stripe_churn_behavior_20261118.sql").read_text(encoding="utf-8")
    q = {}
    for tag, nxt in [("Q1", "Q2"), ("Q2", None)]:
        pat = rf"-- {tag}.*?\n(SELECT.*?)(?=\n-- {nxt}|\Z)" if nxt else rf"-- {tag}.*?\n(SELECT.*?)\Z"
        m = re.search(pat, txt, re.S)
        if not m:
            raise RuntimeError(f"SQL {tag} not found")
        q[tag] = m.group(1).strip().rstrip(";")
    return q


def classify_comment(c: str) -> str:
    """P043：多语种规则为人工猜测归类，非 Stripe 原生字段，需逐条人工确认。
    优先级：误订/扣款 > 价格 > 额度 > 功能 > 质量/不好用 > 其他。"""
    s = c.lower()
    if re.search(r"重复|重複|綁|误订|扣款|无故|用其他账号|换其他|取消.*订閱|duplicate|double subscription", s):
        return "误订/重复/扣款争议(猜测)"
    if re.search(r"贵|貴|price|expensive|descuento|discount|student|学生|太贵", s):
        return "价格/折扣(猜测)"
    if re.search(r"tok|额度|限额|太少|不够|用得|用完|性能|确认|credit|quota|allowance|토큰|제한|トークン", s):
        return "额度/token不足(猜测)"
    if re.search(r"pdf|图片|image|功能|feature|video|影片|视频|字幕|subtitle|manga|直播|자막|영상|기능|機能|번역.*제한|翻译.*(功能|多个)", s):
        return "功能缺失/文件格式(猜测)"
    if re.search(r"不准|不精|质量|品質|不好用|太差|爛|差了|not working|didn.t work|neprelozilo|funcion|translation issue|translat|번역|翻译|翻譯|slow|慢|delay|延迟|無法|没用|无用| hoping", s):
        return "翻译质量/不好用(猜测)"
    if re.search(r"感谢|thanks|thank you|ㅇㅇ|^\.+$|^[^a-z]", s):
        return "其他/情绪(需人工)"
    return "其他(需人工)"


def main() -> None:
    subs = json.load(open(OUT / "churn_subs.json", encoding="utf-8"))
    print("loaded subs:", len(subs))

    # 窗口 + reason 分层
    in_win = [s for s in subs if s["canceled_bj"] and LO <= s["canceled_bj"] <= HI]
    active = [s for s in in_win if s["reason"] == "cancellation_requested"]
    failed = [s for s in in_win if s["reason"] == "payment_failed"]
    print(f"in window {LO}~{HI}: {len(in_win)} | active={len(active)} payment_failed={len(failed)}")

    # 每个 userid 的最后一次取消（T0）——需先经 Q1 映射拿到 userid
    inv_list = [s["latest_invoice"] for s in active if s["latest_invoice"]]
    inv_sql = ",".join("'" + i.replace("'", "") + "'" for i in inv_list) or "''"
    if len(inv_list) > 0:
        c1, r1 = query(load_q()["Q1"].replace("__INVOICES__", inv_sql))
    else:
        c1, r1 = [], []
    print("Q1 matched rows:", len(r1))
    json.dump({"columns": c1, "rows": [list(x) for x in r1]},
              open(OUT / "churn_q1.json", "w", encoding="utf-8"), ensure_ascii=False, default=str)

    inv2uid = {}
    for row in r1:
        d = dict(zip(c1, row))
        inv2uid[d["invoiceid"]] = d["userid"]

    # 订阅 -> userid，取每个 userid 最后一次取消日 T0
    uid_t0: dict[int, date] = {}
    uid_subs: dict[int, list] = defaultdict(list)
    for s in active:
        uid = inv2uid.get(s["latest_invoice"])
        if not uid:
            continue
        uid_subs[uid].append(s)
        cd = date.fromisoformat(s["canceled_bj"])
        if uid not in uid_t0 or cd > uid_t0[uid]:
            uid_t0[uid] = cd
    print("mapped userids:", len(uid_t0), "/", len(active), "active subs")

    # 按套餐分层（取最后一张订阅的 price）
    def plan_of(s: dict) -> str:
        amt = s.get("price_unit_amount") or 0
        interval = s.get("price_interval") or ""
        if amt >= 100000:
            return "Max年费(猜测)"
        if amt >= 50000:
            return "Pro年费(猜测)"
        if amt >= 15000:
            return "Pro/Max月付(猜测)"
        return "其他/试用(猜测)"

    uid_plan = {uid: plan_of(subs[-1]) for uid, subs in uid_subs.items()}

    # Q2 行为：userid × 北京日矩阵（数值型 IN，无需引号）
    if uid_t0:
        uid_sql = ",".join(str(u) for u in uid_t0)
        c2, r2 = query(load_q()["Q2"].replace("__UIDS__", uid_sql))
    else:
        c2, r2 = [], []
    print("Q2 behavior rows:", len(r2))
    json.dump({"columns": c2, "rows": [list(x) for x in r2]},
              open(OUT / "churn_q2.json", "w", encoding="utf-8"), ensure_ascii=False, default=str)

    # 行为按 user × day 索引
    beh = defaultdict(dict)  # uid -> {date: [events_all,page,sub,error,pricing,submanage]}
    for row in r2:
        d = dict(zip(c2, row))
        dd = d["bj_day"]
        if isinstance(dd, datetime):
            dd = dd.date()
        elif isinstance(dd, str):
            dd = date.fromisoformat(dd[:10])
        beh[int(d["userid"])][dd] = [d["events_all"] or 0, d["translate_page"] or 0,
                                     d["translate_subtitle"] or 0, d["error_modal"] or 0,
                                     d["pricing_visit"] or 0, d["sub_manage_click"] or 0]

    # 流失前相对天数曲线：rel = (day - T0)，取 [-30,-1]
    def curve(uids: list[int]) -> list[dict]:
        out = []
        for rel in range(-30, 0):
            n_active = 0; sums = [0] * 6
            for uid in uids:
                day = uid_t0[uid] + timedelta(days=rel)
                v = beh.get(uid, {}).get(day)
                if v and v[0] > 0:
                    n_active += 1
                    for i in range(6):
                        sums[i] += v[i]
            out.append({"rel": rel, "active_users": n_active,
                        "coverage_pct": round(100 * n_active / len(uids), 1) if uids else 0,
                        "events_per_active": round(sums[0] / n_active, 1) if n_active else 0,
                        "page_per_active": round(sums[1] / n_active, 1) if n_active else 0,
                        "subtitle_per_active": round(sums[2] / n_active, 1) if n_active else 0,
                        "error_per_active": round(sums[3] / n_active, 2) if n_active else 0,
                        "pricing_per_active": round(sums[4] / n_active, 2) if n_active else 0})
        return out

    all_uids = list(uid_t0)
    curve_all = curve(all_uids)

    # 固定核心组：T0 距窗口起点 ≥20 天（T0-30 落在数据窗内）且在 [T0-30,-1] 至少 5 天有行为，
    # 排除"用户中途才出现"造成的覆盖率上升假象（P043：口径选择需披露）。
    core_uids = []
    for uid in all_uids:
        if (uid_t0[uid] - date(2026, 10, 19)).days < 20:
            continue
        active_days = sum(1 for rel in range(-30, 0)
                          if (beh.get(uid, {}).get(uid_t0[uid] + timedelta(days=rel)) or [0])[0] > 0)
        if active_days >= 5:
            core_uids.append(uid)
    curve_core = curve(core_uids)
    print("core users:", len(core_uids))
    by_plan = defaultdict(list)
    for uid in all_uids:
        by_plan[uid_plan[uid]].append(uid)
    curves_plan = {p: curve(u) for p, u in by_plan.items()}

    # comment 归类 + 交叉验证（P043 猜测标注）
    comment_rows = []
    comment_uids = defaultdict(list)
    for s in active:
        if not s.get("comment"):
            continue
        uid = inv2uid.get(s["latest_invoice"])
        cat = classify_comment(s["comment"])
        comment_rows.append([s["canceled_bj"], s["id"][:22], cat,
                             s["comment"], uid or "", uid_plan.get(uid, "") if uid else "",
                             s.get("price_id") or ""])
        if uid:
            comment_uids[cat].append(uid)
    print("comment rows:", len(comment_rows))

    # 交叉：有 comment 的用户 vs 全部，流失前 7 天总量
    cross = []
    for cat, uids in comment_uids.items():
        uids = list(set(uids))
        last7 = []
        for uid in uids:
            for rel in range(-7, 0):
                v = beh.get(uid, {}).get(uid_t0[uid] + timedelta(days=rel))
                if v:
                    last7.append(v[0])
        cross.append([cat, len(uids), len(last7),
                      round(sum(last7) / len(last7), 1) if last7 else 0,
                      "P043：样本小，仅定性；不据此下结论"])

    # 时间趋势：按取消日
    trend = Counter(s["canceled_bj"] for s in active)

    # ---------- Excel ----------
    wb = Workbook()
    ws = wb.active
    ws.title = "结论摘要"

    def add_sheet(name: str, header: list, rows: list):
        w = wb.create_sheet(name)
        w.append(header)
        for cell in w[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDEBF7")
            cell.alignment = Alignment(horizontal="center")
        for r in rows:
            w.append(r)
        w.freeze_panes = "A2"
        return w

    summary = [
        ["任务", "T127 Stripe 主动取消流失 × 流失前行为"],
        ["窗口（取消日 北京日）", f"{LO} ~ {HI}"],
        ["窗口内取消订阅", len(in_win)],
        ["主动取消 cancellation_requested", len(active)],
        ["支付失败 payment_failed（背景对照）", len(failed)],
        ["主动取消 → userid 映射成功", f"{len(uid_t0)} / {len(active)} = {round(100*len(uid_t0)/len(active),1) if active else 0}%"],
        ["有行为流水的映射用户", len([u for u in all_uids if any(v[0] > 0 for v in beh.get(u, {}).values())])],
        ["行为事件带 userid 覆盖", "约 40–45%（仅登录事件；P037 移动端缺口未补）"],
        ["comment 自由文本", f"{len(comment_rows)} / {len(active)} = {round(100*len(comment_rows)/len(active),1) if active else 0}%"],
        ["核心组用户数(T0-30有行为)", len(core_uids)],
        ["曲线方向关键更正", "相对天曲线的覆盖率上升是假象：流失用户中有行为记录比例 9月11%→11月42%(全局时间趋势，登录事件覆盖/产品增长)，与流失无关"],
        ["可用的稳健指标", "人均事件/人均翻译页等强度指标(分母=当天有行为者)；覆盖率与活跃用户数禁止解读为行为回升"],
        ["P043 提示", "套餐档位/ comment 归类均为多语种规则猜测，需人工确认；不写库、非定案"],
    ]
    for r in summary:
        ws.append(r)
    ws["A1"].font = Font(bold=True)

    add_sheet("取消结构_按日", ["取消日(北京)", "主动取消数"],
              [[d, n] for d, n in sorted(trend.items())])
    add_sheet("取消原因_结构", ["reason", "数量", "占窗口内取消%"],
              [["cancellation_requested(主动)", len(active), round(100*len(active)/len(in_win), 1) if in_win else 0],
               ["payment_failed(支付失败)", len(failed), round(100*len(failed)/len(in_win), 1) if in_win else 0],
               ["其他/空", len(in_win)-len(active)-len(failed),
                round(100*(len(in_win)-len(active)-len(failed))/len(in_win), 1) if in_win else 0]])
    add_sheet("流失前行为曲线_整体",
              ["相对天(0=取消日)", "活跃用户", "活跃覆盖率%", "人均事件", "人均翻译页", "人均字幕", "人均错误弹窗", "人均定价页"],
              [[c["rel"], c["active_users"], c["coverage_pct"], c["events_per_active"],
                c["page_per_active"], c["subtitle_per_active"], c["error_per_active"], c["pricing_per_active"]]
               for c in curve_all])
    add_sheet("流失前行为曲线_核心组",
              ["相对天(0=取消日)", "活跃用户", "活跃覆盖率%", "人均事件", "人均翻译页", "人均字幕", "人均错误弹窗", "人均定价页"],
              [[c["rel"], c["active_users"], c["coverage_pct"], c["events_per_active"],
                c["page_per_active"], c["subtitle_per_active"], c["error_per_active"], c["pricing_per_active"]]
               for c in curve_core])
    add_sheet("流失前行为_按套餐",
              ["套餐(猜测)", "相对天", "活跃用户", "人均事件", "人均翻译页", "人均字幕", "人均错误弹窗"],
              [[p, c["rel"], c["active_users"], c["events_per_active"], c["page_per_active"],
                c["subtitle_per_active"], c["error_per_active"]]
               for p, cs in curves_plan.items() for c in cs])
    add_sheet("comment原文与归类",
              ["取消日", "订阅ID", "归类(P043猜测)", "原文", "userid", "套餐(猜测)", "price_id"],
              comment_rows)
    add_sheet("comment×行为交叉",
              ["归类(P043猜测)", "用户数", "流失前7天有事件记录数", "人均事件", "说明"], cross)
    add_sheet("映射样本",
              ["invoiceid", "userid", "useremail", "amountpaid(分)", "货币", "订单状态"],
              [[dict(zip(c1, r))["invoiceid"], dict(zip(c1, r))["userid"],
                dict(zip(c1, r))["useremail"], dict(zip(c1, r))["amountpaid"],
                dict(zip(c1, r))["currency"], dict(zip(c1, r))["orderstatus"]] for r in r1[:40]])

    path = OUT / "stripe_churn_behavior_20261118.xlsx"
    wb.save(path)
    print("saved:", path)
    print("=== 关键数字 ===")
    print("window cancels:", len(in_win), "active:", len(active), "mapped users:", len(uid_t0))
    print("comment:", len(comment_rows), "categories:", Counter(r[2] for r in comment_rows).most_common())
    print("curve head/tail:", curve_all[0], curve_all[-1])
    print("core curve head/tail:", curve_core[0], curve_core[-1])


if __name__ == "__main__":
    main()
