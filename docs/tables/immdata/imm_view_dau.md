# `immdata.imm_view_dau`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_view_dau` |
| 类型 | VIEW / VIEW |
| 约行数 | 未知 |
| 创建时间 | 2024-10-22 04:34:51.785011 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：DAU 视图（VIEW）
- **同步方式**：视图定义依赖底层表
- **业务含义**：日活口径封装
- **建议粒度**：按视图字段
- **常用过滤**：使用前 `SHOW CREATE VIEW` / 查字段并核对定义日期范围
- **勿想当然**：视图口径可能随底层变更；重要结论要回底层核对

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `dates` | `date` | YES |  |  |
| 1 | `dau` | `bigint unsigned` | YES |  |  |
| 1 | `eventcount` | `bigint unsigned` | YES |  |  |
| 1 | `translated_new_user` | `bigint unsigned` | YES |  |  |
| 1 | `new_user` | `bigint unsigned` | YES |  |  |
| 1 | `rate_of_new_user_translate` | `double` | YES |  |  |
| 1 | `translate_video_subtitle` | `bigint unsigned` | YES |  |  |
| 1 | `translate_video_subtitle_event` | `bigint unsigned` | YES |  |  |
| 1 | `translate_manga` | `bigint unsigned` | YES |  |  |
| 1 | `translate_manga_event` | `bigint unsigned` | YES |  |  |
| 1 | `translate_manga` | `bigint unsigned` | YES |  |  |
| 1 | `translate_manga_event` | `bigint unsigned` | YES |  |  |
| 1 | `pdfreader` | `bigint unsigned` | YES |  |  |
| 1 | `pdfreader_event` | `bigint unsigned` | YES |  |  |
| 1 | `pdfproreader` | `bigint unsigned` | YES |  |  |
| 1 | `pdfproreader_event` | `bigint unsigned` | YES |  |  |
| 1 | `ebookbuilder` | `bigint unsigned` | YES |  |  |
| 1 | `ebookbuilder_event` | `bigint unsigned` | YES |  |  |
| 1 | `subtitlebuilder` | `bigint unsigned` | YES |  |  |
| 1 | `subtitlebuilder_event` | `bigint unsigned` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_view_dau LIMIT 20;
```
