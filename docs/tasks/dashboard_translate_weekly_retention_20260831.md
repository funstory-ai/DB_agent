# 看板：插件翻译业务分业务周留存

- **需求编号**: T025
- **规范大类**: `dashboard`
- **状态**: ✅ 已完成
- **日期**: 2026-08-31；完成验收 2026-09-03
- **业务口径（共用）**: [`docs/norms/translate_biz.md`](../norms/translate_biz.md)
- **定稿 SQL**:
  1. 周表白名单/TASK：`sql/reports/dashboard_t025_week_event_expand_etl.sql`（§2 历史回填勿无故重跑）
  2. 插件分业务留存：`sql/reports/dashboard_translate_weekly_retention_etl.sql`（Cron：**周一 10:00 上海**）
  3. BabelDoc 留存：`sql/reports/dashboard_t025_babeldoc_weekly_retention_etl.sql`（Cron：**周一 10:30 上海**）
  4. board：`sql/reports/dashboard_translate_weekly_retention_board.sql`
  5. **2026-09-28 调度修复（写仓一次跑完）**：`sql/reports/dashboard_t025_retention_schedule_fix_20260928.sql`
     - 根因：原 06:00/06:30 早于上游周表≈北京 08:02 → 看板停在上上周、最新周无 W1（**P038**）
     - 修复：改 Cron + 立刻全量重算；验收 `biz_max = src_week_max`（当日应为 09-21）

## 初始需求（原文）

想知道我们插件主要翻译业务的周留存并做成看板。

## 交付验收（2026-09-03）✅

| 检查 | 结果 |
|------|------|
| 插件留存 14 业务 | 齐全；max=`2026-08-24`；grain 1198=1198 |
| 周表扩事件 | hover/ebook/pdf/圈选/免费图均有；max 周对齐 |
| BabelDoc | 48 周；max=`2026-08-24` **与插件同 max**；`08-24` W1=0（闭合周） |
| TASK×3 | 均 Started（周表 UTC 周一 / 插件留存 06:00 沪 / BabelDoc 06:30 沪） |
| 挂板 | 插件一业务一表 + BabelDoc 独立 Dataset |

## 已确认口径（2026-09-02 修订）

| 项 | 口径 |
|----|------|
| 留存类型 | **各业务各自首次使用周** cohort（方案 A；与新装无关） |
| 留存窗 | **W1～W4**（该业务首次周之后第 1～4 自然周是否仍有**同一业务**事件） |
| 主体 | 插件业务：**device_id**；BabelDoc：**userid** |
| 周切分 | 自然周，周一 |
| 挂板 | **一业务一图**；BabelDoc **独立 Dataset**（勿与 device 业务共用 Filter） |
| 旧物 | **删除** `imm_translate_firstuse_weekly_retention` 及 TASK（已写入 ETL §0） |

### 业务 ↔ 事件（插件 + 概览看板对照）

| biz_code | 业务名 | 周表 event_name | 说明 |
|----------|--------|-----------------|------|
| web | 网页翻译 | `translate_page` | 既有 |
| video | 视频翻译 | `translate_video_subtitle` | 既有 |
| ai_subtitle | AI字幕 | `use_ai_subtitle` | 既有；渗透率卡不做留存 |
| image_pro | 图片翻译 | `translate_image` | 既有；Pro |
| image_free | 免费图片 | `translate_image_client` | **扩周表**；插件 `isUsePro=false` |
| manga | 漫画翻译 | `translate_manga` | 既有 |
| selection | 划词翻译 | `selection_translate` | 既有（非圈选） |
| input_space | 空格翻译 | `translate_input` | 既有；**事件名不是 space_translate**（插件无此埋点；空格是触发键配置） |
| side_panel | 侧边栏 | `translateTextInSidePanel` | 既有；**侧栏内发起翻译**，不是 `openSidePanel`（打开侧栏） |
| area_select | 圈选翻译 | `screenshot_area_translate` | **扩周表**；插件截图圈选 |
| pdf | PDF | `translate_pdf` | **合成**：`translate_page`+`page_type=pdfReader`+`main_frame=1` |
| pdf_pro | PDFPro | `translate_pdf_pro` | **合成**：`page_type=pdfProReader`+`main_frame=1` |
| hover | 悬浮翻译 | `mouse_hover_translate` | **扩周表**（2026-09-03）；插件悬停 |
| ebook | 电子书 | `translate_ebook` | **合成**（2026-09-03）：`page_type=ebookBuilder`+`main_frame=1`（对齐概览 ebookBuilder；非 ebookReader） |
| babeldoc | BabelDoc | （无周表事件） | **独立表**；源 `imm_babel_doc_record`；userid；首次周+W1～W4（2026-09-03 确认；废弃旧「周活跃+W8」直查） |

