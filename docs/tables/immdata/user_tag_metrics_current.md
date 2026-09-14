# `immdata.user_tag_metrics_current`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_tag_metrics_current` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 5789790 |
| 创建时间 | 2026-04-08 12:59:15.497637 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：用户标签/活跃指标当前快照
- **同步方式**：ETL 快照（`ds` 为快照日）
- **业务含义**：近 7 日活跃天数、翻译次数等当前标签
- **建议粒度**：`userid` + `ds`
- **常用过滤**：先确认最新 `ds`
- **关联建议**：`userid` → 用户
- **勿想当然**：不是全历史；用前查 `MAX(ds)`

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `ds` | `date` | YES |  |  |
| 1 | `userid` | `bigint` | YES |  |  |
| 1 | `active_days_7d` | `bigint` | YES |  |  |
| 1 | `translate_cnt_7d` | `bigint` | YES |  |  |
| 1 | `active_week_streak` | `bigint` | YES |  |  |
| 1 | `has_desktop_30d` | `int` | YES |  |  |
| 1 | `has_mobile_30d` | `int` | YES |  |  |
| 1 | `desktop_browser_cnt_30d` | `bigint` | YES |  |  |
| 1 | `multi_device_bucket` | `varchar(16382)` | YES |  |  |
| 1 | `is_mac_30d` | `int` | YES |  |  |
| 1 | `native_language` | `varchar(16382)` | YES |  |  |
| 1 | `top_target_language_30d` | `varchar(16382)` | YES |  |  |
| 1 | `lang_utc_offset_hour` | `double` | YES |  |  |
| 1 | `local_work_hour_translate_cnt_30d` | `bigint` | YES |  |  |
| 1 | `total_translate_cnt_30d` | `bigint` | YES |  |  |
| 1 | `local_work_hour_ratio_30d` | `double` | YES |  |  |
| 1 | `avg_translated_source_char_count_30d` | `float` | YES |  | 近30天单次平均翻译字符数 |
| 1 | `total_translated_source_char_count_30d` | `bigint` | NO | 0 | 近30天总翻译字符数 |
| 1 | `long_text_char_ratio_30d` | `float` | YES |  | 近30天长文（>4800字符）翻译占比 |
| 1 | `avg_translated_paragraph_count_30d` | `float` | YES |  | 近30天单次平均翻译段落数 |
| 1 | `avg_translate_stay_duration_seconds_30d` | `float` | YES |  | 近30天单次平均停留秒数 |
| 1 | `complex_content_ratio_30d` | `float` | YES |  | 近30天复杂内容（非网页翻译）占比 |
| 1 | `research_domain_translate_cnt_30d` | `int` | NO | 0 | 近30天研究域名翻译次数 |
| 1 | `dev_domain_translate_cnt_30d` | `int` | NO | 0 | 近30天开发域名翻译次数 |
| 1 | `collab_domain_translate_cnt_30d` | `int` | NO | 0 | 近30天协作域名翻译次数 |
| 1 | `commerce_domain_translate_cnt_30d` | `int` | NO | 0 | 近30天商业域名翻译次数 |
| 1 | `finance_domain_translate_cnt_30d` | `int` | NO | 0 | 近30天财经域名翻译次数 |
| 1 | `high_value_domain_tag_type_cnt_30d` | `tinyint` | NO | 0 | 近30天命中高价值域名类型数（0-5） |
| 1 | `has_domain_tag_signal_30d` | `tinyint` | NO | 0 | 近30天是否有域名信号（1=有，0=无） |
| 1 | `domain_tag_report_ratio_30d` | `float` | YES |  | 近30天域名标签上报率 |
| 1 | `pricing_page_visit_cnt_30d` | `int` | NO | 0 | 近30天定价页访问次数 |
| 1 | `limit_hit_cnt_30d` | `int` | NO | 0 | 近30天限额命中次数 |
| 1 | `has_translate_after_limit_30d` | `tinyint` | NO | 0 | 近30天是否有限额命中后回访（1=是） |
| 1 | `paid_order_cnt_30d` | `int` | NO | 0 | 近30天真实付费订单数 |
| 1 | `max_commercial_intent_depth_30d` | `tinyint` | NO | 0 | 近30天最大付费意愿漏斗深度（0-3） |
| 1 | `export_cnt_30d` | `int` | NO | 0 | 近30天导出次数 |
| 1 | `advanced_feature_cnt_30d` | `int` | NO | 0 | 近30天高级功能使用次数 |
| 1 | `has_advanced_feature_30d` | `tinyint` | NO | 0 | 近30天是否使用过高级功能（1=是） |
| 1 | `professional_content_ratio_30d` | `float` | YES |  |  |
| 1 | `formal_comm_ratio_30d` | `float` | YES |  |  |
| 1 | `email_type` | `varchar(16382)` | YES |  |  |
| 1 | `is_temp_email` | `tinyint` | YES |  |  |
| 1 | `is_churn_risk` | `tinyint` | YES |  |  |
| 1 | `max_daily_translate_30d` | `int` | YES |  |  |
| 1 | `total_paid_amount_all` | `decimal(18, 2)` | YES |  |  |
| 1 | `paid_order_count_all` | `int` | YES |  |  |
| 1 | `language_tier` | `varchar(16382)` | YES |  |  |
| 1 | `is_short_term_churn` | `tinyint` | YES | 0 |  |
| 1 | `is_script_like` | `tinyint` | YES | 0 |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_tag_metrics_current LIMIT 20;
```
