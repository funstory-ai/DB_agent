# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query

cols, rows = query("SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'")
for r in rows:
    name = r[1]
    if name not in (
        "update_imm_event_device_count_by_utf8_day",
        "update_imm_event_device_count_by_utf8_day_M",
    ):
        continue
    d = str(r[8])
    print("NAME:", name)
    print("STATE:", r[7])
    print("HAS_embed:", "embed_device_day" in d)
    print("HAS_Safari:", "Safari" in d)
    print("HAS_Maxthon:", "Maxthon" in d)
    print("HAS_ios:", "ios" in d.lower() and "os_name" in d)
    print("HAS_macos:", "macos" in d.lower())
    # print snippet around kick
    idx = d.find("official_userscript")
    print("SNIP:", d[max(0, idx - 80) : idx + 280] if idx >= 0 else "none")
    print("---")
