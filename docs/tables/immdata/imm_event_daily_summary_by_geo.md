# `immdata.imm_event_daily_summary_by_geo`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_event_daily_summary_by_geo` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 19311 |
| 创建时间 | 2026-01-28 11:56:53.021367 |
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
| 1 | `dates` | `date` | YES |  |  |
| 1 | `target_language` | `varchar(16382)` | YES |  |  |
| 1 | `translate_user` | `int` | YES |  |  |
| 1 | `translate_event` | `int` | YES |  |  |
| 1 | `new_user` | `int` | YES |  |  |
| 1 | `new_translate_user` | `int` | YES |  |  |
| 1 | `translate_video_subtitle` | `int` | YES |  |  |
| 1 | `translate_video_subtitle_event` | `int` | YES |  |  |
| 1 | `translate_manga` | `int` | YES |  |  |
| 1 | `translate_manga_event` | `int` | YES |  |  |
| 1 | `translate_input` | `int` | YES |  |  |
| 1 | `translate_input_event` | `int` | YES |  |  |
| 1 | `translate_image` | `int` | YES |  |  |
| 1 | `translate_image_event` | `int` | YES |  |  |
| 1 | `use_ai_subtitle` | `int` | YES |  |  |
| 1 | `use_ai_subtitle_event` | `int` | YES |  |  |
| 1 | `selection_translate` | `int` | YES |  |  |
| 1 | `selection_translate_event` | `int` | YES |  |  |
| 1 | `translatetextinsidepanel` | `int` | YES |  |  |
| 1 | `translatetextinsidepanel_event` | `int` | YES |  |  |
| 1 | `mouse_hover_translate` | `int` | YES |  |  |
| 1 | `mouse_hover_translate_event` | `int` | YES |  |  |
| 1 | `share_to_draft` | `int` | YES |  |  |
| 1 | `share_to_draft_event` | `int` | YES |  |  |
| 1 | `ai_writing_translate` | `int` | YES |  |  |
| 1 | `ai_writing_translate_event` | `int` | YES |  |  |
| 1 | `ai_writing_modal_open` | `int` | YES |  |  |
| 1 | `ai_writing_modal_open_event` | `int` | YES |  |  |
| 1 | `ai_writing_insert` | `int` | YES |  |  |
| 1 | `ai_writing_insert_event` | `int` | YES |  |  |
| 1 | `order_cnt` | `int` | YES |  |  |
| 1 | `order_paid` | `int` | YES |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_event_daily_summary_by_geo LIMIT 20;
```