> 完整对照与红线见 **`docs/norms/translate_biz.md`**（后续查数默认复用）。  
> 概览「自建数据流」日活量级与 behaviour 全量 UV 不完全一致（视频等差更大）；留存按上表**产品使用事件**定义，不追求对齐概览绝对数。

### 插件查阅（`F:\extension`）

- 本次 `git pull` 失败（GitHub 443）；以本地代码为准。
- 圈选：`key: "screenshot_area_translate"`（`screenshot-area/controller.ts`）
- 划词：`key: "selection_translate"`
- 免费图：`isUsePro ? "translate_image" : "translate_image_client"`（`image/mod.ts`）

## ① 需求模块清单

| # | 模块 | 说明 |
|---|------|------|
| 1 | 分业务首次使用 cohort 规模 | 每业务按 `cohort_week_start` |
| 2 | 分业务 W1～W4 留存率 | **一业务一折线**（同图 4 条率） |
| 3 | （可选）每业务最近满窗 W1/W4 卡片 | `ds_retention_latest_by_biz` |

## 写仓执行顺序

1. **只跑** `dashboard_t025_week_event_expand_rerun.sql`（整文件；已含缺口回填 + TASK 重建）  
   - 勿再跑旧 `…_expand_etl.sql` 全文，勿自行找断点  
2. 告知查数侧只读复检周表 4 新事件 + TASK definition  
3. 通过后再跑 `dashboard_translate_weekly_retention_etl.sql`（DROP 旧并集 + 分业务留存）
4. 挂板

### 中断续跑备注（2026-09-02）

| 项 | 查库结果 |
|----|----------|
| 已回填 | `translate_image_client` / `translate_pdf` / `translate_pdf_pro`，max=`2025-06-23` |
| 未回填 | `2025-06-29` 起；`screenshot_area_translate` 全无 |
| 周 TASK | Suspended；definition 仍旧 8 事件 |
| 续跑包 | `dashboard_t025_week_event_expand_rerun.sql` |

### 周表扩事件验收（2026-09-03，只读）✅

| 检查 | 结果 |
|------|------|
| 4 新事件 | 均有行；`max_w=2026-08-24` 与 `translate_page` 对齐 |
| 圈选 | `screenshot_area_translate`：2398 行 / 1661 设备，自 2026-05-18 |
| 免费图 / PDF / PDFPro | 行数正常；PDF 自 2024-09-23 |
| 周 TASK | **Started**；definition 含 4 新事件 + UNION |

### 分业务留存验收（2026-09-03，只读）✅

| 检查 | 结果 |
|------|------|
| 旧并集表 | `imm_translate_firstuse_weekly_retention` **已 DROP** |
| 新表 | 12 业务齐全；grain 948=948；单批 `2026-09-03 02:09` |
| 新鲜度 | `max_cohort=2026-07-27`；源周 max=`08-24`（−28d）✅ |
| 抽周对账 | `web`×`2026-07-06` **完全一致**（263770 / 65165 / 48099 / 40129 / 35427） |
| TASK | `update_imm_translate_biz_firstuse_weekly_retention` **Started**；DELETE+INSERT；旧 TASK 已无 |

### 未满窗上挂验收（2026-09-03，只读）✅

| 检查 | 结果 |
|------|------|
| max cohort | 各业务均到 **2026-08-24**（与源周对齐） |
| 未到窗标 0 | 如 web：`08-24` 四率全 0；`08-17` 仅 W1；`08-10` W1+W2… |
| 历史不变 | web `07-06`、video `05-25` 与改前一致 |
| 抽周对账 | web `08-10` 与周表 **253399 / 59031 / 43184 / 0 / 0** 一致 |
| TASK | Started；definition **已无** `max_w-28` 过滤 |

## Superset 挂板对照表

**Dashboard 名建议**：`翻译业务周留存（分业务）`  
**主 Dataset**：`ds_retention_by_biz`（近 26 周）  
**推荐形态**：**Table（一业务一表）**——同行展示绝对值 + 留存率，比纯折线好读；折线可作加项。

### 推荐 Dataset SQL（同 board）

```sql
SELECT
  biz_code, biz_name, event_name, cohort_week_start,
  cohort_devices,
  ret_w1_devices, ret_w2_devices, ret_w3_devices, ret_w4_devices,
  w1_retention_rate, w2_retention_rate, w3_retention_rate, w4_retention_rate
FROM immdata.imm_translate_biz_firstuse_weekly_retention
WHERE cohort_week_start >= date_add(week, -26, to_date(now()))
ORDER BY biz_code, cohort_week_start
```

