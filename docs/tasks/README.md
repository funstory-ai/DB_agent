# 任务留档（docs/tasks）

每次需求**开查即建档、交付通过后更新**，便于映证与验收。  
开查前先对大类：[`docs/norms/README.md`](../norms/README.md)。

> **命名与编号规范见下方「需求编号与命名（强制）」**——历史文件名保留不改；**新需求必须按新规登记**。

## 目录约定

| 路径 | 用途 |
|------|------|
| `docs/norms/` | 少数大类流程骨架 |
| `docs/tasks/<文件>.md` | 单次需求：口径、产物、规范大类、需求覆盖对照 |
| `docs/tasks/series_*.md` | **系列主档**：跨月连续的 SOP / 期次台账 / 避坑清单（不替代单期任务文档） |
| `docs/tasks/README.md` | **总索引**（本文件）：编号、状态、链接 |
| `sql/reports/` | 定稿 SQL（文件名与任务文档「定稿 SQL」一致） |
| `output/` | 仅当前有效业务交付（抽样不落文件） |

---

## 系列任务（跨月连续）

| 系列 | 主档 | 频次 | 说明 |
|------|------|------|------|
| `SERIES-MR` 沉浸式翻译核心月报 | [series_core_monthly_report.md](series_core_monthly_report.md) | 每月一期 | T031(08) 已交付、T058(09) / T103(10) 已验收；**自 202611 起除正文外，必须进 `immdata` 高维下钻找痛点**（S2–S4）。开查当天再取 `T###` 并回填主档期次台账，不预先占号 |
| 新付费墙赠送周漏斗 | [query_gift_weekly_funnel_20261020.md](query_gift_weekly_funnel_20261020.md) | 每周刷新 | canonical `scripts/export_gift_weekly_funnel.py --asof`（交付须带 `WF_TASK=T###`）；T077/T084/T085/T090/T099/T100/T108 同版刷新 |

> 系列任务的规范、维度与避坑以**主档为准**，单期文档只记本期差异；两边流程不要各写一套。

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
| T096 | query | [query_user_token_yupimelody_20261030.md](query_user_token_yupimelody_20261030.md) | 单用户额度消耗分析（yupimelody24@gmail.com / id=6515557）：10/22-10/30；Pro+两次5M套餐，~9.9M token，重但非异常 |
| T097 | query | [query_user_token_yupimelody_feature_20261030.md](query_user_token_yupimelody_feature_20261030.md) | 同用户「功能」维度日消耗 + 前窗/后窗对比（镜像 T067）：10/20 起 Pro→流量包计费切换，日消耗形态与之前一致，非功能暴增 | |
| T098 | query | [query_user_token_yupimelody_behavior_20261030.md](query_user_token_yupimelody_behavior_20261030.md) | 同用户行为/自动化嫌疑：user_behaviour+token_used_aw 双证据；**无"同请求狂打"**，单台 iPhone/JP、请求全唯一、高频=网页拆段 |
## 搁置

