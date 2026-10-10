import sys
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
out = []
for i, p in enumerate(r.pages, 1):
    out.append(f"\n=== PAGE {i} ===\n" + (p.extract_text() or ""))
open(sys.argv[2], "w", encoding="utf-8").write("".join(out))
print(len(r.pages))