### 单张 Table 设置（12 张，一业务一图；先做网页再另存改 Filter）

| 项 | 设置 |
|----|------|
| 类型 | **Table** |
| Dataset | `ds_retention_by_biz` |
| Query mode | Aggregate |
| 维度 / Group by | `cohort_week_start`（降序） |
| Metrics | 见下列（一律 **MAX**，勿 SUM） |
| Filter | `biz_code = …` |
| 百分比列 | `w*_retention_rate` 用百分比格式（或 ×100） |

**Metrics 列（建议顺序）**

| 列名（自定义） | Metric |
|----------------|--------|
| 首次周设备数 | `MAX(cohort_devices)` |
| W1 留存人数 | `MAX(ret_w1_devices)` |
| W1 留存率 | `MAX(w1_retention_rate)` |
| W2 留存人数 | `MAX(ret_w2_devices)` |
| W2 留存率 | `MAX(w2_retention_rate)` |
| W3 留存人数 | `MAX(ret_w3_devices)` |
| W3 留存率 | `MAX(w3_retention_rate)` |
| W4 留存人数 | `MAX(ret_w4_devices)` |
| W4 留存率 | `MAX(w4_retention_rate)` |

| 图# | 需求来源 | 标题 | Filter `biz_code` |
|-----|----------|------|-------------------|
| 1 | 需求#2 | 网页翻译 | `web` |
| 2 | 需求#2 | 视频翻译 | `video` |
| 3 | 需求#2 | AI字幕 | `ai_subtitle` |
| 4 | 需求#2 | 图片翻译 | `image_pro` |
| 5 | 需求#2 | 免费图片 | `image_free` |
| 6 | 需求#2 | 漫画翻译 | `manga` |
| 7 | 需求#2 | 划词翻译 | `selection` |
| 8 | 需求#2 | 空格翻译 | `input_space`（事件=`translate_input`，非 space_translate） |
| 9 | 需求#2 | 侧边栏 | `side_panel` |
| 10 | 需求#2 | 圈选翻译 | `area_select` |
| 11 | 需求#2 | PDF | `pdf` |
| 12 | 需求#2 | PDFPro | `pdf_pro` |
| 13 | 需求#2 | 悬浮翻译 | `hover` |
| 14 | 需求#2 | 电子书 | `ebook` |
| 15 | 需求#2 | BabelDoc | **另建 Dataset**（见下），勿用 `ds_retention_by_biz` |

### BabelDoc 挂板步骤（写仓已验后）

库里的中间表是 `immdata.imm_babeldoc_firstuse_weekly_retention`。  
`ds_babeldoc_retention` **只是建议的 Virtual Dataset 名字**（和 `ds_retention_by_biz` 同级），要在 Superset **手动新建**，不是库对象。

**① 新建 Virtual Dataset**（名称建议：`ds_babeldoc_retention`）

```sql
SELECT
  biz_code,
  biz_name,
  cohort_week_start,
  cohort_users,
  ret_w1_users,
  ret_w2_users,
  ret_w3_users,
  ret_w4_users,
  w1_retention_rate,
  w2_retention_rate,
  w3_retention_rate,
  w4_retention_rate
FROM immdata.imm_babeldoc_firstuse_weekly_retention
WHERE cohort_week_start >= date_add(week, -26, to_date(now()))
ORDER BY cohort_week_start
```

**② 新建 Chart → 放进同一 Dashboard**

| 项 | 设置 |
|----|------|
| 标题 | BabelDoc |
| 类型 | **Table** |
| Dataset | 刚建的 `ds_babeldoc_retention` |
| Query mode | Aggregate |
| 维度 | `cohort_week_start`（降序） |
| Metrics | 一律 **MAX**（见下） |
| Filter | 不需要（表内只有 babeldoc） |

| 列名（自定义） | Metric |
|----------------|--------|
| 首次周用户数 | `MAX(cohort_users)` |
| W1 留存人数 | `MAX(ret_w1_users)` |
| W1 留存率 | `MAX(w1_retention_rate)` |
| W2 留存人数 | `MAX(ret_w2_users)` |
| W2 留存率 | `MAX(w2_retention_rate)` |
| W3 留存人数 | `MAX(ret_w3_users)` |
| W3 留存率 | `MAX(w3_retention_rate)` |
| W4 留存人数 | `MAX(ret_w4_users)` |
| W4 留存率 | `MAX(w4_retention_rate)` |

注意：字段是 `*_users`，不是插件业务的 `*_devices`。

### BabelDoc 验收（2026-09-03，只读）✅

