# -*- coding: utf-8 -*-
"""T070 扩量后新付费墙：原 T065 字段 + 窄链路列。激活与埋点按 6 小时切片。"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "output"
    / "login_ai_quota_gift"
    / "gift_weekly_funnel_20261016.xlsx"
)
OBS_END = datetime(2026, 10, 15, 17, 6, 0)  # 北京 2026-10-16 01:05，订单日更水位
BEH_START = datetime(2026, 10, 9, 16, 0, 0)
ORDER_START = datetime(2026, 10, 8, 16, 0, 0)
GROUPS = ("老付费墙(a-e)", "新付费墙(f-j)")
SLICES = (
    ("w_1010_1011", "10/10–11", "2026-10-10", "2026-10-12", "扩量后周末（2天）", 1),
    ("w_1012_1016", "10/12–16（未满）", "2026-10-12", "2026-10-17", "本周未满（至01:05）", 2),
    ("agg", "汇总（10-10～10-16 01:05）", "2026-10-10", "2026-10-17", "混合成熟度·50%", 99),
)

GIFT_EVENTS = (
    "login_ai_quota_gift_login_modal_show",
    "login_ai_quota_gift_login_modal_primary_click",
    "login_ai_quota_gift_login_modal_close",
    "login_ai_quota_gift_claim_success",
    "login_ai_quota_gift_exhausted_modal_show",
    "login_ai_quota_gift_exhausted_modal_primary_click",
    "login_ai_quota_gift_exhausted_modal_close",
)
LN = "login_ai_quota_gift_login_modal_primary_click"
SHOW = "login_ai_quota_gift_login_modal_show"
CLOSE = "login_ai_quota_gift_login_modal_close"
CLAIM = "login_ai_quota_gift_claim_success"
EXH = "login_ai_quota_gift_exhausted_modal_show"
PAY = "login_ai_quota_gift_exhausted_modal_primary_click"
EXCLOSE = "login_ai_quota_gift_exhausted_modal_close"
OLD_HIT = "user_need_pro"
OLD_CLICK = "usage_limit_upgrade_click"
OLD_LOGIN_SHOW = "old_login_show"
OLD_LOGIN_CLICK = "old_login_click"
OLD_LOGIN_CLOSE = "old_login_close"


def chunks(start, end, hours=6):
    t = start
    while t < end:
        t2 = min(t + timedelta(hours=hours), end)
        yield t, t2
        t = t2


def ver_ok(version: str) -> bool:
    parts = []
    for p in str(version or "").split(".")[:3]:
        try:
            parts.append(int(p))
        except ValueError:
            return False
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts) >= (1, 33, 2)


def q(sql: str):
    return query(sql)[1]


def load_cohort(install_end="2026-10-16"):
    best = {}
    for t, t2 in chunks(BEH_START, OBS_END):
        rows = q(f"""
        SELECT device_id,
               min(created_ts) AS first_ts,
               arg_min(lower(trim(ab_tag)), created_ts) AS ab_tag,
               arg_min(version, created_ts) AS version,
               arg_min(ex_int_arg1, created_ts) AS act_raw
        FROM immdata.user_behaviour
        WHERE created_ts >= '{t:%Y-%m-%d %H:%M:%S}'
          AND created_ts < '{t2:%Y-%m-%d %H:%M:%S}'
          AND event_name = 'translate_page'
          AND is_new_user_today = '1'
          AND ab_tag IS NOT NULL
          AND length(trim(ab_tag)) = 1
          AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
        GROUP BY device_id
        """)
        print(f"cohort {t} rows {len(rows)}", flush=True)
        for device_id, first_ts, ab_tag, version, act_raw in rows:
            if not ver_ok(version):
                continue
            install_day = (first_ts + timedelta(hours=8)).strftime("%Y-%m-%d")
            if install_day < "2026-10-10" or install_day >= install_end:
                continue
            prev = best.get(device_id)
            if prev is None or first_ts < prev["first_ts"]:
                ab = (ab_tag or "").strip().lower()
                if ab in "abcde":
                    grp = GROUPS[0]
                elif ab in "fghij":
                    grp = GROUPS[1]
                else:
                    continue
                try:
                    act_uid = int(act_raw) if act_raw not in (None, "") else None
                except (TypeError, ValueError):
                    act_uid = None
                best[device_id] = {
                    "first_ts": first_ts,
                    "ab": ab,
                    "grp": grp,
                    "install_day": install_day,
                    "act_uid": act_uid,
                    "userid": None,
                }
    print("cohort devices", len(best), flush=True)
    return best


def load_gift(cohort):
    ev = defaultdict(list)
    ids = set(cohort)
    event_list = ",".join(f"'{e}'" for e in GIFT_EVENTS)
    for t, t2 in chunks(BEH_START, OBS_END):
        rows = q(f"""
        SELECT device_id, event_name, created_ts, TRY_CAST(ex_int_arg1 AS BIGINT)
        FROM immdata.user_behaviour
        WHERE created_ts >= '{t:%Y-%m-%d %H:%M:%S}'
          AND created_ts < '{t2:%Y-%m-%d %H:%M:%S}'
          AND event_name IN ({event_list})
          AND ab_tag IS NOT NULL
          AND length(trim(ab_tag)) = 1
          AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
        """)
        kept = 0
        for device_id, event_name, ts, uid in rows:
            if device_id not in ids or ts >= OBS_END:
                continue
            ev[device_id].append((event_name, ts, uid))
            kept += 1
        print(f"gift {t} raw {len(rows)} kept {kept}", flush=True)
    return ev


def load_old_wall(cohort):
    ev = defaultdict(list)
    ids = set(cohort)
    for t, t2 in chunks(BEH_START, OBS_END):
        rows = q(f"""
        SELECT device_id, event_name, created_ts, TRY_CAST(ex_int_arg1 AS BIGINT),
          trigger, ex_char_arg1, ex_char_arg2
        FROM immdata.user_behaviour
        WHERE created_ts >= '{t:%Y-%m-%d %H:%M:%S}'
          AND created_ts < '{t2:%Y-%m-%d %H:%M:%S}'
          AND (
            (event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal')
            OR event_name = 'usage_limit_upgrade_click'
            OR (event_name = 'user_need_pro' AND trigger = 'unregisteredUsageLimitModal')
            OR (
              event_name IN ('error_modal_primary_click', 'error_modal_close')
              AND ex_char_arg1 = 'translationUsageLimitHard'
              AND ex_char_arg2 = 'not_login'
            )
          )
        """)
        kept = 0
        for device_id, event_name, ts, uid, trigger, arg1, arg2 in rows:
            if device_id not in ids or ts >= OBS_END:
                continue
            if event_name == "user_need_pro" and trigger == "unregisteredUsageLimitModal":
                label = OLD_LOGIN_SHOW
            elif event_name == "error_modal_primary_click":
                label = OLD_LOGIN_CLICK
            elif event_name == "error_modal_close":
                label = OLD_LOGIN_CLOSE
            else:
                label = event_name
            ev[device_id].append((label, ts, uid))
            kept += 1
        print(f"old wall {t} raw {len(rows)} kept {kept}", flush=True)
    return ev


def batched(items, n):
    buf = []
    for x in items:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def sql_in(vals):
    return ",".join("'" + str(v).replace("'", "''") + "'" for v in vals)


def load_device_users(cohort):
    ids = list(cohort)
    for batch in batched(ids, 800):
        rows = q(f"""
        SELECT device_id, userid FROM (
          SELECT d.deviceid AS device_id, d.userid,
                 row_number() OVER (
                   PARTITION BY d.deviceid
                   ORDER BY CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END, d.installtime
                 ) AS rn
          FROM immdata.imt_deviceinfo d
          WHERE COALESCE(d.isdeleted, 0) = 0
            AND d.installtime > '1970-01-02'
            AND d.deviceid IN ({sql_in(batch)})
        ) t WHERE rn = 1 AND userid IS NOT NULL
        """)
        for device_id, userid in rows:
            if device_id in cohort:
                cohort[device_id]["userid"] = int(userid)
    print("with device userid", sum(1 for d in cohort.values() if d["userid"]), flush=True)


def load_orders():
    rows = q(f"""
    SELECT o.userid, o.createtime,
      CASE WHEN lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
            AND COALESCE(o.amountpaid, 0) = 0
            AND COALESCE(CAST(o.subscriptiongoodssnap AS STRING), '')
                NOT LIKE '%"SubscriptionType":"onetime%'
            AND lower(COALESCE(o.ordertype, '')) <> 'code'
           THEN 1 ELSE 0 END AS is_trial,
      CASE WHEN lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
            AND (
              COALESCE(o.amountpaid, 0) > 0
              OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
              OR lower(COALESCE(o.ordertype, '')) = 'code'
            )
           THEN 1 ELSE 0 END AS is_paid,
      CASE WHEN lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
            AND COALESCE(o.amountpaid, 0) > 0
           THEN 1 ELSE 0 END AS is_cash
    FROM immdata.imt_subscriptiongoodsorder o
    WHERE COALESCE(o.isdeleted, 0) = 0
      AND o.userid IS NOT NULL
      AND o.orderstatus = 'finished'
      AND o.createtime >= '{ORDER_START:%Y-%m-%d %H:%M:%S}'
      AND o.createtime < '{OBS_END:%Y-%m-%d %H:%M:%S}'
    """)
    by = defaultdict(list)
    for uid, ts, is_trial, is_paid, is_cash in rows:
        by[int(uid)].append((ts, int(is_trial or 0), int(is_paid or 0), int(is_cash or 0)))
    print("order users", len(by), "rows", len(rows), flush=True)
    return by


def load_checkout():
    rows = q(f"""
    SELECT userid, createtime
    FROM immdata.imt_checkoutsession
    WHERE COALESCE(isdeleted, 0) = 0
      AND userid IS NOT NULL
      AND createtime >= '{BEH_START:%Y-%m-%d %H:%M:%S}'
      AND createtime < '{OBS_END:%Y-%m-%d %H:%M:%S}'
    """)
    by = defaultdict(list)
    for uid, ts in rows:
        by[int(uid)].append(ts)
    print("checkout users", len(by), flush=True)
    return by


def load_userinfo(uids):
    created = {}
    ids = [int(u) for u in uids if u]
    for batch in batched(ids, 400):
        rows = q(
            "SELECT id, createtime FROM immdata.imt_userinfo "
            f"WHERE COALESCE(isdeleted, 0) = 0 AND id IN ({','.join(str(i) for i in batch)})"
        )
        for uid, ct in rows:
            created[int(uid)] = ct
    print("userinfo", len(created), flush=True)
    return created


def first_ts(evs, name):
    xs = [ts for ev, ts, _uid in evs if ev == name]
    return min(xs) if xs else None


def analyze(cohort, gift, old_wall, orders, checkout, userinfo):
    dev = {}
    for device_id, c in cohort.items():
        evs = gift.get(device_id, [])
        login_ts = first_ts(evs, LN)
        show_login = first_ts(evs, SHOW)
        claims = [(ts, uid) for ev, ts, uid in evs if ev == CLAIM]
        # 登录墙漏斗：先弹出，再点登录，再之后出付费墙，再在这张墙上点去付费。
        clicks_after = [
            ts for ev, ts, _uid in evs
            if ev == LN and show_login and ts >= show_login
        ]
        wall_click_ts = min(clicks_after) if clicks_after else None
        wall_exh = [
            ts for ev, ts, _uid in evs
            if ev == EXH and wall_click_ts and ts >= wall_click_ts
        ]
        wall_exh_ts = min(wall_exh) if wall_exh else None
        wall_pays = [
            (ts, uid) for ev, ts, uid in evs
            if ev == PAY and wall_exh_ts and ts >= wall_exh_ts
        ]
        wall_pay_ts, wall_pay_uid = min(wall_pays, key=lambda x: x[0]) if wall_pays else (None, None)
        # 放宽：不论登录墙还是其他入口，只要领到。付费墙从首次领取之后算。
        claim_ts = min((ts for ts, _uid in claims), default=None)
        claim_uids_at = [uid for ts, uid in claims if claim_ts and ts == claim_ts and uid]
        claim_uid = min(claim_uids_at) if claim_uids_at else None
        claim_exh = [
            ts for ev, ts, _uid in evs
            if ev == EXH and claim_ts and ts >= claim_ts
        ]
        claim_exh_ts = min(claim_exh) if claim_exh else None
        claim_pays = [
            (ts, uid) for ev, ts, uid in evs
            if ev == PAY and claim_exh_ts and ts >= claim_exh_ts
        ]
        claim_pay_ts, claim_pay_uid = min(claim_pays, key=lambda x: x[0]) if claim_pays else (None, None)
        any_pay_rows = [(ts, uid) for ev, ts, uid in evs if ev == PAY]
        any_pay, any_pay_uid = min(any_pay_rows, key=lambda x: x[0]) if any_pay_rows else (None, None)
        oevs = old_wall.get(device_id, [])
        old_hit_ts = min((ts for ev, ts, _uid in oevs if ev == OLD_HIT), default=None)
        any_old_click = min((ts for ev, ts, _uid in oevs if ev == OLD_CLICK), default=None)
        old_click_uid = None
        if any_old_click is not None:
            uids_at = [uid for ev, ts, uid in oevs if ev == OLD_CLICK and ts == any_old_click and uid]
            old_click_uid = min(uids_at) if uids_at else None
        is_old_grp = c["grp"] == GROUPS[0]
        uids = set()
        for u in (c["userid"], c["act_uid"], claim_uid, wall_pay_uid, claim_pay_uid, old_click_uid):
            if u:
                uids.add(int(u))
        for ev, _ts, uid in oevs:
            if ev == OLD_LOGIN_CLICK and uid:
                uids.add(int(uid))
        for _ts, uid in claims:
            if uid:
                uids.add(int(uid))
        old = False
        for u in uids:
            ct = userinfo.get(u)
            if ct is not None and ct < c["first_ts"] - timedelta(days=1):
                old = True
                break
        paid_before = False
        if c["userid"] and c["userid"] in orders:
            for ts, _tr, _pd, _cs in orders[c["userid"]]:
                if ts < c["first_ts"]:
                    paid_before = True
                    break

        def hit(kind, start, end):
            uid = c["userid"]
            if not uid or uid not in orders:
                return False
            for ts, is_trial, is_paid, is_cash in orders[uid]:
                if ts < start or ts >= end:
                    continue
                if kind == "trial" and is_trial:
                    return True
                if kind == "paid" and is_paid:
                    return True
                if kind == "cash" and is_cash:
                    return True
            return False

        anchor = c["first_ts"]
        checkout_3d = False
        if c["userid"] and c["userid"] in checkout:
            for ts in checkout[c["userid"]]:
                if anchor <= ts < anchor + timedelta(days=3) and ts < OBS_END:
                    checkout_3d = True
                    break

        def cash_after(click_ts, pay_uid, limit_1h):
            if not click_ts:
                return False
            hi = click_ts + timedelta(hours=1) if limit_1h else OBS_END
            for u in (c["userid"], c["act_uid"], claim_uid, pay_uid):
                if not u:
                    continue
                for ts, _tr, _pd, is_cash in orders.get(int(u), []):
                    if is_cash and click_ts <= ts < hi and ts < OBS_END:
                        return True
            return False

        pay_anchor = any_old_click if is_old_grp else any_pay
        pay_uid = old_click_uid if is_old_grp else any_pay_uid
        pay_then = cash_after(pay_anchor, pay_uid, True)
        pay_open = cash_after(pay_anchor, pay_uid, False)

        def paid_after_wall(shows):
            if not shows:
                return False
            for u in (c["userid"], c["act_uid"], claim_uid, pay_uid):
                if not u:
                    continue
                for ts, _tr, _pd, is_cash in orders.get(int(u), []):
                    if is_cash and ts < OBS_END and any(show <= ts for show in shows):
                        return True
            return False

        if is_old_grp:
            wall_paid = paid_after_wall([ts for ev, ts, _uid in oevs if ev == OLD_HIT])
            show_login = min((ts for ev, ts, _uid in oevs if ev == OLD_LOGIN_SHOW), default=None)
            clicks_after = [
                ts for ev, ts, _uid in oevs
                if ev == OLD_LOGIN_CLICK and show_login and ts >= show_login
            ]
            wall_click_ts = min(clicks_after) if clicks_after else None
            wall_exh = [
                ts for ev, ts, _uid in oevs
                if ev == OLD_HIT and wall_click_ts and ts >= wall_click_ts
            ]
            wall_exh_ts = min(wall_exh) if wall_exh else None
            wall_pays = [
                (ts, uid) for ev, ts, uid in oevs
                if ev == OLD_CLICK and wall_exh_ts and ts >= wall_exh_ts
            ]
            wall_pay_ts, wall_pay_uid = min(wall_pays, key=lambda x: x[0]) if wall_pays else (None, None)
            login_show = show_login is not None
            login_click = any(ev == OLD_LOGIN_CLICK for ev, _ts, _uid in oevs)
            login_close = any(ev == OLD_LOGIN_CLOSE for ev, _ts, _uid in oevs)
        else:
            wall_paid = paid_after_wall([ts for ev, ts, _uid in evs if ev == EXH])
            login_show = first_ts(evs, SHOW) is not None
            login_click = login_ts is not None
            login_close = first_ts(evs, CLOSE) is not None

        dev[device_id] = {
            "grp": c["grp"],
            "install_day": c["install_day"],
            "old": old,
            "reg": c["userid"] is not None,
            "checkout_3d": checkout_3d,
            "trial_3d": hit("trial", anchor, min(anchor + timedelta(days=3), OBS_END)),
            "paid_3d": (not paid_before) and hit("paid", anchor, min(anchor + timedelta(days=3), OBS_END)),
            "paid_7d": (not paid_before) and hit("paid", anchor, min(anchor + timedelta(days=7), OBS_END)),
            "paid_asof": (not paid_before) and hit("paid", anchor, OBS_END),
            "login_show": login_show,
            "login_click": login_click,
            "login_close": login_close,
            "claim": bool(claims),
            "exh_show": old_hit_ts is not None if is_old_grp else first_ts(evs, EXH) is not None,
            "exh_pay": any_old_click is not None if is_old_grp else any_pay is not None,
            "exh_close": first_ts(evs, EXCLOSE) is not None,
            "pay_then": pay_then,
            "pay_open": pay_open,
            "wall_paid": wall_paid,
            "wall_show": show_login is not None,
            "wall_click": wall_click_ts is not None,
            "wall_exh": wall_exh_ts is not None,
            "wall_pay": wall_pay_ts is not None,
            "wall_cash": cash_after(wall_pay_ts, wall_pay_uid, True),
            "wall_cash_open": cash_after(wall_pay_ts, wall_pay_uid, False),
            "claim_any": claim_ts is not None,
            "claim_exh": claim_exh_ts is not None,
            "claim_pay": claim_pay_ts is not None,
            "claim_cash": cash_after(claim_pay_ts, claim_pay_uid, True),
            "claim_cash_open": cash_after(claim_pay_ts, claim_pay_uid, False),
        }
    return dev


def in_slice(install_day, start, end):
    return start <= install_day < end


def agg_rows(dev):
    out = []
    for scope_b in (False, True):
        for key, label, start, end, maturity, no in SLICES:
            for grp in GROUPS:
                rows = [
                    d for d in dev.values()
                    if d["grp"] == grp
                    and in_slice(d["install_day"], start, end)
                    and (not scope_b or not d["old"])
                ]
                n = len(rows)
                def cnt(k):
                    return sum(1 for d in rows if d[k])
                rec = {
                    "scope": "B" if scope_b else "A",
                    "slice": key,
                    "label": label,
                    "start": start,
                    "end": end,
                    "maturity": maturity,
                    "no": no,
                    "grp": grp,
                    "n": n,
                    "reg": cnt("reg"),
                    "checkout_3d": cnt("checkout_3d"),
                    "trial_3d": cnt("trial_3d"),
                    "paid_3d": cnt("paid_3d"),
                    "paid_7d": cnt("paid_7d"),
                    "paid_asof": cnt("paid_asof"),
                    "login_show": cnt("login_show"),
                    "login_click": cnt("login_click"),
                    "login_close": cnt("login_close"),
                    "claim": cnt("claim"),
                    "exh_show": cnt("exh_show"),
                    "exh_pay": cnt("exh_pay"),
                    "pay_then": cnt("pay_then"),
                    "pay_open": cnt("pay_open"),
                    "wall_paid": cnt("wall_paid"),
                    "exh_close": cnt("exh_close"),
                    "wall_show": cnt("wall_show"),
                    "wall_click": cnt("wall_click"),
                    "wall_exh": cnt("wall_exh"),
                    "wall_pay": cnt("wall_pay"),
                    "wall_cash": cnt("wall_cash"),
                    "wall_cash_open": cnt("wall_cash_open"),
                    "claim_any": cnt("claim_any"),
                    "claim_exh": cnt("claim_exh"),
                    "claim_pay": cnt("claim_pay"),
                    "claim_cash": cnt("claim_cash"),
                    "claim_cash_open": cnt("claim_cash_open"),
                }
                out.append(rec)
                if key == "agg" and scope_b:
                    print(
                        grp, "n", n,
                        "wall", rec["wall_show"], rec["wall_click"], rec["wall_exh"], rec["wall_pay"], rec["wall_cash"], rec["wall_cash_open"],
                        "claim", rec["claim_any"], rec["claim_exh"], rec["claim_pay"], rec["claim_cash"], rec["claim_cash_open"],
                        "paywall", rec["exh_show"], rec["exh_pay"], rec["pay_then"], rec["pay_open"], rec["wall_paid"],
                        flush=True,
                    )
    return out


def pct(num, den):
    if not den:
        return None
    return num / den


def write_overview(ws, rows, title, note):
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    ws["A1"] = title
    ws["A1"].font = bold
    ws["A2"] = note
    headers = [
        "实验组", "激活设备(分母)", "注册率%", "3d checkout%", "3d 试用%", "3d 付费%",
        "7d 付费%", "累计付费人数(总付费)", "累计付费%",
        "登录墙弹出%", "点击登录%", "登录墙关闭%", "领取%", "付费墙%",
        "去付费页人数", "去付费页%", "去付费页后1小时内付费人数", "去付费页后1小时内付费率%(÷去付费页)", "去付费页后付费人数(不限1小时)", "付费墙关闭%", "付费墙后付费人数",
        "漏斗·登录墙弹出", "漏斗·点击登录", "漏斗·点击后付费墙", "漏斗·点击后去付费页", "漏斗·点击后1小时内付费", "漏斗·点击后付费(不限1小时)",
        "漏斗·领取", "漏斗·领取后付费墙", "漏斗·领取后去付费页", "漏斗·领取后1小时内付费", "漏斗·领取后付费(不限1小时)",
    ]
    ws["A5"] = "三条链各有两列付费。1小时内付费：该次去付费页点击之后 1 小时内的现金单。不限1小时：同一点击之后到观察截止。付费墙后付费：弹出付费墙之后到观察截止的现金单，不要求点去付费页，包含点了去付费页再付的人。现金单都是 finished 且 amountpaid>0，不含兑换码、0 元、iospay_renew。"
    ws["A5"].font = bold
    for i, h in enumerate(headers, 1):
        ws.cell(6, i, h).font = bold
    agg = [r for r in rows if r["slice"] == "agg"]
    by = {r["grp"]: r for r in agg}
    rate_cols = {3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 16, 18, 20}
    for i, g in enumerate(GROUPS):
        a = by[g]
        n = a["n"]
        vals = [
            g, n,
            pct(a["reg"], n), pct(a["checkout_3d"], n), pct(a["trial_3d"], n),
            pct(a["paid_3d"], n), pct(a["paid_7d"], n),
            a["paid_asof"], pct(a["paid_asof"], n),
            pct(a["login_show"], n), pct(a["login_click"], n), pct(a["login_close"], n),
            pct(a["claim"], n), pct(a["exh_show"], n),
            a["exh_pay"], pct(a["exh_pay"], n),
            a["pay_then"], pct(a["pay_then"], a["exh_pay"]), a["pay_open"],
            pct(a["exh_close"], n), a["wall_paid"],
            a["wall_show"], a["wall_click"], a["wall_exh"], a["wall_pay"], a["wall_cash"], a["wall_cash_open"],
            a["claim_any"], a["claim_exh"], a["claim_pay"], a["claim_cash"], a["claim_cash_open"],
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(7 + i, col, v)
            if col in rate_cols and v is not None:
                cell.number_format = pct_fmt


def write_weekly(ws, rows, title):
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    ws["A1"] = title
    ws["A1"].font = bold
    headers = [
        "同期群", "安装开始", "安装结束", "成熟状态", "实验组", "激活设备(分母)",
        "注册率%", "3d checkout%", "3d 试用%", "3d 付费%", "7d 付费%",
        "累计付费人数", "累计付费率%(÷激活)",
        "W1留存%", "W2留存%", "W3留存%", "W4留存%",
        "登录墙弹出UV", "登录墙弹出%(÷激活)", "点击登录UV", "点击登录%(÷激活)",
        "登录墙关闭UV", "登录墙关闭%(÷激活)", "领取UV", "领取%(÷激活)",
        "付费墙UV", "付费墙%(÷激活)", "去付费页UV", "去付费页%(÷激活)",
        "去付费页后1小时内付费人数", "去付费页后1小时内付费率%(÷去付费页)", "去付费页后付费人数(不限1小时)",
        "付费墙关闭UV", "付费墙关闭%(÷激活)", "付费墙后付费人数",
        "漏斗·登录墙弹出", "漏斗·点击登录", "漏斗·点击后付费墙", "漏斗·点击后去付费页", "漏斗·点击后1小时内付费", "漏斗·点击后付费(不限1小时)",
        "漏斗·领取", "漏斗·领取后付费墙", "漏斗·领取后去付费页", "漏斗·领取后1小时内付费", "漏斗·领取后付费(不限1小时)",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(3, i, h).font = bold
    ordered = sorted(rows, key=lambda r: (r["no"], r["grp"]))
    rate_idx = {7, 8, 9, 10, 11, 13, 19, 21, 23, 25, 27, 29, 31, 34}
    for i, a in enumerate(ordered):
        n = a["n"]
        end_incl = (datetime.fromisoformat(a["end"]) - timedelta(days=1)).date()
        if a["slice"] == "agg":
            end_incl = datetime(2026, 10, 15).date()
        vals = [
            a["label"], datetime.fromisoformat(a["start"]).date(), end_incl, a["maturity"], a["grp"], n,
            pct(a["reg"], n), pct(a["checkout_3d"], n), pct(a["trial_3d"], n),
            pct(a["paid_3d"], n), pct(a["paid_7d"], n),
            a["paid_asof"], pct(a["paid_asof"], n),
            None, None, None, None,
            a["login_show"], pct(a["login_show"], n),
            a["login_click"], pct(a["login_click"], n),
            a["login_close"], pct(a["login_close"], n),
            a["claim"], pct(a["claim"], n),
            a["exh_show"], pct(a["exh_show"], n),
            a["exh_pay"], pct(a["exh_pay"], n),
            a["pay_then"], pct(a["pay_then"], a["exh_pay"]), a["pay_open"],
            a["exh_close"], pct(a["exh_close"], n), a["wall_paid"],
            a["wall_show"], a["wall_click"], a["wall_exh"], a["wall_pay"], a["wall_cash"], a["wall_cash_open"],
            a["claim_any"], a["claim_exh"], a["claim_pay"], a["claim_cash"], a["claim_cash_open"],
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(4 + i, col, v)
            if col in rate_idx and isinstance(v, float):
                cell.number_format = pct_fmt


def main():
    cohort = load_cohort("2026-10-17")
    gift = load_gift(cohort)
    old_wall = load_old_wall(cohort)
    load_device_users(cohort)
    orders = load_orders()
    checkout = load_checkout()
    uids = set()
    for c in cohort.values():
        if c["userid"]:
            uids.add(c["userid"])
        if c["act_uid"]:
            uids.add(c["act_uid"])
    for evs in gift.values():
        for _ev, _ts, uid in evs:
            if uid:
                uids.add(int(uid))
    userinfo = load_userinfo(uids)
    dev = analyze(cohort, gift, old_wall, orders, checkout, userinfo)
    rows = agg_rows(dev)
    wb = Workbook()
    ws = wb.active
    ws.title = "总览_剔老号"
    note = "激活日≥2026-10-10；asof 北京 2026-10-16 01:05（订单日更水位）；版本≥1.33.2；老付费墙=a–e / 新付费墙=f–j。已剔重装老号。"
    write_overview(ws, [r for r in rows if r["scope"] == "B"], "登录赠送·新版50%（T070）· 剔老号", note)
    write_weekly(wb.create_sheet("周_剔老号"), [r for r in rows if r["scope"] == "B"], "周同期群 · 剔老号")
    cal = wb.create_sheet("口径")
    cal["A1"] = "口径"
    cal["A1"].font = Font(bold=True)
    notes = [
        ("原字段", "登录墙弹出、点击登录、付费墙、去付费页没有额外时间窗。每条链两列付费：1小时内，以及点击之后到观察截止、不限1小时"),
        ("留存", "本窗 W1 未收口，W1–W4 留空"),
        ("漏斗·登录墙", "登录墙弹出 → 点击登录 → 之后付费墙 → 去付费页 → 1小时内付费 → 不限1小时付费。老组登录墙=未登录注册墙 user_need_pro 且 unregisteredUsageLimitModal，点击=error_modal_primary_click 且 translationUsageLimitHard、not_login，关闭=error_modal_close 同条件。新组仍是赠送登录弹窗"),
        ("漏斗·领取", "只要领到（登录墙或其他入口）→ 之后付费墙 → 去付费页 → 1小时内付费 → 不限1小时付费"),
        ("去付费页", "付费墙上的按钮，只表示前往付费页。新旧墙都没有再加时间窗"),
        ("1小时内付费", "该次去付费页点击之后 1 小时内，finished 且 amountpaid>0，不含兑换码、0 元、iospay_renew。订单不早于点击"),
        ("不限1小时付费", "同一点击之后、观察截止之前的现金单，规则与 1 小时内付费相同，只是不再卡 1 小时。订单不早于点击"),
        ("付费墙后付费", "弹出这行对应的付费墙之后、观察截止之前的现金单。不要求点去付费页，点了再付的人也算在里面。现金单规则与不限1小时相同"),
        ("付费墙列", "老付费墙行：付费墙=user_need_pro 且 freeUsageLimitModal，去付费页=usage_limit_upgrade_click。新付费墙行：付费墙=赠送耗尽弹窗。两条付费列的时间窗各自相同"),
        ("累计付费", "仍是激活后的付成订单（含兑换码/onetime），不是窄链子集"),
        ("asof", "北京 2026-10-16 01:05（订单日更水位）"),
    ]
    for i, (a, b) in enumerate(notes, 3):
        cal.cell(i, 1, a)
        cal.cell(i, 2, b)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(OUT)
        print("wrote", OUT, flush=True)
    except PermissionError:
        alt = OUT.with_name(OUT.stem + "_v2.xlsx")
        wb.save(alt)
        print("wrote", alt, flush=True)


if __name__ == "__main__":
    main()
