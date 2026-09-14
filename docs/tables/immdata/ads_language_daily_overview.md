# `immdata.ads_language_daily_overview`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.ads_language_daily_overview` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 21502 |
| 创建时间 | 2026-03-12 10:31:55.850015 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：日批 ETL；主路径 `task_run_daily_etl` → `CALL PROCEDURE run_daily_etl()`（聚合自 `imm_entity_daily_funnel` + 订单）。同名旧任务 `update_ads_language_daily_overview` / `task_user_funnel_pipeline_daily` 自 2026-04 起 **Suspended**，勿当现行调度。
- **同步方式**：日批 REPLACE（procedure 内重刷近窗）
- **更新频率**：每日；调度约 UTC 20:10（`CRON 0 10 20 * * * TIMEZONE UTC`），成功时 `update_time` 多在 UTC 20:55–21:05
- **业务含义**：按北京日 `dt` × `native_language` 的 DAU / 新装 / 激活 / 当日付费总览
- **建议粒度**：`dt` × `native_language`
- **主键 / 唯一键**：`(dt, native_language)`（REPLACE ON）
- **常用过滤**：`dt` 范围；排除空 `native_language`
- **关联建议**：明细漏斗看 `imm_entity_daily_funnel`；母语画像 `imm_entity_current_profile`
- **勿想当然**：缺日时先查 `task_run_daily_etl` 的 `system.task_history`，不要只看已 Suspended 的 `update_ads_language_daily_overview`（见 T032）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt` | `date` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `dau` | `bigint` | YES |  |  |
| 1 | `new_install` | `bigint` | YES |  |  |
| 1 | `new_activation` | `bigint` | YES |  |  |
| 1 | `activation_rate` | `double` | YES |  |  |
| 1 | `pay_today_user` | `bigint` | YES |  |  |
| 1 | `pay_today_order_cnt` | `bigint` | YES |  |  |
| 1 | `pay_today_amount` | `double` | YES |  |  |
| 1 | `pay_rate_by_install` | `double` | YES |  |  |
| 1 | `pay_rate_by_activation` | `double` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.ads_language_daily_overview LIMIT 20;
```
