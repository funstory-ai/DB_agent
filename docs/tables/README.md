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
