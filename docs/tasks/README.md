# 任务留档（docs/tasks）

每次需求**开查即建档、交付通过后更新**，便于映证与验收。  
开查前先对大类：[`docs/norms/README.md`](../norms/README.md)。

> **命名与编号规范见下方「需求编号与命名（强制）」**——历史文件名保留不改；**新需求必须按新规登记**。

## 目录约定

| 路径 | 用途 |
|------|------|
| `docs/norms/` | 少数大类流程骨架 |
| `docs/tasks/<文件>.md` | 单次需求：口径、产物、规范大类、需求覆盖对照 |
| `docs/tasks/README.md` | **总索引**（本文件）：编号、状态、链接 |
| `sql/reports/` | 定稿 SQL（文件名与任务文档「定稿 SQL」一致） |
| `output/` | 仅当前有效业务交付（抽样不落文件） |

---

## 需求编号与命名（强制）

规范大类（`query` / `anomaly` / `dashboard` / `audit`）解决的是**怎么做**；  
**需求编号**解决的是**这一单叫什么、在哪登记**——二者都要有。

### 1. 需求编号

| 项 | 规则 |
|----|------|
| 格式 | `T###`（三位，从历史最大号 +1） |
| 分配时机 | **开查前**在本 README「进行中」登记一行后即占用 |
| 任务文档头部 | 必须写 `- **需求编号**: T0xx` |
| 历史 | 既有文档已补 `T###`，任务文档已统一重命名为 `{大类}_…_{日期}.md`；`sql/reports/` / `output/` 旧 `taskN_*` 产物名保留 |

### 2. 新文档文件名（自 T021 起）

```
{大类}_{短主题英文或拼音}_{YYYYMMDD}.md
```

示例：

- `query_paywall_activation_cohort_20260901.md`
- `dashboard_xxx_20260901.md`
- `anomaly_xxx_20260901.md`
- `audit_xxx_20260901.md`

禁止再使用无大类前缀的 `taskN_...` 作为任务文档文件名（历史产物 SQL/Excel 文件名可保留）。

### 3. 任务文档头部必填

```markdown
# 简短标题

- **需求编号**: T0xx
- **规范大类**: query|anomaly|dashboard|audit
- **状态**: 进行中 | ✅ 已完成 | ⏸ 搁置 | ❌ 取消
- **日期**: YYYY-MM-DD（开查；修订另注）
- **定稿 SQL**: `sql/reports/...`（无则写「无 / 仅对话汇总」）
```

正文须有 **需求覆盖对照** 表（见各大类 norms）。可从 [`_TEMPLATE.md`](_TEMPLATE.md) 复制。

### 4. SQL / 产物命名

- 定稿 SQL：`sql/reports/{与任务文件主题一致}_*.sql`（可带需求编号，如 `T021_xxx.sql`）
- 禁止长期堆 `*_patch` / `*_fix`（收尾并入后删除）

### 5. 本 README 维护

| 状态区 | 何时动 |
|--------|--------|
| **进行中** | 开查登记；交付或搁置后挪走 |
| **搁置** | 明确暂停、后续可能恢复 |
| **已完成** | 验收通过；按编号或日期可查 |

---

## 进行中

