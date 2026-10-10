"""Replica of tests/unit/test_terms.py: digest of the notice section's visible text."""
import hashlib, re, sys
from html.parser import HTMLParser
from pathlib import Path

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self._skip = 0
    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if self._skip or "alert" in classes:
            self._skip += 1
    def handle_endtag(self, tag):
        if self._skip:
            self._skip -= 1
    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

for path in sys.argv[1:]:
    page = Path(path).read_text(encoding="utf-8")
    section = re.search(r'<section class="screen" data-screen="signup-notice".*?</section>', page, re.S)
    parser = _Text(); parser.feed(section.group(0))
    text = re.sub(r"\s+", " ", "".join(parser.parts)).strip()
    print(hashlib.sha256(text.encode("utf-8")).hexdigest(), path)
    print("   ", text)
