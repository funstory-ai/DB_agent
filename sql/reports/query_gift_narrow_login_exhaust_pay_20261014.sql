-- T070 最窄漏斗（规格）
-- 实际跑数时按 6 小时切 created_ts，避免一次扫完整窗把计算卡住；过滤与下面一致。
-- 有墙组 f–j，版本 ≥1.33.2，北京 2026-10-10 00:00 至 2026-10-15 12:40。
-- 当场去付费 = 这张墙弹出后的去付费点击，只表示前往付费页。
-- 付费两列：1 小时内，以及同一去付费页点击之后到观察截止（不限 1 小时）。都是现金单。
-- 付费墙后付费：弹出付费墙之后到观察截止的现金单。不要求点去付费页，包含点了去付费页再付的人。
-- finished、amountpaid>0、不是 iospay_renew。兑换码和 0 元单不算。订单不早于点击。
-- 老付费墙（a–e）登录墙：未登录注册墙 user_need_pro 且 trigger=unregisteredUsageLimitModal。去登录=error_modal_primary_click，关闭=error_modal_close，都要 ex_char_arg1=translationUsageLimitHard 且 ex_char_arg2=not_login。窄漏斗顺序与新组相同，之后的付费墙仍是 freeUsageLimitModal。
-- 去付费 = 观察窗内的 usage_limit_upgrade_click（与新墙一样，不另加时间窗）。真买 = 该次点击之后 1 小时内现金单。
-- 放宽：只要 claim_success（登录墙或其他入口）→ 首次领取之后出付费墙 → 当场去付费 → 1 小时内真买。
-- 老号：登录点击 / 领取 / 去付费点击上的 userid，userinfo.createtime < 登录点击 −1 天则整台设备剔除（P039）。
-- 现金单：finished、amountpaid>0、不是 iospay_renew。兑换码单不计入这次「当场付费」。

WITH params AS (
  SELECT
    '2026-10-09 16:00:00' AS beh_start,
    '2026-10-15 04:40:00' AS obs_end
)
SELECT
  g.device_id,
  g.event_name,
  g.created_ts,
  TRY_CAST(g.ex_int_arg1 AS BIGINT) AS uid,
  g.is_new_user_today
FROM immdata.user_behaviour g
CROSS JOIN params p
WHERE g.created_ts >= p.beh_start
  AND g.created_ts < p.obs_end
  AND g.event_name IN (
    'login_ai_quota_gift_login_modal_primary_click',
    'login_ai_quota_gift_claim_success',
    'login_ai_quota_gift_exhausted_modal_show',
    'login_ai_quota_gift_exhausted_modal_primary_click'
  )
  AND g.ab_tag IS NOT NULL
  AND length(trim(g.ab_tag)) = 1
  AND lower(trim(g.ab_tag)) BETWEEN 'f' AND 'j'
  AND (
    TRY_CAST(split_part(g.version, '.', 1) AS INT) > 1
    OR (
      TRY_CAST(split_part(g.version, '.', 1) AS INT) = 1
      AND (
        TRY_CAST(split_part(g.version, '.', 2) AS INT) > 33
        OR (
          TRY_CAST(split_part(g.version, '.', 2) AS INT) = 33
          AND TRY_CAST(split_part(g.version, '.', 3) AS INT) >= 2
        )
      )
    )
  )