| 编号 | 大类 | 文档 | 说明 |
|------|------|------|------|
| T061 | query | [query_paywall_ab_ver_excl_old_hit_20261010.md](query_paywall_ab_ver_excl_old_hit_20261010.md) | 旧墙≥1.32.6+剔老号+触墙；**asof=10-10 已出** |
| T046 | query | [query_old_paywall_new_user_hit_rate_20260930.md](query_old_paywall_new_user_hit_rate_20260930.md) | 旧版硬墙·新用户7d触墙率；待验收 |
| T040 | query | [query_ja_paid_free_engine_rank_20260916.md](query_ja_paid_free_engine_rank_20260916.md) | 日语付费/免费用户翻译引擎用量排序 |
| T018 | query | [query_paywall_ab_20260821.md](query_paywall_ab_20260821.md) | 旧付费墙 AB；主周刷见 T061（含触墙 asof=10-10） |
| T028 | anomaly | [anomaly_new_install_surge_ios_20260901.md](anomaly_new_install_surge_ios_20260901.md) | 新装突增；init_page_daily×is_new_user_today；是否 iOS |
| T080 | dashboard | [dashboard_translate_model_latency_error_20261021.md](dashboard_translate_model_latency_error_20261021.md) | 各真实模型翻译时长+报错率看板（网页）；**中间表已落库并验收通过·待 Superset 挂板** |
| T079 | query | [query_sales_discount_20261021.md](query_sales_discount_20261021.md) | 2026 实付低于标价的销售活动 |
| T087 | query | [query_sales_discount_2025_20261026.md](query_sales_discount_2025_20261026.md) | 2025 打折销售活动清单（CNY，按 couponname 聚合） |
| T081 | query | [query_ucloud_model_detail_202607_20261022.md](query_ucloud_model_detail_202607_20261022.md) | UCloud 各模型明细（7月→现在）脱敏 Excel；**已出，待对外给供应商** |
| T091 | query | [query_mrr_growth_decisions_20261028.md](query_mrr_growth_decisions_20261028.md) | 全量证据梳理：MRR 增长方案与五个最紧迫决策 |
| T095 | dashboard | [dashboard_ingest_ledger_20261029.md](dashboard_ingest_ledger_20261029.md) | 新账本（计费 v2.4/路由 v1.1）入 immdata，供 UCloud request 级对账；**ETL 草案已出，阻塞于 B1–B4**（详见文档） |
## 搁置

| 编号 | 大类 | 文档 | 说明 |
|------|------|------|------|
| T077 | query | [query_gift_weekly_funnel_20261020.md](query_gift_weekly_funnel_20261020.md) | 新墙周漏斗剔老号；**10-23 已由 T084、10-26 已由 T085 同版刷新（asof 10-26 01:04）** |
| T085 | query | [query_gift_weekly_funnel_refresh_20261026.md](query_gift_weekly_funnel_refresh_20261026.md) | 新墙周漏斗剔老号 asof 10-26 01:04；**已刷新见 T090（asof 10-28 01:04，由 canonical `scripts/export_gift_weekly_funnel.py` 产出）** |
| T073 | query | [query_gpt_token_monthly_ucloud_20261015.md](query_gpt_token_monthly_ucloud_20261015.md) | GPT 含/不含 UCloud；**10-20 搁置·等 v2.4/路由 v1.1 上生产看 log** |
| T071 | query | [query_ucloud_token_cost_1m_20261015.md](query_ucloud_token_cost_1m_20261015.md) | UCloud 近 30 天估成本 $2,820；**10-20 与 T073 一起搁置** |
| T065 | query | [query_login_ai_quota_gift_50pct_from1010_20261012.md](query_login_ai_quota_gift_50pct_from1010_20261012.md) | 新墙50%（无墙/有墙）；**10-13 搁置·后续周更续跟** |
| T064 | query | [query_login_ai_quota_gift_ge1332_20261012.md](query_login_ai_quota_gift_ge1332_20261012.md) | 新墙旧版仅j·扩量前；**10-13 搁置·基线保留** |
| T060 | query | [query_login_ai_quota_gift_ge1332_20261009.md](query_login_ai_quota_gift_ge1332_20261009.md) | 新付费墙≥1.33.2 asof=10-09；**10-13 搁置（并入 T064/T065 续跟）** |
| T062 | query | [query_login_ai_quota_gift_exhausted_pay_20261010.md](query_login_ai_quota_gift_exhausted_pay_20261010.md) | 新墙去付费→付费+P042；**10-10 搁置续跟** |
| T063 | query | [query_school_campaign_convert_20261010.md](query_school_campaign_convert_20261010.md) | 校园两链；指纹→新装断链；**10-10 搁置** |
| T059 | audit | [audit_funstory_august2026_dig_20261008.md](audit_funstory_august2026_dig_20261008.md) | 8 月 dig；团队版补不了缺口；**10-12 搁置** |
| T017 | audit | [audit_ucloud_gpt54_june2026.md](audit_ucloud_gpt54_june2026.md) | 6 月 gpt-5.4 对账根因；形状命中时间亦对齐；优先级中等 |
| T042 | audit | [audit_funstory_august2026.md](audit_funstory_august2026.md) | UCloud 8 月；luna output 少记；细查见 T059⏸；**10-20 与 T073 等上线 log** |
| T041 | query | [query_colleague_thai_funnel_reconcile_20260921.md](query_colleague_thai_funnel_reconcile_20260921.md) | 同事泰语漏斗对照；**09-28 已验收**；漏斗不重做 |
| T044 | query | [query_meeting_translate_by_domain_20260928.md](query_meeting_translate_by_domain_20260928.md) | 会议翻译分 Zoom/Teams/Meet；**等前端补字段后恢复** |
| T018续 | query | [query_paywall_ab_dogpay_cluster_20260930.md](query_paywall_ab_dogpay_cluster_20260930.md) | 旧付费墙7d异动/DogPay簇；**09-30 暂挂** |
| T057 | query | [query_paywall_ab_ver_excl_old_hit_20260930.md](query_paywall_ab_ver_excl_old_hit_20260930.md) | 老墙限版本+剔老号+触墙；首版已出；**每周追踪暂挂** |

