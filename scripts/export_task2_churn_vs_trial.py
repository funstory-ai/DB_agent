"""Task2: 近30天到期流失会员(A) vs 试用未付费 — 同结构一人一行 Excel。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query
from openpyxl import Workbook
from openpyxl.styles import Font

OUT = Path(__file__).resolve().parents[1] / "output"
OUT.mkdir(exist_ok=True)

DETAIL_SQL = """
WITH trial_30d AS (
  SELECT userid,
         MIN(createtime) AS first_trial_ts_30d,
         MAX(createtime) AS last_trial_ts_30d,
         COUNT(*) AS trial_orders_30d
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND COALESCE(amountpaid, 0) = 0
    AND createtime >= DATEADD(day, -30, NOW())
    AND userid IS NOT NULL
    AND (
      subscriptiongoodssnap IS NULL
      OR CAST(subscriptiongoodssnap AS STRING) NOT LIKE '%\"SubscriptionType\":\"onetime%'
    )
  GROUP BY userid
),
paid_ever AS (
  -- 历史上有过现金付费 / onetime* / ordertype=code → 不算「试用未付费」（P024）
  SELECT DISTINCT userid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND (
      COALESCE(amountpaid, 0) > 0
      OR (
        COALESCE(subscriptionday, 0) > 0
        AND (
          CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
          OR LOWER(COALESCE(ordertype, '')) = 'code'
        )
      )
    )
),
trial_unpaid AS (
  SELECT t.*
  FROM trial_30d t
  LEFT JOIN paid_ever p ON t.userid = p.userid
  WHERE p.userid IS NULL
),
-- 会员时长覆盖：createtime + subscriptionday
-- 含：现金 / snap onetime* / ordertype=code（code 的 SubscriptionType 常为 monthly，不能只认 onetime）
-- 排除额度包 day=0；排除真试用(amountpaid=0 且非 onetime/code)
member_cover AS (
  SELECT
    userid,
    createtime,
    DATEADD(day, COALESCE(subscriptionday, 0), createtime) AS cover_end,
    CASE WHEN COALESCE(amountpaid, 0) > 0 THEN 1 ELSE 0 END AS is_cash_paid
  FROM immdata.imt_subscriptiongoodsorder
  WHERE COALESCE(isdeleted, 0) = 0
    AND orderstatus = 'finished'
    AND userid IS NOT NULL
    AND COALESCE(subscriptionday, 0) > 0
    AND (
      COALESCE(amountpaid, 0) > 0
      OR CAST(subscriptiongoodssnap AS STRING) LIKE '%"SubscriptionType":"onetime%'
      OR LOWER(COALESCE(ordertype, '')) = 'code'
    )
),
user_cover AS (
  SELECT
    userid,
    MAX(cover_end) AS last_cover_end,
    MAX(createtime) AS last_member_order_ts,
    SUM(is_cash_paid) AS paid_time_orders
  FROM member_cover
  GROUP BY userid
),
-- 口径 A：近30天内到期，且当前已无覆盖（含兑换码续期后不再算流失）
churn_30d AS (
  SELECT
    userid,
    last_cover_end,
    last_member_order_ts,
    paid_time_orders,
    DATEDIFF(day, last_cover_end, NOW()) AS days_unpaid_since_expiry
  FROM user_cover
  WHERE last_cover_end < NOW()
    AND last_cover_end >= DATEADD(day, -30, NOW())
),
cohort AS (
  SELECT
    '流失会员' AS cohort_label,
    c.userid,
    c.last_cover_end,
    c.last_member_order_ts,
    c.paid_time_orders,
    c.days_unpaid_since_expiry,
    CAST(NULL AS TIMESTAMP) AS first_trial_ts_30d,
    CAST(NULL AS TIMESTAMP) AS last_trial_ts_30d,
    CAST(NULL AS BIGINT) AS trial_orders_30d
  FROM churn_30d c
  UNION ALL
  SELECT
    '试用未付费' AS cohort_label,
    t.userid,
    CAST(NULL AS TIMESTAMP) AS last_cover_end,
    CAST(NULL AS TIMESTAMP) AS last_member_order_ts,
    CAST(NULL AS BIGINT) AS paid_time_orders,
    CAST(NULL AS INT) AS days_unpaid_since_expiry,
    t.first_trial_ts_30d,
    t.last_trial_ts_30d,
    t.trial_orders_30d
  FROM trial_unpaid t
),
device_user_cnt AS (
  SELECT deviceid, COUNT(DISTINCT userid) AS users_on_device
  FROM immdata.imt_deviceinfo
  WHERE COALESCE(isdeleted, 0) = 0
    AND userid IS NOT NULL
    AND deviceid IS NOT NULL
    AND deviceid <> ''
  GROUP BY deviceid
),
user_devices AS (
  SELECT DISTINCT c.userid, d.deviceid
  FROM cohort c
  INNER JOIN immdata.imt_deviceinfo d
    ON c.userid = d.userid
   AND COALESCE(d.isdeleted, 0) = 0
   AND d.deviceid IS NOT NULL
   AND d.deviceid <> ''
),
user_device_stats AS (
  SELECT
    ud.userid,
    COUNT(DISTINCT ud.deviceid) AS device_cnt,
    COUNT(DISTINCT CASE WHEN duc.users_on_device > 1 THEN ud.deviceid END) AS shared_device_cnt,
    MAX(duc.users_on_device) AS max_users_on_any_device,
    MAX(CASE WHEN ud.deviceid = 'LK8j8qPLDa3gUgujz9Yt7RtmltkXP0bD' THEN 1 ELSE 0 END) AS has_device_LK8
  FROM user_devices ud
  INNER JOIN device_user_cnt duc ON ud.deviceid = duc.deviceid
  GROUP BY ud.userid
),
devices AS (
  SELECT DISTINCT deviceid FROM user_devices
),
beh AS (
  SELECT
    b.device_id,
    SUM(CASE WHEN b.event_name = 'translate_page' AND b.page_type = 'html' THEN 1 ELSE 0 END) AS web_cnt,
    SUM(CASE WHEN b.event_name = 'translate_video_subtitle' THEN 1 ELSE 0 END) AS video_cnt,
    SUM(CASE WHEN b.event_name IN ('translate_image', 'translate_image_client') THEN 1 ELSE 0 END) AS image_cnt,
    SUM(CASE WHEN b.event_name = 'translate_manga' THEN 1 ELSE 0 END) AS manga_cnt,
    SUM(CASE WHEN b.event_name = 'translate_page' AND b.page_type IN ('pdfReader', 'pdfProReader') THEN 1 ELSE 0 END) AS pdf_cnt
  FROM immdata.user_behaviour b
  INNER JOIN devices d ON b.device_id = d.deviceid
  WHERE b.created_ts >= DATEADD(day, -30, NOW())
    AND b.created_ts < NOW()
    AND (
      (b.event_name = 'translate_page' AND b.page_type IN ('html', 'pdfReader', 'pdfProReader'))
      OR b.event_name IN (
        'translate_video_subtitle',
        'translate_image',
        'translate_image_client',
        'translate_manga'
      )
    )
  GROUP BY b.device_id
),
user_agg AS (
  SELECT
    ud.userid,
    SUM(COALESCE(beh.web_cnt, 0)) AS web_translate_cnt,
    SUM(COALESCE(beh.video_cnt, 0)) AS video_translate_cnt,
    SUM(COALESCE(beh.image_cnt, 0)) AS image_translate_cnt,
    SUM(COALESCE(beh.manga_cnt, 0)) AS manga_translate_cnt,
    SUM(COALESCE(beh.pdf_cnt, 0)) AS pdf_translate_cnt
  FROM user_devices ud
  LEFT JOIN beh ON ud.deviceid = beh.device_id
  GROUP BY ud.userid
),
user_native_lang AS (
  SELECT
    ud.userid,
    nl.native_language,
    SUM(COALESCE(nl.cnt, 0)) AS cnt_sum
  FROM user_devices ud
  INNER JOIN immdata.imm_device_native_language nl
    ON ud.deviceid = nl.device_id
  WHERE nl.native_language IS NOT NULL
    AND nl.native_language <> ''
  GROUP BY ud.userid, nl.native_language
),
user_native_top AS (
  SELECT userid, native_language, cnt_sum
  FROM (
    SELECT
      userid,
      native_language,
      cnt_sum,
      ROW_NUMBER() OVER (
        PARTITION BY userid
        ORDER BY cnt_sum DESC, native_language
      ) AS rn
    FROM user_native_lang
  ) t
  WHERE rn = 1
)
SELECT
  c.cohort_label,
  c.userid,
  u.email,
  nt.native_language AS account_native_language,
  COALESCE(nt.cnt_sum, 0) AS native_language_cnt_sum,
  c.last_cover_end,
  c.last_member_order_ts,
  c.paid_time_orders,
  c.days_unpaid_since_expiry,
  c.first_trial_ts_30d,
  c.last_trial_ts_30d,
  c.trial_orders_30d,
  COALESCE(ds.device_cnt, 0) AS device_cnt,
  COALESCE(ds.shared_device_cnt, 0) AS shared_device_cnt,
  COALESCE(ds.max_users_on_any_device, 0) AS max_users_on_any_device,
  COALESCE(ds.has_device_LK8, 0) AS has_device_LK8,
  CASE WHEN ds.userid IS NULL THEN 0 ELSE 1 END AS has_deviceinfo,
  COALESCE(ua.web_translate_cnt, 0) AS web_translate_cnt,
  COALESCE(ua.video_translate_cnt, 0) AS video_translate_cnt,
  COALESCE(ua.image_translate_cnt, 0) AS image_translate_cnt,
  COALESCE(ua.manga_translate_cnt, 0) AS manga_translate_cnt,
  COALESCE(ua.pdf_translate_cnt, 0) AS pdf_translate_cnt,
  COALESCE(ua.web_translate_cnt, 0)
    + COALESCE(ua.video_translate_cnt, 0)
    + COALESCE(ua.image_translate_cnt, 0)
    + COALESCE(ua.manga_translate_cnt, 0)
    + COALESCE(ua.pdf_translate_cnt, 0) AS translate_total_cnt
