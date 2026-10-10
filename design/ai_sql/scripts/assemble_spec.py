"""Assemble ai_spec.md from the three parts and the verified SQL files; fail if the SQL differs."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
base = ROOT / "ai_sql"
doc = "".join((base / "src" / f"spec_part{i}.md").read_text(encoding="utf-8") for i in (1, 2, 3))
up = (base / "NEXT_ai_layer.up.sql").read_text(encoding="utf-8").rstrip("\n")
down = (base / "NEXT_ai_layer.down.sql").read_text(encoding="utf-8").rstrip("\n")
assert doc.count("{{UP_SQL}}") == 1 and doc.count("{{DOWN_SQL}}") == 1
doc = doc.replace("{{UP_SQL}}", up).replace("{{DOWN_SQL}}", down)
blocks = re.findall(r"```sql\n(.*?)\n```", doc, re.S)
assert up in blocks and down in blocks
(ROOT / "ai_spec.md").write_text(doc, encoding="utf-8")
print("ai_spec.md:", doc.count("\n"), "lines; embedded SQL identical to the verified files")
