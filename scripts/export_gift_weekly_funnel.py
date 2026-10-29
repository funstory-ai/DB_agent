# -*- coding: utf-8 -*-
"""新付费墙周漏斗（canonical，按 asof 刷新）：只出剔老号。

治本约定（docs/norms/query.md「刷新类分析」）：同一分析只保留这一份脚本，
刷新时改 --asof 参数，**不复制文件、不新增 dated 脚本**。

默认 --asof=2026-10-28（北京数据日）时，本脚本与历史 export_t085
（asof 10-28 01:04）逐字节等价——其余日期（OBS_END / BEH_START /
ORDER_START / 周切片 / PRESCALE_SQL 边界 / 口径说明 / 输出文件名）全部从
asof 与 --expansion-start 推导。

其它口径（分组 a–e/f–j、版本≥1.33.2、剔老号、1 小时付费、付费墙后付费、
Wk 留存由数据推导自动收口 P045 等）与 T077/T085/T090 完全一致，见对应任务文档。
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]

GROUPS = ("老付费墙(a-e)", "新付费墙(f-j)")

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


# ===== 以下为「随 asof 推导」的运行期全局，由 main() 按参数赋值 =====
OBS_END = None        # UTC，订单副本最新 createtime（北京 asof 日 01:04:29 对应 UTC）
BEH_START = None      # UTC，行为扫描起点 = 扩量开始（北京）− 8h
ORDER_START = None    # UTC，订单扫描起点 = BEH_START − 1 天
SLICES = ()           # 周切片（随 asof 下推）
OUT = None            # 输出 Excel（稳定文件名，刷新覆盖）
ASOF_BEIJING = None   # 北京数据日（date）
INSTALL_END = None    # 设备激活日上界（字符串）


def chunks(start, end, hours=6):
    t = start
    while t < end:
        t2 = min(t + timedelta(hours=hours), end)
        yield t, t2
        t = t2


def monday_on_or_after(d: date) -> date:
    """返回 d 当天或之后最近的周一（与 imm_device_event_by_utf8_week.week_start_day 的周定义一致）。"""
    return d + timedelta(days=(7 - d.weekday()) % 7)


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


def md(d: date) -> str:
    return f"{d.month}/{d.day}"


def build_slices(exp_start: date, asof_date: date):
    """周切片：首桶=扩量后周末 2 天，其后每 7 天一桶，直到覆盖 asof；最后含 asof 的桶标『部分激活』。

    默认 exp_start=2026-10-10、asof=2026-10-28 时，得到与历史完全一致的四桶 + 汇总。
    """
    b0_start = exp_start
    b0_end = exp_start + timedelta(days=2)
    slices = [
        ("w_launch", f"{md(b0_start)}–{md(b0_end - timedelta(days=1))}",
         b0_start.isoformat(), b0_end.isoformat(), "扩量后周末（2天）", 1),
    ]
    cur = b0_end
    k = 2
    while cur < asof_date + timedelta(days=1):
        nxt = cur + timedelta(days=7)
        is_partial = nxt > (asof_date + timedelta(days=1))
        maturity = "完整自然周（7天）" + ("·部分激活" if is_partial else "")
        slices.append((
            f"w_{k}", f"{md(cur)}–{md(nxt - timedelta(days=1))}",
            cur.isoformat(), nxt.isoformat(), maturity, k,
        ))
        cur = nxt
        k += 1
    slices.append((
        "agg", f"汇总（{md(exp_start)}～{md(asof_date)}；asof {asof_date.isoformat()}）",
        exp_start.isoformat(), (asof_date + timedelta(days=1)).isoformat(),
        "混合成熟度·50%", 99,
    ))
    return tuple(slices)


_MAX_RETRY = 6


def q(sql: str):
    last = None
    for attempt in range(_MAX_RETRY):
        try:
            return query(sql)[1]
        except Exception as e:
            msg = str(e)
            if "AccessDenied" in msg or "OssError" in msg or "403" in msg:
                wait = 2 ** attempt
                print(f"q retry {attempt + 1}/{_MAX_RETRY} after {wait}s: {msg[:140]}", flush=True)
                time.sleep(wait)
                last = e
                continue
            raise
    raise last


def load_cohort():
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
            if install_day < "2026-10-10" or install_day >= INSTALL_END:
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
                    "all_uids": set(),
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
        SELECT device_id, userid, rn FROM (
          SELECT d.deviceid AS device_id, d.userid,
                 row_number() OVER (
                   PARTITION BY d.deviceid
                   ORDER BY CASE WHEN d.userid IS NOT NULL THEN 0 ELSE 1 END,
                            d.installtime, d.userid
                 ) AS rn
          FROM immdata.imt_deviceinfo d
          WHERE COALESCE(d.isdeleted, 0) = 0
            AND d.installtime > '1970-01-02'
            AND d.deviceid IN ({sql_in(batch)})
        ) t WHERE userid IS NOT NULL
        """)
        for device_id, userid, rn in rows:
            if device_id not in cohort:
                continue
            uid = int(userid)
            cohort[device_id]["all_uids"].add(uid)
            if int(rn) == 1:
                cohort[device_id]["userid"] = uid
    print("with device userid", sum(1 for d in cohort.values() if d["userid"]), flush=True)


