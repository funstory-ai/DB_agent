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
| T018 | query | [query_paywall_ab_20260821.md](query_paywall_ab_20260821.md) | 付费墙 AB；**分母=激活**；09-14 本周已验收 |
| T028 | anomaly | [anomaly_new_install_surge_ios_20260901.md](anomaly_new_install_surge_ios_20260901.md) | 新装突增；init_page_daily×is_new_user_today；是否 iOS |

## 搁置

| 编号 | 大类 | 文档 | 说明 |
|------|------|------|------|
| T017 | audit | [audit_ucloud_gpt54_june2026.md](audit_ucloud_gpt54_june2026.md) | 6 月 gpt-5.4 对账根因；优先级中等 |

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
| T018 | query | 进行中 | 08-21～09-14 | [query_paywall_ab_20260821.md](query_paywall_ab_20260821.md) | 付费墙 AB；分母=激活；09-14 本周验收 |
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

**下一可用编号：`T038`。**（T018 / T028 进行中）

### 按大类速查

| 大类 | 编号 |
|------|------|
| query | T001–T003, T007–T008, T011, T015, T018进行中, T020, T024, T026, T029, T030, T031, T033, T034, T035, T036, T037 |
| dashboard | T004–T006, T009, T025 ✅ |
| anomaly | T012, T014, T016, T021, T022, T023, T028, T032 |
| audit | T010, T013, T017⏸, T019, T027 |

---

## 完成后必做

1. 更新本 README：从「进行中」移到「已完成」或「搁置」，核对状态列  
2. 任务文档：需求覆盖对照逐项 ✅；定稿 SQL 只列最终文件  
3. 过程 `*_patch` / `*_fix` 并入后删除；清零 `sql/adhoc/`、过期 `output/`、`_tmp_*.py`  
4. 库内临时表本仓不 DROP；分析不引用 `tmp_*`（P010）

## 互相映证

新任务开查前：扫本索引与 `sql/reports/` 是否已有相近口径；抽样/复核对照历史 SQL 过滤条件。
