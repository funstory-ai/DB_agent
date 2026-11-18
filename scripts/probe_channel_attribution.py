"""T119 渠道归因字段可行性探查（只读）。

按 sql/reports/probe_channel_attribution_fields_20261116.sql 的 @Qn 分段执行，
打印每段的列名与结果。可传参只跑指定段：python scripts/probe_channel_attribution.py Q1 Q3
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db import query  # noqa: E402

SQL_FILE = ROOT / "sql" / "reports" / "probe_channel_attribution_fields_20261116.sql"


def q(sql: str, retries: int = 6):
    """只读查询 + 指数退避重试（覆盖 OSS AccessDenied 等瞬态）。"""
    d = 2.0
    for i in range(retries):
        try:
            return query(sql)
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i + 1} ({d:.0f}s): {str(e)[:160]}", flush=True)
            time.sleep(d)
            d *= 2


def load_parts() -> dict[str, str]:
    text = SQL_FILE.read_text(encoding="utf-8")
    parts, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^--\s+@([A-Za-z0-9_]+)\b", line)
        if m:
            if cur:
                parts[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        parts[cur] = "\n".join(buf)
    out = {}
    for k, v in parts.items():
        v = "\n".join(l for l in v.splitlines() if not l.strip().startswith("--"))
        v = v.strip().rstrip(";").strip()
        if v.upper().startswith(("SELECT", "WITH")):
            out[k] = v
    return out


def main() -> None:
    wanted = set(a.upper() for a in sys.argv[1:])
    parts = load_parts()
    for name in sorted(parts):
        if wanted and name not in wanted:
            continue
        print(f"\n=== {name} ===", flush=True)
        t = time.time()
        cols, rows = q(parts[name])
        print("cols:", cols, flush=True)
        for r in rows[:30]:
            print(r, flush=True)
        print(f"rows={len(rows)} elapsed={time.time() - t:.1f}s", flush=True)


if __name__ == "__main__":
    main()
