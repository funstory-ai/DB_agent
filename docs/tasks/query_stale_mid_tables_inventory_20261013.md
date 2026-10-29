# immdata 疑似废弃中间表 / 一次性表盘点

- **需求编号**: T066
- **规范大类**: query
- **状态**: ✅ 已验收结束（2026-10-13）
- **日期**: 2026-10-13
- **定稿 SQL**: 无（对话汇总 + 写仓清理清单；探查脚本已清零）

## 初始需求

看中间表/一次性表哪些不用（无自动 TASK、时间停很久等）；全盘；≥90 天；尽量附建表人；对话汇总。

## 口径

| 项 | 定义 |
|----|------|
| 范围 | `immdata` 全部 BASE TABLE |
| 停更辅证 | `system.tables.updated_on` 距今 ≥ **90** 天（**不可靠单独定案**：Fuse 上 REPLACE 常不刷新该字段） |
| 主判据 | 是否有 **Started** TASK 对表做 `INSERT/REPLACE/MERGE/DELETE/COPY INTO` |
| 属主 | `system.tables.owner`（角色：`account_admin`/`public`/`etl_owner`）；**不是**个人账号/邮箱 |
| 交付 | 对话汇总 |

## 关键结论

1. **属主**：库内只有角色级 `owner`，**拿不到具体建表人**。分布约 account_admin 97 / public 20 / etl_owner 1。别人建的表无法从元数据点名到人，清表前仍须写仓/同事确认。
2. **高置信可清（A）**：`tmp_*` / `t_*` / `temp*` / `test*` 且无 Started 写入 TASK → **21** 张（见对话）。
3. **疑似闲置中间表（B∩停更≥90d）**：无 Started 写入、也无 Started 只读引用，且 `updated_on`≥90d → 约 **22** 张（大表如 `imm_device_by_utf8_week_geo`、`dwd_behaviour*`、一次性 `beh_user_*` / `google_sem_*` / stripe 导出等）。**勿直接 DROP**：可能被外部管道/人工 SQL/看板直查。
4. **勿当废弃**：仍有 Started 写入的约 51 张；仅被读的静态维如 `exchangerates`；以及 B 里 `updated_on` 很新的业务源表（`imt_*`、`token_used_aw`、babel 等，靠库外同步）。
5. **Suspended TASK×10**：含 `update_imm_entity_*`、`update_ads_language_*`、`task_user_funnel_pipeline_daily` 等（last_commit 多在 2026-04）；部分对应表仍在日更 → 另有写入路径或 TASK 已换名。

## 需求覆盖对照

| 条目 | 落点 | 状态 |
|------|------|------|
| 对话汇总疑似不用表 | 本轮对话 | ✅ |
| ≥90 天 | 辅以 updated_on；主看无写入 TASK | ✅ |
| 全盘 | immdata 开查约 118 → 验收约 73 | ✅ |
| 建表人 | 仅有 owner 角色；已说明局限 | ✅（能力上限） |
| 可退役清理 + 验收 | A 僵尸 5 套已删；B 旧 TASK 大部已删 | ✅ |
| 清单外保留 | 见下「有意保留」 | ✅ 不做 |

## 抽样复核

写入型 TASK 解析后 A/B 不含活跃写入表；核心 `imt_userinfo` 因无 immdata TASK 进 B 但 `updated_on` 新鲜 → 对话中剔除出「可清」：**通过**。

## 复扫（用户清完一波后 · 2026-10-13）

- 表数 118→**98**；`tmp_/t_/temp/test` 几乎清空，仅留 **`tmp_model_price`**（对账价表，保留）
- 仍像杂表/一次性：`google_sem_2024_*`、`beh_user_202512_202603`、`stripe_*`、`dwd_homepage_ab260330`、`mrr_temp`
- 下一波可选：停更的 `ads_ab_paywall_*` / `dws_ab_*` / `dwd_behaviour*`（无写入 TASK；须写仓确认）

## 自动任务表：僵尸 / 已 Suspended（2026-10-13）

**注意**：`ads_language_*` / `imm_regional_*_lang` **仍在日更**，不是「被母语表替代」——母语表 `imm_device_native_language` 是维度源；分语言看板表是另一层。

