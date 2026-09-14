# `immdata.imm_device_event_by_utf8_week`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_device_event_by_utf8_week` |
| 类型 | BASE TABLE / FUSE |
| 约行数 | 311478932 |
| 创建时间 | 2024-10-22 08:34:18.059951 |
| 表注释 | （待补充） |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_device_event_by_utf8_week`（每周一 UTC `0 2 0 * * 1`）
- **上游**：`user_behaviour`（白名单事件；`version<>1.11.4`）
- **业务含义**：设备 × 事件 × 自然周（周一）活跃
- **主键 / 唯一键**：`(week_start_day, event_name, device_id)`（REPLACE ON）
- **T025 扩事件**：
  - `translate_image_client`（免费图片）
  - `screenshot_area_translate`（圈选）
  - `mouse_hover_translate`（悬浮；`dashboard_t025_add_hover_ebook_patch.sql`）
  - `translate_pdf` / `translate_pdf_pro` / `translate_ebook`（由 `translate_page`+`page_type`+`main_frame=1` 合成；**不**改变原 `translate_page` 行）
- **业务口径**：`docs/norms/translate_biz.md`
- **勿想当然**：合成 PDF/电子书事件只存在于周表分析层，behaviour 里仍是 `translate_page`；`ebookBuilder`≠`ebookReader`

<!-- AUTO:SCHEMA:START -->
## 字段结构（自动同步，勿手改本段）

| # | 字段 | 类型 | 可空 | 默认 | 注释 |
|---|------|------|------|------|------|
| 1 | `week_start_day` | `date` | YES |  |  |
| 1 | `event_name` | `varchar(16382)` | YES |  |  |
| 1 | `device_id` | `varchar(16382)` | YES |  |  |
| 1 | `install_week_start_day` | `date` | YES |  |  |
| 1 | `event_count` | `bigint unsigned` | NO |  |  |
| 1 | `update_time` | `timestamp` | NO |  |  |

<!-- AUTO:SCHEMA:END -->

## 样例核对（可选）

```sql
SELECT * FROM immdata.imm_device_event_by_utf8_week LIMIT 20;
```
