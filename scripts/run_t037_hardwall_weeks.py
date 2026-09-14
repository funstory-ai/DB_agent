"""T037 weeks: run one period at a time to avoid OOM."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

PERIODS = [
    ("w1", "0824-0830", "week", "2026-08-23 16:00:00", "2026-08-30 16:00:00"),
    ("w2", "0831-0904", "week", "2026-08-30 16:00:00", "2026-09-04 16:00:00"),
    ("w3", "0906-0913", "week", "2026-09-05 16:00:00", "2026-09-13 16:00:00"),
    ("pre", "0824-0904_pre", "launch_cmp", "2026-08-23 16:00:00", "2026-09-04 16:00:00"),
]
# post = 同 w3，脚本末尾复制一行 period_id=post


def sql_for(period_id: str, label: str, kind: str, w0: str, w1: str) -> str:
    return f"""
WITH first_expo AS (
  SELECT device_id, MIN(created_ts) AS first_expo_ts
  FROM immdata.user_behaviour
  WHERE created_ts >= '{w0}' AND created_ts < '{w1}'
    AND event_name = 'user_need_pro' AND trigger = 'freeUsageLimitModal'
  GROUP BY device_id
),
lang AS (
  SELECT
    f.device_id,
    f.first_expo_ts,
    CASE
      WHEN MAX(CASE
        WHEN LOWER(TRIM(COALESCE(b.interface_language,''))) IN ('zh-cn','zh','zh-hans')
          OR LOWER(TRIM(COALESCE(b.interface_language,''))) LIKE 'zh-cn%'
          OR LOWER(TRIM(COALESCE(b.interface_language,''))) LIKE 'zh_cn%'
        THEN 1 ELSE 0 END) = 1
      THEN 'zh_cn' ELSE 'non_zh_cn'
    END AS lang_bucket,
    MAX(CASE WHEN b.ex_int_arg1 IS NOT NULL AND b.ex_int_arg1 > 0 THEN b.ex_int_arg1 END) AS expo_uid
  FROM first_expo f
  INNER JOIN immdata.user_behaviour b
    ON b.device_id = f.device_id
   AND b.created_ts = f.first_expo_ts
   AND b.created_ts >= '{w0}' AND b.created_ts < '{w1}'
   AND b.event_name = 'user_need_pro' AND b.trigger = 'freeUsageLimitModal'
  GROUP BY f.device_id, f.first_expo_ts
),
upg AS (
  SELECT device_id, MIN(created_ts) AS first_upg_ts,
    MIN(CASE WHEN ex_int_arg1 IS NOT NULL AND ex_int_arg1 > 0 THEN ex_int_arg1 END) AS click_uid
  FROM immdata.user_behaviour
  WHERE created_ts >= '{w0}' AND created_ts < '{w1}'
    AND event_name = 'usage_limit_upgrade_click'
  GROUP BY device_id
),
bas AS (
  SELECT DISTINCT device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= '{w0}' AND created_ts < '{w1}'
    AND event_name = 'usage_limit_basic_continue_click'
),
cls AS (
  SELECT DISTINCT device_id
  FROM immdata.user_behaviour
  WHERE created_ts >= '{w0}' AND created_ts < '{w1}'
    AND event_name = 'error_modal_close'
    AND ex_char_arg1 = 'translationUsageLimitHard'
    AND ex_char_arg2 = 'usage_limit_hard'
),
dev AS (
  SELECT d.deviceid, MIN(d.userid) AS userid
  FROM immdata.imt_deviceinfo d
  INNER JOIN first_expo f ON f.device_id = d.deviceid
  WHERE d.userid IS NOT NULL
  GROUP BY d.deviceid
),
base AS (
  SELECT
    l.device_id, l.first_expo_ts, l.lang_bucket,
    CASE WHEN u.device_id IS NOT NULL THEN 1 ELSE 0 END AS did_upg,
    CASE WHEN ba.device_id IS NOT NULL THEN 1 ELSE 0 END AS did_basic,
    CASE WHEN c.device_id IS NOT NULL THEN 1 ELSE 0 END AS did_close,
    u.first_upg_ts,
    COALESCE(u.click_uid, l.expo_uid, d.userid) AS userid
  FROM lang l
  LEFT JOIN upg u ON u.device_id = l.device_id
  LEFT JOIN bas ba ON ba.device_id = l.device_id
  LEFT JOIN cls c ON c.device_id = l.device_id
  LEFT JOIN dev d ON d.deviceid = l.device_id
),
paid AS (
  SELECT userid, MIN(createtime) AS first_cash_ts
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0 AND userid IS NOT NULL
    AND orderstatus = 'finished' AND COALESCE(amountpaid, 0) > 0
    AND createtime >= '{w0}' AND createtime < '{w1}'
  GROUP BY userid
),
trial AS (
  SELECT userid, MIN(createtime) AS first_trial_ts
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0 AND userid IS NOT NULL
    AND orderstatus = 'finished' AND COALESCE(amountpaid, 0) = 0
    AND COALESCE(CAST(subscriptiongoodssnap AS STRING), '')
        NOT LIKE '%"SubscriptionType":"onetime%'
    AND LOWER(COALESCE(ordertype, '')) <> 'code'
    AND createtime >= '{w0}' AND createtime < '{w1}'
  GROUP BY userid
),
labeled AS (
  SELECT
    b.*,
    CASE WHEN b.did_upg = 1 AND p.first_cash_ts IS NOT NULL AND p.first_cash_ts >= b.first_upg_ts THEN 1 ELSE 0 END AS cash_after_upg,
    CASE WHEN b.did_upg = 1 AND p.first_cash_ts IS NOT NULL AND p.first_cash_ts >= b.first_upg_ts
      AND p.first_cash_ts < DATEADD(day, 1, b.first_upg_ts) THEN 1 ELSE 0 END AS cash_1d_after_upg,
    CASE WHEN p.first_cash_ts IS NOT NULL AND p.first_cash_ts >= b.first_expo_ts THEN 1 ELSE 0 END AS cash_after_expo,
    CASE WHEN b.did_upg = 1 AND t.first_trial_ts IS NOT NULL AND t.first_trial_ts >= b.first_upg_ts THEN 1 ELSE 0 END AS trial_after_upg,
    CASE WHEN b.did_upg = 1 AND t.first_trial_ts IS NOT NULL AND t.first_trial_ts >= b.first_upg_ts
      AND t.first_trial_ts < DATEADD(day, 1, b.first_upg_ts) THEN 1 ELSE 0 END AS trial_1d_after_upg,
    CASE WHEN t.first_trial_ts IS NOT NULL AND t.first_trial_ts >= b.first_expo_ts THEN 1 ELSE 0 END AS trial_after_expo
  FROM base b
  LEFT JOIN paid p ON p.userid = b.userid
  LEFT JOIN trial t ON t.userid = b.userid
)
SELECT
  '{period_id}' AS period_id,
  '{label}' AS period_label,
  '{kind}' AS period_kind,
  lang_bucket,
  COUNT(*) AS expo_uv,
  SUM(did_upg) AS upgrade_uv,
  ROUND(100.0 * SUM(did_upg) / COUNT(*), 2) AS upgrade_pct,
  SUM(did_basic) AS basic_uv,
  ROUND(100.0 * SUM(did_basic) / COUNT(*), 2) AS basic_pct,
  SUM(did_close) AS close_uv,
  ROUND(100.0 * SUM(did_close) / COUNT(*), 2) AS close_pct,
  SUM(cash_after_upg) AS cash_after_upg_uv,
  ROUND(100.0 * SUM(cash_after_upg) / NULLIF(SUM(did_upg), 0), 2) AS cash_cvr_of_upgrade_pct,
  SUM(cash_1d_after_upg) AS cash_1d_after_upg_uv,
  ROUND(100.0 * SUM(cash_1d_after_upg) / NULLIF(SUM(did_upg), 0), 2) AS cash_1d_cvr_of_upgrade_pct,
  SUM(cash_after_expo) AS cash_after_expo_uv,
  ROUND(100.0 * SUM(cash_after_expo) / COUNT(*), 2) AS cash_cvr_of_expo_pct,
  SUM(trial_after_upg) AS trial_after_upg_uv,
  ROUND(100.0 * SUM(trial_after_upg) / NULLIF(SUM(did_upg), 0), 2) AS trial_cvr_of_upgrade_pct,
  SUM(trial_1d_after_upg) AS trial_1d_after_upg_uv,
  ROUND(100.0 * SUM(trial_1d_after_upg) / NULLIF(SUM(did_upg), 0), 2) AS trial_1d_cvr_of_upgrade_pct,
  SUM(trial_after_expo) AS trial_after_expo_uv,
  ROUND(100.0 * SUM(trial_after_expo) / COUNT(*), 2) AS trial_cvr_of_expo_pct