## 已完成（历史总表）

按 **需求编号** 排列。任务文档已统一为 `{大类}_{主题}_{YYYYMMDD}.md`；`sql/reports/` / `output/` 里历史 `taskN_*` 产物文件名保留（避免断脚本）。

| 编号 | 大类 | 状态 | 开查/修订 | 文档 | 一句话 |
|------|------|------|-----------|------|--------|
| T001 | query | ✅ | 08-14 | [query_trial_unpaid_30d_translate_20260814.md](query_trial_unpaid_30d_translate_20260814.md) | 近 30 天试用未付费 × 翻译 |
| T002 | query | ✅ | 08-14 | [query_churn30d_vs_trial_unpaid_20260814.md](query_churn30d_vs_trial_unpaid_20260814.md) | 近 30 天到期流失 vs 试用未付费 |
| T003 | query | ✅ | 08-14 | [query_platform_native_deviceinfo_userid_20260814.md](query_platform_native_deviceinfo_userid_20260814.md) | 平台/母语/deviceinfo/账号字段探查 |
| T004 | dashboard | ✅ | 08-14～27 | [dashboard_team_usage_superset_20260814.md](dashboard_team_usage_superset_20260814.md) | 团队用量 Superset；修双计与写死日期 |
| T005 | dashboard | ✅ | 08-14～17 | [dashboard_google_workspace_20260814.md](dashboard_google_workspace_20260814.md) | Workspace 按日看板（中间表+TASK） |
| T006 | dashboard | ✅ | 08-17～21 | [dashboard_paywall_roi_20260817.md](dashboard_paywall_roi_20260817.md) | 付费墙监测看板；定稿 3 SQL |
| T007 | query | ✅ | 08-14 | [query_trial14d_ex_int_arg1_match_20260814.md](query_trial14d_ex_int_arg1_match_20260814.md) | 近两周试用 × ex_int_arg1 匹配（旁支，非看板） |
| T008 | query | ✅ | 08-17 | [query_month_end_active_members_20260817.md](query_month_end_active_members_20260817.md) | 月末有效会员 Excel |
| T009 | dashboard | ✅ | 08-18 | [dashboard_mobile_os_name_unify_20260818.md](dashboard_mobile_os_name_unify_20260818.md) | 移动端 os_name 大小写统一 |
| T010 | audit | ✅ | 08-17 | [audit_datapack_202607.md](audit_datapack_202607.md) | 推文 datapack 202607 加工审核 |
| T011 | query | ✅ | 08-21 | [query_error_modal_primary_click_action_20260821.md](query_error_modal_primary_click_action_20260821.md) | error_modal 是否有 action 字段 |
| T012 | anomaly | ✅ | 08-24 | [anomaly_webapp_document_dau_aug2026.md](anomaly_webapp_document_dau_aug2026.md) | WebApp document DAU 口径迁移 |
| T013 | audit | ✅ | 08-24 | [audit_gcp_bill_202607.md](audit_gcp_bill_202607.md) | GCP 7 月账单 vs AW |
| T014 | anomaly | ✅ | 08-25 | [anomaly_team_gd_yinghui_token_20260824.md](anomaly_team_gd_yinghui_token_20260824.md) | 广东英辉异常 token + 看板翻倍 |
| T015 | query | ✅ | 08-25 | [query_deepseek_chenghuili_20260822_24.md](query_deepseek_chenghuili_20260822_24.md) | chenghuili DeepSeek 明细 |
| T016 | anomaly | ✅ | 08-25～26 | [anomaly_same_token_highfreq_202605_aug2026.md](anomaly_same_token_highfreq_202605_aug2026.md) | 同 token 高频 5～8 月 |
| T017 | audit | ⏸ | 08-27 | （见搁置）UCloud gpt-5.4 | |
| T018 | query | 进行中 | 08-21～09-29 | [query_paywall_ab_20260821.md](query_paywall_ab_20260821.md) | 付费墙 AB；分母=激活；asof=09-28 已验收 |
| T019 | audit | ✅ | 08-27 | [audit_funstory_july2026.md](audit_funstory_july2026.md) | Funstory 7 月 UCloud vs AW |
| T020 | query | ✅ | 08-27 | [query_free_translate_error_tracking_20260827.md](query_free_translate_error_tracking_20260827.md) | 免费翻译错误 vs track 埋点 |
| T021 | anomaly | ✅ | 08-31 | [anomaly_order_before_install_20260831.md](anomaly_order_before_install_20260831.md) | ≥30d前付费29人：非刷新；主因老号晚进设备表+现金早于账号 |
| T022 | anomaly | ✅ | 08-31 | [anomaly_new_user_cvr_renew_mix_20260831.md](anomaly_new_user_cvr_renew_mix_20260831.md) | iOS 付费皆 renew；首单付费口径下老客二次付费虚高≈0 |
| T023 | anomaly | ✅ | 08-31 | [anomaly_userinfo_createtime_check_20260831.md](anomaly_userinfo_createtime_check_20260831.md) | userinfo.createtime 可信；不能代替 install，可作账号新用户锚点 |
| T024 | query | ✅ | 08-31 | [query_new_install_user_filter_20260831.md](query_new_install_user_filter_20260831.md) | 账号级新装三过滤 → **P033**；T021 验证通过 |
| T025 | dashboard | ✅ | 08-31～09-03 | [dashboard_translate_weekly_retention_20260831.md](dashboard_translate_weekly_retention_20260831.md) | 分业务周留存+BabelDoc；口径见 translate_biz.md |
| T026 | query | ✅ | 09-01 | [query_active_member_vs_lang_gap_20260901.md](query_active_member_vs_lang_gap_20260901.md) | 有效会员总数 vs 按语言；扣电商后仍差 ~787 |
| T027 | audit | ✅ | 09-01 | [audit_datapack_retention_baseline_20260901.md](audit_datapack_retention_baseline_20260901.md) | datapack 留存/ARPU 改表；Max 占比归一；阶段完成 |
| T029 | query | ✅ | 09-03 | [query_translate_page_ruleA_active_retention_20260903.md](query_translate_page_ruleA_active_retention_20260903.md) | 月留/30d/MAU 剔 Rule A，对齐 T028 |
| T030 | query | ✅ | 09-03 | [query_install_activation_weekly_from_csv_20260903.md](query_install_activation_weekly_from_csv_20260903.md) | 日新装/激活 CSV 按周汇总 |

