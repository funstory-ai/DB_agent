# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

TARGETS = [
    'update_imm_event_device_count_by_utf8_day',
    'update_imm_event_device_count_by_utf8_day_M',
    'update_imm_app_new_event_device_count_by_utf8_day',
]

cols, rows = query("SHOW TASKS")
out = Path(__file__).resolve().parents[1] / 'output' / 'task_def_event_device_count.txt'
out.parent.mkdir(exist_ok=True)

with out.open('w', encoding='utf-8') as f:
    for r in rows:
        name = r[1] if len(r) > 1 else str(r)
        if name in TARGETS:
            f.write(f"\n{'='*80}\nTASK: {name}\n{'='*80}\n")
            # definition usually last column
            defn = r[-2] if 'Started' in str(r[-3]) else r[-1]
            for i, c in enumerate(r):
                f.write(f"[{i}] {c}\n\n")
print('written', out)
