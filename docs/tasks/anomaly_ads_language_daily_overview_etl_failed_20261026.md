# 异常：ads_language_daily_overview 日更自 10-24 起连续失败（OSS 403）

- **需求编号**: T086
- **规范大类**: anomaly
- **状态**: ✅ 已完成（只读诊断；修复需写仓/运维）
- **日期**: 2026-10-26
- **现象**: 用户反馈「看板数据停在 6 月 23 号，自动任务是否出问题」
- **定稿 SQL**: 无（仅对话汇总 + 只读诊断）；复用 `sql/reports/anomaly_t032_fix_run_daily_etl_install_day_20260907.sql` 的修复思路不适用本因

## 结论（一句话）

数据库侧 **`ads_language_daily_overview` 没有停在 6 月 23**，而是**当前水位到 2026-10-23**；真正的问题是写仓自动任务 **`task_run_daily_etl` 在 10-24、10-25 连续 FAILED**，根因是 **OSS `AccessDenied`（HTTP 403 / bucket ACL）**，导致 10-24、10-25 两天的分语言总览缺失、看板「断更」于 10-23。与 T032（日期解析炸任务）**不是同一类故障**。

## 需求覆盖对照

| 需求项 | 落点 | 状态 |
|--------|------|------|
| 表最新 dt / 是否断更 | `MAX(dt)=2026-10-23`（非 6 月 23）；近 25 天按日连续，无内部空缺 | ✅ |
| 找出写入方与近期调度状态 | `task_run_daily_etl`（Started）；10-23 SUCCEEDED，10-24/10-25 FAILED | ✅ |
| 给出根因 | `OSS AccessDenied 403`，读 `query-storage-aqua.cn-beijing.oss.aliyuncs.com/...parquet` 被 bucket ACL 拒 | ✅ |
| 回应「是不是自动任务出问题」 | 是，当前确实在出错（连续 2 天）；但非 Suspended 的旧 `update_ads_language_daily_overview` | ✅ |
| 解释「6 月 23」 | DB 侧最新为 10-23；6 月 23 应为看板绑定了**不同/陈旧数据源**，或误述日期 | ⚠️ 需用户侧核对看板数据集绑定 |

## 证据链

### 1) 表状态（2026-10-26 查）
| 项 | 值 |
|----|-----|
| `MAX(dt)` | 2026-10-23 |
| `MIN(dt)` | 2026-03-04 |
| 总行数 | 31,591；271 个 `native_language`，各语言 2026-03-04→2026-10-23 连续 234 天无空缺 |
| 上游 `imm_entity_daily_funnel.MAX(dt)` | 2026-10-23（与 overview 一致，管道未整体卡死） |
| 用户原查询（zh-CN）输出 | 最新 2026-10-23，SUM(dau)=634,552；若看板直连本表应显示到 10-23，而非 6-23 |

### 2) 自动任务 `system.task_history`（近 7 次）
| scheduled_time (UTC) | state | 说明 |
|----------------------|-------|------|
| 2026-10-25 20:10 | **FAILED** (code 1) | OSS AccessDenied 403，`tmp_ub_d7` 段读 parquet 被拒 |
| 2026-10-24 20:10 | **FAILED** (code 1) | OSS AccessDenied 403，`tmp_ub_d1` 段读 parquet 被拒 |
| 2026-10-23 20:10 | SUCCEEDED | 产出 dt=10-23 |
| 2026-10-22 20:10 | SUCCEEDED | — |
| 2026-10-21 20:10 | SUCCEEDED | — |
| 2026-10-20 20:10 | SUCCEEDED | — |
| 2026-10-19 20:10 | SUCCEEDED | — |

失败原文（节选）：
```
OssError { code: "AccessDenied", message: "You have no right to access this object because of bucket acl.",
request_id: "6ADE66E3F23BAE3930C95C5A", host_id: "query-storage-aqua.cn-beijing.oss.aliyuncs.com" }
=> .../_b/h019e355b5f2175e0ab26e61c7e73ddbb_v2.parquet, range: 4399358-4410556
```

### 3) 对照组探针（只读账号，2026-10-26）
| 动作 | 结果 |
|------|------|
| 只读账号 `SELECT COUNT(*) FROM user_behaviour WHERE created_ts ∈ [2026-10-25 00:00, 00:10)` | **OK**，返回 161,020（说明本账号可正常读 `user_behaviour` 的主数据桶） |
| ETL 任务 `CREATE TEMP TABLE tmp_ub_d1 AS SELECT ... FROM user_behaviour` 落临时表块 | **403 AccessDenied**（URI 落在 `query-storage-aqua.cn-beijing.oss.aliyuncs.com/.../_b/*.parquet`） |

→ 只读账号能读 `user_behaviour` 但 ETL 在 `CREATE TEMP TABLE` 这步 403，说明：失败桶 `query-storage-aqua` 是 Databend 实例 `tneqaz1f8` 的**查询/临时表/落盘中间结果存储桶**（temp 表与 spill 都写这里），而非常规"主数据桶"。只读轻量查询不落临时表也不 spill，因此没碰 `query-storage-aqua`；ETL 的 7 句 `CREATE TEMP TABLE` 必须在这里落块 → 触发 ACL 拒绝。