| T031 | query | ✅ | 09-07 | [query_monthly_report_202608.md](query_monthly_report_202608.md) | 2026-08 核心月报文稿 |
| T032 | anomaly | ✅ | 09-07 | [anomaly_ads_language_daily_overview_task_20260907.md](anomaly_ads_language_daily_overview_task_20260907.md) | overview 缺 09-06：daily_etl 因 install_day=2026-30-08 失败 |
| T033 | query | ✅ | 09-10 | [query_zh_hant_high_freq_user_20260910.md](query_zh_hant_high_freq_user_20260910.md) | 繁中高频三 cohort + 7 日月费到期 |
| T034 | query | ✅ | 09-10 | [query_zh_hant_gemma_events_20260910.md](query_zh_hant_gemma_events_20260910.md) | 近30d繁中 gemma TP：可识别为0；free-model≈49.8%对照 |
| T035 | query | ✅ | 09-10 | [query_thailand_user_profile_20260910.md](query_thailand_user_profile_20260910.md) | 近30d泰语设备5507；主功能web/video/划词；桌面Windows为主 |
| T036 | query | ✅ | 09-10 | [query_thailand_user_pay_member_20260910.md](query_thailand_user_pay_member_20260910.md) | 泰语账号6251；历史付费152；当前有效会员65 |
| T037 | query | ✅ | 09-14 | [query_usage_limit_hard_banner_20260914.md](query_usage_limit_hard_banner_20260914.md) | 新版硬墙：简中/非简中点击+现金/试用；三周对照升级率下降 |
| T038 | query | ✅ | 09-14～16 | [query_colleague_paywall_uv_reconcile_20260914.md](query_colleague_paywall_uv_reconcile_20260914.md) | 同事非简中~6k触墙 vs T037：口径差非算错 |
| T039 | audit | ✅ | 09-16 | [audit_gcp_bill_202608.md](audit_gcp_bill_202608.md) | GCP 8 月账单 vs AW；对齐 7/31 后残差~1% |
| T042 | audit | ⏸ | 09-24 | [audit_funstory_august2026.md](audit_funstory_august2026.md) | UCloud 8 月；整票对不上；luna output 少记暂挂细查 |

