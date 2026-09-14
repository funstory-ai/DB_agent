# `immdata.user_access_log`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.user_access_log` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 1820614087 |
| 创建时间 | 2024-10-12 07:04:05.490089 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：插件访问/性能类埋点（结构近似 `user_behaviour`，另含 `url`/`site`）
- **同步方式**：持续写入；十亿级，必须限时限事件
- **更新频率**：近实时
- **业务含义**：页面访问、performance 等；带完整 URL
- **建议粒度**：事件行（`device_id` × `created_ts`）
- **主键 / 唯一键**：无
- **常用过滤**：`created_ts`；`event_name`（如 `performance`）
- **关联建议**：同 behaviour，以 `device_id` 为主
- **勿想当然**：不要与 `user_behaviour` 混为一谈；字段高度相似但用途与事件集合不同

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
| 1 | `temp_translate_domain_minutes` | `int` | YES |  |  |
| 1 | `translation_area` | `varchar(16382)` | YES |  |  |
| 1 | `translation_mode` | `varchar(16382)` | YES |  |  |
| 1 | `translation_service` | `varchar(16382)` | YES |  |  |
| 1 | `translation_theme` | `varchar(16382)` | YES |  |  |
| 1 | `user_type` | `varchar(16382)` | YES |  |  |
| 1 | `userscript` | `varchar(16382)` | YES |  |  |
| 1 | `version` | `varchar(16382)` | YES |  |  |
| 1 | `created_ts` | `timestamp` | YES |  |  |
| 1 | `url` | `varchar(16382)` | YES |  |  |
| 1 | `site` | `varchar(16382)` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.user_access_log LIMIT 20;
```
