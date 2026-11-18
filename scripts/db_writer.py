"""T119 受控写入通道：Google Ads 数据接入 Databend 专用。

背景：scripts/db.py 用正则强制只读（项目纪律，不改它）。实测账号 'cloudapp'@'%'
在 *.* 上有 CREATE/INSERT/DELETE/DROP 等全权限，因此「接进 Databend」只需新增
一条受控写通道，不需要 BigQuery / 外部文件中转。

安全边界（本模块强制）：
  1. 写操作的目标对象必须以 growth. 开头，或为 CREATE DATABASE growth；
  2. 对 immdata / webdata / 其它库的一切写操作一律拒绝；
  3. 只读语句（SELECT/SHOW/DESCRIBE/EXPLAIN）放行，便于脚本自检。
连接默认库用 default（一定存在），所有对象一律写全限定名 growth.<table>。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from databend_driver import BlockingDatabendClient
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

ALLOWED_SCHEMA = "growth"

_OBJ_RE = re.compile(
    r"\b(?:INSERT\s+INTO|DELETE\s+FROM|UPDATE|TRUNCATE(?:\s+TABLE)?|"
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|"
    r"DROP\s+TABLE(?:\s+IF\s+EXISTS)?|ALTER\s+TABLE|"
    r"CREATE\s+DATABASE(?:\s+IF\s+NOT\s+EXISTS)?|"
    r"REPLACE\s+INTO|COPY\s+INTO)\s+([A-Za-z_][\w.]*)",
    re.IGNORECASE,
)
_WRITE_START_RE = re.compile(
    r"^\s*(INSERT|DELETE|UPDATE|TRUNCATE|CREATE|DROP|ALTER|REPLACE|COPY|MERGE|GRANT|REVOKE|SET|OPTIMIZE|VACUUM)\b",
    re.IGNORECASE,
)


def _dsn() -> str:
    host = os.environ["DATABEND_HOST"]
    port = os.environ.get("DATABEND_PORT", "443")
    user = os.environ["DATABEND_USER"]
    password = os.environ["DATABEND_PASSWORD"]
    warehouse = os.environ.get("DATABEND_WAREHOUSE", "default")
    return f"databend://{user}:{password}@{host}:{port}/default?warehouse={warehouse}"


def get_cursor():
    client = BlockingDatabendClient(_dsn())
    return client.cursor()


def guard(sql: str) -> None:
    """拒绝任何非 growth 库目标的写操作。"""
    if not _WRITE_START_RE.match(sql):
        return  # 只读语句放行
    objs = _OBJ_RE.findall(sql)
    if not objs:
        raise PermissionError(f"写语句无法解析目标对象，已拒绝：{sql[:120]}")
    for obj in objs:
        parts = obj.split(".")
        if parts[0].strip('`"') != ALLOWED_SCHEMA:
            raise PermissionError(
                f"禁止写入 {obj}：本通道只允许 {ALLOWED_SCHEMA} 库（保护 immdata/webdata）。"
            )


def execute(sql: str):
    """执行一条受控语句，返回 (columns, rows)。"""
    guard(sql)
    cursor = get_cursor()
    try:
        cursor.execute(sql)
        desc = cursor.description or []
        cols = [d[0] for d in desc]
        rows = []
        if cols:
            raw = cursor.fetchall()
            for r in raw:
                rows.append(tuple(r.values()) if hasattr(r, "values") else tuple(r))
        return cols, rows
    finally:
        cursor.close()


def sql_quote(value) -> str:
    """生成 SQL 字面量（防注入用；CSV/API 文本可能含引号与分号）。"""
    if value is None or value == "":
        return "''"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def sql_num(value, default="0") -> str:
    if value is None or value == "":
        return default
    return str(value)
