# `immdata.dwd_homepage_ab260330`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.dwd_homepage_ab260330` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 27755 |
| 创建时间 | 2026-03-30 10:58:44.570621 |
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
| 1 | `ab_group` | `varchar(16382)` | YES |  |  |
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `real_ip` | `varchar(16382)` | YES |  |  |
| 1 | `real_geo` | `varchar(16382)` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `trigger` | `varchar(16382)` | YES |  |  |
| 1 | `ab_tag` | `varchar(16382)` | YES |  |  |
| 1 | `always_translate_languages` | `varchar(16382)` | YES |  |  |
| 1 | `beta` | `varchar(16382)` | YES |  |  |
| 1 | `browser_name` | `varchar(16382)` | YES |  |  |
| 1 | `browser_version` | `varchar(16382)` | YES |  |  |
| 1 | `campaign` | `varchar(16382)` | YES |  |  |
| 1 | `enable_default_always_translated_urls` | `varchar(16382)` | YES |  |  |
| 1 | `enable_input_translation` | `varchar(16382)` | YES |  |  |
| 1 | `engine_name` | `varchar(16382)` | YES |  |  |
| 1 | `engine_version` | `varchar(16382)` | YES |  |  |
| 1 | `install_day` | `varchar(16382)` | YES |  |  |
| 1 | `install_from` | `varchar(16382)` | YES |  |  |
| 1 | `install_week` | `varchar(16382)` | YES |  |  |
| 1 | `interface_language` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_month` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_week` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_this_year` | `varchar(16382)` | YES |  |  |
| 1 | `is_new_user_today` | `varchar(16382)` | YES |  |  |
| 1 | `main_frame` | `int` | YES |  |  |
| 1 | `os_name` | `varchar(16382)` | YES |  |  |
| 1 | `os_version` | `varchar(16382)` | YES |  |  |
| 1 | `os_version_name` | `varchar(16382)` | YES |  |  |
| 1 | `page_type` | `varchar(16382)` | YES |  |  |
| 1 | `platform_type` | `varchar(16382)` | YES |  |  |
| 1 | `site_host` | `varchar(16382)` | YES |  |  |
| 1 | `source_language` | `varchar(16382)` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `temp_translate_domain_minutes` | `bigint` | YES |  |  |
| 1 | `translation_area` | `varchar(16382)` | YES |  |  |
| 1 | `translation_mode` | `varchar(16382)` | YES |  |  |
| 1 | `translation_service` | `varchar(16382)` | YES |  |  |
| 1 | `translation_theme` | `varchar(16382)` | YES |  |  |
| 1 | `user_type` | `varchar(16382)` | YES |  |  |
| 1 | `userscript` | `varchar(16382)` | YES |  |  |
| 1 | `version` | `varchar(16382)` | YES |  |  |
| 1 | `created_ts` | `timestamp` | YES |  |  |
| 1 | `ex_char_arg1` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg2` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg3` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg4` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg5` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg6` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg7` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg8` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg9` | `varchar(16382)` | YES |  |  |
| 1 | `ex_char_arg10` | `varchar(16382)` | YES |  |  |
| 1 | `ex_int_arg1` | `int` | YES |  |  |
| 1 | `ex_int_arg2` | `int` | YES |  |  |
| 1 | `ex_int_arg3` | `int` | YES |  |  |
| 1 | `ex_int_arg4` | `int` | YES |  |  |
| 1 | `ex_int_arg5` | `int` | YES |  |  |
| 1 | `ex_int_arg6` | `int` | YES |  |  |
| 1 | `ex_int_arg7` | `int` | YES |  |  |
| 1 | `ex_int_arg8` | `int` | YES |  |  |
| 1 | `ex_int_arg9` | `int` | YES |  |  |
| 1 | `ex_int_arg10` | `int` | YES |  |  |
| 1 | `real_city` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.dwd_homepage_ab260330 LIMIT 20;
```
