# 主要翻译业务定义（跨任务共用）

> **非任务大类**。查数 / 看板凡涉及「网页 / PDF / 悬浮 / 电子书…」产品功能，先读本文件再写 SQL。  
> 变更须改本文件 + 同步 T025 留存 `biz_map` / 周表白名单；禁止各任务自行发明事件名。

来源核对（2026-09-03）：

- 插件 `F:\extension`（`dom/context.ts` pageType；各业务 `reportSingle` key）
- 概览 `imm_view_dau`：`pdfReader` / `pdfProReader` / `ebookBuilder` 来自 `imm_translate_page_device_count_by_utf8_day.page_type`
- T025 周留存：`imm_device_event_by_utf8_week` + `imm_translate_biz_firstuse_weekly_retention`

## 业务 ↔ 事件

| biz_code | 业务名 | 取数定义 | 类型 |
|----------|--------|----------|------|
| `web` | 网页翻译 | `event_name = 'translate_page'`（周表行；**含各 page_type**，未剔除 PDF/电子书） | 原事件 |
| `video` | 视频翻译 | `translate_video_subtitle` | 原事件 |
| `ai_subtitle` | AI字幕 | `use_ai_subtitle` | 原事件 |
| `image_pro` | 图片翻译 | `translate_image`（Pro） | 原事件 |
| `image_free` | 免费图片 | `translate_image_client`（插件 `isUsePro=false`） | 原事件 |
| `manga` | 漫画翻译 | `translate_manga` | 原事件 |
| `selection` | 划词翻译 | `selection_translate`（**不是**圈选） | 原事件 |
| `input_space` | 空格翻译 | `translate_input`（**无** `space_translate` 埋点；空格是触发键配置） | 原事件 |
| `side_panel` | 侧边栏 | `translateTextInSidePanel`（侧栏**内翻译**；打开侧栏是 `openSidePanel`） | 原事件 |
| `area_select` | 圈选翻译 | `screenshot_area_translate`（一次操作多 stage 同名上报，PV 会放大；`stage` 未落表） | 原事件 |
| `hover` | 悬浮翻译 | `mouse_hover_translate`（插件 `hotkey-hover`；不按 page_type 切） | 原事件 |
| `pdf` | PDF | **合成**周事件 `translate_pdf`：`translate_page` + `page_type='pdfReader'` + `main_frame='1'` | 合成 |
| `pdf_pro` | PDFPro | **合成** `translate_pdf_pro`：`page_type='pdfProReader'` + `main_frame='1'` | 合成 |
| `ebook` | 电子书 | **合成** `translate_ebook`：`translate_page` + `page_type='ebookBuilder'` + `main_frame='1'` | 合成 |

## BabelDoc（账号级，不走 behaviour）

| biz_code | 业务名 | 取数定义 | 主体 |
|----------|--------|----------|------|
| `babeldoc` | BabelDoc | `immdata.imm_babel_doc_record`：`userid` × `useddate`；首次使用周 = `min(to_start_of_week(useddate,1))`；W1～W4 = 之后第 1～4 自然周是否仍有记录；**只含已闭合周**（`week_start < 北京本周一`，与周表一致） | **userid** |

- 中间表：`imm_babeldoc_firstuse_weekly_retention`（与插件 device 留存表分开，勿混 Filter）
- ETL：`sql/reports/dashboard_t025_babeldoc_weekly_retention_etl.sql`（已含闭合周过滤）
- **不要**用旧 Superset「每周活跃当 cohort + W1～W8」直查当正式口径（已废弃）
- 当前 `translatetype` 均为 `babel_doc`；空 userid 已排除

## 合成事件（与概览 DAU 对齐）

| 产品卡 / 概览字段 | page_type | 周表合成 event_name |
|-------------------|-----------|---------------------|
| PDF | `pdfReader` | `translate_pdf` |
| PDFPro | `pdfProReader` | `translate_pdf_pro` |
| 电子书 | `ebookBuilder` | `translate_ebook` |

统一条件：`event_name='translate_page' AND page_type=… AND main_frame='1'`，再 `version<>'1.11.4'`、合法 `install_day`（写周表时）。

插件 pageType 判定（`dom/context.ts`）：

| 全局对象 | page_type | 说明 |
|----------|-----------|------|
| `PDFViewerApplication` | `pdfReader` | PDF 阅读器 |
| `immersiveTranslateEbookBuilder` | `ebookBuilder` | **电子书制作器**＝概览「电子书」 |
| `immersiveTranslateEbookViewer` | `ebookReader` | 电子书阅读器，量极小，**不要**当概览电子书 |

## 红线

1. **勿混**：划词 `selection_translate` ≠ 圈选 `screenshot_area_translate` ≠ 悬浮 `mouse_hover_translate`
2. **勿猜空格事件名**：只用 `translate_input`
3. **侧栏**：默认「侧栏内翻译」；若产品要「打开侧栏」须改用 `openSidePanel` 并单独说明
4. **网页 vs 切片**：`web`/`translate_page` 不剔除 PDF/电子书行；PDF/电子书是**额外切片业务**，不是从网页分母里挖走
5. **圈选 PV**：一次成功约 5 条同名事件；比用量用 UV / 去重操作，勿裸比 PV
6. **周表合成名**只存在于 `imm_device_event_by_utf8_week`（及下游留存）；`user_behaviour` 里仍是 `translate_page`
7. **BabelDoc** 不走 behaviour；主体 userid；与插件 device 留存分表挂板；勿用旧「周活跃+W8」直查
8. 埋点对不上 → `docs/norms/extension.md`（先 `git pull` `F:\extension`）

## 复用位置

- 周留存看板 T025：`imm_translate_biz_firstuse_weekly_retention.biz_code`
- BabelDoc 留存：`imm_babeldoc_firstuse_weekly_retention`（ETL `dashboard_t025_babeldoc_weekly_retention_etl.sql`）
- 周表白名单 / 合成：TASK `update_imm_device_event_by_utf8_week`（定稿 `dashboard_t025_week_event_expand_etl.sql`）
- 插件分业务留存 ETL：`dashboard_translate_weekly_retention_etl.sql`
