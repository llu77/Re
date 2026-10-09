"""
Content-fit estimate for the three new pre-account screens (size step, «ما يُحفظ», «ما يُرسَل»).

Not the visual design: plain HTML with the v2 client's own size tokens (v2/client/src/styles/globals.css,
compact and gaze), its bundled Noto Sans Arabic, and lucide's own icon shapes. It answers two questions:

  1. Does each screen fit with no scroll and nothing clipped, at both sizes, in every handheld frame?
  2. How long may each workspace's line on «ما يُرسَل» be and still fit at gaze size in the 320x635 frame?

Usage: python3 fit.py   (writes fit_results.json and PNGs next to this file)
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ICONS = json.loads((HERE / "icons.json").read_text(encoding="utf-8"))
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FRAMES = [(320, 635), (375, 635), (390, 664), (390, 763)]

# The v2 tokens (globals.css), in px.
TOKENS = {
    "compact": dict(fs_small=14, lh_small=1.45, fs_body=16, lh_body=1.6, fs_title=20, lh_title=1.35,
                    ctl=44, ctl_lg=48, tg=12, edge=16, sec=24, icon=18, radius=10),
    "gaze": dict(fs_small=16, lh_small=1.45, fs_body=18, lh_body=1.55, fs_title=24, lh_title=1.3,
                 ctl=72, ctl_lg=72, tg=24, edge=16, sec=24, icon=24, radius=16),
}


def icon(name: str, cls: str = "ico") -> str:
    parts = []
    for tag, attrs in ICONS[name]:
        rendered = " ".join(f'{k}="{html.escape(str(v))}"' for k, v in attrs.items() if k != "key")
        parts.append(f"<{tag} {rendered}/>")
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{"".join(parts)}</svg>')


def css(size: str) -> str:
    t = TOKENS[size]
    return f"""
