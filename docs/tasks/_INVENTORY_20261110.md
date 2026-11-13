# 需求归档清单（自动生成 · 2026-11-10）

> 由 `docs/tasks/*.md` 头部解析生成，作为 README 索引的可信镜像。共 **105** 个需求文档（+1 系列主档 `series_core_monthly_report.md`）。

## 一、概览

| 大类 | 需求数 |
|------|------|
| query | 50 |
| anomaly | 5 |
| dashboard | 1 |
| 未分类 | 3 |

| 状态 | 需求数 |
|------|------|
| 进行中 | 9 |
| 其他 | 96 |

下一可用编号：**T108**（README 现写 T107，已过期）。

## 二、按大类 × 状态

### query · 进行中（4）

| 编号 | 日期 | 文档 | 状态原文 |
|------|------|------|------|
| T061 | 2026-10-10 | `query_paywall_ab_ver_excl_old_hit_20261010.md` | 进行中（asof=2026-10-10 已出数；抽样通过） |
| T079 | 2026-10-21 | `query_sales_discount_20261021.md` | 进行中 |
| T091 | 2026-10-28 | `query_mrr_growth_decisions_20261028.md` | 进行中 |

### query · 其他（46）

| 编号 | 日期 | 文档 | 状态原文 |
|------|------|------|------|
| T034 | 2026-09-10 | `query_zh_hant_gemma_events_20260910.md` | ✅ 已完成 |
| T035 | 2026-09-10 | `query_thailand_user_profile_20260910.md` | ✅ 已完成（用户验收 2026-09-14） |
| T036 | 2026-09-10 | `query_thailand_user_pay_member_20260910.md` | ✅ 已完成（用户验收 2026-09-14） |
| T037 | 2026-09-14 | `query_usage_limit_hard_banner_20260914.md` | ✅ 已完成（2026-09-14 验收） |
| T038 | 2026-09-14 | `query_colleague_paywall_uv_reconcile_20260914.md` | ✅ 已完成（2026-09-16 验收） |
| T041 | 2026-09-21 | `query_colleague_thai_funnel_reconcile_20260921.md` | ⏸ 搁置（漏斗本身不重做）；**2026-09-28 用户确认本对照需求已验收* |
| T047 | 2026-09-30 | `query_paywall_ab_paid_flip_after_0907_20260930.md` | ✅ 已完成 |
| T048 | 2026-09-30 | `query_paywall_ab_ver_excl_old_20260930.md` | ✅ 已完成 |
| T049 | 2026-09-30 | `query_paywall_ab_week0921_a_high_20260930.md` | ✅ 已完成 |
| T050 | 2026-09-30 | `query_paywall_ab_bcd_drop_maturity_20260930.md` | ✅ 已完成 |
| T051 | 2026-09-30 | `query_paywall_ab_b_missing_tag_skew_20260930.md` | ✅ 已完成 |
| T052 | 2026-09-30 | `query_paywall_ab_cd_drop_decomp_20260930.md` | ✅ 已完成 |
| T054 | 2026-09-30 | `query_paywall_ab_raw_口径_qa_20260930.md` | ✅ 已完成 |
| T055 | 2026-09-30 | `query_paywall_ab_dogpay_cluster_20260930.md` | ✅ 已完成 |
| T056 | 2026-09-30 | `query_login_ai_quota_gift_ge1332_20260930.md` | ✅ 已完成 |
| T057 | 2026-09-30 | `query_paywall_ab_ver_excl_old_hit_20260930.md` | ⏸ 搁置（首版 asof=09-28；**周刷已恢复 → T061 asof=1 |
| T060 | 2026-10-09 | `query_login_ai_quota_gift_ge1332_20261009.md` | ⏸ 搁置（10-13；续跟见 T064/T065） |
| T062 | 2026-10-10 | `query_login_ai_quota_gift_exhausted_pay_20261010.md` | ⏸ 搁置（asof=10-10 + P042 已出；**2026-10-10 暂 |
| T063 | 2026-10-10 | `query_school_campaign_convert_20261010.md` | ⏸ **搁置**（2026-10-10：指纹→新装断链，感觉链路有问题） |
| T064 | 2026-10-12 | `query_login_ai_quota_gift_ge1332_20261012.md` | ⏸ 搁置（10-13；扩量前基线保留；续跟见 T065） |
| T065 | 2026-10-12 | `query_login_ai_quota_gift_50pct_from1010_20261012.md` | ⏸ 搁置（10-13；后续周更续跟） |
| T066 | 2026-10-13 | `query_stale_mid_tables_inventory_20261013.md` | ✅ 已验收结束（2026-10-13） |
| T067 | 2026-10-13 | `query_gift_token_model_daily_20261013.md` | ✅ 已完成 |
| T068 | 2026-10-13 | `query_pro_model_blended_token_price_20261013.md` | ✅ 已完成（**用户验收 2026-10-13**） |
| T069 | 2026-10-14 | `query_gift_old_user_misgrant_20261014.md` | ✅ 已完成（2026-10-14 验收） |
| T070 | 2026-10-14 | `query_gift_narrow_login_exhaust_pay_20261014.md` | ✅ 已完成，2026-10-16 已验收 |
| T071 | 2026-10-15 | `query_ucloud_token_cost_1m_20261015.md` | ⏸ 搁置（2026-10-20：与 T073 / T042 供应商对账一起暂挂； |
| T073 | 2026-10-15 | `query_gpt_token_monthly_ucloud_20261015.md` | ⏸ 搁置（2026-10-20：与 T071 / T042 一起暂挂；等计费 v |
| T077 | 2026-10-20 | `query_gift_weekly_funnel_20261020.md` | ⏸ 搁置（2026-10-20 本周已验收；下周同一版再刷） |
| T081 | 2026-10-22 | `query_ucloud_model_detail_202607_20261022.md` | ✅ 已完成（2026-10-22） |
| T082 | 2026-10-23 | `query_total_paid_users_20261023.md` | ✅ 已完成 |
| T083 | 2026-10-23 | `query_zhcn_share_20261023.md` | ✅ 已完成 |
| T084 | 2026-10-23 | `query_gift_weekly_funnel_refresh_20261023.md` | ✅ 已完成（2026-10-23；基于 T077 周二版同一口径刷新） |
| T085 | 2026-10-26 | `query_gift_weekly_funnel_refresh_20261026.md` | ✅ 已完成（2026-10-26；基于 T077 周二版同一口径再次刷新） |
| T087 | 2026-10-26 | `query_sales_discount_2025_20261026.md` | ✅ 已完成 |
| T088 | 2026-10-27 | `query_trial_conversion_30d_20261027.md` | ✅ 已完成（已验收） |
| T090 | 2026-10-28 | `query_gift_weekly_funnel_refresh_20261028.md` | ✅ 已完成（2026-10-28；基于 T077 周二版、T085 脚本同一口径 |
| T092 | 2026-10-28 | `query_max_trial_abuse_20261028.md` | ✅ 已完成（账号维度 + 卡维度双口径均出数；卡维度 4,580 个 Max 试 |
| T094 | 2026-10-29 | `query_user_token_kjzkg84ctb_20261029.md` | ✅ 已完成 |
| T096 | 2026-10-30 | `query_user_token_yupimelody_20261030.md` | ✅ 已完成（2026-10-30 二次复核：额度归属 + 自动化嫌疑） |
| T097 | 2026-10-30 | `query_user_token_yupimelody_feature_20261030.md` | ✅ 已完成 |
| T099 | 2026-10-30 | `query_gift_weekly_funnel_refresh_20261030.md` | ✅ 已完成（2026-10-30；canonical 脚本 `--asof 20 |
| T100 | 2026-11-02 | `query_gift_weekly_funnel_refresh_20261102.md` | ✅ 已完成（2026-11-02；canonical 脚本 `--asof 20 |
| T104 | 2026-11-09 | `query_user_token_qq4776466_20261109.md` | ✅ 已完成 |
| T105 | 2026-11-09 | `query_ucloud_luna_monthly_ratio_loss_20261109.md` | ✅ 已完成（2026-11-09） |
| T106 | 2026-11-09 | `query_luna_ratio_by_provider_20261109.md` | ✅ 已完成（2026-11-09） |

