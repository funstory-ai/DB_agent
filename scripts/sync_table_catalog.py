"""从 information_schema 同步表目录文档（只读）。

生成/更新：
- docs/tables/INDEX.md
- docs/tables/<schema>/<table>.md

已有文档中，手工填写区（来源、口径等）会被保留；
仅刷新 <!-- AUTO:SCHEMA --> 之间的结构段落。
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = ROOT / "docs" / "tables"

SKIP_SCHEMAS = {"information_schema", "system"}

SCHEMA_BLOCK_RE = re.compile(
    r"<!-- AUTO:SCHEMA:START -->.*?<!-- AUTO:SCHEMA:END -->",
    re.DOTALL,
)


def _fetch_tables():
    _, rows = query(
        """
        SELECT table_schema, table_name, table_type, engine,
               table_comment, table_rows, create_time
        FROM information_schema.tables
        WHERE table_schema = 'immdata'
        ORDER BY table_name
        """
    )
    return rows


def _fetch_columns():
    _, rows = query(
        """
        SELECT table_schema, table_name, ordinal_position, column_name,
               column_type, is_nullable, column_comment, `default`
        FROM information_schema.columns
        WHERE table_schema = 'immdata'
        ORDER BY table_name, ordinal_position
        """
    )
    by_table: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        by_table[(r[0], r[1])].append(r)
    return by_table


def _schema_markdown(cols: list) -> str:
    lines = [
        "<!-- AUTO:SCHEMA:START -->",
        "## 字段结构（自动同步，勿手改本段）",
        "",
        "| # | 字段 | 类型 | 可空 | 默认 | 注释 |",
        "|---|------|------|------|------|------|",
    ]
    for r in cols:
        # schema, table, pos, name, type, nullable, comment, default
        pos, name, ctype, nullable, comment, default = (
            r[2],
            r[3],
            r[4],
            r[5],
            r[6] or "",
            r[7] if r[7] not in (None, "") else "",
        )
        comment = str(comment).replace("|", "\\|").replace("\n", " ")
        default = str(default).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {pos} | `{name}` | `{ctype}` | {nullable} | {default} | {comment} |"
        )
    if not cols:
        lines.append("| — | — | — | — | — | （information_schema 无列信息） |")
    lines.append("")
    lines.append("<!-- AUTO:SCHEMA:END -->")
    return "\n".join(lines)


def _new_doc(schema: str, table: str, table_type: str, engine, comment, rows, created, cols) -> str:
    fq = f"{schema}.{table}"
    comment_s = (comment or "").strip() or "（待补充）"
    return f"""# `{fq}`

## 基本信息

| 项 | 内容 |
|----|------|
| 全名 | `{fq}` |
| 类型 | {table_type} / {engine or '-'} |
| 约行数 | {rows if rows is not None else '未知'} |
| 创建时间 | {created or '-'} |
| 表注释 | {comment_s} |

## 来源与用途（手工维护）

- **数据来源**：待补充（业务库同步 / 埋点 / ETL 任务名 / 上游表）
- **同步方式**：待补充（实时 / 日批 / 一次性导入）
- **更新频率**：待补充
- **业务含义**：待补充
- **建议粒度**：待补充（如 user_id × day）
- **主键 / 唯一键**：待补充
- **常用过滤**：待补充（软删、测试账号、有效状态等）
- **关联建议**：待补充（与哪些表 join、用什么键）
- **勿想当然**：待补充（易误用字段、同名异义等）

{_schema_markdown(cols)}

## 样例核对（可选）

```sql
SELECT * FROM {fq} LIMIT 20;
```
"""


def _upsert_doc(path: Path, schema: str, table: str, meta, cols) -> None:
    schema_md = _schema_markdown(cols)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if SCHEMA_BLOCK_RE.search(text):
            text = SCHEMA_BLOCK_RE.sub(schema_md, text)
        else:
            text = text.rstrip() + "\n\n" + schema_md + "\n"
        path.write_text(text, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _new_doc(
                schema,
                table,
                meta["table_type"],
                meta["engine"],
                meta["comment"],
                meta["rows"],
                meta["created"],
                cols,
            ),
            encoding="utf-8",
        )


def _write_index(tables: list, by_cols: dict) -> None:
    by_schema: dict[str, list] = defaultdict(list)
    for r in tables:
        by_schema[r[0]].append(r)

    lines = [
        "# 表目录 INDEX（仅 immdata）",
        "",
        "> 由 `python scripts/sync_table_catalog.py` 自动生成（只同步 `immdata`）。",
        "> 先读 [OVERVIEW.md](OVERVIEW.md)，再打开单表文档；禁止凭印象引用字段。",
        "",
        "## 统计",
        "",
        f"- Schema：immdata",
        f"- 表/视图合计：{len(tables)}",
        "",
        "## 表清单",
        "",
    ]
    for schema in sorted(by_schema.keys()):
        items = by_schema[schema]
        lines.append(f"### `{schema}`（{len(items)}）")
        lines.append("")
        lines.append("| 表 | 类型 | 约行数 | 注释 | 文档 |")
        lines.append("|----|------|--------|------|------|")
        for r in items:
            _schema, name, ttype, _engine, comment, rows, _created = r
            comment_s = (comment or "").replace("|", "\\|").replace("\n", " ")[:80]
            doc_rel = f"{schema}/{name}.md"
            lines.append(
                f"| `{name}` | {ttype} | {rows if rows is not None else '-'} | "
                f"{comment_s} | [{doc_rel}]({doc_rel}) |"
            )
        lines.append("")

    (TABLES_DIR / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tables = _fetch_tables()
    by_cols = _fetch_columns()

    meta_by_key = {}
    for r in tables:
        schema, name, ttype, engine, comment, rows, created = r
        meta_by_key[(schema, name)] = {
            "table_type": ttype,
            "engine": engine,
            "comment": comment,
            "rows": rows,
            "created": created,
        }
        path = TABLES_DIR / schema / f"{name}.md"
        _upsert_doc(path, schema, name, meta_by_key[(schema, name)], by_cols.get((schema, name), []))

    _write_index(tables, by_cols)
    print(f"Synced {len(tables)} tables -> {TABLES_DIR}")


if __name__ == "__main__":
    main()
