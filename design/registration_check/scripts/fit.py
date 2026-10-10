"""
Does the proposed copy fit? Builds variants of the committed index.html, opens each screen in
Chromium at the tightest frames and iOS Text Size steps, and runs the repo's own gaze audit (AUDIT).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/home/user/Re")
from eyework.tests.ui.flow import AUDIT  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(sys.argv[1])
HEAD = ROOT / "head" / "eyework" / "static"
OUT = ROOT / "variants"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FRAMES = [(320, 635), (375, 635), (390, 664)]
SIZES = [None, 17, 23, 53]

ENUM = " ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا."
CONTACT = "support@example.sa"


def base() -> str:
    return (HEAD / "index.html").read_text(encoding="utf-8")


def swap_operator(html: str) -> str:
    assert "مَن أعطاك الرابط" in html
    return html.replace("مَن أعطاك الرابط", "مَن يدير التطبيق")


def add_enum_to_email_line(html: str) -> str:
    line = re.search(r'<p class="line">البريد لا يُحفظ[^<]*</p>', html)
    assert line
    return html.replace(line.group(0), line.group(0).replace("</p>", ENUM + "</p>"))


def merged_first_lines(html: str) -> str:
    """The shorter wording in flight in the working tree: lines one and two in one sentence."""
    first = re.search(r'<p class="line">يُحفظ في هذا التطبيق[^<]*</p>', html).group(0)
    second = re.search(r'<p class="line">البريد لا يُحفظ[^<]*</p>', html).group(0)
    merged = ('<p class="line">يُحفظ في هذا التطبيق: الاسم، وتاريخ الميلاد، والمهنة، وكلمة المرور مجزّأة، '
              'وبصمة البريد لا البريد، فلا يصله شيء ولا يُستردّ الحساب به.</p>')
    html = html.replace(first, merged).replace(second, "")
    ai = re.search(r'<p class="line">في بوابة التسويق[^<]*</p>', html).group(0)
    return html.replace(ai, '<p class="line">في بوابة التسويق تُرسَل صورة المنتج ونصّه، دون الاسم والميلاد، '
                            'إلى Anthropic خارج المملكة للصياغة، وتحذفها خلال 30 يوماً إلا ما تُبقيه سياستها أو القانون.</p>')


def merged_with_enum(html: str) -> str:
    html = merged_first_lines(html)
    line = re.search(r'<p class="line">يُحفظ في هذا التطبيق[^<]*</p>', html).group(0)
    return html.replace(line, line.replace("</p>", ENUM + "</p>"))


def other_screens(html: str) -> str:
    # login: the entry in the top bar's end slot, and the help line naming the operator's address
    old = '<header class="bar bar--top"><div class="slot"></div><p class="step"></p><div class="slot"></div></header>'
    i = html.index('data-screen="login"')
    j = html.index(old, i)
    html = html[:j] + ('<header class="bar bar--top"><div class="slot"></div><p class="step"></p><div class="slot">'
                       '<button class="btn" type="button" id="login-signup" data-safe>أنشئ حساباً</button></div></header>'
                       ) + html[j + len(old):]
    html = re.sub(r'<p class="help">تعذّر الدخول؟[^<]*</p>',
                  f'<p class="help" id="login-help">تعذّر الدخول؟ اكتب إلى <bdi dir="ltr">{CONTACT}</bdi> من بريد حسابك.</p>',
                  html)
    # email step: the enumeration note under the field
    k = html.index('id="signup-email-input"')
    end = html.index("</div>", k) + len("</div>")
    html = html[:end] + ('\n            <p class="help" id="signup-email-help">من يحاول التسجيل بهذا البريد يعرف أن '
                         'له حساباً هنا. إن كان ذلك يضرّك فاختر بريداً لا يعرفه غيرك.</p>') + html[end:]
    # review: recovery by writing to the operator from the same address
    html = re.sub(r'<p class="help">لا يصل هذا البريدَ شيء[^<]*</p>',
                  f'<p class="help" id="signup-review-help">لا يصل هذا البريدَ شيء، ولا يُستردّ الحساب به. إن نُسيت كلمة '
                  f'المرور فاكتب إلى <bdi dir="ltr">{CONTACT}</bdi> من هذا البريد.</p>', html)
    html = re.sub(r'(<p class="help">تُفتح بها بوابتك\.)[^<]*</p>', r'\1 تغييرها بعد التسجيل بطلبٍ ممّن يدير التطبيق.</p>',
                  html)
    return html


def trim_condition(html: str) -> str:
    old = "أو يحذفه بطلبك مَن يدير التطبيق إن أُوقف أو نسيت كلمة مرورك؛"
    assert old in html
    return html.replace(old, "أو يحذفه بطلبك مَن يدير التطبيق؛")


def enum_in_first(html: str) -> str:
    old = "فلا يصله شيء ولا يُستردّ الحساب به.</p>"
    assert old in html
    return html.replace(old, "فلا يصله شيء ولا يُستردّ الحساب به، ومن يحاول التسجيل به يعرف أن لك حساباً هنا.</p>")


def enum_in_last(html: str) -> str:
    old = "والنسخ الاحتياطية الأقدم تبقى حتى تُحذف.</p>"
    assert old in html
    return html.replace(old, "والنسخ الاحتياطية الأقدم تبقى حتى تُحذف. ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا.</p>")


def entry_only(html: str) -> str:
    old = '<header class="bar bar--top"><div class="slot"></div><p class="step"></p><div class="slot"></div></header>'
    i = html.index('data-screen="login"')
    j = html.index(old, i)
    return html[:j] + ('<header class="bar bar--top"><div class="slot"></div><p class="step"></p><div class="slot">'
                       '<button class="btn" type="button" id="login-signup" data-safe>أنشئ حساباً</button></div></header>'
                       ) + html[j + len(old):]


def help_contact_short(html: str) -> str:
    return re.sub(r'<p class="help">تعذّر الدخول؟[^<]*</p>',
                  f'<p class="help" id="login-help">نسيت كلمة المرور؟ اكتب إلى <bdi dir="ltr">{CONTACT}</bdi></p>', html)


VARIANTS = {
    "A_head": lambda h: h,
    "F_inflight": merged_first_lines,
    "G_inflight_swap": lambda h: merged_first_lines(swap_operator(h)),
    "H1_trim_enum_first": lambda h: enum_in_first(trim_condition(merged_first_lines(swap_operator(h)))),
    "H3_trim_enum_last": lambda h: enum_in_last(trim_condition(merged_first_lines(swap_operator(h)))),
    "L1_entry_only": entry_only,
    "L2_entry_help": lambda h: help_contact_short(entry_only(h)),
    "E_screens": lambda h: other_screens(enum_in_last(trim_condition(merged_first_lines(swap_operator(h))))),
}

SCREENS = {
    "A_head": ["signup-notice", "login", "signup-email", "signup-review"],
    "F_inflight": ["signup-notice"],
    "G_inflight_swap": ["signup-notice"],
    "H1_trim_enum_first": ["signup-notice"],
    "H3_trim_enum_last": ["signup-notice"],
    "L1_entry_only": ["login", "login+alert"],
    "L2_entry_help": ["login", "login+alert"],
    "E_screens": ["signup-notice", "signup-email", "signup-email+alert", "signup-review", "signup-profession"],
}


def system_rules(css: str) -> list[str]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [s.strip() for s, block in re.findall(r"([^{}]+)\{([^}]*)\}", css)
            if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", block)]


def build(name: str, transform) -> Path:
    target = OUT / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(HEAD, target)
    (target / "index.html").write_text(transform(base()), encoding="utf-8")
    return target


def show(page, screen: str) -> None:
    name, _, alert = screen.partition("+")
    page.evaluate("""([name, alert]) => {
        document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.dataset.screen !== name; });
        const section = document.querySelector(`.screen[data-screen="${name}"]`);
        section.querySelectorAll('.alert').forEach((a) => { a.hidden = true; });
        if (name === 'signup-review') {
            document.querySelector('#signup-review-name').textContent = 'الاسم: عبدالرحمن بن عبدالعزيز آل سعود';
            document.querySelector('#signup-review-birth').textContent = 'تاريخ الميلاد: 28 ديسمبر 1999';
            document.querySelector('#signup-review-profession').textContent = 'المهنة: أمين المخزون';
            document.querySelector('#signup-review-email').textContent = 'abdulrahman.alotaibi.works@example-mail.sa';
        }
        if (name === 'signup-profession') {
            const list = document.querySelector('#signup-professions');
            for (const label of ['التسويق', 'أمين المخزون', 'الدعم الفني']) {
                const b = document.createElement('button'); b.className = 'btn'; b.type = 'button'; b.textContent = label;
                list.append(b);
            }
        }
        if (alert) {
            const a = section.querySelector('.alert'); a.hidden = false;
            a.querySelector('.alert__text').textContent = 'يوجد حسابٌ بهذا البريد. ادخل به، أو اكتب بريداً آخر.';
            section.querySelectorAll('.bar .btn').forEach((b) => { b.disabled = true; });
        }
    }""", [name, alert])


def main() -> int:
    OUT.mkdir(exist_ok=True)
    rules = system_rules((HEAD / "styles.css").read_text(encoding="utf-8"))
    report = {}
    failed = False
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        for name, transform in VARIANTS.items():
            folder = build(name, transform)
            for width, height in FRAMES:
                for size in SIZES:
                    context = browser.new_context(viewport={"width": width, "height": height}, locale="ar-SA",
                                                  java_script_enabled=True)
                    if size:
                        css = " ".join(f"{s} {{ font-size: {size}px; }}" for s in rules)
                        context.add_init_script(
                            "(() => { const sheet = new CSSStyleSheet();"
                            f" sheet.replaceSync({json.dumps(css)});"
                            " document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();")
                    # Served over http (fonts are not loaded from file://). The app's scripts are not
                    # wanted: only the markup and the styles are measured.
                    def serve(route, request, folder=folder):
                        path = route.request.url.split("http://local.test/", 1)[1].split("?")[0] or "index.html"
                        if path.endswith(".js"):
                            return route.abort()
                        kind = {"html": "text/html; charset=utf-8", "css": "text/css", "woff2": "font/woff2",
                                "png": "image/png", "webmanifest": "application/manifest+json"}
                        route.fulfill(status=200, body=(folder / path).read_bytes(),
                                      content_type=kind.get(path.rsplit(".", 1)[-1], "application/octet-stream"))
                    context.route("http://local.test/**", serve)
                    page = context.new_page()
                    page.goto("http://local.test/index.html")
                    for screen in SCREENS[name]:
                        show(page, screen)
                        page.evaluate("""async () => {
                            await Promise.all(['400', '700'].map((w) => document.fonts.load(`${w} 18px Amiri`, 'ابت')));
                            await document.fonts.ready;
                            await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
                        }""")
                        loaded = page.evaluate("() => [...document.fonts].filter((f) => f.status === 'loaded').length")
                        audit = page.evaluate(AUDIT)
                        problems = {k: audit[k] for k in ("small", "close", "edge", "fonts", "clipped") if audit[k]}
                        if audit["vertical"] or audit["horizontal"]:
                            problems["scroll"] = [audit["vertical"], audit["horizontal"]]
                        if audit["enabled"] > 10:
                            problems["enabled"] = audit["enabled"]
                        content = page.evaluate("""() => { const c = document.querySelector('.screen:not([hidden]) .content');
                            return [c.scrollHeight, c.clientHeight]; }""")
                        key = f"{name} {screen} {width}x{height} size={size or 'default'}"
                        report[key] = {"problems": problems, "content(scroll,client)": content + [f"fonts={loaded}"]}
                        failed |= bool(problems) and name != "A_head" or (name == "A_head" and bool(problems))
                    context.close()
        browser.close()
    for key, value in report.items():
        mark = "FAIL" if value["problems"] else "ok  "
        print(f"{mark} {key}  {value['content(scroll,client)']}  {value['problems'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