| T043 | query | ✅ | 09-24 | [query_max_users_lang_1y_20260924.md](query_max_users_lang_1y_20260924.md) | 近1年曾MAX 5261；语言+仍在籍/退订；**已验收** |
| T045 | query | ✅ | 09-29～30 | [query_login_ai_quota_gift_funnel_20260929.md](query_login_ai_quota_gift_funnel_20260929.md) | 登录赠送墙；双口径+仅1.33.3；**已验收**；P039默认 |
| T047 | query | ✅ | 09-30 | [query_paywall_ab_paid_flip_after_0907_20260930.md](query_paywall_ab_paid_flip_after_0907_20260930.md) | 9/7后A付费率翻转；非集成/老号，小样本+漏斗 |
| T048 | query | ✅ | 09-30 | [query_paywall_ab_ver_excl_old_20260930.md](query_paywall_ab_ver_excl_old_20260930.md) | AB限版本P040+剔老号重跑；修1.32.10误踢 |
| T049 | query | ✅ | 09-30 | [query_paywall_ab_week0921_a_high_20260930.md](query_paywall_ab_week0921_a_high_20260930.md) | 09/21A相对高=它组掉+噪声；A人数未升 |
| T050 | query | ✅ | 09-30 | [query_paywall_ab_bcd_drop_maturity_20260930.md](query_paywall_ab_bcd_drop_maturity_20260930.md) | BCD「大跌」不成立；B/D短窗升；仅C弱 |
| T051 | query | ✅ | 09-30 | [query_paywall_ab_b_missing_tag_skew_20260930.md](query_paywall_ab_b_missing_tag_skew_20260930.md) | B少18单=同臂噪声+1.33.1；哈希偏→非3:3:2:2 |
| T052 | query | ✅ | 09-30 | [query_paywall_ab_cd_drop_decomp_20260930.md](query_paywall_ab_cd_drop_decomp_20260930.md) | D费率未降；BCD量缩因1.33.1分流；C确弱 |
| T054 | query | ✅ | 09-30 | [query_paywall_ab_raw_口径_qa_20260930.md](query_paywall_ab_raw_口径_qa_20260930.md) | 7d异动：09/21截断口径；09/07非脏数据 |
| T055 | query | ✅ | 09-30 | [query_paywall_ab_dogpay_cluster_20260930.md](query_paywall_ab_dogpay_cluster_20260930.md) | 09/07付费暴增=DogPay/USDT/g53簇 |
| T056 | query | ✅ | 09-30 | [query_login_ai_quota_gift_ge1332_20260930.md](query_login_ai_quota_gift_ge1332_20260930.md) | 新付费墙≥1.33.2双口径；asof09-30 |
| T057 | query | ⏸ | 09-30 | [query_paywall_ab_ver_excl_old_hit_20260930.md](query_paywall_ab_ver_excl_old_hit_20260930.md) | 老墙限版本+剔老号+触墙；周刷暂挂 |
| T058 | query | ✅ | 10-08 | [query_monthly_report_202609.md](query_monthly_report_202609.md) | 2026-09 核心月报；**已验收** |
| T066 | query | ✅ | 10-13 | [query_stale_mid_tables_inventory_20261013.md](query_stale_mid_tables_inventory_20261013.md) | 疑似废弃表盘点+清理验收；僵尸5套已删；余项有意保留 |
| T067 | query | ✅ | 10-13 | [query_gift_token_model_daily_20261013.md](query_gift_token_model_daily_20261013.md) | 赠 token 误发全员；babelfast 11–12 日消耗约 4.4 倍 |
| T068 | query | ✅ | 10-13 | [query_pro_model_blended_token_price_20261013.md](query_pro_model_blended_token_price_20261013.md) | Pro 档模型近月混算百万 token 成本单价 ~$0.33；**已验收** |
| T069 | query | ✅ | 10-14 | [query_gift_old_user_misgrant_20261014.md](query_gift_old_user_misgrant_20261014.md) | 5 万 token 错发老用户；10 日起 44.3 万、AW 已消耗 33.3 亿；**已验收** |
| T070 | query | ✅ | 10-14 | [query_gift_narrow_login_exhaust_pay_20261014.md](query_gift_narrow_login_exhaust_pay_20261014.md) | 扩量后窄链；10/12–16 新墙累计付费 52；**已验收**；P018-E、P044 |
| T072 | anomaly | ✅ | 10-15 | [anomaly_order_sync_gap_20261014.md](anomaly_order_sync_gap_20261014.md) | 10-14 收入偏低（结构）当天订单齐；日更水位非故障；**已验收**；P043 |
| T074 | query | ✅ | 10-19 | [query_user_token_karehaizai_20261019.md](query_user_token_karehaizai_20261019.md) | karehaizai token；多笔网页请求，非单笔扣光、非同 token 高频；**已验收** |
| T075 | query | ✅ | 10-19 | [query_user_token_6665970_20261019.md](query_user_token_6665970_20261019.md) | userid 6665970 token 为 0；免费引擎 6 次翻译；**已验收** |
| T076 | query | ❌ 已清理 | 10-20 | （版式作废，文档/脚本/SQL 已于 10-29 清理；以 T077/T090 为准） | 版式不对（含未剔除）；以 T077 为准 |
| T077 | query | ⏸ | 10-20 | [query_gift_weekly_funnel_20261020.md](query_gift_weekly_funnel_20261020.md) | 新墙周漏斗剔老号；**10-20 已验收暂挂·下周同一版再刷** |
| T078 | anomaly | ✅ | 10-20 | [anomaly_lang_activation_two_sql_20261020.md](anomaly_lang_activation_two_sql_20261020.md) | 两套「分语言激活」不是同一批人；without_fb 漏掉只译当天的设备 |
| T084 | query | ✅ | 10-23 | [query_gift_weekly_funnel_refresh_20261023.md](query_gift_weekly_funnel_refresh_20261023.md) | 新付费墙周漏斗剔老号刷新到 asof 10-23 00:58（T077 同版再刷） |
| T085 | query | ✅ | 10-26 | [query_gift_weekly_funnel_refresh_20261026.md](query_gift_weekly_funnel_refresh_20261026.md) | 新付费墙周漏斗剔老号刷新到 asof 10-26 01:04（T077 同版再刷）；10/19–25 收口为完整周；**10-28 已由 T085 同版再刷** |
| T086 | anomaly | ✅ | 10-26 | [anomaly_ads_language_daily_overview_etl_failed_20261026.md](anomaly_ads_language_daily_overview_etl_failed_20261026.md) | overview 日更 10-24/25 连续 FAILED：OSS 403 bucket ACL；水位停在 10-23（非 6-23）；待写仓/运维修权限补数 |
| T090 | query | ✅ | 10-28 | [query_gift_weekly_funnel_refresh_20261028.md](query_gift_weekly_funnel_refresh_20261028.md) | 新付费墙周漏斗剔老号刷新到 asof 10-28 01:04（T085 同版再刷）；新增 10/26–11/01 部分激活 cohort；W1–W4 由数据推导自动收口（P045） |
| T088 | query | ✅ | 10-27 | [query_trial_conversion_30d_20261027.md](query_trial_conversion_30d_20261027.md) | 近一个月首次试用→累计付费转化率 12.41%（含未成熟 cohort 拆分，W0=16.9%） |
| T082 | query | ✅ | 10-23 | [query_total_paid_users_20261023.md](query_total_paid_users_20261023.md) | 累计总付费用户 153,644（含已流失；P013 付费 + P018-D 主体；P044 同源） |
| T083 | query | ✅ | 10-23 | [query_zhcn_share_20261023.md](query_zhcn_share_20261023.md) | 简中(zh-CN)占比：DAU 85.9% / 网页翻译量 87.5%（锚点 73W/500W 吻合） |
| T089 | query | ✅ | 10-28 | [query_promo_3cohorts_20261028.md](query_promo_3cohorts_20261028.md) | 促销三类：高频免费(前1%)/月费/年费到期(≤11-13)；已出 Excel，待验收 |
| T092 | query | ✅ | 10-28 | [query_max_trial_abuse_20261028.md](query_max_trial_abuse_20261028.md) | Max 试用薅羊毛：账号口径突发 118 人/纯羊毛 48 人；卡维度 157 张农场卡、4,574 次 Max 试用（近月 21.4%） |
| T093 | query | ✅ | 10-29 | [query_max_upgrade_20261029.md](query_max_upgrade_20261029.md) | Max 会员「存量升级补差价」取证→P047：升级占比下限 28.15%；Max 单 amountpaid 含 ¥1.15 级差价，非全价 |
| T094 | query | ✅ | 10-29 | [query_user_token_kjzkg84ctb_20261029.md](query_user_token_kjzkg84ctb_20261029.md) | 单用户月度 token 消耗（kjzkg84ctb@privaterelay.appleid.com / id=609408）：2026-01-27 起全月 0；长期 Pro 月付但极少使用 |