FROM labeled
GROUP BY lang_bucket
UNION ALL
SELECT
  '{period_id}', '{label}', '{kind}', 'ALL',
  COUNT(*),
  SUM(did_upg), ROUND(100.0 * SUM(did_upg) / COUNT(*), 2),
  SUM(did_basic), ROUND(100.0 * SUM(did_basic) / COUNT(*), 2),
  SUM(did_close), ROUND(100.0 * SUM(did_close) / COUNT(*), 2),
  SUM(cash_after_upg), ROUND(100.0 * SUM(cash_after_upg) / NULLIF(SUM(did_upg), 0), 2),
  SUM(cash_1d_after_upg), ROUND(100.0 * SUM(cash_1d_after_upg) / NULLIF(SUM(did_upg), 0), 2),
  SUM(cash_after_expo), ROUND(100.0 * SUM(cash_after_expo) / COUNT(*), 2),
  SUM(trial_after_upg), ROUND(100.0 * SUM(trial_after_upg) / NULLIF(SUM(did_upg), 0), 2),
  SUM(trial_1d_after_upg), ROUND(100.0 * SUM(trial_1d_after_upg) / NULLIF(SUM(did_upg), 0), 2),
  SUM(trial_after_expo), ROUND(100.0 * SUM(trial_after_expo) / COUNT(*), 2)
FROM labeled
"""


def main() -> None:
    header = None
    all_rows = []
    w3_rows = []
    for pid, label, kind, w0, w1 in PERIODS:
        print("running", pid, label, flush=True)
        cols, rows = query(sql_for(pid, label, kind, w0, w1))
        header = cols
        all_rows.extend(rows)
        if pid == "w3":
            w3_rows = rows
    # post 同 w3
    for r in w3_rows:
        row = list(r)
        row[0] = "post"
        row[1] = "0906-0913_post"
        row[2] = "launch_cmp"
        all_rows.append(tuple(row))
    assert header
    print("|".join(header))
    for r in all_rows:
        print("|".join("" if x is None else str(x) for x in r))


if __name__ == "__main__":
    main()