### 3.5) `SHOW STAGES` 结果（2026-10-26，佐证"非用户级 stage 凭证"）
| stage | 类型 | bucket | 说明 |
|-------|------|--------|------|
| `log_1f93b76af0bd4b1d8e018667865fbc65` | External/OSS | `cloud-storage-aqua`（无显式凭证，`has_credentials=False`） | 查询历史日志桶，实例身份访问 |
| `rss_test_stage` | External/OSS | `nofeed`（ap-northeast-2，有显式 AK/SK） | 第三方桶 |
| `user_access_log_stage` | Internal | — | 内部 stage |

→ `query-storage-aqua` **未出现在任何用户 stage 中**，它属于实例内部存储层（与 `cloud-storage-aqua` 同属本实例 `tneqaz1f8` 的"aqua"存储体系），由实例存储身份（IAM/RAM 角色或实例级 AK/SK）访问，而非某个 `CREATE STAGE` 绑定的显式凭证。因此修复入口在**实例存储配置 / OSS 桶策略层**，不在 SQL 里的 stage 定义。

### 4) 任务登记（`system.tasks`，相关）
| 任务 | state | schedule（UTC） | 备注 |
|------|-------|----------------|------|
| `task_run_daily_etl` | **Started** | `CRON 0 10 20 * * *` ≈ BJ 次日 04:10 | 实际写入方（见 T032） |
| `update_ads_language_daily_overview` | Suspended | — | 同名旧任务，自 4 月挂起，**非**现行写入者，勿误判 |
| `update_imm_device_native_language` 等 | Started | — | 母语画像链，与本表上游同源 |

## 根因判断

- **不是数据质量问题**（不像 T032 的 `install_day='2026-30-08'` 非法日期）。
- **是基础设施权限问题**：ETL 的 `CREATE TEMP TABLE` 必须把临时表块落到实例的查询/中间存储桶 `query-storage-aqua.cn-beijing.oss.aliyuncs.com`（实例 `tneqaz1f8`），而该桶对所有读请求返回 `AccessDenied ... because of bucket acl`。连续 2 天同一类 403，提示该桶的访问权限/策略/凭证在 ~10-24 前后被变更或过期，而非偶发抖动。
- **影响范围待定（两种候选根因）**：
  - **候选 A（实例级桶策略/ACL 被改）**：`query-storage-aqua` 的 Bucket Policy / ACL 被收紧，导致实例存储身份整体无法读写该桶。若是这样，**所有需要落临时表或 spill 的较重查询都会失败**（不止 ETL）。修复在 Aliyun OSS 控制台或 Databend Cloud 实例存储设置。
  - **候选 B（ETL 任务执行角色的存储身份被收权）**：仅 `task_run_daily_etl` 的执行角色/连接失去了对 `query-storage-aqua` 的权限。修复在该任务 owner 角色的存储连接 / RAM 策略。
  - 两者修复目标资源一致 —— **`query-storage-aqua` 桶（实例 `tneqaz1f8`，前缀 `tneqaz1f8/`）**；区别只在"去 OSS 控制台还是去 Databend Cloud 实例存储设置"改。因本仓只读且无法访问上述控制台，需运维/有写仓权限者操作。
- 影响：`ads_language_daily_overview`、`ads_language_install_week_feature_funnel`（同由 `task_run_daily_etl` 经 `imm_entity_daily_funnel` 产出）等日更表自 10-24 起缺数。

## 建议动作（写仓/运维，本仓只读不能代跑）

### A. 修复 `query-storage-aqua` 的访问权限（根因，二选一入口）
- **入口 1 — Aliyun OSS 控制台（候选 A）**：桶 `query-storage-aqua`（cn-beijing）→ 权限管理 / **Bucket Policy** / ACL：
  - 确认授予 Databend 实例 `tneqaz1f8` 的存储身份（RAM 角色或 AK/SK）对 `query-storage-aqua` 及前缀 `tneqaz1f8/*` 的 `oss:GetObject`、`oss:PutObject`、`oss:ListObjects`、`oss:DeleteObject`、`oss:AbortMultipartUpload` 权限；错误原文明确是 "because of bucket acl"，优先核对 Bucket Policy 与桶 ACL 是否被改。
- **入口 2 — Databend Cloud 控制台（候选 A/B 都覆盖）**：实例 `tneqaz1f8` → Storage / 存储连接设置 → 找到"查询/临时/spill"存储（即 `query-storage-aqua` 对应的连接），确认其 RAM 角色 ARN 或 AK/SK 未被 detach / 过期，必要时重新绑定或轮换凭证。

### B. 验证修复
- 权限恢复后，确认该桶可正常读写（可让运维在实例内跑一条会落临时表的查询，或直接看下一步任务是否 SUCCEEDED）。