FROM cohort c
LEFT JOIN immdata.imt_userinfo u
  ON c.userid = u.id AND COALESCE(u.isdeleted, 0) = 0
LEFT JOIN user_native_top nt ON c.userid = nt.userid
LEFT JOIN user_device_stats ds ON c.userid = ds.userid
LEFT JOIN user_agg ua ON c.userid = ua.userid
ORDER BY c.cohort_label, translate_total_cnt DESC, c.userid
"""

# Fix onetime escape - use same as task1 export which uses \"% in regular string
# In the string above I over-escaped. Fix to match export_task1.

HEADER_CN = [
    "人群",
    "用户ID",
    "邮箱",
    "账号母语",
    "母语合计cnt",
    "末次会员覆盖结束时间",
    "末次会员订单时间",
    "历史包月/包年现金付费订单数",
    "到期后未付费天数",
    "近30天首次试用时间",
    "近30天末次试用时间",
    "近30天试用订单数",
    "关联设备数",
    "共享设备数",
    "单设备最大绑定账号数",
    "是否绑定异常设备LK8",
    "是否有deviceinfo",
    "网页翻译次数",
    "视频翻译次数",
    "图片翻译次数",
    "漫画翻译次数",
    "PDF翻译次数",
    "五类合计",
]


def main():
    print("Querying (churn A + trial unpaid)...", flush=True)
    cols, rows = query(DETAIL_SQL)
    print(f"rows={len(rows)}", flush=True)

    churn = [r for r in rows if r[0] == "流失会员"]
    trial = [r for r in rows if r[0] == "试用未付费"]
    churn_ids = {int(r[1]) for r in churn}
    trial_ids = {int(r[1]) for r in trial}
    overlap = churn_ids & trial_ids
    print(f"churn={len(churn)} trial={len(trial)} overlap={len(overlap)}", flush=True)
    if overlap:
        print("OVERLAP sample:", list(overlap)[:20], flush=True)

    wb = Workbook()
    note = wb.active
    note.title = "口径说明"
    for row in [
        ["项目", "说明"],
        ["流失会员(A)", "末次会员覆盖结束日 last_cover_end 落在近30天且 <NOW()；覆盖含现金、onetime*、ordertype=code（P024）"],
        ["覆盖结束日", "单笔=createtime+subscriptionday；用户取 MAX；含 amountpaid>0 或 SubscriptionType=onetime*；不含额度包 day=0；不含真试用"],
        ["到期后未付费天数", "DATEDIFF(day, last_cover_end, 拉表时刻 NOW())；仅流失人群"],
        ["历史包月/包年现金付费订单数", "member_cover 中 is_cash_paid 合计（amountpaid>0）；兑换码不计此列"],
        ["试用未付费", "近30天 finished+amountpaid=0，排除当笔 onetime*；且历史上无现金付费、无 onetime* 会员单（P024）"],
        ["重叠预期", "逻辑上不应重叠；导出错重叠须排查"],
        ["邮箱", "imt_userinfo.email"],
        ["账号母语", "P020：设备母语按语言 SUM(cnt) 取最大"],
        ["翻译次数", "近30天；用户下全部设备累加；五类同任务一"],
        ["样例纠错", "userid=211939：onetime_yearly 仍有效，旧口径误判流失，新口径已排除"],
    ]:
        note.append(row)
    for c in note[1]:
        c.font = Font(bold=True)

    def write_sheet(title: str, data: list):
        ws = wb.create_sheet(title)
        ws.append(HEADER_CN)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in data:
            ws.append(list(r))

    write_sheet("流失会员", churn)
    write_sheet("试用未付费", trial)

    out = OUT / "task2_churn30d_vs_trial_unpaid_translate.xlsx"
    wb.save(out)
    print(f"Wrote {out}", flush=True)
    # 硬验收：兑换码仍有效用户不得出现在流失
    bad = [r for r in churn if int(r[1]) in (211939, 90644)]
    print(f"check_211939_90644_in_churn={len(bad)} (expect 0)", flush=True)
    print("churn TOP5:", flush=True)
    for r in churn[:5]:
        print(r, flush=True)

    # 补「主要平台/所属平台」，避免重导后丢失
    from patch_add_primary_platform import patch_task_files

    print("patch primary platform...", flush=True)
    patch_task_files(task2=out, task1=None, days=30)


if __name__ == "__main__":
    main()
