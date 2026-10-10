"""Try wording variants for the notice and the login help line.

    python3 variants.py <static folder> <variants.json>

variants.json: {"notice": {"name": [line1, line2, line3]}, "login_help": {"name": "text with {contact}"}}
Prints, per variant, overflow in px (positive = clipped) at the tight viewports and body sizes.
"""

from __future__ import annotations

import functools
import http.server
import json
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

FOLDER = Path(sys.argv[1])
VARIANTS = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
CONTACT = "operator.support@example.com"
CASES = [(320, 635, None), (320, 635, 23), (375, 635, None), (375, 635, 23)]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        pass


def body_script(px: int) -> str:
    css = re.sub(r"/\*.*?\*/", "", (FOLDER / "styles.css").read_text(encoding="utf-8"), flags=re.S)
    selectors = [s.strip() for s, b in re.findall(r"([^{}]+)\{([^}]*)\}", css)
                 if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", b)]
    rules = " ".join(f"{s} {{ font-size: {px}px; }}" for s in selectors)
    return ("(() => { const sheet = new CSSStyleSheet(); sheet.replaceSync(" + json.dumps(rules)
            + "); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();")


OVERFLOW = """
(name) => {
    document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== name; });
    const c = document.querySelector(`.screen[data-screen="${name}"] .content`);
    const box = c.getBoundingClientRect();
    const bottoms = [...c.querySelectorAll('*')].filter((e) => !e.closest('[hidden]') && !e.closest('.alert'))
        .map((e) => e.getBoundingClientRect()).filter((r) => r.height > 0).map((r) => r.bottom);
    return Math.round(Math.max(...bottoms) - box.bottom);
}
"""


def main() -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(FOLDER)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                                    args=["--no-sandbox"])
        for width, height, size in CASES:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.route("**/app.js", lambda r: r.abort())
            page.route("**/portal.js", lambda r: r.abort())
            if size:
                page.add_init_script(script=body_script(size))
            page.goto(f"http://127.0.0.1:{port}/index.html")
            page.evaluate("async () => { await Promise.all([...document.fonts].map((f) => f.load()"
                          ".catch(() => null))); await document.fonts.ready; }")
            label = f"{width}x{height} body{size or 17}"
            for name, lines in VARIANTS.get("notice", {}).items():
                page.evaluate("""(lines) => {
                    const ps = document.querySelectorAll('.screen[data-screen="signup-notice"] .content > p.line');
                    ps.forEach((p, i) => { p.textContent = lines[i] || ''; p.hidden = !lines[i]; });
                }""", lines)
                print(f"notice {name:12} {label:18} overflow {page.evaluate(OVERFLOW, 'signup-notice')}")
            for name, text in VARIANTS.get("login_help", {}).items():
                page.evaluate("""([text, contact]) => {
                    const help = document.querySelector('.screen[data-screen="login"] p.help');
                    const [before, after] = text.split('{contact}');
                    const bdi = document.createElement('bdi'); bdi.dir = 'ltr'; bdi.textContent = contact;
                    if (after === undefined) { help.replaceChildren(before); } else { help.replaceChildren(before, bdi, after); }
                    const button = document.getElementById('login-signup'); if (button) button.hidden = false;
                }""", [text, CONTACT])
                print(f"login  {name:12} {label:18} overflow {page.evaluate(OVERFLOW, 'login')}")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
