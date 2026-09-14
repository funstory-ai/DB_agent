# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

QUERIES = [
    "SHOW TASKS LIKE '%event_device_count%'",
    "SHOW TASKS LIKE '%utf8_day%'",
]

for sql in QUERIES:
    print(f"\n=== {sql} ===", flush=True)
    try:
        cols, rows = query(sql)
        print(cols, flush=True)
        for r in rows:
            print(r, flush=True)
    except Exception as e:
        print("ERR:", e, flush=True)

# Try describe task if we find name
try:
    cols, rows = query("SHOW TASKS")
    print("\n=== ALL TASKS (filter event) ===", flush=True)
    for r in rows:
        s = str(r)
        if 'event_device' in s.lower() or 'utf8_day' in s.lower():
            print(r, flush=True)
except Exception as e:
    print("SHOW TASKS all ERR:", e, flush=True)
