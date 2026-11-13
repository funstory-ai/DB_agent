# 表结构与来源目录（仅 immdata）

本项目只维护 **沉浸式翻译** 库 **`immdata`** 的表文档。

## 强制约定

1. 写 SQL 前：读 [`OVERVIEW.md`](OVERVIEW.md) → [`INDEX.md`](INDEX.md) → `immdata/<表>.md`
2. 禁止臆造表/字段/关联键；禁止默认使用非 immdata 表
3. 首次使用某表：补全「来源与用途」
4. 文档与事实不符：当轮改正；因此导致的错误记入 `docs/pitfalls.md`

## 刷新结构

```bash
python scripts/sync_table_catalog.py
```

仅同步 `immdata`。手工「来源与用途」会保留。

> ⚠️ **2026-11-09 起暂勿直接刷新**：当前只读账号下 `information_schema.tables` 只返回 **80** 张表，而 `INDEX.md` 收录 **111** 张（含手工补录的 `routing_ledger`）。直接跑会把历史索引条目刷掉。需先确认账号权限 / `information_schema` 视图完整性，再刷新并 diff 校验。
>
> 新建表未收录时采用**手工补录**：按既有体例写 `immdata/<表>.md`（含 `AUTO:SCHEMA` 段，取自 `information_schema.columns`），并在 `INDEX.md` 按字母序插一行 + 顶部注明补录日期。样板：[`immdata/routing_ledger.md`](immdata/routing_ledger.md)。
