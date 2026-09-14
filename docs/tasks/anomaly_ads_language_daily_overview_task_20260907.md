# 异常：ads_language_daily_overview 昨日未更新

- **需求编号**: T032
- **规范大类**: `anomaly`
- **状态**: ✅ 已完成（诊断 + 写仓修复 SQL）
- **日期**: 2026-09-07
- **现象**: 昨日（2026-09-06）数据未更新
- **定稿 SQL（写仓执行）**: [`sql/reports/anomaly_t032_fix_run_daily_etl_install_day_20260907.sql`](../../sql/reports/anomaly_t032_fix_run_daily_etl_install_day_20260907.sql)

## 需求覆盖对照

| 需求项 | 状态 |
|--------|------|
| 核对表最新 dt / update_time | ✅ max_dt=`2026-09-05`，max_update_time=`2026-09-05 20:59:10` |
| 检查 TASK 状态与调度 | ✅ |
| 给出根因与建议动作 | ✅ |
| 完整修改 SQL（改 procedure + 补数） | ✅ 见定稿 SQL；TASK 定义仍为 `CALL PROCEDURE run_daily_etl()`，无需改 schedule |
| 写仓跑完后验收 | ✅ 2026-09-10：overview/funnel `MAX(dt)=2026-09-09`；09-06 已在；ETL 09-07～09-09 连续 SUCCEEDED |

## 结论（一句话）

表的真实日更来自 **`task_run_daily_etl` → `CALL PROCEDURE run_daily_etl()`**，不是已 Suspended 的 `update_ads_language_daily_overview`。2026-09-06 该 ETL **FAILED**：`user_behaviour.install_day = '2026-30-08'`（非法月日）触发 `TO_DATE(..., '%Y-%m-%d')` **out of range**，整段 procedure 中断，overview / funnel 均未刷到 09-06。

## 证据链

### 1) 表状态

| 项 | 值 |
|----|-----|
| `MAX(dt)` | 2026-09-05 |
| `MAX(update_time)` | 2026-09-05 20:59:10 |
| 近两周 | 有 09-05，无 09-06 |
| 上游 `imm_entity_daily_funnel` | 同样卡在 max_dt=09-05、update≈09-05 20:56 |

### 2) 同名旧 TASK（易误判）

| TASK | state | schedule | last_suspended |
|------|-------|----------|----------------|
| `update_ads_language_daily_overview` | **Suspended** | UTC 21:40（BJ 05:40） | 2026-04-15 |
| `task_user_funnel_pipeline_daily` | **Suspended** | UTC 20:10 | 2026-04-17 |
| `update_imm_entity_daily_funnel` 等 | **Suspended** | — | 2026-04-15 |

自 4 月起上述任务无 `next_schedule_time`；**不是**昨日缺数的直接执行者。

### 3) 实际写入方

| TASK | state | schedule | definition |
|------|-------|----------|------------|
| `task_run_daily_etl` | **Started** | `CRON 0 10 20 * * * TIMEZONE UTC`（≈ BJ 次日 04:10） | `CALL PROCEDURE run_daily_etl()` |

`system.task_history`（近 7 天）：

| scheduled_time (UTC) | state | 说明 |
|----------------------|-------|------|
| 2026-09-01～05 20:10 | SUCCEEDED | 与 overview `update_time`≈20:55–21:00 对齐 |
| **2026-09-06 20:10** | **FAILED**（完成 20:53:33） | 见下 |

失败片段（procedure 内）：

```text
CREATE TEMP TABLE tmp_install_day_d1 AS
SELECT ub.device_id,
       MIN(TO_DATE(ub.install_day, '%Y-%m-%d')) AS install_day
...
AND TO_DATE(ub.install_day, '%Y-%m-%d') <= add_days(r.biz_today, 30)
→ code 1006: input is out of range while evaluating function `to_date`
```

### 4) 脏数据举例 + 占比

**直接炸任务的一行（ASCII 伪日期）：**

| 字段 | 值 |
|------|-----|
| `install_day` | `2026-30-08`（月=30，非法） |
| `device_id` | `3e4ca542cf90db4d2c292b37eda49ad32a0d9290c2489664d774d5f0a3648d4d` |
| `created_ts` | **2026-09-06 06:44:10**（故 09-05 ETL 仍成功，09-06 才踩中） |
| `event_name` | `init_page_daily` |
| 窗口内条数 | **1** |

**旁证（同窗大量脏 install_day，多数未单独炸 TO_DATE out-of-range）：**

- 窗口：`user_behaviour` `created_ts ∈ [2026-09-01, 2026-09-07)`
- 分母：约 **3.07 亿** 行
- `install_day` 无法 `TRY_CAST` 为 DATE（含阿拉伯数字日期、`undefined-Invalid-undefined` 等）：约 **89,183** ≈ **0.029%**
- 例：Eastern Arabic digits 伪 `YYYY-MM-DD`（hex 以 `d9a2…` 开头）；`undefined-Invalid-undefined`（≥2k 行）

## 【异常审查】ads_language_daily_overview 日更中断

- **涉及表/字段**：`immdata.ads_language_daily_overview`；上游 procedure 读 `user_behaviour.install_day`；链路经 `imm_entity_daily_funnel`
- **观察窗口**：表缺 2026-09-06；ETL 失败日 UTC 2026-09-06；behaviour 脏值窗 09-01～09-06
- **举例**：
  - 例1：`install_day='2026-30-08'` / device=`3e4ca542…a3648d4d` / `created_ts=2026-09-06 06:44:10` / 事件=`init_page_daily`
- **规模与占比**：
  - 致命非法 ASCII 日期：本窗 **1** 行（即可中断整 job）
  - 广义脏 install_day：89,183 / 3.07e8 ≈ **0.029%**
- **影响指标**：分语言日活/新装/激活/付费总览整表停更；funnel 同步卡住
- **建议动作**（写仓，本仓只读不能代跑）：
  1. procedure 内 `TO_DATE(install_day, '%Y-%m-%d')` 改为安全解析（`TRY_CAST` / 先 `REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'` 且 `TRY_CAST AS DATE` 非空）再聚合
  2. 修完后 `EXECUTE TASK task_run_daily_etl`（或只重跑 overview 段）补 09-06
  3. **不必**重启已 Suspended 的 `update_ads_language_daily_overview`（已被 `task_run_daily_etl` 取代；避免双写）
- **是否写入 pitfalls**：待你确认

## 勿混淆

看 `SHOW TASKS` 里 `update_ads_language_daily_overview = Suspended` 会误判「任务停了所以没数」——实际上日常成功时也是靠 `task_run_daily_etl`；昨日是 **ETL 失败**，不是 overview 专用 TASK 被挂起。
