import functools, http.server, json, re, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
folder = Path(sys.argv[1])
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(folder)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
ns = {}; exec(compile(Path("/home/user/Re/eyework/tests/ui/flow.py").read_text(encoding="utf-8"), "flow.py", "exec"), ns)
css = re.sub(r"/\*.*?\*/", "", (folder / "styles.css").read_text(encoding="utf-8"), flags=re.S)
sel = [s.strip() for s, b in re.findall(r"([^{}]+)\{([^}]*)\}", css) if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", b)]
def script(px):
    rules = " ".join(f"{s} {{ font-size: {px}px; }}" for s in sel)
    return "(() => { const s = new CSSStyleSheet(); s.replaceSync(" + json.dumps(rules) + "); document.adoptedStyleSheets = [...document.adoptedStyleSheets, s]; })();"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
    for (w, h) in [(320, 635), (375, 635), (390, 664), (390, 763), (1280, 800)]:
        for size in [None, 23, 53]:
            page = b.new_page(viewport={"width": w, "height": h})
            page.route("**/app.js", lambda r: r.abort()); page.route("**/portal.js", lambda r: r.abort())
            if size: page.add_init_script(script=script(size))
            page.goto(f"http://127.0.0.1:{port}/index.html")
            page.evaluate("async () => { await Promise.all([...document.fonts].map((f) => f.load().catch(() => null))); await document.fonts.ready; }")
            page.evaluate("""() => {
                document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== 'login'; });
                const s = document.querySelector('.screen[data-screen="login"]');
                s.querySelector('h2').classList.add('visually-hidden');
                s.querySelector('.bar--top .step').textContent = 'تسجيل الدخول';
                document.getElementById('login-signup').hidden = false;
                const help = document.getElementById('login-help');
                const bdi = document.createElement('bdi'); bdi.dir = 'ltr'; bdi.textContent = 'operator.support@example.com';
                help.replaceChildren('نسيت كلمة المرور؟ اكتب من بريد حسابك إلى ', bdi);
            }""")
            a = page.evaluate(ns["AUDIT"])
            bad = [f"{k}={a[k]}" for k in ("small", "close", "edge", "fonts", "clipped") if a[k]]
            if a["vertical"] or a["horizontal"]: bad.append("scroll")
            if a["enabled"] > 10: bad.append(f"enabled={a['enabled']}")
            print(f"{w}x{h} body{size or 17}: {'OK' if not bad else bad} enabled={a['enabled']}")
            page.close()
    b.close()