| 编号 | 大类 | 文档 | 说明 |
|------|------|------|------|
| T077 | query | [query_gift_weekly_funnel_20261020.md](query_gift_weekly_funnel_20261020.md) | 新墙周漏斗剔老号；**10-23 已由 T084、10-26 已由 T085 同版刷新（asof 10-26 01:04）** |
| T085 | query | [query_gift_weekly_funnel_refresh_20261026.md](query_gift_weekly_funnel_refresh_20261026.md) | 新墙周漏斗剔老号 asof 10-26 01:04；**已刷新见 T090（asof 10-28）、T099（asof 10-30）、T100（asof 11-02）、T108（asof 11-11），均由 canonical `scripts/export_gift_weekly_funnel.py` 产出** |
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
| T090 | query | ✅ | 10-28 | [query_gift_weekly_funnel_refresh_20261028.md](query_gift_weekly_funnel_refresh_20261028.md) | 新付费墙周漏斗剔老号刷新到 asof 10-28 01:04（T085 同版再刷）；新增 10/26–11/01 部分激活 cohort；W1–W4 由数据推导自动收口（P045）；**10-30 已由 T099 同版刷新（asof 10-30 01:04）** |
| T088 | query | ✅ | 10-27 | [query_trial_conversion_30d_20261027.md](query_trial_conversion_30d_20261027.md) | 近一个月首次试用→累计付费转化率 12.41%（含未成熟 cohort 拆分，W0=16.9%） |
| T082 | query | ✅ | 10-23 | [query_total_paid_users_20261023.md](query_total_paid_users_20261023.md) | 累计总付费用户 153,644（含已流失；P013 付费 + P018-D 主体；P044 同源） |
| T083 | query | ✅ | 10-23 | [query_zhcn_share_20261023.md](query_zhcn_share_20261023.md) | 简中(zh-CN)占比：DAU 85.9% / 网页翻译量 87.5%（锚点 73W/500W 吻合） |
| T089 | query | ✅ | 10-28 | [query_promo_3cohorts_20261028.md](query_promo_3cohorts_20261028.md) | 促销三类：高频免费(前1%)/月费/年费到期(≤11-13)；已出 Excel，待验收 |
| T092 | query | ✅ | 10-28 | [query_max_trial_abuse_20261028.md](query_max_trial_abuse_20261028.md) | Max 试用薅羊毛：账号口径突发 118 人/纯羊毛 48 人；卡维度 157 张农场卡、4,574 次 Max 试用（近月 21.4%） |
| T093 | query | ✅ | 10-29 | [query_max_upgrade_20261029.md](query_max_upgrade_20261029.md) | Max 会员「存量升级补差价」取证→P047：升级占比下限 28.15%；Max 单 amountpaid 含 ¥1.15 级差价，非全价 |
| T094 | query | ✅ | 10-29 | [query_user_token_kjzkg84ctb_20261029.md](query_user_token_kjzkg84ctb_20261029.md) | 单用户月度 token 消耗（kjzkg84ctb@privaterelay.appleid.com / id=609408）：2026-01-27 起全月 0；长期 Pro 月付但极少使用 |
| T099 | query | ✅ | 10-30 | [query_gift_weekly_funnel_refresh_20261030.md](query_gift_weekly_funnel_refresh_20261030.md) | 新付费墙周漏斗剔老号刷新到 asof 10-30 01:04（canonical `--asof 2026-10-30`）；10/26–11/01 部分激活增至 43,622；本次无新增留存周（10/19–25 W1 等成熟度均在 11-01）；**11-02 已由 T100 同版刷新** |
| T100 | query | ✅ | 11-02 | [query_gift_weekly_funnel_refresh_20261102.md](query_gift_weekly_funnel_refresh_20261102.md) | 新付费墙周漏斗剔老号刷新到 asof 11-02 01:04（canonical `--asof 2026-11-02`）；**留存三线同时收口**：10/10–11 W3 23.5%、10/12–18 W2 26.7%、10/19–25 W1 34.8%；10/26–11/01 走完整周 n=69,719；**11-11 已由 T108 同版刷新** |
| T101 | anomaly | ✅ 已验收 | 11-04 | [anomaly_monthly_retention_install_day_drift_20261103.md](anomaly_monthly_retention_install_day_drift_20261103.md) | 月留存 9 月桶"变少"真因 = **两次用了不同 SQL**：10 月初 Rule A 版（1,010,718≈10/08 的 1,010,191），11 月初换成 `browser_name<>'Electron'`（真实 11/01 快照实测 930,694≈931,096），该过滤整台剔除 106,467 台 Electron 设备（占 9 月桶 10.3%）。两条曲线各自单调递增、差恒定 ~98k；**数据纯追加、从未变少**。此前"install_day 被 ETL 改小 / 表被重写"等推断全部收回 |
| T102 | anomaly | ✅ 已完成 | 11-03 | [anomaly_user_token_maxime_epub_20261103.md](anomaly_user_token_maxime_epub_20261103.md) | 单用户功能使用/EPUB 消费异常核查（maximefouquet33@gmail.com / id=7154600）：84.3% 花在 EPUB；单请求 input 段长大 ~11.8 倍=每页消耗上涨根源（回应工单 5 问）；无系统提示膨胀、无重复计费；订阅 AI 累计 ~99.6M 远超 Max 50M 名义额度，待计费复核 |
| T103 | query | ✅ **已验收** | 11-05 | [query_monthly_report_202610.md](query_monthly_report_202610.md) | 2026-10 核心月报（`SERIES-MR` 第 202610 期，**基线期**）；canonical `scripts/export_monthly_report.py --month`；10 月日活 683,878/828,329 业务侧提供；净收入同比 −9.7% 年内首次转负、自建 MRR −1.4% 首次回落；18/18 抽样对账通过。用户 11-05 验收并要求**系列化**：本月不补高维分析，**自 202611 起须进库下钻找痛点**，见 [系列主档](series_core_monthly_report.md) |
| T104 | query | ✅ 已完成 | 11-09 | [query_user_token_qq4776466_20261109.md](query_user_token_qq4776466_20261109.md) | 单用户额度消耗分析（4776466@qq.com / id=5993459）：用户自述用电子书；合法但极耗 token 的电子书分段翻译，撞破 Pro 20M/月硬上限并抽干 10M 流量包（剩 4.5K）；10 月 4,547 条固定 ~5.6K 小段 Qwen/GLM 请求；无同请求重发；行为表无 translate_page 事件（日志缺失待查） |
| T105 | query | ✅ 已完成 | 11-09 | [query_ucloud_luna_monthly_ratio_loss_20261109.md](query_ucloud_luna_monthly_ratio_loss_20261109.md) | luna 逐月输入输出比与账单多计损失：我方 out/in 8月 0.2022 / 9月 0.2383 / 10月 0.2530 / 11月 0.2813；**8 月账单 0.6087 = 我方 3.01 倍**（input 仅差 0.11%），27 天连续 2.14~4.15 倍，同月 terra/mini 正常 → 只 luna 被系统性放大；8 月多计 61.73亿 token = **$5,928.69**，星图 10/06~11/05 多计 $78.15，累计 **$6,006.83 ≈ ¥42,649**（9 月账单缺失未计入）；10 月起切 gpt-6-luna 后倍率降至 1.1~1.6，形态转为 128000 上限型幽灵行 |

