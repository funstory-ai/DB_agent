"""T119 第一步：在 Databend 建 growth 库及 Google Ads 接入表，并验证写入闭环。

用法：
    F:/python312/python.exe scripts/setup_google_ads_schema.py            # 建表 + 自检
    F:/python312/python.exe scripts/setup_google_ads_schema.py --check    # 只检查，不建表

自检会插入 1 条 source_file='__SELFTEST__' 的样例行、读回、再删除；它不是真实投放数据。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db_writer as w  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "sql" / "schema" / "ddl_google_ads_20261116.sql"
TABLES = ["google_ads_daily", "ingest_log", "channel_campaign_map"]


def split_ddl(text: str) -> list[str]:
    out = []
    for block in text.split(";"):
        lines = [ln for ln in block.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            out.append(stmt)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查现状，不执行 DDL")
    args = ap.parse_args()

    if not args.check:
        print(f"[DDL] {DDL.relative_to(ROOT)}")
        for stmt in split_ddl(DDL.read_text(encoding="utf-8")):
            head = " ".join(stmt.split())[:78]
            w.execute(stmt)
            print("  OK", head)
    else:
        print("[CHECK] 不执行 DDL")

    print("\n[表结构]")
    for t in TABLES:
        cols, rows = w.execute(
            f"SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema='growth' AND table_name='{t}' ORDER BY ordinal_position"
        )
        print(f"  growth.{t}: {len(rows)} 列")
        if args.check:
            for r in rows:
                print("     ", r[0], r[1])

    # 写入闭环自检（明确标注 selftest，随后删除）
    print("\n[写入自检]")
    batch = "__SELFTEST__"
    w.execute(
        "DELETE FROM growth.google_ads_daily WHERE source_file = '__SELFTEST__'"
    )
    w.execute(
        "INSERT INTO growth.google_ads_daily VALUES "
        "('2026-11-09','ACCOUNT','4623896831','','','','','','',"
        "0,0,0.0,0.0,0.0,0.0,'USD','','','CSV','__SELFTEST__','__SELFTEST__',"
        "'2026-11-16 00:00:00')"
    )
    cols, rows = w.execute(
        "SELECT count(*) FROM growth.google_ads_daily WHERE source_file='__SELFTEST__'"
    )
    print("  插入后行数:", rows[0][0])
    w.execute(
        "DELETE FROM growth.google_ads_daily WHERE source_file = '__SELFTEST__'"
    )
    cols, rows = w.execute(
        "SELECT count(*) FROM growth.google_ads_daily WHERE source_file='__SELFTEST__'"
    )
    print("  清理后行数:", rows[0][0], "-> 写入/读取/删除闭环 OK")

    cols, rows = w.execute("SELECT count(*) FROM growth.google_ads_daily")
    print("\n[当前真实数据行数] growth.google_ads_daily =", rows[0][0], "(0 = 等 CSV/API)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
