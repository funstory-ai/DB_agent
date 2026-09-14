# `immdata.imm_babeldoc_firstuse_weekly_retention`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `immdata.imm_babeldoc_firstuse_weekly_retention` |
| 类型 | BASE TABLE（写仓；T025） |
| 表注释 | BabelDoc：首次使用周 cohort → W1～W4 留存（userid） |

## 来源与用途（手工维护）

- **数据来源**：TASK `update_imm_babeldoc_firstuse_weekly_retention`（每周一 06:30 Asia/Shanghai）
- **上游**：`imm_babel_doc_record`（**不走** `user_behaviour`）
- **粒度**：`cohort_week_start` 一行；含未满窗（Wn 可为 0）
- **主体**：`userid`（与插件业务 device 留存表分离）
- **口径**：首次使用周 + W1～W4；见 `docs/norms/translate_biz.md`
- **DDL**：`sql/reports/dashboard_t025_babeldoc_weekly_retention_etl.sql`（含闭合周过滤）
- **勿想当然**：勿与旧「每周活跃 cohort + W8」直查混比；勿把本表人数当 device；max 周应与周表对齐

## 字段

| 字段 | 说明 |
|------|------|
| `biz_code` / `biz_name` | 固定 `babeldoc` / `BabelDoc` |
| `cohort_week_start` | 首次使用周（周一） |
| `cohort_users` | 分母 |
| `ret_w1_users`～`ret_w4_users` | 留存人数 |
| `w1_retention_rate`～`w4_retention_rate` | 留存率 |
| `update_time` | 写入时间 |
