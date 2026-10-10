"""
Measure the proposed open-registration copy against the gaze contract.

Serves a copy of eyework/static (current and proposed), blocks app.js and
portal.js so nothing boots, shows one screen at a time and runs the repo's own
AUDIT / LANDING / NEAREST scripts from tests/ui/flow.py at every viewport and
at the three iOS Text Size body sizes used by tests/ui/test_text_size.py.

    python3 measure.py <measure_root> <eyework_root>
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

ROOT = Path(sys.argv[1])
EYEWORK = Path(sys.argv[2])
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
VIEWPORTS = [(375, 635), (390, 664), (390, 763), (320, 635), (1280, 800)]
SIZES = [None, 17, 23, 53]

flow_ns: dict = {}
exec(compile((EYEWORK / "tests/ui/flow.py").read_text(encoding="utf-8"), "flow.py", "exec"), flow_ns)
AUDIT, LANDING, NEAREST = flow_ns["AUDIT"], flow_ns["LANDING"], flow_ns["NEAREST"]


def system_font_rules(styles: Path) -> list[str]:
    css = re.sub(r"/\*.*?\*/", "", styles.read_text(encoding="utf-8"), flags=re.S)
    return [selector.strip() for selector, block in re.findall(r"([^{}]+)\{([^}]*)\}", css)
            if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", block)]


def body_script(styles: Path, px: int) -> str:
    rules = " ".join(f"{s} {{ font-size: {px}px; }}" for s in system_font_rules(styles))
    return ("(() => { const sheet = new CSSStyleSheet();"
            f" sheet.replaceSync({json.dumps(rules)});"
            " document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();")


def serve(directory: Path) -> int:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


SHOW = """
(name) => {
    document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== name; });
    return document.querySelector(`.screen[data-screen="${name}"]`) !== null;
}
"""

#: What renderLogin would do in open mode with an operator contact (proposed client).
OPEN_LOGIN = """
(contact) => {
    const button = document.getElementById('login-signup');
    if (button) button.hidden = false;
    const help = document.getElementById('login-help');
    if (help && contact) {
        const bdi = document.createElement('bdi');
        bdi.dir = 'ltr';
        bdi.textContent = contact;
        help.replaceChildren('تعذّر الدخول؟ اكتب إلى مشغّل التطبيق من بريد حسابك: ', bdi);
    }
}
"""


def bad(audit: dict) -> list[str]:
    out = []
    for key in ("small", "close", "edge", "fonts", "clipped"):
        if audit[key]:
            out.append(f"{key}={audit[key]}")
    if audit["enabled"] > 10:
        out.append(f"enabled={audit['enabled']}")
    if audit["vertical"] or audit["horizontal"]:
        out.append("scroll")
    return out


def press_points(page, selector: str) -> list[list[float]]:
    box = page.locator(selector).bounding_box()
    page.locator(selector).evaluate(
        "(e) => { window.__activated = e; window.__activatedKey = e.id || e.dataset.key || ''; }")
    inset = 8
    return [
        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
        [box["x"] + inset, box["y"] + inset],
        [box["x"] + box["width"] - inset, box["y"] + inset],
        [box["x"] + inset, box["y"] + box["height"] - inset],
        [box["x"] + box["width"] - inset, box["y"] + box["height"] - inset],
    ]


def main() -> int:
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        for variant in ("current", "proposed"):
            folder = ROOT / variant
            port = serve(folder)
            styles = folder / "styles.css"
            screens = ["signup-notice", "signup-email", "signup-review", "signup-profession", "login"]
            for width, height in VIEWPORTS:
                for size in SIZES:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    page = context.new_page()
                    page.route("**/app.js", lambda r: r.abort())
                    page.route("**/portal.js", lambda r: r.abort())
                    if size:
                        page.add_init_script(script=body_script(styles, size))
                    page.goto(f"http://127.0.0.1:{port}/index.html")
                    page.wait_for_load_state("load")
                    page.evaluate("async () => { await Promise.all([...document.fonts].map((f) => f.load().catch(() => null))); await document.fonts.ready; }")
                    for screen in screens:
                        page.evaluate(SHOW, screen)
                        if screen == "login" and variant == "proposed":
                            page.evaluate(OPEN_LOGIN, "operator.support@example.com")
                        if screen == "signup-review":
                            page.evaluate("""() => {
                                const set = (id, t) => { const e = document.getElementById(id); if (e) e.textContent = t; };
                                set('signup-review-name', 'الاسم: عبدالرحمن محمد');
                                set('signup-review-birth', 'تاريخ الميلاد: 28 سبتمبر 1990');
                                set('signup-review-profession', 'المهنة: أمين المخزون');
                                set('signup-review-email', 'abdulrahman.mohammed.alotaibi@example.com');
                            }""")
                        audit = page.evaluate(AUDIT)
                        key = f"{variant} {screen} {width}x{height} body{size or '-'}"
                        report[key] = bad(audit)
                    if variant == "proposed":
                        # login «أنشئ حساباً» -> signup-notice, then notice «رجوع» -> login.
                        page.evaluate(SHOW, "login")
                        page.evaluate(OPEN_LOGIN, "operator.support@example.com")
                        points = press_points(page, "#login-signup")
                        page.evaluate(SHOW, "signup-notice")
                        landing = page.evaluate(LANDING, points)
                        nearest = page.evaluate(NEAREST, points)
                        report[f"press login-signup {width}x{height} body{size or '-'}"] = (
                            landing + [f"nearest-commit {n['name']}" for n in nearest if n["commit"]])
                        points = press_points(page, ".screen[data-screen='signup-notice'] [data-back]")
                        page.evaluate(SHOW, "login")
                        page.evaluate(OPEN_LOGIN, "operator.support@example.com")
                        landing = page.evaluate(LANDING, points)
                        nearest = page.evaluate(NEAREST, points)
                        report[f"press notice-back {width}x{height} body{size or '-'}"] = (
                            landing + [f"nearest-commit {n['name']}" for n in nearest if n["commit"]])
                        # notice heights for the record
                        page.evaluate(SHOW, "signup-notice")
                        spare = page.evaluate("""() => {
                            const c = document.querySelector('.screen[data-screen="signup-notice"] .content');
                            const last = [...c.querySelectorAll('p.line')].pop();
                            return Math.round(c.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom);
                        }""")
                        report[f"spare notice {width}x{height} body{size or '-'}"] = spare
                    else:
                        page.evaluate(SHOW, "signup-notice")
                        spare = page.evaluate("""() => {
                            const c = document.querySelector('.screen[data-screen="signup-notice"] .content');
                            const last = [...c.querySelectorAll('p.line')].pop();
                            return Math.round(c.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom);
                        }""")
                        report[f"spare-current notice {width}x{height} body{size or '-'}"] = spare
                    context.close()
        browser.close()
    failures = {k: v for k, v in report.items() if isinstance(v, list) and v}
    print(json.dumps({"failures": failures,
                      "spare": {k: v for k, v in report.items() if k.startswith("spare")}},
                     ensure_ascii=False, indent=1))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