| 检查 | 结果 |
|------|------|
| 表 | 49 周；`2025-09-29`～`2026-08-31`；sum_users=260292；grain 49=49；单批 `09-03 09:13` |
| 与源对齐 | max cohort = 源 max 周 `2026-08-31` |
| 抽周对账 | `2026-07-06`：**5596 / 519 / 291 / 254 / 239** 与源完全一致 |
| 未满窗 | `08-31` 四率 0；`08-24` 仅 W1；`08-17` W1+W2… |
| TASK | Started；`CRON 0 30 6 * * 1` Asia/Shanghai |

### 日期未对齐说明（2026-09-03 看板对照）

看板中 BabelDoc 比侧栏/漫画多出 `2026-08-31`，且 `08-24` 已有 W1，插件业务 `08-24` W1=0。

| 源 | max cohort（当日） | 原因 |
|----|-------------------|------|
| 周表 / 插件留存 | `2026-08-24` | 周 TASK 只写入**已闭合周**（`< 本周一`） |
| BabelDoc 源/留存 | `2026-08-31` | `useddate` 日表可含本周；首次周含**进行中周** |

**已改并验收（2026-09-03）**：BabelDoc 只统计已闭合周（`< 北京本周一`）；max=`2026-08-24` 与插件业务一致。

### hover+ebook 补丁验收（2026-09-03，只读）✅

| 检查 | 结果 |
|------|------|
| 周表 hover | `mouse_hover_translate`：1163 万行 / 124.8 万设备；`2024-09-23`～`2026-08-24` |
| 周表 ebook | `translate_ebook`：23.7 万行 / 9.1 万设备；同窗 |
| 周 TASK | Started；definition 含 hover + ebook + pdf |
| 留存表 | **14** 业务；grain 1198=1198；单批 `2026-09-03 08:29` |
| 抽周对账 | hover / ebook × `2026-08-10` 与周表 **完全一致**（hover 6362/1919/1530；ebook 768/128/79） |
| 历史不变 | web `2026-07-06` 仍为 263770 / 65165 / … |
| 留存 TASK | Started；definition 含 hover / ebook |

**加项（可选）**：同 Filter 再挂一张 Line，只画 `w1`～`w4_retention_rate` 看趋势。

可选卡片：`ds_retention_latest_by_biz` 看每业务最近满窗 W1/W4。

## 需求覆盖对照

| 需求项 | 状态 |
|--------|------|
| 分业务（非并集） | ✅ |
| 各自首次周（A） | ✅ |
| 一业务一图 | ✅ 插件 14 图 + BabelDoc 1 图 |
| 圈选/免费图/PDF/PDFPro | ✅ |
| 悬浮翻译 / 电子书 | ✅ |
| BabelDoc 首次周留存（闭合周对齐） | ✅ |
| 删旧并集表 | ✅ |
| 做成看板 | ✅ |
| 定稿 SQL 收尾（过程补丁已删） | ✅ |

### 看板抽点对账（2026-09-03）✅

与 `imm_translate_biz_firstuse_weekly_retention` 一致，例如：web `08-17` 244705/W1=23.02%；video `07-27` 85090/30.92%；selection `07-27` 98049/23.05%；side_panel `08-24` 2949；area_select 小样本波动属实。

### 旁支：圈选「使用频次很高」核查（2026-09-03）

同事称圈选频次高于其它翻译业务。短窗（近 7 日 BJ）behaviour：

| 业务 | UV | PV | PV/UV |
|------|-----|-----|-------|
| 视频 | 87.5 万 | 4232 万 | **48.3** |
| 侧栏翻译 | 1.3 万 | 36.6 万 | 27.3 |
| **圈选** | **390** | 0.93 万 | **23.9** |
| 漫画 | 0.55 万 | 12.8 万 | 23.5 |
| 网页 | 213 万 | 3341 万 | 15.7 |
| 划词 | 65.3 万 | 329 万 | 5.0 |

结论：
- **绝对值不高**：圈选 UV 极小；看板「新设备数」两位数～数百属实。
- **人均次数偏高是真的**（在「用过的人」里），主要因为：
  1. 插件一次圈选会多次上报同一事件（`start` / `area_complete` / `capture_success` / `ocr_success` 等 stage，`controller.ts`）→ PV 被放大；
  2. 头部设备一周可达数百～近千条（重度/刷用），抬高均值。
- 若同事拿 **PV/UV** 比各业务，圈选会看起来「比划词/网页还勤」——指标选错，不是库造假。
- 对比总量或留存分母时，圈选仍是小业务；勿与 **划词** `selection_translate` 混淆。


## 已知限制

- 周表历史起点 / 新事件上线前会左截断首次周
- 圈选量级目前很小（日 UV 两位数级）
- 改周 TASK 为**加事件**，不改既有 8 事件语义；其他读周表的看板不受影响