| T106 | query | ✅ 已完成 | 11-09 | [query_luna_ratio_by_provider_20261109.md](query_luna_ratio_by_provider_20261109.md) | 澄清 T105 真实意图：**按供应商拆** luna 逐月量与输入输出比。luna out/in 8月 0.2025 / 9月 0.2274 / 10月 0.2723 / 11月 0.2900，**与全模型 LLM 基线 0.2059/0.2281/0.2717/0.2823 几乎重合**；8 月同一 gpt-5.6-luna 三家账本 UCloud 0.2022 / OneRouter 0.1967 / OpenRouter 0.2353，只有 **UCloud 账单 0.6087（基线 2.96 倍）** → luna 模型本身无 3 倍问题，是 UCloud 账单单侧计量。UCloud 占 luna 份额 93.4%→15.8%→35.2%→8.3%（切走后落 OneRouter/OpenAI）。⚠️ 我方账本不能证明其他供应商账单也正常（无其对账单） |
| T107 | query | ✅ 已交付 | 11-10 | [query_t107_sg_my_revenue.md](query_t107_sg_my_revenue.md) | 新加坡/马来西亚近 12 个月收入趋势（real_geo 主导国家；移动端归入 NO_GEO 之下界，非全量）；库内无现成地区收入分表，SG/MY 靠 IP 国家识别，币种覆盖 <0.2% 仅作交叉校验 |
| T108 | query | ✅ 已验收 | 11-11 | [query_gift_weekly_funnel_refresh_20261111.md](query_gift_weekly_funnel_refresh_20261111.md) | 新付费墙周漏斗剔老号刷新到 asof 11-11 01:02（canonical `--asof 2026-11-11` + `WF_TASK=T108`，wf 门禁 audited）；**跨 11-08 节点四条留存同时收口**：10/10–11 W4 20.4%、10/12–18 W3 22.8%、10/19–25 W2 26.4%、10/26–11/01 W1 34.3%；首批 cohort W1–W4 全序列完成（41.1→27.3→23.4→20.4）；新增 11/2–11/8、11/9–11/15 两桶。修复脚本漏 `import os` 门禁缺陷 |
| T109 | query | ✅ 已验收 | 11-11 | [query_user_token_70764498_20261111.md](query_user_token_70764498_20261111.md) | 单用户额度使用核查 70764498@qq.com（userid=5339075）10-06~11-06；wf 状态机 audited（补登记：此前 README 漏登记） |
| T110 | audit | ✅ 已验收 | 11-12 | [audit_funstory_ucloud_bill_sep_oct_2026.md](audit_funstory_ucloud_bill_sep_oct_2026.md) | Funstory UCloud 2026 年 9 / 10 月账单 vs AW 对账（9 月账单补齐）；wf 状态机 audited |
| T111 | query | ✅ 已验收 | 11-12 | [query_tab2_mobile_metrics_20261112.md](query_tab2_mobile_metrics_20261112.md) | **Tab2 浏览页移动端 7 指标 + 登录引导漏斗**（北京日 10-13~11-11，仅国际版 com）：日均 Tab2 4,132 人占国际版 App 36.88%、人均 2.21 次、会均 P50 3.29s/P90 17.39s、内容点击率 26.04%（tap 6.98%）、Tab2 D+7 2.76%、使用者 vs 未使用者 14d 付费率 5.79% vs 0.20%（组间不可比，见结构诊断）、登录引导漏斗 715→38→2（10 月）/ 389→21→1（11 月）；canonical `scripts/export_tab2_mobile_metrics.py --end --days`，交付须带 `WF_TASK=T111`；**实测 CTA 事件库内为 `tab2_login_cta_click`（文档写法 `tab2_login_card_cta_click` 库内 0 条）** |
| T112 | query | ✅ 已验收 | 11-12 | [query_sg_my_daily_revenue_yoy_20261112.md](query_sg_my_daily_revenue_yoy_20261112.md) | **SG/MY 按天收入**（沿用 T107 用户主导 real_geo 口径）：今年 10-25~11-12 + 去年同月日，北京自然日、多 sheet Excel；完整日 SG+MY ¥88,578.75 vs ¥88,519.42 **+0.1%**（SG −5.7% / MY +48.0%）；⚠️ **NO_GEO 移动端缺口 ¥5.34万→¥14.82万（+177.7%），占比 62.4%→37.4%，故持平不可外推为真实总量持平**；11-12 为当天不完整日已剔除；canonical `scripts/export_sg_my_daily_revenue_yoy.py --start --end`（须带 `WF_TASK=T112`），11/11 抽样 PASS（含 T107b 周版交叉 <1%、P046 影响面核查） |

