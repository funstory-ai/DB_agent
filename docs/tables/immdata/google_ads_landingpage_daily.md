# `immdata.google_ads_landingpage_daily`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.google_ads_landingpage_daily` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 123456 |
| 创建时间 | 2026-11-17 02:18:47.412474 |
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
| 1 | `report_date` | `date` | YES |  |  |
| 1 | `customer_id` | `varchar(16382)` | YES |  |  |
| 1 | `campaign_id` | `varchar(16382)` | YES |  |  |
| 1 | `campaign_name` | `varchar(16382)` | YES |  |  |
| 1 | `expanded_final_url` | `varchar(16382)` | YES |  |  |
| 1 | `currency_code` | `varchar(16382)` | YES |  |  |
| 1 | `account_timezone` | `varchar(16382)` | YES |  |  |
| 1 | `clicks` | `bigint` | YES |  |  |
| 1 | `impressions` | `bigint` | YES |  |  |
| 1 | `cost_micros` | `bigint` | YES |  |  |
| 1 | `conversions` | `double` | YES |  |  |
| 1 | `conversions_value` | `double` | YES |  |  |
| 1 | `api_version` | `varchar(16382)` | YES |  |  |
| 1 | `gaql` | `varchar(16382)` | YES |  |  |
| 1 | `ingest_batch` | `varchar(16382)` | YES |  |  |
| 1 | `ingested_at` | `timestamp` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.google_ads_landingpage_daily LIMIT 20;
```
