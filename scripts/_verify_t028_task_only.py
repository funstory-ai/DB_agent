import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import query
cols, rows = query("SHOW TASKS LIKE 'update_imm_event_device_count_by_utf8_day%'")
print("tasks found:", len(rows))
for r in rows:
    print("\nNAME:", r[1])
    print("STATE:", r[7])
    print("SCHEDULE:", r[6])
    print("LAST_COMPLETED:", r[14] if len(r) > 14 else "?")
    print("NEXT:", r[13] if len(r) > 13 else "?")
    d = str(r[8])
    print("HAS_EMBED_CTE:", "embed_device_day" in d)
    print("HAS_KICK:", "official_userscript" in d)