### B'. 绕过方案（SQL 侧 stopgap，若工单周期长可先行）
- **不可行**：TEMP→CTE（WITH）改写。源码 26 个 TEMP 表中 6 个多引用（`tmp_ub_d7`×4 / 2.99 亿行、`tmp_ub_d1`×3 / 3319 万行、`tmp_entity_map_d7`×3、`tmp_device_d1`×2、`tmp_feature_recent`×2）；Databend 普通 CTE 每次引用重算，且大聚合超内存会 spill 回 query-storage-aqua，同样 403。
- **可行**：TEMP 表 → 真表（`CREATE OR REPLACE TABLE immdata.etl_tmp_* / etl_stg_*`）。普通表块写主数据桶（10-24 后可读可写），语义与 TEMP 版完全等价（物化一次、多处引用）。改写版已留档 `sql/reports/anomaly_t086_bypass_run_daily_etl_scratch_tables_20261026.sql`（禁跑，写仓执行）；前提=过程 owner 有 immdata CREATE TABLE 权限；桶权限修复后回滚 TEMP 版并 DROP 26 张 etl_* 表。

### C. 补数
- 直接 `EXECUTE TASK task_run_daily_etl;`（日更任务会按窗口补算 10-24、10-25；其上游 `imm_entity_daily_funnel` 同为该任务产出，会一并补齐）。若只想补 overview/funnel 段，单独重跑对应 procedure 段即可。

### D. 看板侧核对
- 若看板仍显示「6 月 23」，说明它绑定的数据集并非本集群本表——检查 Superset 数据集指向的表/SQL/集群，刷新该数据集；本集群表已到 10-23（断更于 10-23，不是 6-23）。

### E. 加监控（防复发）
- 对 `system.task_history` 中 `state='FAILED'` 加告警（尤其 `exception_text` 含 `OSS`/`AccessDenied`/`403`），避免连续失败无人知。可参考 `sql/reports/` 下后续整理的巡检脚本。

## 桶归属判定：query-storage-aqua 为 Databend Cloud 平台代管（2026-10-26 补充定论）

多维证据（用户侧排查 + SQL 侧验证交叉印证）：

1. **用户阿里云账号桶列表实查**（OSS Browser 全量 5 页 + 网页控制台）：无 `query-storage-aqua`（同列表可见 `imt-databend`、`babel-*` 等业务桶）。
2. **DSN 无存储凭证**：连接串 `databend://cloudapp:<pw>@tneqaz1f8.gw...databend.cn:443/immdata` 仅含计算端点账号，**不含任何 OSS AK/SK/桶名**——用户接入实例时未配置过存储身份。
3. **`system.stages` 对照（决定性）**：
   - 平台自动建的 log stage 指向 `cloud-storage-aqua`：`has_credentials=False`，`access_key_id=""`、`role_arn=""`，creator 为平台内部账号 `'tneqaz1f8-cl-00002-history-log'@'0.0.0.0'` → **aqua 桶走实例自带的平台存储身份，无需用户提供凭证**；
   - 用户自建的 `rss_test_stage` 指向自己的桶 `nofeed`：`has_credentials=True`（带 AK）→ **用户桶的正确形态是带 AK 的 stage**。
   - 同理，失败桶 `query-storage-aqua` 与 `cloud-storage-aqua` 同属 `*-aqua` 平台托管体系，按实例 ID（`tneqaz1f8/`）组织目录。
4. **OSS 路径前缀 = 实例 ID**：报错对象 `tneqaz1f8/8689780/8704078/_b/*.parquet` 与 DSN 中实例 ID 一致，为平台按实例组织的托管目录。

**结论**：该桶归属 Databend Cloud 平台账号，用户侧（含其任一子账号）无修复入口，只能走 Databend Cloud 控制台/工单。

## 复核与结案（2026-10-29 14:3x）

- **主故障已修复、已补数**：`task_run_daily_etl` 10-27、10-28 两日 SUCCEEDED；`ads_language_daily_overview` 水位 `MAX(dt)=2026-10-28`，10-24~10-28 逐日全有数（10-24/25 DAU 57.6万/54.1万 为周六周日自然回落，10-26 周一回 76.7万，量级正常）；上游 `imm_entity_daily_funnel` 同步到 10-28。断档 10-24/25 已由 14 天回刷窗口覆盖补齐。
- 10-26 20:10 那次运行曾 FAILED（code 3002，SQL:37，与 OSS 403 不同，疑为修复期间的中间状态），随后连续两日成功且数据无缺口，不再深究。
- **遗留项（结案转新故障，本档不再展开）**：`user_access_log_task` 10-29 04:45 起再次连败（99 次+），报 `code 2604 Cannot connect to UDF Server https://databend-udf.immersivetranslate.com/ ... InvalidCertificate(NotValidForNameContext)`——是**自家 UDF 服务器的 TLS 证书与域名不匹配**（证书过期/换签未含该 SAN），与 OSS 桶无关，需内部运维换证。其影响面为 user_access_log 相关数据装载，另立任务跟踪。

## 勿混淆

- 看到 `update_ads_language_daily_overview = Suspended` 会误判「任务被挂所以没数」——实际写入者是 `task_run_daily_etl`，它 Started 但近期在报错（见 T032）。
- 把「副本时间落后」当「同步故障」——本次是明确 FAILED 且带 403 错误，非水位滞后。