### anomaly · 其他（5）

| 编号 | 日期 | 文档 | 状态原文 |
|------|------|------|------|
| T072 | 2026-10-15 | `anomaly_order_sync_gap_20261014.md` | ✅ 已完成（2026-10-15 验收） |
| T078 | 2026-10-20 | `anomaly_lang_activation_two_sql_20261020.md` | ✅ 已完成 |
| T086 | 2026-10-26 | `anomaly_ads_language_daily_overview_etl_failed_20261026.md` | ✅ 已完成（只读诊断；修复需写仓/运维） |
| T101 | 2026-11-03 | `anomaly_monthly_retention_install_day_drift_20261103.md` | ✅ 已定案（数据侧证伪"变少"；取数来源待用户提供当时 SQL） |
| T102 | 2026-11-03 | `anomaly_user_token_maxime_epub_20261103.md` | ✅ 已完成 · 已验收（2026-11-05；分析交付部分用户验收通过；外部复核 |

### dashboard · 进行中（1）

| 编号 | 日期 | 文档 | 状态原文 |
|------|------|------|------|
| T095 | 2026-10-29 | `dashboard_ingest_ledger_20261029.md` | 进行中（**P0：`imt_data_synch` _loader 因账本切版将 |

### 未分类 · 其他（3）

| 编号 | 日期 | 文档 | 状态原文 |
|------|------|------|------|
| T093 | 2026-10-29 | `query_max_upgrade_20261029.md` | ✅ |
| T107 | 2026-11-10 | `query_t107_sg_my_revenue.md` | ✅ 已交付 |
| T098 | 2026-10-30 | `query_user_token_yupimelody_behavior_20261030.md` | ✅ 已完成 |

## 三、索引 / 数据质量待修项

- **README 已完成总表**：经核对 T100–T106 实际已在表中，**唯一缺的是 T107**（已于 2026-11-10 补入），"下一可用编号"改为 T108。
- **T079 重复**：`query_sales_discount_2026.md` 与 `query_sales_discount_20261021.md` 逐字节相同，**已于 2026-11-10 删除裸名 `query_sales_discount_2026.md`**，保留 README 已链接的日期版。✅ 已解决
- **缺 `需求编号` 头部**：`query_max_upgrade_20261029.md`(=T093)、`query_t107_sg_my_revenue.md`(=T107)、`query_user_token_yupimelody_behavior_20261030.md`(=T098) 三份 **已于 2026-11-10 补 `需求编号` 头**。✅ 已解决
- **README「下一可用编号」**：已改为 T108。✅ 已解决
- **搁置/进行中混在总表**：README 把 T018/T028/T040/T046/T061/T079/T080/T081/T087/T091/T095 标进行中、十数项标搁置，但「已完成」总表与之有重叠/缺口，建议以本清单为准重排。
- **`paywall_ab_archive/` 子目录**存在但未在 README 体现，建议注明归属。

## 四、系列任务（跨月连续）

- `SERIES-MR` 核心月报：主档 `series_core_monthly_report.md`，每月一期（T031/T058/T103 已验收；自 202611 起须进库下钻）。
- 新付费墙赠送周漏斗：T077/T084/T085/T090/T099/T100 同版 `--asof` 刷新。
