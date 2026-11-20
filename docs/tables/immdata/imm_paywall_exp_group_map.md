# `immdata.imm_paywall_exp_group_map`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_paywall_exp_group_map` |
| 类型 | BASE TABLE（写仓建表；实验上线前可空） |
| 表注释 | 付费墙实验：`ab_tag` → A/B/C/D |

## 来源与用途（手工维护）

- **写入**：写仓按实验配置 INSERT（示例见 ETL 文件末尾注释）
- **用途**：回填/日更 `imm_paywall_first_device.exp_group`
- **未填时**：`exp_group` 为空，dim 中记 `(unset)`；日常看板用 `ab_tag`
- **DDL**：`sql/reports/task6_paywall_daily_etl.sql`
- **勿用**：3 月实验的 `control`/`loose`/`strict`（`ads_ab_paywall_*`）当本轮分组

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `exp_group` | `varchar(16382)` | YES |  |  |
| 1 | `start_dt` | `date` | YES |  |  |
| 1 | `end_dt` | `date` | YES |  |  |
| 1 | `note` | `varchar(16382)` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->
