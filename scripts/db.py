"""Databend 只读连接封装。禁止在此模块中执行写操作。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from databend_driver import BlockingDatabendClient
from dotenv import load_dotenv

# 项目根目录的 .env
_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

# 粗粒度拦截：语句中出现写操作关键字则拒绝执行
_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|ALTER|CREATE|REPLACE|"
    r"COPY\s+INTO|REMOVE|UNDROP|OPTIMIZE|VACUUM|GRANT|REVOKE|SET\s+ROLE)\b",
    re.IGNORECASE,
)


def _dsn() -> str:
    host = os.environ["DATABEND_HOST"]
    port = os.environ.get("DATABEND_PORT", "443")
    user = os.environ["DATABEND_USER"]
    password = os.environ["DATABEND_PASSWORD"]
    database = os.environ.get("DATABEND_DATABASE", "immdata")
    warehouse = os.environ.get("DATABEND_WAREHOUSE", "default")
    return (
        f"databend://{user}:{password}@{host}:{port}/{database}"
        f"?warehouse={warehouse}"
    )


def get_cursor():
    """返回只读用途的 cursor（调用方仍须只发 SELECT/元数据语句）。"""
    client = BlockingDatabendClient(_dsn())
    return client.cursor()


def assert_readonly(sql: str) -> None:
    """若 SQL 含写操作关键字则抛错。"""
    if _WRITE_PATTERN.search(sql):
        raise PermissionError(
            "本项目仅允许只读查询，禁止执行写操作 / DDL。SQL 已拦截。"
        )


def _row_to_tuple(row) -> tuple:
    if hasattr(row, "values"):
        vals = row.values()
        return tuple(vals) if not isinstance(vals, tuple) else vals
    return tuple(row)


def query(sql: str):
    """执行只读 SQL，返回 (columns, rows)。"""
    assert_readonly(sql)
    cursor = get_cursor()
    try:
        cursor.execute(sql)
        raw = cursor.fetchall()
        rows = [_row_to_tuple(r) for r in raw]
        columns = [d[0] for d in (cursor.description or [])]
        return columns, rows
    finally:
        cursor.close()


if __name__ == "__main__":
    cols, rows = query("SELECT 1 AS ok")
    print(cols, rows)
