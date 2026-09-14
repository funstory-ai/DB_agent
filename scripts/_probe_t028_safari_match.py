# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

def daily(where_extra: str, title: str):
    sql = f"""
    SELECT
      to_date(created_ts) AS d,
      COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' THEN device_id END) AS ni,
      COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' THEN device_id END) AS act,
      COUNT(DISTINCT CASE WHEN event_name='translate_page' THEN device_id END) AS dau
    FROM immdata.user_behaviour
    WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
      {where_extra}
    GROUP BY 1 ORDER BY 1
    """
    cols, rows = query(sql)
    print(f"\n=== {title} ===", flush=True)
    for r in rows:
        d, ni, act, dau = r
        rate = act/ni*100 if ni else 0
        print(f"{d}\t{ni}\t{act}\t{dau}\t{rate:.2f}%", flush=True)

def daily_ex(where_extra: str, title: str):
    sql = f"""
    WITH base AS (
      SELECT to_date(created_ts) d, device_id, event_name, is_new_user_today,
        MAX(CASE WHEN LOWER(TRIM(install_from))='official_userscript' AND TRIM(browser_name)='Safari' THEN 1 ELSE 0 END)
          OVER (PARTITION BY device_id, to_date(created_ts)) embed
      FROM immdata.user_behaviour
      WHERE created_ts >= '2026-07-24' AND created_ts < '2026-08-04'
        {where_extra}
    )
    SELECT d,
      COUNT(DISTINCT CASE WHEN event_name='init_page_daily' AND is_new_user_today='1' AND embed=0 THEN device_id END),
      COUNT(DISTINCT CASE WHEN event_name='translate_page' AND is_new_user_today='1' AND embed=0 THEN device_id END),
      COUNT(DISTINCT CASE WHEN event_name='translate_page' AND embed=0 THEN device_id END)
    FROM base GROUP BY 1 ORDER BY 1
    """
    cols, rows = query(sql)
    print(f"\n=== {title} ===", flush=True)
    for r in rows:
        d, ni, act, dau = r
        rate = act/ni*100 if ni else 0
        print(f"{d}\t{ni}\t{act}\t{dau}\t{rate:.2f}%", flush=True)

if __name__ == '__main__':
    daily("AND TRIM(browser_name)='Safari'", "all_os Safari")
    daily("AND LOWER(TRIM(os_name))='ios' AND TRIM(browser_name)='Safari'", "ios Safari")
    daily_ex("AND TRIM(browser_name)='Safari'", "all_os Safari ex embed")
    daily("AND LOWER(TRIM(install_from))='safari'", "install_from=safari")
    # summary table all safari
    sql2 = """
    SELECT dates,
      SUM(IF(event_name='init_page_daily', new_device_count, 0)),
      SUM(IF(event_name='translate_page', new_device_count, 0)),
      SUM(IF(event_name='translate_page', device_count, 0))
    FROM immdata.imm_app_new_event_device_count_by_utf8_day
    WHERE dates>='2026-07-24' AND dates<'2026-08-04' AND TRIM(browser_name)='Safari'
    GROUP BY 1 ORDER BY 1
    """
    try:
        _, rows = query(sql2)
        print("\n=== summary Safari all os ===", flush=True)
        for r in rows:
            d, ni, act, dau = r
            print(f"{d}\t{ni}\t{act}\t{dau}\t{act/ni*100 if ni else 0:.2f}%", flush=True)
    except Exception as e:
        print('summary err', e)
