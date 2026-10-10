"""0001–0007 ثم NEXT صعوداً ونزولاً وصعوداً، مع مقارنة pg_dump. قاعدةٌ مؤقتة تُحذف في آخره."""
import os
import subprocess
import sys
from pathlib import Path

import psycopg

MIG = Path(sys.argv[1])
DB = sys.argv[2]
OWNER = f"postgresql://eyework_owner:eyework_dev_owner@localhost:5432/{DB}"


def pg(sql: str) -> None:
    subprocess.run(["su", "postgres", "-c", f'psql -qtAX -c "{sql}"'], check=True)


def files(direction: str) -> list[Path]:
    found = sorted(MIG.glob(f"*.{direction}.sql"))
    return found if direction == "up" else list(reversed(found))


def apply(path: Path) -> None:
    with psycopg.connect(OWNER, autocommit=True) as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))


def dump() -> str:
    out = subprocess.run(["pg_dump", "--schema-only", "--no-owner", OWNER], check=True, capture_output=True, text=True).stdout
    return "\n".join(line for line in out.splitlines() if not line.startswith("-- Dumped") and "\\restrict" not in line and "\\unrestrict" not in line)


pg(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
pg(f"CREATE DATABASE {DB} OWNER eyework_owner")
ups = files("up")
base = [p for p in ups if not p.name.startswith("0008")]
nxt_up = MIG / "0008_inventory.up.sql"
nxt_down = MIG / "0008_inventory.down.sql"
for p in base:
    apply(p)
a = dump()
apply(nxt_up)
b = dump()
apply(nxt_down)
c = dump()
apply(nxt_up)
d = dump()
print("down restores 0007 exactly:", a == c)
print("second up equals first up:", b == d)
# نزولٌ كامل إلى الفراغ ثم صعود
for p in files("down"):
    apply(p)
empty = dump()
for p in files("up"):
    apply(p)
e = dump()
print("full down then up equals first up:", e == b)
if a != c:
    import difflib
    print("\n".join(list(difflib.unified_diff(a.splitlines(), c.splitlines(), lineterm=""))[:80]))
if len(sys.argv) > 3 and sys.argv[3] == "keep":
    print("kept", DB)
else:
    pg(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
