# -*- coding: utf-8 -*-
"""Evaluate selective userscript embed kick rules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

RULE_A = """
  CASE WHEN (
    (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
    OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
  ) THEN 1 ELSE 0 END
"""


def show(title: str, sql: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    cols, rows = query(sql)
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(x) for x in r))


def eval_rule(seg: str, window: str) -> None:
    show(
        f"Rule A embed kick {seg}",
        f"""
    WITH base AS (
      SELECT device_id, event_name, is_new_user_today, {RULE_A} AS kick
      FROM immdata.user_behaviour
      WHERE {window}
        AND LOWER(TRIM(install_from)) = 'official_userscript'
    ),
    dev AS (
      SELECT device_id, MAX(kick) kick,
        MAX(CASE WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' THEN 1 ELSE 0 END) ni,
        MAX(CASE WHEN event_name = 'translate_page' AND is_new_user_today = '1' THEN 1 ELSE 0 END) act
      FROM base GROUP BY 1
    )
    SELECT
      SUM(CASE WHEN kick = 1 AND ni = 1 THEN 1 ELSE 0 END) kick_ni,
      SUM(CASE WHEN kick = 1 AND act = 1 THEN 1 ELSE 0 END) kick_act,
      ROUND(SUM(CASE WHEN kick = 1 AND act = 1 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN kick = 1 AND ni = 1 THEN 1 ELSE 0 END), 0), 1) kick_rate,
      SUM(CASE WHEN kick = 0 AND ni = 1 THEN 1 ELSE 0 END) keep_ni,
      SUM(CASE WHEN kick = 0 AND act = 1 THEN 1 ELSE 0 END) keep_act,
      ROUND(SUM(CASE WHEN kick = 0 AND act = 1 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN kick = 0 AND ni = 1 THEN 1 ELSE 0 END), 0), 1) keep_rate,
      ROUND(SUM(CASE WHEN kick = 1 AND ni = 1 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN ni = 1 THEN 1 ELSE 0 END), 0), 1) kick_share_ni
    FROM dev
    """,
    )


if __name__ == "__main__":
    eval_rule("PRE 7/1-7/27", "created_ts >= '2026-07-01' AND created_ts < '2026-07-28'")
    eval_rule("POST 7/28-8/31", "created_ts >= '2026-07-28' AND created_ts < '2026-09-01'")

    show(
        "Rule C: kick browser embed (Safari/Maxthon/WinChrome), keep App UA",
        """
    WITH base AS (
      SELECT device_id, event_name, is_new_user_today,
        CASE WHEN created_ts < '2026-07-28' THEN 'pre' ELSE 'post' END seg,
        CASE
          WHEN TRIM(browser_name) LIKE 'Imt%' THEN 0
          WHEN TRIM(browser_name) IN ('Safari', 'Maxthon') THEN 1
          WHEN LOWER(TRIM(os_name)) = 'windows' AND TRIM(browser_name) = 'Chrome' THEN 1
          ELSE 0 END kick
      FROM immdata.user_behaviour
      WHERE created_ts >= '2026-07-01' AND created_ts < '2026-09-01'
        AND LOWER(TRIM(install_from)) = 'official_userscript'
    ),
    dev AS (
      SELECT device_id, seg, MAX(kick) kick,
        MAX(CASE WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' THEN 1 ELSE 0 END) ni,
        MAX(CASE WHEN event_name = 'translate_page' AND is_new_user_today = '1' THEN 1 ELSE 0 END) act
      FROM base GROUP BY 1, 2
    )
    SELECT seg,
      SUM(CASE WHEN kick = 1 AND ni = 1 THEN 1 ELSE 0 END) kick_ni,
      SUM(CASE WHEN kick = 1 AND act = 1 THEN 1 ELSE 0 END) kick_act,
      ROUND(SUM(CASE WHEN kick = 1 AND act = 1 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN kick = 1 AND ni = 1 THEN 1 ELSE 0 END), 0), 1) kick_rate,
      SUM(CASE WHEN kick = 0 AND ni = 1 THEN 1 ELSE 0 END) keep_ni,
      SUM(CASE WHEN kick = 0 AND act = 1 THEN 1 ELSE 0 END) keep_act,
      ROUND(SUM(CASE WHEN kick = 0 AND act = 1 THEN 1 ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN kick = 0 AND ni = 1 THEN 1 ELSE 0 END), 0), 1) keep_rate
    FROM dev GROUP BY 1 ORDER BY 1
    """,
    )

    show(
        "Aug ALL platform Rule A impact",
        f"""
    WITH flagged AS (
      SELECT device_id,
        MAX(CASE
          WHEN LOWER(TRIM(install_from)) = 'official_userscript'
           AND (
             (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
             OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
           ) THEN 1 ELSE 0 END) kick,
        MAX(CASE WHEN event_name = 'init_page_daily' AND is_new_user_today = '1' THEN 1 ELSE 0 END) ni,
        MAX(CASE WHEN event_name = 'translate_page' AND is_new_user_today = '1' THEN 1 ELSE 0 END) act
      FROM immdata.user_behaviour
      WHERE created_ts >= '2026-08-01' AND created_ts < '2026-09-01'
      GROUP BY 1
    )
    SELECT
      SUM(ni) all_ni, SUM(act) all_act,
      ROUND(SUM(act) * 100.0 / NULLIF(SUM(ni), 0), 2) all_rate,
      SUM(CASE WHEN kick = 1 THEN ni ELSE 0 END) kick_ni,
      SUM(CASE WHEN kick = 1 THEN act ELSE 0 END) kick_act,
      SUM(CASE WHEN kick = 0 THEN ni ELSE 0 END) remain_ni,
      SUM(CASE WHEN kick = 0 THEN act ELSE 0 END) remain_act,
      ROUND(SUM(CASE WHEN kick = 0 THEN act ELSE 0 END) * 100.0
        / NULLIF(SUM(CASE WHEN kick = 0 THEN ni ELSE 0 END), 0), 2) remain_rate
    FROM flagged
    """,
    )

    show(
        "PRE false positive detail Rule A",
        """
    SELECT TRIM(browser_name) browser, version,
      COUNT(DISTINCT device_id) ni
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-07-01' AND created_ts < '2026-07-28'
      AND event_name = 'init_page_daily' AND is_new_user_today = '1'
      AND LOWER(TRIM(install_from)) = 'official_userscript'
      AND (
        (LOWER(TRIM(os_name)) = 'ios' AND TRIM(browser_name) = 'Safari')
        OR (LOWER(TRIM(os_name)) = 'macos' AND TRIM(browser_name) = 'Maxthon')
      )
    GROUP BY 1, 2 ORDER BY ni DESC LIMIT 15
    """,
    )
