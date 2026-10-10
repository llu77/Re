import hashlib, sys
from pathlib import Path
sys.path.insert(0, "/home/user/Re")
import eyework.tests.unit.test_terms as terms
for name in sys.argv[2:]:
    terms.INDEX = Path(sys.argv[1]) / "variants" / name / "index.html"
    text = terms._notice_text()
    print(name, hashlib.sha256(text.encode()).hexdigest())
    print("  ", text)
