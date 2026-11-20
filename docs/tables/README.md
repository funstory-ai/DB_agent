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

> ⚠️ **Stripe 数据不是 `immdata` 表**：`stripe_users` / `stripe_churn_users_*` 是僵尸表（文档在、库里已不存在），不要用。Stripe 直读走 API，连接与字段见 [`docs/stripe/`](../stripe/README.md)。

> ✅ **2026-11-20 已刷新**：按库内 **86** 张表（83 BASE + 3 VIEW）重建 INDEX，当前索引与库一致。历史上的「80 vs 111」不是权限/视图问题：11-09 库里确实 80 张，11-17 新建 6 张 Google Ads 表后为 86；旧 INDEX 是没刷新的快照，多留 46 张已删表、漏 20 张现存表。
>
> ⚠️ 重跑前须知两个坑：① 只保留 `<!-- AUTO:SCHEMA -->` 段**之外**的手工内容，写在自动段内的列注释会被冲掉（字段速记放段外）；② 注释取库内 `table_comment`，`routing_ledger` 等为空，INDEX 中相关说明是手工补的，重跑需重补。46 张已下线表的孤儿单表文档已于 2026-11-20 删除（另含 8-27 废弃的 `imm_paywall_daily_dim`）；脚本本身不会自动删，将来表下线需手工清理。
>
> 新建表未收录时采用**手工补录**：按既有体例写 `immdata/<表>.md`（含 `AUTO:SCHEMA` 段，取自 `information_schema.columns`），并在 `INDEX.md` 按字母序插一行 + 顶部注明补录日期。样板：[`immdata/routing_ledger.md`](immdata/routing_ledger.md)。
