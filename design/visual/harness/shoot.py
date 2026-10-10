"""
Screenshots and gaze-contract measurements for the redesign prototype.

Runs the built client behind harness/serve.py (real CSP), then:
  1. renders every prototype screen at 390x844 @2x (mock_<name>.png) and at 375x635
     @2x (mock_<name>_375x635.png);
  2. runs the repo's own AUDIT script (eyework/tests/ui/flow.py) on every screen at
     375x635, 390x664, 390x763, 320x635 (stress), 1280x800 and 390x844, plus
     Increase Contrast and iOS Text Size (Body 53pt) at the tightest frames;
  3. presses through the prototype's transitions and runs LANDING and NEAREST after
     each press, as Flow.press does;
  4. records timers, listeners (with their target), CSP violations and foreign requests.

Writes measure.json next to the screenshots and prints a summary.
Usage: python3 shoot.py <redesign dir>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/user/Re")
from eyework.tests.ui.flow import AUDIT, LANDING, NEAREST  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(sys.argv[1]).resolve()          # redesign/: screenshots and measure.json land here
WORK = ROOT / "visual"                       # this track's client, harness and fixtures
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"

INSTRUMENT = r"""
(() => {
    const log = { timers: [], listeners: [], csp: [] };
    Object.defineProperty(window, '__eyework', { value: log });
    const app = (stack) => /\/assets\/[^/]+\.js/.test(stack || '');
    for (const name of ['setTimeout', 'setInterval', 'requestAnimationFrame', 'requestIdleCallback']) {
        const original = window[name];
        if (!original) continue;
        window[name] = function (...args) {
            if (app(new Error().stack)) log.timers.push(name);
            return original.apply(this, args);
        };
    }
    const add = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (type, ...rest) {
        if (app(new Error().stack)) {
            const t = this === window ? 'window' : this === document ? 'document'
                : (this && this.id ? '#' + this.id : (this && this.nodeName) || '?');
            log.listeners.push(t + ':' + type);
        }
        return add.call(this, type, ...rest);
    };
    document.addEventListener('securitypolicyviolation', (e) => log.csp.push(e.violatedDirective + ' ' + e.blockedURI));
})();
"""

TEXT_SIZE = """
(() => { const sheet = new CSSStyleSheet();
  sheet.replaceSync('.screen { font-size: 53px; }');
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();
"""

SIGNED_IN = [{"name": "proto_session", "value": "1", "url": BASE}]
WITH_TOOL = SIGNED_IN + [{"name": "proto_tool", "value": "1", "url": BASE}]

# name, hash, cookies, screen, preparation (list of (action, selector[, value]))
SCENES = [
    ("welcome", "#/welcome", [], "welcome", []),
    ("login", "#/login", [], "login", []),
    ("login_alert", "#/login", [], "login", [("fill", "#login-username", "sara@example.sa"),
                                               ("fill", "#login-password", "wrong-password"),
                                               ("click", "#login-submit"), ("wait", ".alert:not([hidden])")]),
    ("signup_notice", "#/signup", [], "signup-notice", []),
    ("signup_name", "#/signup/name", [], "signup-name", [("fill", "#signup-name-input", "سارة")]),
    ("signup_year", "#/signup/year", [], "signup-year", [("click", "#signup-year-presets .chip >> nth=3"),
                                                          ("wait", "#signup-year-next:not([disabled])")]),
    ("home", "#/", SIGNED_IN, "home", [("wait", "#home-actions:not([hidden])")]),
    ("home_tool", "#/", WITH_TOOL, "home", [("wait", "#home-tool")]),
    ("about", "#/about", SIGNED_IN, "about", [("wait", "#home-about:not(:empty)")]),
    ("portal_item", "#/tasks/1", SIGNED_IN, "portal-item", [("wait", "#portal-item-text:not(:empty)")]),
    ("portal_skill", "#/skills/2", SIGNED_IN, "portal-item", [("wait", "#portal-item-text:not(:empty)")]),
    ("assistant", "#/assistant", SIGNED_IN, "assistant", [("wait", "#assistant-suggestions .chip"),
                                                         ("click", "#assistant-suggestions .chip >> nth=0")]),
    ("assistant_answer", "#/assistant", SIGNED_IN, "assistant-answer", [
        ("wait", "#assistant-suggestions .chip"), ("click", "#assistant-suggestions .chip >> nth=0"),
        ("click", "#assistant-ask"), ("wait", "#assistant-answer-text")]),
    ("assistant_write", "#/assistant/write", SIGNED_IN, "assistant-write", []),
    ("account", "#/account", SIGNED_IN, "account", [("wait", "#account-profession [data-slot=badge]")]),
    ("logout", "#/account/logout", SIGNED_IN, "account-logout", []),
]

FRAMES = [(375, 635), (390, 664), (390, 763), (320, 635), (1280, 800), (390, 844)]
TIGHT = [(375, 635), (320, 635)]

# (label, scene name to start from, press selector, settle selector)
PRESSES = [
    ("ادخل (welcome)", "welcome", "#welcome-login", ".screen[data-screen=login]"),
    ("أنشئ حساباً (welcome)", "welcome", "#welcome-signup", ".screen[data-screen=signup-notice]"),
    ("أوافق وأتابع", "signup_notice", "#signup-agree", ".screen[data-screen=signup-name]"),
    ("التالي (name)", "signup_name", "#signup-name-next", ".screen[data-screen=signup-year]"),
    ("سنة جاهزة", "signup_year", "#signup-year-presets .chip >> nth=4", "#signup-year-presets [aria-pressed=true]"),
    ("أحدث (year)", "signup_year", "#signup-year-up", "#signup-year-value"),
    ("حسابي", "home", "#home-account", ".screen[data-screen=account]"),
    ("اسأل سيمبول (home)", "home", "#home-assistant", ".screen[data-screen=assistant]"),
    ("المهامّ", "home", "#home-tasks", ".screen[data-screen=portal-item]"),
    ("المهارات", "home", "#home-skills", ".screen[data-screen=portal-item]"),
    ("عن المهنة", "home", "#home-about-open", ".screen[data-screen=about]"),
    ("أداة العمل", "home_tool", "#home-tool", "body"),
    ("التالي (item)", "portal_item", "#portal-item-next", "#portal-item-previous:not(.is-reserved)"),
    ("اسأل سيمبول عنها", "portal_item", "#portal-item-ask", ".screen[data-screen=assistant]"),
    ("اختيار سؤال", "assistant", "#assistant-suggestions .chip >> nth=1", "#assistant-suggestions .chip[aria-pressed=true]"),
    ("اسأل سيمبول (ask)", "assistant", "#assistant-ask", ".screen[data-screen=assistant-answer]"),
    ("اكتب سؤالك", "assistant", "#assistant-write", ".screen[data-screen=assistant-write]"),
    ("التالي (answer)", "assistant_answer", "#assistant-next", "#assistant-previous:not(.is-reserved)"),
    ("سؤالٌ آخر", "assistant_answer", "#assistant-again", ".screen[data-screen=assistant]"),
    ("تسجيل الخروج", "account", "#account-logout", ".screen[data-screen=account-logout]"),
    ("احذف حسابي", "account", "#account-delete", "body"),
    ("رجوع (logout)", "logout", "#account-logout-back", ".screen[data-screen=account]"),
]

GEOMETRY = """
() => {
    const screen = document.querySelector('.screen');
    const visible = (e) => { const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]'); };
    const controls = [...screen.querySelectorAll('button, a[href], label.btn, input, textarea')].filter(visible);
    const rects = controls.map((e) => [e.id || e.textContent.trim().slice(0, 18), e.getBoundingClientRect(), e.disabled]);
    let minGap = Infinity, pair = null;
    for (let i = 0; i < rects.length; i += 1) for (let j = i + 1; j < rects.length; j += 1) {
        const a = rects[i][1], b = rects[j][1];
        const gap = Math.max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom);
        if (gap < minGap) { minGap = gap; pair = rects[i][0] + ' / ' + rects[j][0]; }
    }
    const content = screen.querySelector('.content');
    // نصٌّ يفيض داخل زرّه (ثلاثة أسطر في خانة نصف الشريط مثلاً): لا يراه AUDIT.
    const spill = controls.filter((e) => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
        .map((e) => e.id || e.textContent.trim().slice(0, 18));
    return {
        spill,
        targets: rects.map(([n, r, d]) => ({ name: n, w: Math.round(r.width), h: Math.round(r.height), disabled: d })),
        minW: Math.min(...rects.map(([, r]) => r.width)), minH: Math.min(...rects.map(([, r]) => r.height)),
        minGap: Math.round(minGap), minGapPair: pair,
        contentSlack: content.clientHeight - content.scrollHeight,
        contentHeight: content.clientHeight,
        used: Math.round([...content.children].filter((c) => !c.classList.contains('alert') && visible(c))
            .reduce((m, c) => Math.max(m, c.getBoundingClientRect().bottom), 0) - content.getBoundingClientRect().top),
    };
}
"""


def prepare(page, steps):
    for step in steps:
        action, selector = step[0], step[1]
        if action == "fill":
            page.fill(selector, step[2])
        elif action == "click":
            page.click(selector)
        elif action == "wait":
            page.wait_for_selector(selector)


def open_scene(browser, scene, width, height, *, scale=1, contrast="no-preference", scheme="light", text_size=False):
    name, hash_, cookies, screen, steps = scene
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale,
                                  locale="ar-SA", has_touch=True, color_scheme=scheme)
    context.add_init_script(INSTRUMENT)
    if text_size:
        context.add_init_script(TEXT_SIZE)
    if cookies:
        context.add_cookies(cookies)
    page = context.new_page()
    page.emulate_media(contrast=contrast, color_scheme=scheme)
    page.requests = []
    page.errors = []
    page.on("request", lambda r: page.requests.append(r.url))
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.goto(f"{BASE}/{hash_}")
    page.wait_for_selector(".screen")
    prepare(page, steps)
    page.wait_for_selector(f".screen[data-screen='{screen}']")
    page.evaluate("() => document.fonts.ready")
    return context, page


def main() -> None:
    dist = WORK / "client" / "dist"
    server = subprocess.Popen([sys.executable, str(WORK / "harness" / "serve.py"), str(dist),
                               str(WORK / "fixtures"), str(PORT)])
    time.sleep(0.8)
    results = {"audits": [], "geometry": {}, "landings": [], "nearest": [], "instrument": {}, "errors": []}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
            by_name = {s[0]: s for s in SCENES}

            # 1. Screenshots.
            for scene in SCENES:
                for (w, h), suffix in (((390, 844), ""), ((375, 635), "_375x635")):
                    context, page = open_scene(browser, scene, w, h, scale=2)
                    page.screenshot(path=str(ROOT / f"mock_visual_{scene[0]}{suffix}.png"))
                    results["errors"] += [f"{scene[0]}: {e}" for e in page.errors]
                    context.close()
            for label, kwargs in (("home_dark", {"scheme": "dark"}), ("home_contrast", {"contrast": "more"})):
                context, page = open_scene(browser, by_name["home"], 390, 844, scale=2, **kwargs)
                page.screenshot(path=str(ROOT / f"mock_visual_{label}.png"))
                context.close()
            context, page = open_scene(browser, by_name["assistant_answer"], 390, 844, scale=2, scheme="dark")
            page.screenshot(path=str(ROOT / "mock_visual_assistant_answer_dark.png"))
            context.close()
            context, page = open_scene(browser, by_name["portal_item"], 320, 635, scale=2, text_size=True)
            page.screenshot(path=str(ROOT / "mock_visual_portal_item_320x635_textsize.png"))
            context.close()

            # 2. Audits.
            variants = [((w, h), {}, "") for (w, h) in FRAMES]
            variants += [((w, h), {"contrast": "more"}, "+contrast") for (w, h) in TIGHT]
            variants += [((w, h), {"text_size": True}, "+textsize53") for (w, h) in TIGHT]
            for scene in SCENES:
                for (w, h), kwargs, tag in variants:
                    context, page = open_scene(browser, scene, w, h, **kwargs)
                    audit = page.evaluate(AUDIT)
                    audit["label"] = f"{scene[0]} {w}x{h}{tag}"
                    results["audits"].append(audit)
                    if not tag:
                        results["geometry"][f"{scene[0]} {w}x{h}"] = page.evaluate(GEOMETRY)
                    context.close()

            # 2b. Every portal item and every portal's about screen, in the tightest frames.
            results["items"] = []
            for profession in ("MARKETING", "STOREKEEPER", "SUPPORT"):
                portal = json.loads((WORK / "fixtures" / f"portal_{profession}.json").read_text(encoding="utf-8"))
                jar = SIGNED_IN + [{"name": "proto_prof", "value": profession, "url": BASE}]
                routes = [(f"#/{k}/{n}", "portal-item", "#portal-item-text:not(:empty)")
                          for k in ("tasks", "skills") for n in range(1, len(portal[k]) + 1)]
                routes.append(("#/about", "about", "#home-about:not(:empty)"))
                for (w, h) in TIGHT:
                    for tag, kwargs in (("", {}), ("+textsize53", {"text_size": True}), ("+contrast", {"contrast": "more"})):
                        context, page = open_scene(browser, ("x", "#/", jar, "home", []), w, h, **kwargs)
                        for hash_, screen, ready in routes:
                            page.evaluate(f"() => {{ location.hash = '{hash_}' }}")
                            page.wait_for_selector(f".screen[data-screen='{screen}'] {ready}")
                            page.wait_for_function(f"() => document.querySelector('.screen[data-screen={screen}]') !== null")
                            audit = page.evaluate(AUDIT)
                            compact = page.evaluate("() => !!document.querySelector('[data-compact]')")
                            audit["label"] = f"{profession} {hash_} {w}x{h}{tag}"
                            audit["compact"] = compact
                            results["items"].append(audit)
                        context.close()

            # 3. Landing and nearest after each press, at every handheld frame.
            for (w, h) in [(375, 635), (390, 664), (390, 763), (320, 635)]:
                for label, start, selector, settle in PRESSES:
                    context, page = open_scene(browser, by_name[start], w, h)
                    locator = page.locator(selector)
                    box = locator.bounding_box()
                    locator.evaluate("(e) => { window.__activated = e; window.__activatedKey = e.id || e.dataset.key || ''; }")
                    inset = 8
                    points = [[box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
                              [box["x"] + inset, box["y"] + inset], [box["x"] + box["width"] - inset, box["y"] + inset],
                              [box["x"] + inset, box["y"] + box["height"] - inset],
                              [box["x"] + box["width"] - inset, box["y"] + box["height"] - inset]]
                    locator.click()
                    page.wait_for_selector(settle)
                    page.evaluate("() => document.fonts.ready")
                    hazards = page.evaluate(LANDING, points)
                    nearest = page.evaluate(NEAREST, points)
                    results["nearest"].append({"frame": f"{w}x{h}", "press": label,
                                               "nearest": sorted({f"{n['name']}@{n['distance']}" for n in nearest})})
                    if hazards:
                        results["landings"].append(f"{w}x{h} {label}: under the press {sorted(set(hazards))}")
                    bad = sorted({n["name"] for n in nearest if n["commit"]})
                    if bad:
                        results["landings"].append(f"{w}x{h} {label}: nearest commits {bad}")
                    context.close()

            # 4. Instrumentation over a full logged-in walk.
            context, page = open_scene(browser, by_name["home"], 390, 664)
            for selector, settle in (("#home-tasks", ".screen[data-screen=portal-item]"),
                                     ("#portal-item-next", "#portal-item-previous:not(.is-reserved)"),
                                     ("#portal-item-ask", ".screen[data-screen=assistant]"),
                                     ("#assistant-ask", ".screen[data-screen=assistant-answer]"),
                                     ("#assistant-again", ".screen[data-screen=assistant]"),
                                     ("[data-back]", ".screen[data-screen=home]"),
                                     ("#home-account", ".screen[data-screen=account]")):
                page.click(selector)
                page.wait_for_selector(settle)
            log = page.evaluate("() => window.__eyework")
            results["instrument"] = {
                "timers": log["timers"],
                "listeners": sorted(set(log["listeners"])),
                "csp": log["csp"],
                "foreign": [u for u in page.requests if not u.startswith(BASE)],
                "errors": page.errors,
            }
            context.close()
            browser.close()
    finally:
        server.terminate()

    (WORK / "measure.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failures = []
    for a in results["audits"]:
        for key in ("small", "close", "edge", "fonts", "clipped"):
            if a[key]:
                failures.append(f"{a['label']} {key}: {a[key]}")
        if a["enabled"] > 10:
            failures.append(f"{a['label']}: {a['enabled']} enabled")
        if a["vertical"] or a["horizontal"]:
            failures.append(f"{a['label']}: scroll")
    print("AUDIT failures:", len(failures))
    print("\n".join(failures[:80]))
    item_fail = []
    for a in results["items"]:
        keys = [k for k in ("small", "close", "edge", "fonts", "clipped") if a[k]]
        if a["vertical"] or a["horizontal"]:
            keys.append("scroll")
        if keys:
            item_fail.append(f"{a['label']}: {keys}")
    print("ITEM checks:", len(results["items"]), "failures:", len(item_fail),
          "compacted:", sum(1 for a in results["items"] if a["compact"]))
    print("\n".join(item_fail[:40]))
    spills = [f"{k}: {g['spill']}" for k, g in results["geometry"].items() if g["spill"]]
    print("BUTTON text spill:", len(spills))
    print("\n".join(spills[:30]))
    print("LANDING failures:", len(results["landings"]))
    print("\n".join(results["landings"][:60]))
    print("instrument:", json.dumps(results["instrument"], ensure_ascii=False))
    print("errors:", results["errors"][:10])


if __name__ == "__main__":
    main()
