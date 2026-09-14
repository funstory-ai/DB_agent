# `immdata.imm_translate_biz_firstuse_weekly_retention`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_translate_biz_firstuse_weekly_retention` |
| 类型 | BASE TABLE（写仓；T025） |
| 表注释 | 分业务：首次使用周 cohort → W1～W4 留存 |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_translate_biz_firstuse_weekly_retention`（每周一 06:00 Asia/Shanghai）
- **上游**：`imm_device_event_by_utf8_week`（含合成 `translate_pdf` / `translate_pdf_pro` / `translate_ebook`；含 `mouse_hover_translate`）
- **粒度**：`biz_code` × `cohort_week_start` 一行；**含未满 4 周** cohort（未到窗 Wn=0）
- **业务列表**：见 `docs/norms/translate_biz.md`（14 业务含 hover / ebook）
- **DDL / 补丁**：`dashboard_translate_weekly_retention_etl.sql`；增业务见 `dashboard_t025_add_hover_ebook_patch.sql`
- **替代**：原并集表 `imm_translate_firstuse_weekly_retention` **已废弃并 DROP**
- **勿想当然**：各业务首次周独立；勿把多业务事件并成一个 cohort

## 字段

| 字段 | 说明 |
|------|------|
| `biz_code` / `biz_name` | 业务键 / 中文名 |
| `event_name` | 周表事件名 |
| `cohort_week_start` | 该业务首次周（周一） |
| `cohort_devices` | 分母 |
| `ret_w1_devices`～`ret_w4_devices` | 留存人数 |
| `w1_retention_rate`～`w4_retention_rate` | 留存率 |
| `update_time` | 写入时间 |