def load_orders():
    rows = q(f"""
    SELECT o.userid, o.createtime,
      CASE WHEN lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
            AND COALESCE(o.amountpaid, 0) = 0
            AND CAST(o.subscriptiongoodssnap AS STRING)
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
        for u in c.get("all_uids") or []:
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
        pay_uids = set(c.get("all_uids") or [])
        if c["userid"]:
            pay_uids.add(c["userid"])

        def uid_blocked(uid):
            for ts, _tr, _pd, _cs in orders.get(uid, []):
                if ts < c["first_ts"]:
                    return True
            return False

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

        def hit_paid_any(start, end):
            for uid in pay_uids:
                if uid_blocked(uid):
                    continue
                for ts, _tr, is_paid, _cs in orders.get(uid, []):
                    if is_paid and start <= ts < end:
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
            seen = set()
            for u in (c["userid"], c["act_uid"], claim_uid, pay_uid, *pay_uids):
                if not u:
                    continue
                u = int(u)
                if u in seen:
                    continue
                seen.add(u)
                for ts, _tr, _pd, is_cash in orders.get(u, []):
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
            seen_paid = set()
            for u in (c["userid"], c["act_uid"], claim_uid, pay_uid, *pay_uids):
                if not u or int(u) in seen_paid:
                    continue
                seen_paid.add(int(u))
                u = int(u)
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
            "paid_3d": hit_paid_any(anchor, min(anchor + timedelta(days=3), OBS_END)),
            "paid_7d": hit_paid_any(anchor, min(anchor + timedelta(days=7), OBS_END)),
            "paid_asof": hit_paid_any(anchor, OBS_END),
            "w1": False,
            "w2": False,
            "w3": False,
            "w4": False,
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


def agg_rows(dev, ret_slices=None):
    if ret_slices is None:
        ret_slices = {}
    out = []
    for scope_b in (True,):
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
                    "w1": cnt("w1") if key in ret_slices.get(1, set()) else None,
                    "w2": cnt("w2") if key in ret_slices.get(2, set()) else None,
                    "w3": cnt("w3") if key in ret_slices.get(3, set()) else None,
                    "w4": cnt("w4") if key in ret_slices.get(4, set()) else None,
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
    rate_idx = {7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 21, 23, 25, 27, 29, 31, 34}
    for i, a in enumerate(ordered):
        n = a["n"]
        end_incl = (datetime.fromisoformat(a["end"]) - timedelta(days=1)).date()
        if a["slice"] == "agg":
            end_incl = ASOF_BEIJING
        vals = [
            a["label"], datetime.fromisoformat(a["start"]).date(), end_incl, a["maturity"], a["grp"], n,
            pct(a["reg"], n), pct(a["checkout_3d"], n), pct(a["trial_3d"], n),
            pct(a["paid_3d"], n), pct(a["paid_7d"], n),
            a["paid_asof"], pct(a["paid_asof"], n),
            pct(a["w1"], n) if a["w1"] is not None else None,
            pct(a["w2"], n) if a["w2"] is not None else None,
            pct(a["w3"], n) if a["w3"] is not None else None,
            pct(a["w4"], n) if a["w4"] is not None else None,
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


def load_retention(device_ids, week_start_day):
    """取回访周 week_start_day 内有 translate_page 的设备集合（Wk 留存判定，k 由调用方决定）。"""
    hit = set()
    ids = list(device_ids)
    print("retention candidates", week_start_day, len(ids), flush=True)
    for batch in batched(ids, 800):
        rows = q(f"""
        SELECT device_id
        FROM immdata.imm_device_event_by_utf8_week
        WHERE event_name = 'translate_page'
          AND week_start_day = DATE '{week_start_day}'
          AND device_id IN ({sql_in(batch)})
        """)
        for (device_id,) in rows:
            hit.add(device_id)
    print("retention hit", week_start_day, len(hit), flush=True)
    return hit


def prescale_sql():
    """扩量前已在用的用户（随 asof / 扩量开始推导）。返回 SQL 字符串。"""
    beh = BEH_START.strftime("%Y-%m-%d %H:%M:%S")
    obs = OBS_END.strftime("%Y-%m-%d %H:%M:%S")
    return f"""
-- 扩量前已在用的用户：北京 {ASOF_BEIJING.isoformat()} 之前注册，扩量后到订单水位有翻译
-- 对照含会员表。两边字母都出现的人排除。
-- asof：订单 createtime < {obs}（北京 {ASOF_BEIJING.isoformat()} 01:04）

WITH ev AS (
  SELECT
    TRY_CAST(ex_int_arg1 AS BIGINT) AS uid,
    lower(trim(ab_tag)) AS ab,
    created_ts,
    event_name,
    trigger
  FROM immdata.user_behaviour
  WHERE created_ts >= '{beh}'
    AND created_ts < '{obs}'
    AND ex_int_arg1 IS NOT NULL
    AND ab_tag IS NOT NULL
    AND length(trim(ab_tag)) = 1
    AND lower(trim(ab_tag)) BETWEEN 'a' AND 'j'
    AND (
      event_name = 'translate_page'
      OR (event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal')
      OR event_name = 'login_ai_quota_gift_exhausted_modal_show'
    )
    AND (
      TRY_CAST(split_part(version, '.', 1) AS INT) > 1
      OR (
        TRY_CAST(split_part(version, '.', 1) AS INT) = 1
        AND (
          TRY_CAST(split_part(version, '.', 2) AS INT) > 33
          OR (
            TRY_CAST(split_part(version, '.', 2) AS INT) = 33
            AND TRY_CAST(split_part(version, '.', 3) AS INT) >= 2
          )
        )
      )
    )
),
tagged AS (
  SELECT
    uid,
    max(CASE WHEN event_name = 'translate_page' AND ab BETWEEN 'a' AND 'e' THEN 1 ELSE 0 END) AS old_tr,
    max(CASE WHEN event_name = 'translate_page' AND ab BETWEEN 'f' AND 'j' THEN 1 ELSE 0 END) AS new_tr,
    min(CASE
          WHEN event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal'
           AND ab BETWEEN 'a' AND 'e' THEN created_ts
        END) AS old_wall_ts,
    min(CASE
          WHEN event_name = 'login_ai_quota_gift_exhausted_modal_show'
           AND ab BETWEEN 'f' AND 'j' THEN created_ts
        END) AS new_wall_ts
  FROM ev
  WHERE uid IS NOT NULL
  GROUP BY uid
),
users AS (
  SELECT
    t.uid,
    CASE WHEN t.old_tr = 1 THEN '老墙 a–e' ELSE '新墙 f–j' END AS grp,
    CASE WHEN t.old_tr = 1 THEN t.old_wall_ts ELSE t.new_wall_ts END AS wall_ts
  FROM tagged t
  INNER JOIN immdata.imt_userinfo ui
    ON ui.id = t.uid
   AND COALESCE(ui.isdeleted, 0) = 0
  WHERE ui.createtime < '{beh}'
    AND (t.old_tr = 1 OR t.new_tr = 1)
    AND NOT (t.old_tr = 1 AND t.new_tr = 1)
),
ord AS (
  SELECT o.userid, o.createtime
  FROM immdata.imt_subscriptiongoodsorder o
  WHERE COALESCE(o.isdeleted, 0) = 0
    AND o.orderstatus = 'finished'
    AND o.userid IS NOT NULL
    AND o.createtime >= '{beh}'
    AND o.createtime < '{obs}'
    AND lower(COALESCE(o.ordertype, '')) <> 'iospay_renew'
    AND (
      COALESCE(o.amountpaid, 0) > 0
      OR CAST(o.subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
      OR lower(COALESCE(o.ordertype, '')) = 'code'
    )
)
SELECT
  u.grp,
  count(*) AS translated,
  count(CASE WHEN u.wall_ts IS NOT NULL THEN 1 END) AS hit,
  count(CASE WHEN u.wall_ts IS NOT NULL AND p.wall_paid = 1 THEN 1 END) AS wall_paid,
  count(CASE WHEN p.any_paid = 1 THEN 1 END) AS any_paid
FROM users u
LEFT JOIN (
  SELECT
    u2.uid,
    max(CASE WHEN o.createtime >= u2.wall_ts THEN 1 ELSE 0 END) AS wall_paid,
    1 AS any_paid
  FROM users u2
  INNER JOIN ord o ON o.userid = u2.uid
  GROUP BY u2.uid
) p ON p.uid = u.uid
GROUP BY u.grp
ORDER BY u.grp
"""


def run_prescale():
    _cols, rows = query(prescale_sql())
    return rows


def write_prescale(ws, rows):
    bold = Font(bold=True)
    pct_fmt = "0.00%"
    ws["A1"] = "扩量前已在用的用户 · 含当时仍是会员"
    ws["A1"].font = bold
    ws["A2"] = (
        f"注册早于北京 {ASOF_BEIJING.isoformat()} 之前扩量开始；扩量后到北京 {ASOF_BEIJING.isoformat()} 01:04 有 translate_page；版本≥1.33.2."
        "两边字母都出现的人不进对比。触墙：老墙=付费硬墙 freeUsageLimitModal，新墙=赠送耗尽弹窗。"
        "付费含兑换码。墙后付费的订单不早于首次触墙。"
    )
    headers = ["组", "扩量后有翻译", "触墙", "触墙率", "墙后付费", "触墙转化", "扩量后付费", "整体转化"]
    for i, h in enumerate(headers, 1):
        c = ws.cell(4, i, h)
        c.font = bold
    for r_i, (grp, translated, hit, wall_paid, any_paid) in enumerate(rows, start=5):
        t = int(translated); h_ = int(hit); wp = int(wall_paid); ap = int(any_paid)
        vals = [
            grp, t, h_,
            (h_ / t) if t else None,
            wp,
            (wp / h_) if h_ else None,
            ap,
            (ap / t) if t else None,
        ]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(r_i, col, v)
            if col in (4, 6, 8) and isinstance(v, float):
                cell.number_format = pct_fmt


def main():
    ap = argparse.ArgumentParser(description="新付费墙周漏斗（canonical，按 asof 刷新）")
    ap.add_argument("--asof", default="2026-10-28",
                    help="北京数据日 YYYY-MM-DD（订单水位日）；默认 2026-10-28 复现 T090")
    ap.add_argument("--expansion-start", default="2026-10-10",
                    help="扩量开始日 YYYY-MM-DD（北京）；默认 2026-10-10")
    ap.add_argument("--install-end-days", type=int, default=5,
                    help="设备激活日上界 = asof + N 天（宽松捕获）；默认 5")
    ap.add_argument("--obs-end", default=None,
                    help="可选：直接指定订单副本最新 createtime(UTC) YYYY-MM-DD HH:MM:SS；"
                         "默认 = (asof-1) 17:04:29（与历史 T090 一致）")
    ap.add_argument("--out", default=None,
                    help="输出 Excel 路径；默认 output/login_ai_quota_gift/gift_weekly_funnel.xlsx（稳定名，刷新覆盖）")
    args = ap.parse_args()

    global OBS_END, BEH_START, ORDER_START, SLICES, OUT, ASOF_BEIJING, INSTALL_END

    asof_date = datetime.strptime(args.asof, "%Y-%m-%d").date()
    ASOF_BEIJING = asof_date
    exp_start = datetime.strptime(args.expansion_start, "%Y-%m-%d").date()
    if args.obs_end:
        OBS_END = datetime.strptime(args.obs_end, "%Y-%m-%d %H:%M:%S")
    else:
        OBS_END = datetime(asof_date.year, asof_date.month, asof_date.day) - timedelta(days=1) + timedelta(hours=17, minutes=4, seconds=29)
    beh_date = datetime(exp_start.year, exp_start.month, exp_start.day) - timedelta(hours=8)
    BEH_START = beh_date
    ORDER_START = BEH_START - timedelta(days=1)
    SLICES = build_slices(exp_start, asof_date)
    INSTALL_END = (asof_date + timedelta(days=args.install_end_days)).isoformat()
    OUT = Path(args.out) if args.out else (ROOT / "output" / "login_ai_quota_gift" / "gift_weekly_funnel.xlsx")

    print(f"=== canonical gift weekly funnel | asof={ASOF_BEIJING} "
          f"OBS_END(UTC)={OBS_END} BEH_START(UTC)={BEH_START} "
          f"ORDER_START(UTC)={ORDER_START} INSTALL_END={INSTALL_END} ===", flush=True)

    cohort = load_cohort()
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
        for u in c.get("all_uids") or []:
            uids.add(int(u))
    for evs in gift.values():
        for _ev, _ts, uid in evs:
            if uid:
                uids.add(int(uid))
    userinfo = load_userinfo(uids)
    dev = analyze(cohort, gift, old_wall, orders, checkout, userinfo)
    # Wk 留存（k=1..4）：按各同期群各自的回访周（激活区间结束日的当周周一）独立计算。
    # 回访周 = monday_on_or_after(end) + (k-1)*7 天。
    # 成熟度采用标准口径：cohort 最后激活日 + k*7 天 ≤ asof（= end + (k*7-1) 天 ≤ OBS_END.date()），
    # 允许回访周最后一天尾段（数小时）尚未完全入库——与常规周报一致。
    # 不写死任何回访周：随 asof 推进自动收口（P045）。
    ret_weeks = {1: "w1", 2: "w2", 3: "w3", 4: "w4"}
    ret_slices = {k: set() for k in ret_weeks}
    for key, _label, start, end, _maturity, _no in SLICES:
        if key == "agg":
            continue
        end_d = datetime.fromisoformat(end).date()
        for k, sname in ret_weeks.items():
            if end_d + timedelta(days=k * 7 - 1) > OBS_END.date():
                continue  # 回访周未收口
            ws_d = monday_on_or_after(end_d) + timedelta(days=(k - 1) * 7)
            ids = load_retention(
                (d for d, c in cohort.items() if start <= c["install_day"] < end),
                ws_d.isoformat(),
            )
            for device_id in ids:
                if device_id in dev:
                    dev[device_id][sname] = True
            ret_slices[k].add(key)
    rows = agg_rows(dev, ret_slices)
    b_rows = [r for r in rows if r["scope"] == "B"]
    ok = True
    weekly = [r for r in b_rows if r["slice"] != "agg"]
    agg = {r["grp"]: r for r in b_rows if r["slice"] == "agg"}
    for g in GROUPS:
        s = sum(r["n"] for r in weekly if r["grp"] == g)
        if s != agg[g]["n"]:
            print("FAIL weekly sum", g, s, agg[g]["n"], flush=True)
            ok = False
        if agg[g]["pay_then"] > agg[g]["exh_pay"]:
            print("FAIL pay_then", g, flush=True)
            ok = False
        if agg[g]["wall_click"] > agg[g]["wall_show"]:
            print("FAIL wall click", g, flush=True)
            ok = False
    for k, sname in ret_weeks.items():
        for key in ret_slices.get(k, set()):
            for r in b_rows:
                if r["slice"] != key:
                    continue
                if r[sname] is None or r["n"] == 0:
                    print("FAIL", sname, "empty", key, r["grp"], flush=True)
                    ok = False
                else:
                    print(r["grp"], key, sname, "n", r["n"], sname, r[sname], "paid", r["paid_asof"], flush=True)
    new = agg["新付费墙(f-j)"]
    if new["n"] and new["login_show"] / new["n"] < 0.4:
        print("FAIL new wall login low", flush=True)
        ok = False
    print("【抽样复核】", "通过" if ok else "不通过", flush=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "总览_剔老号"
    beijing_obs = (OBS_END + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    note = (f"激活日≥{exp_start.isoformat()}；asof 北京 {beijing_obs}（订单日更水位）；版本≥1.33.2；"
            f"老付费墙=a–e / 新付费墙=f–j。只含剔重装老号。")
    title = f"登录赠送·新版50% · 剔老号 · asof {ASOF_BEIJING.isoformat()}"
    write_overview(ws, b_rows, title, note)
    write_weekly(wb.create_sheet("周_剔老号"), b_rows, "周同期群 · 剔老号")
    write_prescale(wb.create_sheet("扩量前用户"), run_prescale())
    cal = wb.create_sheet("口径")
    cal["A1"] = "口径"
    cal["A1"].font = Font(bold=True)
    notes = [
        ("原字段", "登录墙弹出、点击登录、付费墙、去付费页没有额外时间窗。每条链两列付费：1小时内，以及点击之后到观察截止、不限1小时"),
        ("留存", "Wk=回访周有 translate_page（k=1..4，由数据推导的回访周自动收口，不写死）。回访周=monday_on_or_after(激活区间结束日)+(k-1)*7天；成熟度=最后激活日+k*7天 ≤ asof。未收口留空（非0）。"),
        ("漏斗·登录墙", "登录墙弹出 → 点击登录 → 之后付费墙 → 去付费页 → 1小时内付费 → 不限1小时付费。老组登录墙=未登录注册墙 user_need_pro 且 unregisteredUsageLimitModal，点击=error_modal_primary_click 且 translationUsageLimitHard、not_login，关闭=error_modal_close 同条件。新组仍是赠送登录弹窗"),
        ("漏斗·领取", "只要领到（登录墙或其他入口）→ 之后付费墙 → 去付费页 → 1小时内付费 → 不限1小时付费"),
        ("去付费页", "付费墙上的按钮，只表示前往付费页。新旧墙都没有再加时间窗"),
        ("1小时内付费", "该次去付费页点击之后 1 小时内，finished 且 amountpaid>0，不含兑换码、0 元、iospay_renew。订单不早于点击"),
        ("不限1小时付费", "同一点击之后、观察截止之前的现金单，规则与 1 小时内付费相同，只是不再卡 1 小时。订单不早于点击"),
        ("付费墙后付费", "弹出这行对应的付费墙之后、观察截止之前的现金单。不要求点去付费页，点了再付的人也算在里面。现金单规则与不限1小时相同"),
        ("付费墙列", "老付费墙行：付费墙=user_need_pro 且 freeUsageLimitModal，去付费页=usage_limit_upgrade_click。新付费墙行：付费墙=赠送耗尽弹窗。两条付费列的时间窗各自相同"),
        ("累计付费", "仍是激活后的付成订单（含兑换码/onetime），不是窄链子集。同一设备多个账号时，任一账号付过费即算（P018-E）"),
        ("未剔除", "本文件只有剔老号，没有全量对照"),
        ("asof", f"北京 {beijing_obs}（订单副本最新 createtime {OBS_END.strftime('%Y-%m-%d %H:%M:%S')} UTC）；由 --asof 参数推导"),
        ("刷新约定", "本脚本为 canonical：刷新只改 --asof，不复制 dated 脚本（见 docs/norms/query.md「刷新类分析」）"),
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