| T113 | query | ✅ 已验收 | 11-13 | [query_tab2_retention_sanity_20261113.md](query_tab2_retention_sanity_20261113.md) | **T111 反直觉留存结论复核**（用户追问「用 Tab2 留存反而更低，确定吗」）：数字确定（8 条独立路径复现、全窗 23 cohort 无一天反转，非 SQL/主体映射/home_show 漏报/窄窗/版本/device_id 问题），但属 **Simpson 悖论** —— 用过组 72.2% 是 30 天首见新设备、未用组仅 16.1%，同年龄层 0d 内 3.06% vs 2.81% 几乎相同，双向结构标准化解释 72~93% 差距；设备内固定效应（15,382 台配对）差从 22.85pt 缩到 13.42pt、设备级配对差中位数 0.00pt。**Excel 数字不修订，T111 文档已回填正确读法**（不可解读为 Tab2 降低留存，P043） |

**下一可用编号：`T114`。**（T018 / T028 / T040 / T046 / T061 / T079 / T080 / T081 / T087 / T091 / T095 进行中；T017 / T041 / T042 / T044 / T018续 / T057 / T059 / T060 / T062 / T063 / T064 / T065 / T071 / T073 / T077 搁置）

### 按大类速查

| 大类 | 编号 |
|------|------|
| query | T001–T003, T007–T008, T011, T015, T018进行中, T020, T024, T026, T029, T030, T031, T033, T034, T035, T036, T037, T038, T040进行中, T041⏸, T043 ✅, T044⏸, T045 ✅, T046进行中, T047 ✅, T048 ✅, T049 ✅, T050 ✅, T051 ✅, T052 ✅, T054 ✅, T055 ✅, T056 ✅, T057⏸, T058 ✅, T060⏸, T061进行中, T062⏸, T063⏸, T064⏸, T065⏸, T066 ✅, T067 ✅, T068 ✅, T069 ✅, T070 ✅, T071⏸, T073⏸, T074 ✅, T075 ✅, T076 版式作废, T077⏸, T084 ✅, T087 进行中, T088 ✅, T090 ✅, T093 ✅, T094 ✅, T098 ✅, T099 ✅, T100 ✅, T103 ✅, T104 ✅, T105 ✅, T106 ✅, T107 ✅, T108 ✅, T109 ✅, T111 ✅, T112 ✅, T113 ✅ |
| dashboard | T004–T006, T009, T025 ✅, T080进行中, T095进行中（不挂板，见文档偏差说明） |
| anomaly | T012, T014, T016, T021, T022, T023, T028, T032, T072, T086 ✅ |
| audit | T010, T013, T017⏸, T019, T027, T039, T042⏸, T059⏸, T110 ✅ |

---

## 完成后必做

1. 更新本 README：从「进行中」移到「已完成」或「搁置」，核对状态列  
2. 任务文档：需求覆盖对照逐项 ✅；定稿 SQL 只列最终文件  
3. 过程 `*_patch` / `*_fix` 并入后删除；清零 `sql/adhoc/`、过期 `output/`、`_tmp_*.py`  
4. 库内临时表本仓不 DROP；分析不引用 `tmp_*`（P010）

## 互相映证

新任务开查前：扫本索引与 `sql/reports/` 是否已有相近口径；抽样/复核对照历史 SQL 过滤条件。