@font-face {{ font-family: "Noto Sans Arabic"; font-weight: 400; src: url("fonts/noto-sans-arabic-arabic-400.woff2"); }}
@font-face {{ font-family: "Noto Sans Arabic"; font-weight: 500; src: url("fonts/noto-sans-arabic-arabic-500.woff2"); }}
@font-face {{ font-family: "Noto Sans Arabic"; font-weight: 700; src: url("fonts/noto-sans-arabic-arabic-700.woff2"); }}
@font-face {{ font-family: "Noto Sans"; font-weight: 400; src: url("fonts/noto-sans-latin-400.woff2"); }}
@font-face {{ font-family: "Noto Sans"; font-weight: 700; src: url("fonts/noto-sans-latin-700.woff2"); }}
* {{ box-sizing: border-box; margin: 0; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ font-family: "Noto Sans Arabic", "Noto Sans", sans-serif; font-size: {t['fs_body']}px;
        line-height: {t['lh_body']}; color: #0E1A33; background: #F4F7FC; }}
.screen {{ height: 100vh; display: flex; flex-direction: column; }}
.bar {{ display: flex; align-items: center; justify-content: space-between; gap: {t['tg']}px;
        padding: {t['edge']}px {t['edge']}px; flex: none; }}
.bar.bottom {{ padding-top: {t['tg']}px; }}
.step {{ font-size: {t['fs_small']}px; color: #4E5B6C; }}
.content {{ flex: 1 1 auto; min-height: 0; overflow: hidden; padding: 0 {t['edge']}px;
            display: flex; flex-direction: column; gap: {max(12, t['tg'] - 8)}px; }}
h2 {{ font-size: {t['fs_title']}px; line-height: {t['lh_title']}; font-weight: 700; color: #061840; }}
.btn {{ min-height: {t['ctl']}px; min-width: {t['ctl']}px; border: 2px solid #7B8799; border-radius: {t['radius']}px;
        background: #fff; font: inherit; font-weight: 600; display: inline-flex; align-items: center;
        justify-content: center; gap: 8px; padding: 0 16px; color: #0E1A33; }}
.btn.next {{ border-color: #2455CC; background: #E8EFFD; color: #1B3F99; }}
.btn.commit {{ border-color: #2455CC; background: #2455CC; color: #fff; }}
.btn[disabled] {{ border-color: #D3DCE8; background: #EDF2F9; color: #4E5B6C; }}
.ico {{ width: {t['icon']}px; height: {t['icon']}px; flex: none; }}
.lines {{ display: flex; flex-direction: column; gap: {8 if size == 'compact' else 10}px; }}
.line {{ display: grid; grid-template-columns: {t['icon'] + 12}px 1fr; gap: 10px; align-items: start;
         font-size: {t['fs_small']}px; line-height: {t['lh_small']}; }}
.line .badge {{ width: {t['icon'] + 12}px; height: {t['icon'] + 12}px; border-radius: 8px; background: #E8EFFD;
               color: #1B3F99; display: flex; align-items: center; justify-content: center; }}
.line .badge .ico {{ width: {t['icon'] - 4}px; height: {t['icon'] - 4}px; }}
.options {{ display: flex; flex-direction: column; gap: {t['tg']}px; }}
.option {{ width: 100%; min-height: {t['ctl_lg']}px; justify-content: flex-start; padding: 8px 14px; text-align: start; }}
.option .name {{ font-weight: 700; }}
.option[aria-pressed="true"] {{ border-color: #2455CC; background: #E8EFFD; }}
.option .detail {{ display: block; font-weight: 400; font-size: {t['fs_small']}px; color: #4E5B6C; }}
.toggle {{ width: 100%; justify-content: flex-start; flex: none; }}
.help {{ font-size: {t['fs_small']}px; line-height: {t['lh_small']}; color: #4E5B6C; }}
.spacer {{ flex: 1 1 auto; }}
bdi {{ font-family: "Noto Sans", "Noto Sans Arabic", sans-serif; }}
"""


def page(size: str, top: str, body: str, bottom_end: str, bottom_start: str = "<span></span>") -> str:
    return f"""<!doctype html><html lang="ar" dir="rtl" data-size="{size}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css(size)}</style></head><body>
<section class="screen"><header class="bar top">{top}</header><div class="content">{body}</div>
<footer class="bar bottom">{bottom_start}{bottom_end}</footer></section></body></html>"""


BACK = f'<button class="btn" id="back">{icon("chevron-right")}رجوع</button><span class="step">قبل أن تبدأ</span>'
BACK_STEP = f'<button class="btn" id="back">{icon("chevron-right")}رجوع</button><span class="step">الخطوة 1 من 9</span>'


def line(name: str, text: str, scope: str = "") -> str:
    return (f'<div class="line" data-scope="{scope}"><span class="badge">{icon(name)}</span>'
            f'<p>{text}</p></div>')


ANTHROPIC = '<bdi dir="ltr">Anthropic</bdi>'

def use(size: str) -> str:
    """The size step, starting with the size the screen is shown in (spec §8.2)."""
    pressed = {"compact": "true" if size == "compact" else "false", "gaze": "true" if size == "gaze" else "false"}
    return (
        '<h2>كيف تستخدم الجهاز؟</h2><div class="options">'
        f'<button class="btn option" id="signup-use-COMPACT" data-value aria-pressed="{pressed["compact"]}">'
        f'{icon("hand")}<span><span class="name">باللمس</span>'
        '<span class="detail">أزرارٌ وخطٌّ بالحجم المعتاد.</span></span></button>'
        f'<button class="btn option" id="signup-use-GAZE" data-value aria-pressed="{pressed["gaze"]}">'
        f'{icon("scan-eye")}<span><span class="name">بتتبّع العين</span>'
        '<span class="detail">أزرارٌ أكبر بينها مسافات، تُضغط بالنظر.</span></span></button></div>'
        '<p class="help">تُحفظ مع حسابك لتُفتح بوابتك بحجمها، ولا تُرسَل إلى مزوّد النموذج.'
        ' وتغيّرها متى شئت من «حسابي».</p>'
    )


KEPT_LINES = [
    ("database", "يُحفظ: الاسم، وتاريخ الميلاد، والمهنة، وطريقة الاستخدام، وكلمة المرور مجزّأة."),
    ("mail", "البريد لا يُحفظ، بل بصمته للدخول: لا يصله شيء، ولا يُستردّ الحساب به."),
    ("folder-lock", "وما تعمله في بوابتك لحسابك وحده، لا يراه مستخدمٌ غيرك."),
    ("trash", "تحذف حسابك وبياناته متى شئت من «حسابي»، أو يحذفه بطلبك مَن يدير التطبيق؛"
              " والنسخ الاحتياطية الأقدم تبقى حتى تُحذف."),
    ("user-round-search", "ومن يحاول التسجيل ببريدك يعرف أن لك حساباً هنا."),
]
KEPT = "<h2>ما يُحفظ هنا</h2><div class=\"lines\">" + "".join(line(n, t) for n, t in KEPT_LINES) + "</div>"

SENT_INTRO = (f"يُرسَل إلى {ANTHROPIC} خارج المملكة ما يحتاجه المساعد وحده،"
              " بلا اسمك ولا ميلادك ولا طريقة استخدامك:")
#: Draft lines. The exact text of each comes from its track (spec §9.3); these are placeholders of a typical length.
SENT_ITEMS = [
    ("megaphone", "MARKETING", "التسويق: صورة المنتج ونصّ الحملة."),
    ("headset", "SUPPORT", "الدعم الفني: رسائل العملاء وردودك عليها."),
    ("package", "STOREKEEPER", "المخزون: بنود الفواتير ليراجعها المساعد."),
]
SENT_OUTRO = "وتحذفه خلال 30 يوماً، إلا ما تُبقيه سياستها أو القانون."
TOGGLE = f'<button class="btn" id="signup-read" data-value aria-pressed="false">{icon("square")}قرأتُه</button>'


def sent(items) -> str:
    body = "".join(line(n, t, scope) for n, scope, t in items)
    return (f'<h2>ما يُرسَل إلى {ANTHROPIC}</h2><div class="lines">{line("globe", SENT_INTRO)}{body}'
            f'{line("clock", SENT_OUTRO)}</div>')


NEXT_ON = f'<button class="btn next">التالي{icon("chevron-left")}</button>'
AGREE_OFF = f'<button class="btn commit" id="signup-agree" data-commit disabled>أوافق وأتابع{icon("chevron-left")}</button>'

MEASURE = """() => {
  const c = document.querySelector('.content');
  const box = c.getBoundingClientRect();
  const clipped = [...c.querySelectorAll('*')].filter((e) => {
    const r = e.getBoundingClientRect(); return r.height > 0 && (r.bottom > box.bottom + 1 || r.top < box.top - 1);
  }).length;
  const last = [...c.children].pop().getBoundingClientRect();
  return { overflow: c.scrollHeight > c.clientHeight + 1, clipped, spare: Math.round(box.bottom - last.bottom),
           page_scroll: document.scrollingElement.scrollHeight > innerHeight + 1 };
}"""

FILLER = ("وصف المنتج وسعره وكمية كل صنف ورقم الطلب وتاريخه واسم المورد وملاحظات العميل كما كتبها في رسالته "
          * 6)


def main() -> None:
    results: dict = {"screens": [], "budget": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        for size in ("compact", "gaze"):
            screens = {"use": page(size, BACK_STEP, use(size), NEXT_ON), "kept": page(size, BACK, KEPT, NEXT_ON),
                       "sent": page(size, BACK, sent(SENT_ITEMS), AGREE_OFF, TOGGLE)}
            for name, markup in screens.items():
                path = HERE / f"_{name}_{size}.html"
                path.write_text(markup, encoding="utf-8")
                for width, height in FRAMES:
                    pg = browser.new_page(viewport={"width": width, "height": height})
                    pg.goto(path.as_uri())
                    pg.evaluate("document.fonts.ready")
                    pg.wait_for_function("document.fonts.status === 'loaded'")
                    found = pg.evaluate(MEASURE)
                    results["screens"].append({"screen": name, "size": size, "frame": f"{width}x{height}", **found})
                    if (width, height) == (375, 635):
                        pg.screenshot(path=str(HERE / f"signup_{name}_{size}_375x635.png"))
                    pg.close()
        # Budget: the longest line each of three (then four) workspace items may have at gaze size, 320x635.
        for count in (3, 4):
            low, high = 10, 400
            while low < high:
                mid = (low + high + 1) // 2
                items = [(n, s, (t.split(":")[0] + ": " + FILLER)[:mid]) for n, s, t in
                         (SENT_ITEMS + [("sparkles", "ALL", "كل بوابة: ما تسأل عنه المساعد.")])[:count]]
                path = HERE / "_budget.html"
                path.write_text(page("gaze", BACK, sent(items), AGREE_OFF, TOGGLE), encoding="utf-8")
                pg = browser.new_page(viewport={"width": 320, "height": 635})
                pg.goto(path.as_uri())
                pg.wait_for_function("document.fonts.status === 'loaded'")
                found = pg.evaluate(MEASURE)
                pg.close()
                if found["overflow"] or found["clipped"]:
                    high = mid - 1
                else:
                    low = mid
            results["budget"][f"{count}_items_gaze_320x635_max_chars_each"] = low
        browser.close()
    for stale in HERE.glob("_*.html"):
        stale.unlink()
    (HERE / "fit_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for row in results["screens"]:
        flag = "FITS" if not (row["overflow"] or row["clipped"] or row["page_scroll"]) else "OVER"
        print(f"{flag}  {row['screen']:5} {row['size']:7} {row['frame']:8} spare={row['spare']}px")
    print(results["budget"])


if __name__ == "__main__":
    main()
