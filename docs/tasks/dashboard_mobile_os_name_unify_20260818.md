# 移动端看板：统一 `os_name` 大小写

- **需求编号**: T009
- **规范大类**: `dashboard`
- **状态**: ✅ 已完成
- **日期**: 2026-08-18

- **需求**: 平台过滤无效；字段有的大写有的小写，统一成一个字段
- **做法**: 不改建表。Superset 数据集 SQL 内 `CASE LOWER(os_name)` 归并为 `Android` / `iOS` / `iPadOS`
- **SQL**: `sql/reports/task8_mobile_os_name_board.sql`
