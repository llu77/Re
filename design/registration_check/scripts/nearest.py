"""
Where does a resting gaze land after «أنشئ حساباً» (login, top-end slot) opens the notice, and after
«رجوع» on the notice returns to the sign-in screen? Uses the repo's own NEAREST and LANDING scripts on
the measured variant (in-flight notice wording + this spec's edits + the entry on the sign-in screen).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/home/user/Re")
from eyework.tests.ui.conftest import VIEWPORTS  # noqa: E402
from eyework.tests.ui.flow import LANDING, NEAREST  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FOLDER = Path(sys.argv[1]) / "variants" / "E_screens"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

SHOW = """(name) => {
    document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== name; });
    document.querySelectorAll('.alert').forEach((a) => { a.hidden = true; });
}"""


def points(page, selector: str) -> list[list[float]]:
    box = page.locator(selector).bounding_box()
    inset = 8
    return [[box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
            [box["x"] + inset, box["y"] + inset], [box["x"] + box["width"] - inset, box["y"] + inset],
            [box["x"] + inset, box["y"] + box["height"] - inset],
            [box["x"] + box["width"] - inset, box["y"] + box["height"] - inset]]


def main() -> int:
    bad = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        for width, height in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height}, locale="ar-SA")

            def serve(route, request):
                path = request.url.split("http://local.test/", 1)[1] or "index.html"
                if path.endswith(".js"):
                    return route.abort()
                kind = {"html": "text/html; charset=utf-8", "css": "text/css", "woff2": "font/woff2"}
                route.fulfill(status=200, body=(FOLDER / path).read_bytes(),
                              content_type=kind.get(path.rsplit(".", 1)[-1], "application/octet-stream"))

            context.route("http://local.test/**", serve)
            page = context.new_page()
            page.goto("http://local.test/index.html")
            page.evaluate("async () => { await document.fonts.ready; }")
            for source, selector, target, label in (
                ("login", "#login-signup", "signup-notice", "أنشئ حساباً → الإشعار"),
                ("signup-notice", ".screen[data-screen='signup-notice'] [data-back]", "login", "رجوع → الدخول"),
            ):
                page.evaluate(SHOW, source)
                pts = points(page, selector)
                page.evaluate("(s) => { const e = document.querySelector(s); window.__activated = e;"
                              " window.__activatedKey = e.id || ''; }", selector)
                page.evaluate(SHOW, target)
                landing = page.evaluate(LANDING, pts)
                nearest = page.evaluate(NEAREST, pts)
                names = sorted({f"{n['name']}@{n['distance']}px" for n in nearest})
                commits = [n for n in nearest if n["commit"]]
                agree = [n for n in nearest if n["name"] == "signup-agree"]
                verdict = "ok  " if not landing and not commits and not agree else "FAIL"
                bad += verdict == "FAIL"
                print(f"{verdict} {width}x{height} {label}: landing={landing} nearest={names}")
            context.close()
        browser.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