**下一可用编号：`T096`。**（T018 / T028 / T040 / T046 / T061 / T079 / T080 / T081 / T087 / T091 / T095 进行中；T017 / T041 / T042 / T044 / T018续 / T057 / T059 / T060 / T062 / T063 / T064 / T065 / T071 / T073 / T077 搁置）

### 按大类速查

| 大类 | 编号 |
|------|------|
| query | T001–T003, T007–T008, T011, T015, T018进行中, T020, T024, T026, T029, T030, T031, T033, T034, T035, T036, T037, T038, T040进行中, T041⏸, T043 ✅, T044⏸, T045 ✅, T046进行中, T047 ✅, T048 ✅, T049 ✅, T050 ✅, T051 ✅, T052 ✅, T054 ✅, T055 ✅, T056 ✅, T057⏸, T058 ✅, T060⏸, T061进行中, T062⏸, T063⏸, T064⏸, T065⏸, T066 ✅, T067 ✅, T068 ✅, T069 ✅, T070 ✅, T071⏸, T073⏸, T074 ✅, T075 ✅, T076 版式作废, T077⏸, T084 ✅, T087 进行中, T088 ✅, T090 ✅ |
| dashboard | T004–T006, T009, T025 ✅, T080进行中, T095进行中（不挂板，见文档偏差说明） |
| anomaly | T012, T014, T016, T021, T022, T023, T028, T032, T072, T086 ✅ |
| audit | T010, T013, T017⏸, T019, T027, T039, T042⏸, T059⏸ |

---

## 完成后必做

1. 更新本 README：从「进行中」移到「已完成」或「搁置」，核对状态列  
2. 任务文档：需求覆盖对照逐项 ✅；定稿 SQL 只列最终文件  
3. 过程 `*_patch` / `*_fix` 并入后删除；清零 `sql/adhoc/`、过期 `output/`、`_tmp_*.py`  
4. 库内临时表本仓不 DROP；分析不引用 `tmp_*`（P010）

## 互相映证

新任务开查前：扫本索引与 `sql/reports/` 是否已有相近口径；抽样/复核对照历史 SQL 过滤条件。
