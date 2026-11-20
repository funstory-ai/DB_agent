# `immdata.imm_paywall_daily_wide_paywall_rate`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_paywall_daily_wide_paywall_rate` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 109614 |
| 创建时间 | 2026-08-20 04:47:58.037275 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：待补充
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：待补充（易误用字段、同名异义等）

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dt_bj` | `date` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `lang_bucket` | `varchar(16382)` | YES |  |  |
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `exp_group` | `varchar(16382)` | YES |  |  |
| 1 | `paywall_uv` | `bigint` | YES |  |  |
| 1 | `dau` | `bigint` | YES |  |  |
| 1 | `paywall_rate` | `double` | YES |  |  |
| 1 | `update_time` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_paywall_daily_wide_paywall_rate LIMIT 20;
```
