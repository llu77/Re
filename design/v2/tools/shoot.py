"""
صور v2 وقياسها
==============
يبني لا شيء: يخدم client/dist-demo (بـ`npx vite build --mode demo`) بسياسة المحتوى نفسها
التي يرسلها eyework (serve.py)، ثم لكل شاشةٍ ولكل حجم:

  • صورةٌ 390×844 بكثافة 2، وصورةٌ 1280×800، في redesign/v2_mock_<الشاشة>_<الحجم>[_1280].png؛
  • قياس كل هدفٍ ومسافة (audit.js) عند 390×844 و1280×800، وعند أصغر إطارين في
    eyework/tests/ui/conftest.py (375×635 و320×635)؛
  • قاعدة الهبوط والأقرب إلى النظر بعد ضغطاتٍ مختارة (landing.js).

    python3 -I shoot.py <client-dir> <out-dir> --mode compact|gaze [--no-shots]

المخرجات: <out-dir>/v2_measure_<mode>.json، و<out-dir>/v2_landing_<mode>.json، والصور.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
AUDIT = (HERE / "audit.js").read_text(encoding="utf-8")
LANDING = (HERE / "landing.js").read_text(encoding="utf-8")

RULES = {
    "compact": {"min": 44, "gap": 8, "edge": 16, "max_enabled": None, "no_scroll": False, "floatingFab": True},
    "gaze": {"min": 72, "gap": 24, "edge": 16, "max_enabled": 10, "no_scroll": True, "floatingFab": False},
}

#: الشاشات المطلوبة في المهمّة، ثم حالاتٌ إضافية تُري ما بينها.
SCREENS = [
    ("welcome", "welcome"),
    ("signin", "signin"),
    ("signup-size", "signup_size_step"),
    ("home", "storekeeper_home"),
    ("totals", "storekeeper_totals"),
    ("purchase-combobox", "purchase_item_combobox"),
    ("purchase-create", "purchase_create_item"),
    ("return", "return_from_invoice"),
    ("expenses", "expenses"),
    ("marketing-board", "marketing_campaigns"),
    ("support-queue", "support_queue"),
    ("support-ticket", "support_ticket_draft"),
    ("purchase-flag", "ai_flag_invoice_line"),
    ("fab-sheet", "fab_sheet"),
    ("account", "account_usage_mode"),
    ("nav-open", "sections_menu"),
    ("fab-vat", "fab_vat_calculator"),
    ("fab-assistant", "fab_assistant"),
    ("marketing-home", "marketing_home"),
    ("support-home", "support_home"),
]

#: ما تُمرَّر إليه الصفحة في الحجم العادي قبل الصورة.
SCROLL_TO = {
    "purchase-combobox": "[role=combobox][aria-expanded=true]",
    "purchase-create": "input[maxlength='80']",
    "purchase-ready": "[role=combobox]",
    "purchase-flag": "[data-flag-status]",
}
SCROLL_JS = """(selector) => {
    const target = document.querySelector(selector)
    if (!target) return
    const block = target.closest('li') || target
    const header = document.querySelector('header')
    const top = block.getBoundingClientRect().top + scrollY - (header ? header.getBoundingClientRect().height : 0) - 16
    window.scrollTo(0, Math.max(0, top))
}"""

PHONE = (390, 844)
DESKTOP = (1280, 800)
SMALL = [(375, 635), (320, 635)]

#: ضغطاتٌ تُفحص بعدها قاعدة الهبوط: (الشاشة، المحدِّد، ما يُنتظر بعدها، الوصف).
PRESSES = [
    ("home", "button[aria-haspopup=dialog]", "dialog[open]", "الأدوات ← ورقة الأدوات"),
    ("home", "main a >> nth=0", "text=فاتورة المورّد", "فاتورة شراء جديدة ← الفاتورة"),
    ("fab-sheet", "dialog[open] button:has-text('اسأل سيمبول')", "dialog[open] textarea", "اسأل سيمبول ← لوحته"),
    ("fab-sheet", "dialog[open] button:has-text('حاسبة الضريبة')", "dialog[open] input[inputmode=decimal]", "حاسبة الضريبة ← لوحتها", "compact"),
    ("fab-sheet", "dialog[open] button:has-text('إغلاق')", "body:not(:has(dialog[open]))", "إغلاق ← الشاشة"),
    ("purchase-ready", "button:has-text('راجِع وسجّل')", "[data-flag-status]", "راجِع وسجّل ← المراجعة بتنبيه"),
    ("purchase-flag", "button:has-text('تابع رغم ذلك')", "[data-flag-status=acknowledged]", "تابع رغم ذلك ← قرارٌ محفوظ"),
    ("purchase-combobox", "[role=option]:has-text('صنف جديد باسم')", "text=اسم الصنف", "صنف جديد باسم ← نموذج الصنف"),
    ("welcome", "#welcome-login", "text=ادخل إلى بوابتك", "ادخل ← شاشة الدخول"),
    ("signup-size", "#signup-use-next", "main a", "التالي ← الرئيسية"),
    ("support-queue", "main ul button >> nth=1", "#customer-message", "تذكرة ← رسالة العميل"),
    ("support-ticket-open", "button:has-text('المسودة')", "#draft-title", "المسودة ← المسودة والقرار", "gaze"),
    ("nav-open", "[role=region] a >> nth=2", "body:not(:has([role=region]))", "بندٌ من القائمة ← شاشته"),
    ("account", "#account-ui-size-apply", "html[data-size]", "طبّق ← الحجم الآخر"),
]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def settle(page) -> None:
    page.wait_for_load_state("networkidle")
    page.evaluate("() => document.fonts.ready")
    # تُجاب الطلبات من البيانات الثابتة بوعودٍ محلولة: إطاران يكفيان ليُرسم ما وصل.
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("client")
    parser.add_argument("out")
    parser.add_argument("--mode", choices=["compact", "gaze"], required=True)
    parser.add_argument("--no-shots", action="store_true")
    args = parser.parse_args()
    mode = args.mode
    rules = RULES[mode]
    dist = Path(args.client) / "dist-demo"
    out = Path(args.out)
    port = free_port()
    server = subprocess.Popen([sys.executable, "-I", str(HERE / "serve.py"), str(dist), str(port)])
    base = f"http://127.0.0.1:{port}/demo.html"
    time.sleep(0.4)
    measures: dict[str, dict] = {}
    landings: list[dict] = []
    problems: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])

            def open_page(width: int, height: int, scale: int):
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale,
                                              locale="ar-SA", has_touch=True)
                page = context.new_page()
                page.csp = []
                page.on("console", lambda m: page.csp.append(m.text) if "Content Security Policy" in m.text or m.type == "error" else None)
                page.on("pageerror", lambda e: page.csp.append(str(e)))
                return context, page

            for screen, label in SCREENS:
                for (width, height), scale, suffix, shoot in [
                    (PHONE, 2, "", True), (DESKTOP, 1, "_1280", True), (SMALL[0], 1, "_375x635", False), (SMALL[1], 1, "_320x635", False),
                ]:
                    context, page = open_page(width, height, scale)
                    page.goto(f"{base}?screen={screen}" + ("&size=large" if mode == "gaze" else ""))
                    settle(page)
                    if screen == "purchase-combobox":
                        page.wait_for_selector("[role=option]")
                    # في الحجم العادي تمرّ الصفحة: تُمرَّر إلى ما تُري الصورة (السطر المفتوح، أو التنبيه).
                    if mode == "compact" and screen in SCROLL_TO:
                        page.evaluate(SCROLL_JS, SCROLL_TO[screen])
                    if shoot and not args.no_shots:
                        page.screenshot(path=str(out / f"v2_mock_{label}_{mode}{suffix}.png"))
                    result = page.evaluate(AUDIT, rules)
                    if page.csp:
                        problems.append(f"{label}{suffix}: {page.csp}")
                    measures[f"{label}{suffix or '_390x844'}"] = result
                    context.close()

            for screen, selector, until, description, *only in PRESSES:
                if only and only[0] != mode:
                    continue
                for width, height in [PHONE, *SMALL]:
                    context, page = open_page(width, height, 1)
                    page.goto(f"{base}?screen={screen}" + ("&size=large" if mode == "gaze" else ""))
                    settle(page)
                    locator = page.locator(selector).first
                    if locator.count() == 0 or not locator.is_visible():
                        landings.append({"press": description, "viewport": [width, height], "skipped": "الهدف غير ظاهر"})
                        context.close()
                        continue
                    box = locator.bounding_box()
                    locator.evaluate("(e) => { window.__activated = e; window.__activatedKey = e.id || e.textContent.trim(); }")
                    inset = 8
                    points = [
                        [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
                        [box["x"] + inset, box["y"] + inset],
                        [box["x"] + box["width"] - inset, box["y"] + inset],
                        [box["x"] + inset, box["y"] + box["height"] - inset],
                        [box["x"] + box["width"] - inset, box["y"] + box["height"] - inset],
                    ]
                    locator.click()
                    try:
                        page.wait_for_selector(until, state="attached", timeout=5000)
                    except Exception:
                        landings.append({"press": description, "viewport": [width, height], "skipped": f"لم يظهر {until}"})
                        context.close()
                        continue
                    settle(page)
                    result = page.evaluate(LANDING, points)
                    hazards = list(result["under"])
                    if mode == "gaze":
                        hazards += [f"أقرب هدفٍ يعتمد: {n['name']} على {n['distance']}px" for n in result["nearest"] if n["commit"]]
                    landings.append({"press": description, "viewport": [width, height], "box": box,
                                     "under": result["under"], "nearest": result["nearest"], "hazards": sorted(set(hazards))})
                    context.close()
            browser.close()
    finally:
        server.terminate()

    summary = {}
    for key, m in measures.items():
        failures = []
        for check in ("small", "close", "edge", "fonts"):
            if m[check]:
                failures.append(f"{check}: {m[check]}")
        if rules["no_scroll"] and (m["vertical"] or m["offscreen"] or m["clipped"]):
            failures.append(f"scroll/clip: vertical={m['vertical']} offscreen={m['offscreen']} clipped={m['clipped']}")
        if m["horizontal"]:
            failures.append("horizontal scroll")
        if rules["max_enabled"] and m["enabled"] > rules["max_enabled"]:
            failures.append(f"enabled targets: {m['enabled']}")
        if mode == "gaze" and m["underFab"]:
            failures.append(f"under FAB: {m['underFab']}")
        summary[key] = {"pass": not failures, "failures": failures, "targets": m["count"], "enabled": m["enabled"],
                        "minTarget": m["minTarget"], "minGap": m["minGap"]}
    (out / f"v2_measure_{mode}.json").write_text(json.dumps(
        {"mode": mode, "rules": rules, "summary": summary, "screens": measures, "console": problems}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"v2_landing_{mode}.json").write_text(json.dumps({"mode": mode, "presses": landings}, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = {k: v["failures"] for k, v in summary.items() if not v["pass"]}
    print(json.dumps({"mode": mode, "screens": len(summary), "failed": failed,
                      "landing_hazards": [(l["press"], l["viewport"], l.get("hazards") or l.get("skipped")) for l in landings if l.get("hazards") or l.get("skipped")],
                      "console": problems}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
