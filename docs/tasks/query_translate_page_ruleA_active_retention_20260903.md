# translate_page 月留 / 近30天活跃 / 月活 · 对齐 Rule A 踢油猴

- **需求编号**: T029
- **规范大类**: `query`
- **状态**: ✅ 已完成
- **日期**: 2026-09-03
- **定稿 SQL**: `sql/reports/query_translate_page_monthly_retention_ruleA.sql`

## 初始需求

1. 原「新装月留存 M1～M6」直扫 `user_behaviour`，在 T028 踢油猴后是否还能用？要对齐则改 SQL。
2. 日常「近 30 天活跃」「自然月活」一并改，与日看板踢除口径一致。
3. 每月手工跑，不建中间表；勿为验收重跑小时级全量。

## 口径

- 事件：`translate_page`；`version != '1.11.4'`
- **Rule A**（与 T028 / `imm_event_device_count` 日看板一致，P034）：
  ```text
  踢：official_userscript × (ios×Safari | macos×Maxthon)
  留：ImtiOS_* 等 App UA 的 userscript
  ```
- 近 30 天窗：`[yesterday()-30d, yesterday())`（保持原写法）
- 月活：自然月 `[月初, 下月初)`（例 2026-08）
- 月留：安装月 cohort + 活跃月对齐；安装月用 `to_start_of_month(add_hours(created_ts,8))` 体系（保持原 SQL）

## 结论（开查时）

- 昨日踢除只改了日表 ETL，**未改** behaviour；旧月留/活跃 SQL **仍含**油猴。
- 2026-07-28 起 cohort / 活跃会被集成抬分母、压留存；正式口径须加 Rule A。

## 需求覆盖对照

| 需求项 | 状态 |
|--------|------|
| 月留存 SQL 加 Rule A | ✅ §3 |
| 近 30 天活跃加 Rule A | ✅ §1 |
| 自然月活加 Rule A | ✅ §2 |
| 与 T028 日看板踢规则一致 | ✅ |
| 不建中间表 / 不跑全量验收扫表 | ✅（交付为定稿 SQL） |

## 定稿文件

`sql/reports/query_translate_page_monthly_retention_ruleA.sql`（三段查询）
