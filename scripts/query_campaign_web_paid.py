"""T097: run a read-only SQL file, retaining aggregate evidence locally."""
import argparse
import json
import os
from urllib.parse import quote
from datetime import datetime, timezone
from pathlib import Path
import db
from dotenv import load_dotenv

# DSN components must be encoded; credentials stay in .env and are never logged.
def encoded_dsn():
    return ('databend://' + quote(os.environ['DATABEND_USER'], safe='') + ':'
            + quote(os.environ['DATABEND_PASSWORD'], safe='') + '@'
            + os.environ['DATABEND_HOST'] + ':' + os.environ.get('DATABEND_PORT','443')
            + '/' + os.environ.get('DATABEND_DATABASE','immdata')
            + '?warehouse=' + quote(os.environ.get('DATABEND_WAREHOUSE','default'), safe=''))

db._dsn = encoded_dsn

p = argparse.ArgumentParser()
p.add_argument('sql', type=Path)
p.add_argument('--output', type=Path)
p.add_argument('--env-file', type=Path)
a = p.parse_args()
if a.env_file:
    load_dotenv(a.env_file, override=True)
sql = a.sql.read_text()
columns, rows = db.query(sql)
result = {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
          'sql': sql, 'columns': columns, 'rows': rows}
if a.output:
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
print(json.dumps(result, ensure_ascii=False, default=str))
