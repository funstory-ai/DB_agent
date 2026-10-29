-- T045 登录赠送额度：新用户漏斗
-- 任务：docs/tasks/query_login_ai_quota_gift_funnel_20260929.md
-- 窗：created_ts >= '2026-09-21' AND created_ts < '2026-09-29 16:00:00'
-- 新用户：事件 is_new_user_today='1'（脚本另有 P034 激活叠加）
-- 导出：scripts/export_t045_gift_new_user_funnel.py

SELECT
  CASE
    WHEN lower(trim(ab_tag)) IN ('a', 'b', 'c') THEN 'A'
    WHEN lower(trim(ab_tag)) IN ('d', 'e', 'f') THEN 'B'
    WHEN lower(trim(ab_tag)) IN ('g', 'h') THEN 'C'
    WHEN lower(trim(ab_tag)) = 'i' THEN 'D_i'
    WHEN lower(trim(ab_tag)) = 'j' THEN 'D_j'
    ELSE 'other'
  END AS exp_group,
  event_name,
  count(*) AS n,
  count(DISTINCT device_id) AS uv
FROM immdata.user_behaviour
WHERE created_ts >= '2026-09-21'
  AND created_ts < '2026-09-29 16:00:00'
  AND is_new_user_today = '1'
  AND event_name IN (
    'login_ai_quota_gift_login_modal_show',
    'login_ai_quota_gift_login_modal_primary_click',
    'login_ai_quota_gift_login_modal_close',
    'login_ai_quota_gift_claim_success',
    'login_ai_quota_gift_received_modal_show',
    'login_ai_quota_gift_exhausted_modal_show',
    'login_ai_quota_gift_exhausted_modal_primary_click',
    'login_ai_quota_gift_exhausted_modal_close'
  )
GROUP BY 1, 2
ORDER BY 1, 2;
