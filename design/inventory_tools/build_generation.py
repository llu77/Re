"""يستخرج ew_begin_generation من 0007 حرفاً بحرف، ويكتب نسخة NEXT بالسطرين المعلَّمين."""
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding="utf-8")
start = src.index("CREATE OR REPLACE FUNCTION ew_begin_generation(")
end = src.index("$$;\n", start) + len("$$;\n")
original = src[start:end]
Path(sys.argv[2]).write_text(original, encoding="utf-8")

old_global = """       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN"""
new_global = """       + (SELECT count(*) FROM attempt_tombstones
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
       -- NEXT_inventory: مراجعات المخزون من السقف نفسه.
       + (SELECT count(*) FROM inv_review_calls
           WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 2000 THEN"""
old_new = """               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN"""
new_new = """               + (SELECT count(*) FROM attempt_tombstones
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours')
               -- NEXT_inventory: ومراجعات الحسابات الجديدة من حصّتها.
               + (SELECT count(*) FROM inv_review_calls
                   WHERE new_account AND ew_is_billable(outcome) AND started_at > now() - interval '24 hours') >= 400 THEN"""
assert original.count(old_global) == 1 and original.count(old_new) == 1
modified = original.replace(old_global, new_global).replace(old_new, new_new)
Path(sys.argv[3]).write_text(modified, encoding="utf-8")
print(len(original), len(modified))
