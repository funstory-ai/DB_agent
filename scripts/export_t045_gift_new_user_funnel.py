# -*- coding: utf-8 -*-
"""T045: new-user gift funnel (is_new_user_today + P034 overlap). Not full T018."""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, numbers

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "login_ai_quota_gift" / "gift_new_user_funnel_20260929.xlsx"
TS_START = "2026-09-21"
TS_END = "2026-09-29 16:00:00"
EVENTS = (
    "login_ai_quota_gift_login_modal_show",
    "login_ai_quota_gift_login_modal_primary_click",
    "login_ai_quota_gift_login_modal_close",
    "login_ai_quota_gift_claim_success",
    "login_ai_quota_gift_received_modal_show",
    "login_ai_quota_gift_exhausted_modal_show",
    "login_ai_quota_gift_exhausted_modal_primary_click",
    "login_ai_quota_gift_exhausted_modal_close",
)
EV_IN = ",".join(f"'{e}'" for e in EVENTS)


def q(sql: str):
    cols, rows = query(sql)
    return cols, rows


def main() -> None:
    print("A) event-day new user, by group...", flush=True)
    sql_a = f"""
    SELECT
      CASE
        WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
        WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
        WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
        WHEN lower(trim(ab_tag)) = 'i' THEN 'D_i'
        WHEN lower(trim(ab_tag)) = 'j' THEN 'D_j'
        ELSE 'other'
      END AS exp_group,
      event_name,
      count(*) AS n,
      count(DISTINCT device_id) AS uv
    FROM immdata.user_behaviour
    WHERE created_ts >= '{TS_START}'
      AND created_ts < '{TS_END}'
      AND is_new_user_today = '1'
      AND event_name IN ({EV_IN})
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    cols_a, rows_a = q(sql_a)
    for r in rows_a:
        print(r, flush=True)

    print("A2) j device path among event-day new...", flush=True)
    sql_path = f"""
    WITH e AS (
      SELECT device_id, event_name, created_ts
      FROM immdata.user_behaviour
      WHERE created_ts >= '{TS_START}'
        AND created_ts < '{TS_END}'
        AND is_new_user_today = '1'
        AND lower(trim(ab_tag)) = 'j'
        AND event_name IN ({EV_IN})
    ),
    d AS (
      SELECT
        device_id,
        max(CASE WHEN event_name = 'login_ai_quota_gift_login_modal_show' THEN 1 ELSE 0 END) AS login_show,
        max(CASE WHEN event_name = 'login_ai_quota_gift_login_modal_primary_click' THEN 1 ELSE 0 END) AS login_click,
        max(CASE WHEN event_name = 'login_ai_quota_gift_login_modal_close' THEN 1 ELSE 0 END) AS login_close,
        max(CASE WHEN event_name = 'login_ai_quota_gift_claim_success' THEN 1 ELSE 0 END) AS claim,
        max(CASE WHEN event_name = 'login_ai_quota_gift_exhausted_modal_show' THEN 1 ELSE 0 END) AS exhausted,
        max(CASE WHEN event_name = 'login_ai_quota_gift_exhausted_modal_primary_click' THEN 1 ELSE 0 END) AS exh_pay,
        max(CASE WHEN event_name = 'login_ai_quota_gift_exhausted_modal_close' THEN 1 ELSE 0 END) AS exh_close
      FROM e
      GROUP BY 1
    )
    SELECT
      count(*) AS devices,
      count_if(login_show = 1) AS login_show_uv,
      count_if(login_click = 1) AS login_click_uv,
      count_if(login_close = 1) AS login_close_uv,
      count_if(claim = 1) AS claim_uv,
      count_if(claim = 1 AND login_show = 0) AS claim_silent,
      count_if(claim = 1 AND login_click = 1) AS claim_after_click,
      count_if(exhausted = 1) AS exhausted_uv,
      count_if(exhausted = 1 AND claim = 1) AS exhausted_with_claim,
      count_if(exh_pay = 1) AS exh_pay_uv,
      count_if(exh_close = 1) AS exh_close_uv
    FROM d
    """
    cols_p, rows_p = q(sql_path)
    path = dict(zip(cols_p, rows_p[0]))
    print(path, flush=True)

    print("B) P034 activate UV by group, then gift overlap...", flush=True)
    sql_act = f"""
    WITH first_act AS (
      SELECT
        device_id,
        ab_tag,
        created_ts,
        CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) AS act_day
      FROM (
        SELECT
          device_id,
          ab_tag,
          created_ts,
          row_number() OVER (PARTITION BY device_id ORDER BY created_ts) AS rn
        FROM immdata.user_behaviour
        WHERE created_ts >= '2026-09-20 16:00:00'
          AND created_ts < '{TS_END}'
          AND event_name = 'translate_page'
          AND is_new_user_today = '1'
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
      ) t
      WHERE rn = 1
        AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) >= '2026-09-21'
        AND CAST(to_date(add_hours(created_ts, 8)) AS VARCHAR) < '2026-09-30'
    ),
    labeled AS (
      SELECT
        device_id,
        CASE
          WHEN lower(trim(ab_tag)) IN ('a','b','c') THEN 'A'
          WHEN lower(trim(ab_tag)) IN ('d','e','f') THEN 'B'
          WHEN lower(trim(ab_tag)) IN ('g','h') THEN 'C'
          WHEN lower(trim(ab_tag)) = 'i' THEN 'D_i'
          WHEN lower(trim(ab_tag)) = 'j' THEN 'D_j'
          ELSE 'other'
        END AS exp_group
      FROM first_act
    ),
    gift AS (
      SELECT DISTINCT device_id, event_name
      FROM immdata.user_behaviour
      WHERE created_ts >= '{TS_START}'
        AND created_ts < '{TS_END}'
        AND event_name IN ({EV_IN})
    )
    SELECT
      l.exp_group,
      count(DISTINCT l.device_id) AS activate_uv,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_show' THEN l.device_id END) AS login_show,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_primary_click' THEN l.device_id END) AS login_click,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_login_modal_close' THEN l.device_id END) AS login_close,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_claim_success' THEN l.device_id END) AS claim,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_show' THEN l.device_id END) AS exhausted,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_primary_click' THEN l.device_id END) AS exh_pay,
      count(DISTINCT CASE WHEN g.event_name = 'login_ai_quota_gift_exhausted_modal_close' THEN l.device_id END) AS exh_close
    FROM labeled l
    LEFT JOIN gift g ON g.device_id = l.device_id
    GROUP BY 1
    ORDER BY 1
    """
    cols_b, rows_b = q(sql_act)
    for r in rows_b:
        print(r, flush=True)

    print("sample 20 j new-today claim devices...", flush=True)
    sql_s = f"""
    WITH c AS (
      SELECT device_id, min(created_ts) claim_ts
      FROM immdata.user_behaviour
      WHERE created_ts >= '{TS_START}' AND created_ts < '{TS_END}'
        AND is_new_user_today = '1'
        AND lower(trim(ab_tag)) = 'j'
        AND event_name = 'login_ai_quota_gift_claim_success'
      GROUP BY 1
    ),
    samp AS (
      SELECT device_id, claim_ts FROM (
        SELECT device_id, claim_ts, ROW_NUMBER() OVER (ORDER BY device_id) AS rn FROM c
      ) t WHERE rn <= 20
    )
    SELECT
      count(*) n,
      count_if(s.claim_ts IS NOT NULL) has_claim,
      sum(CASE WHEN l.device_id IS NOT NULL THEN 1 ELSE 0 END) had_login_show
    FROM samp s
    LEFT JOIN (
      SELECT DISTINCT device_id
      FROM immdata.user_behaviour
      WHERE created_ts >= '{TS_START}' AND created_ts < '{TS_END}'
        AND event_name = 'login_ai_quota_gift_login_modal_show'
        AND lower(trim(ab_tag)) = 'j'
    ) l ON l.device_id = s.device_id
    """
    cols_s, rows_s = q(sql_s)
    samp = dict(zip(cols_s, rows_s[0]))
    print("sample", samp, flush=True)
    ok = int(samp["n"]) == 20 and int(samp["has_claim"]) == 20
    print(f"【抽样复核】新用户领取样本20；结论={'通过' if ok else '不通过'}", flush=True)

    wb = Workbook()
    bold = Font(bold=True)
    ws = wb.active
    ws.title = "事件当日新用户"
    ws["A1"] = "T045 登录赠送 · 新用户漏斗（非正式 T018）"
    ws["A1"].font = bold
    ws["A2"] = (
        f"窗 created_ts>={TS_START} <{TS_END}；本页=事件 is_new_user_today=1；"
        "D_j=实验 D_i=对照；A/B/C 应接近 0"
    )
    ws["A4"] = "按组×事件"
    ws["A4"].font = bold
    for i, h in enumerate(["实验组", "事件", "次数", "UV"], 1):
        ws.cell(5, i, h).font = bold
    for ri, r in enumerate(rows_a, 6):
        for ci, v in enumerate(r, 1):
            ws.cell(ri, ci, v)

    ws2 = wb.create_sheet("j组新用户设备路径")
    ws2["A1"] = "j 组：当日新用户 gift 事件设备交叉"
    ws2["A1"].font = bold
    ws2["A2"] = "仅统计 is_new_user_today=1 的 gift 事件"
    ws2["A4"] = "指标"
    ws2["B4"] = "UV"
    ws2["A4"].font = bold
    ws2["B4"].font = bold
    labels = [
        ("有任一当日新 gift 事件", "devices"),
        ("登录弹窗 show", "login_show_uv"),
        ("立即登录 click", "login_click_uv"),
        ("登录弹窗 close", "login_close_uv"),
        ("领取 claim", "claim_uv"),
        ("领取且无 login_show（静默）", "claim_silent"),
        ("领取且有 login_click", "claim_after_click"),
        ("耗尽墙 show", "exhausted_uv"),
        ("耗尽且同设备有领取", "exhausted_with_claim"),
        ("耗尽去付费 click", "exh_pay_uv"),
        ("耗尽 close/降级", "exh_close_uv"),
    ]
    for i, (lab, key) in enumerate(labels, 5):
        ws2.cell(i, 1, lab)
        ws2.cell(i, 2, int(path[key] or 0))

    ws3 = wb.create_sheet("P034激活后gift")
    ws3["A1"] = "P034 激活（本窗首条 translate_page×is_new_user_today）上的 gift UV"
    ws3["A1"].font = bold
    ws3["A2"] = "激活日北京 09-21～09-29；gift 事件不要求当日新（激活后再领也计入）"
    headers = [
        "实验组", "激活UV", "login_show", "login_click", "login_close",
        "claim", "exhausted", "exh_pay", "exh_close",
    ]
    for i, h in enumerate(headers, 1):
        ws3.cell(4, i, h).font = bold
    for ri, r in enumerate(rows_b, 5):
        for ci, v in enumerate(r, 1):
            ws3.cell(ri, ci, v)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