| 优先级 | 对象 | 依据 |
|--------|------|------|
| 高 | Started 但业务日停更：`imm_event_daily_summary_by_geo`(max~03-07)、`imm_official_pv_click_*`(max~2025-11)、`imm_regional_conversion_geo`(max~2025-03；同族 `_lang` 仍活)、`imm_regional_income`(max~03-23)、`imm_new_user_cohort_dedup`(0 行) | TASK 空转 |
| 中 | 已 Suspended 旧调度：`update_ads_language_*`、`update_imm_entity_*`、`task_user_funnel_pipeline_daily`、`user_behaviour_task` | 已被 `task_run_daily_etl` / `user_behaviour_task_new` 取代；可 DROP TASK |
| 问 | `imt_device_regional_test`（名带 test，仍日更） | 是否试验残留 |

## 写仓清理清单（可退役 · 2026-10-13）

**顺序**：确认无看板/SQL 依赖 → `SUSPEND`/`DROP TASK` → 观察 1～2 天 → `DROP TABLE`。  
本仓只读，不代跑。

### A. 僵尸日更（Started TASK + 业务日停更）→ 停任务后可删表

| 表 | 行数 | 建立时间 | 元数据更新 | 业务日约停 | 关联 TASK |
|----|-----:|----------|------------|------------|-----------|
| `imm_event_daily_summary_by_geo` | 19,311 | 2026-01-28 | 2026-03-08 | **2026-03-07** | `imm_event_daily_summary_by_geo` |
| `imm_official_pv_click_by_utf8_day` | 3,836 | 2025-09-05 | 2025-11-14 | **2025-11-13** | `update_imm_official_pv_click_by_utf8_day` |
| `imm_regional_conversion_geo` | 14,376 | 2025-01-21 | 2025-03-03 | **2025-03-03** | `update_imm_regional_conversion_geo`（同族 `_lang` 仍活） |
| `imm_regional_income` | 19,366 | 2025-03-20 | 2026-03-23 | **2026-03-23** | `update_imm_regional_income_by_utf8_day` |
| `imm_new_user_cohort_dedup` | **0** | 2026-02-27 | 2026-02-27 | 空表 | `refresh_new_user_cohort_dedup` |

### B. 仅清旧 TASK（表仍可能被 `task_run_daily_etl` 写，勿删表）

| TASK（均为 Suspended） | 原写表 | 现行替代 |
|------------------------|--------|----------|
| `update_ads_language_daily_overview` | `ads_language_daily_overview` | `task_run_daily_etl` |
| `update_ads_language_install_week_feature_funnel` | `ads_language_install_week_feature_funnel` | 同上 |
| `update_imm_entity_current_profile` | `imm_entity_current_profile` | 同上 |
| `update_imm_entity_daily_feature_usage` | `imm_entity_daily_feature_usage` | 同上 |
| `update_imm_entity_daily_funnel` | `imm_entity_daily_funnel` | 同上 |
| `task_user_funnel_pipeline_daily` | 上面一串 | 同上 |
| `user_behaviour_task` | `user_behaviour` | `user_behaviour_task_new` |

### C. 无活跃写入 TASK 的残留（可直接评估 DROP）

| 表 | 行数 | 建立 | 更新 | 说明 |
|----|-----:|------|------|------|
| `mrr_temp` | 325,031 | 2026-09-01 | 2026-09-01 | 临时名 |
| `imm_host_type_sha_new` | 12,243 | 2025-07-03 | 2025-08-25 | 无任务、停更久（谨慎） |

（`ads_ab_paywall_*` / `dws_ab_*` / `dws_order_user_firsts` 用户侧已清掉）

### D. 先问再动

| 对象 | 原因 |
|------|------|
| `imt_device_regional_test` + `update_imt_device_regional_test` | 名带 test，仍日更、体量大 |

### 不要放进本清单

`imm_device_native_language`、`ads_language_*`（仍日更）、`imm_regional_*_lang`（仍日更）、`tmp_model_price`、`dwd_order_clean`（仍被 TASK 读）。

### 验收（用户清理后 · 2026-10-13）— **已结束**

- immdata 表约 **73**；TASK 约 **56**
- **A 全部通过**：5 张僵尸表 + 对应 TASK 均已删
- **B**：`update_ads_language_*` / `update_imm_entity_*` / `task_user_funnel_pipeline_daily` 已删；`user_behaviour_task` **有意保留**（Suspended）
- **C/D 有意保留**：`mrr_temp`、`imm_host_type_sha_new`、`imt_device_regional_test` + TASK（用户确认仍要用）
- **勿误伤：通过**

### 有意保留（验收确认 · 不再清）

| 对象 | 说明 |
|------|------|
| `user_behaviour_task` | Suspended，保留 |
| `mrr_temp` | 仍要用 |
| `imm_host_type_sha_new` | 仍要用 |
| `imt_device_regional_test` + `update_imt_device_regional_test` | 仍要用 |
