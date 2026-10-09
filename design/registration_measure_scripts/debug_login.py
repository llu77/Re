import functools, http.server, json, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location("measure_mod", str(Path(__file__).parent / "measure.py"))
folder = Path(sys.argv[1]); size = int(sys.argv[2]); width = int(sys.argv[3])
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(folder)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
port = httpd.server_address[1]
import re
css = re.sub(r"/\*.*?\*/", "", (folder / "styles.css").read_text(encoding="utf-8"), flags=re.S)
sel = [s.strip() for s, b in re.findall(r"([^{}]+)\{([^}]*)\}", css) if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", b)]
rules = " ".join(f"{s} {{ font-size: {size}px; }}" for s in sel)
script = ("(() => { const sheet = new CSSStyleSheet(); sheet.replaceSync(" + json.dumps(rules) + "); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    page = b.new_page(viewport={"width": width, "height": 635})
    page.route("**/app.js", lambda r: r.abort()); page.route("**/portal.js", lambda r: r.abort())
    page.add_init_script(script=script)
    page.goto(f"http://127.0.0.1:{port}/index.html")
    page.evaluate("async () => { await Promise.all([...document.fonts].map((f) => f.load().catch(() => null))); await document.fonts.ready; }")
    print("selectors with -apple-system-body:", sel)
    print(json.dumps(page.evaluate("""() => {
      document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== 'login'; });
      const s = document.querySelector('.screen[data-screen="login"]');
      const c = s.querySelector('.content');
      const r = (e) => { const b = e.getBoundingClientRect(); return [e.tagName + '#' + e.id + '.' + e.className, Math.round(b.top), Math.round(b.bottom), getComputedStyle(e).fontSize]; };
      return { content: r(c), sh: c.scrollHeight, ch: c.clientHeight, kids: [...c.querySelectorAll('*')].filter(e => e.getBoundingClientRect().height > 0).map(r) };
    }"""), ensure_ascii=False))
    b.close()
