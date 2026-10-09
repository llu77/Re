"""
«حجم النصّ» في iOS — للنصّ وحده
================================
`font: -apple-system-body` قيمةٌ لـWebKit وحده تأخذ حجم نمط Body من «حجم النصّ»
(Text Size) في iOS، وChromium يُسقطها. فيُحاكى هنا ما يفعله WebKit: كل محدِّدٍ يحملها
في styles.css يأخذ حجم Body — 17 عند الحجم الافتراضي، و23 عند xxxLarge، و53 عند
AX5 (جدول Apple بالنقاط؛ ويُفترض بلا قياسٍ أن النقطة px في الصفحة بلا تكبير).
وعند كلٍّ منها:

  • متن المحتوى بين 18 والسقف (19)، والعنوان فوقه بفرقه الثابت.
  • الجذر 16px، والأزرار وأشرطة الإطار بأحجامها: لا يكبر هدفٌ ولا تتغيّر مسافة.
  • عقد النظر كلّه — الحجم والتباعد والحوافّ وعدد الأهداف، ولا تمرير ولا قصّ،
    وقاعدة الهبوط والأقرب إلى النظر بعد كل نقرة — في المسار الكامل والتسجيل
    والحساب، وفي كل بندٍ من كل بوابة، وفي أطول نصٍّ مقبول، وفي شاشات الدخول
    والتفعيل والخروج والمصادر.

ما يُقاس بالحجم وحده (البوابات والصفحة الكاملة والنصّ المقترح) يكفيه أضيق إطارين،
375×635 و320×635: كل إطارٍ آخر أعرض منهما وأطول. وما فيه هبوطٌ يُفحص في كل إطار.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eyework import auth, professions
from eyework.tests.fakes import ok
from eyework.tests.ui import test_passkeys, test_portals, test_proposal_fit
from eyework.tests.ui.conftest import DESKTOP, HANDHELD, LOGIN, PHONES, STRESS, VIEWPORTS
from eyework.tests.ui.flow import Flow, sample_photo

STYLES = Path(__file__).resolve().parents[2] / "static" / "styles.css"
#: حجم Body بالنقاط: الافتراضي (Large)، وxxxLarge، وAX5.
SIZES = [17, 23, 53]
#: سقف المتن في `.content` (`--fs-cap`)، وأرضه المتن الثابت.
CAP = 19
FLOOR = 18
#: أضيق إطارين: لا يتّسع نصٌّ فيهما إلا اتّسع في كل إطارٍ أعرض وأطول.
TIGHTEST = [PHONES[0], STRESS]
IDS = [f"{w}x{h}" for w, h in VIEWPORTS]
TIGHTEST_IDS = [f"{w}x{h}" for w, h in TIGHTEST]


def _system_font_rules() -> list[str]:
    """المحدِّدات التي تحمل `font: -apple-system-body` في styles.css."""
    css = re.sub(r"/\*.*?\*/", "", STYLES.read_text(encoding="utf-8"), flags=re.S)
    return [selector.strip() for selector, block in re.findall(r"([^{}]+)\{([^}]*)\}", css)
            if re.search(r"(?<![\w-])font\s*:\s*-apple-system-body\b", block)]


def _system_body(px: int) -> str:
    """نصٌّ مُهيّأ: ما يعطيه WebKit لتلك المحدِّدات عند حجم Body هذا. ورقة أنماطٍ
    مبنيّة لا عنصر <style>: CSP الصفحة (style-src 'self') باقيةٌ كما هي."""
    rules = " ".join(f"{selector} {{ font-size: {px}px; }}" for selector in _system_font_rules())
    return ("(() => { const sheet = new CSSStyleSheet();"
            f" sheet.replaceSync({json.dumps(rules)});"
            " document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();")


@pytest.fixture(params=SIZES, ids=[f"body{px}" for px in SIZES])
def text_size(request) -> int:
    return request.param


@pytest.fixture
def sized_factory(page_factory, text_size):
    """`page_factory` نفسه، وكل صفحةٍ فيه بحجم Body المختار."""
    def make(*args, **kwargs):
        page = page_factory(*args, **kwargs)
        page.add_init_script(script=_system_body(text_size))
        return page

    return make


def test_text_follows_the_system_size_and_the_frame_does_not(sized_factory, server, text_size):
    page = sized_factory()
    page.goto(server["base"] + "/#/")
    flow = Flow(page, server["base"])
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    sizes = page.evaluate("""() => {
        const px = (e) => parseFloat(getComputedStyle(e).fontSize);
        const box = (e) => { const r = e.getBoundingClientRect(); return [r.width, r.height]; };
        const $ = (s) => document.querySelector(s);
        return {
            root: px(document.documentElement),
            text: px($('.screen[data-screen=home] .content')),
            heading: px($('#home-greeting')),
            step: px($('#home-portal')),
            bar_button: px($('#home-account')),
            content_button: px($('#home-tasks')),
            bar_box: box($('#home-account')),
            content_box: box($('#home-tasks')),
        };
    }""")
    expected = min(max(text_size, FLOOR), CAP)
    assert sizes["text"] == expected, sizes
    assert sizes["heading"] == expected + 4, sizes
    assert sizes["root"] == 16, sizes
    assert sizes["step"] == 16, sizes
    # «المهامّ» في شبكةٍ من ثلاثة أزرار، وخطّها فيها 16.
    assert sizes["bar_button"] == FLOOR and sizes["content_button"] == 16, sizes
    assert abs(sizes["bar_box"][1] - 72) < 0.5 and min(sizes["content_box"]) >= 71.5, sizes


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_every_screen_honours_the_gaze_contract_at_each_text_size(sized_factory, server, width, height):
    page = sized_factory(width, height)
    flow = Flow(page, server["base"])
    flow.run()
    failures = test_portals._failures(flow)
    if (width, height) != DESKTOP:
        failures += flow.landings
    assert not failures, "\n".join(failures)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_signing_up_at_each_text_size(sized_factory, server, owner, width, height):
    test_portals.test_signing_up_from_the_link_to_the_portal(sized_factory, server, owner, width, height)


@pytest.mark.parametrize(("width", "height"), HANDHELD, ids=[f"{w}x{h}" for w, h in HANDHELD])
def test_deleting_the_account_at_each_text_size(sized_factory, server, owner, width, height):
    test_portals.test_deleting_the_account_takes_two_steps(sized_factory, server, owner, width, height)


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
@pytest.mark.parametrize("profession", list(professions.Profession), ids=lambda p: p.value)
def test_every_portal_item_at_each_text_size(sized_factory, server, owner, profession, width, height):
    test_portals.test_every_portal_and_every_item_fit_one_screen(
        sized_factory, server, owner, profession, width, height)


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_a_full_page_of_campaigns_at_each_text_size(sized_factory, server, owner, app, width, height):
    test_portals.test_a_full_page_of_campaigns_fits_the_home_screen(sized_factory, server, owner, app, width, height)


@pytest.mark.parametrize("description", [test_proposal_fit.EVEN, test_proposal_fit.WASTEFUL],
                         ids=["even", "wasteful"])
@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_the_longest_valid_copy_at_each_text_size(sized_factory, server, description, width, height):
    """
    والملاحظة إن عُرضت وحدها أولاً تُقرأ كاملةً في مكانها: التنبيه يغطّي المحتوى
    المقصوص، وفحص القصّ العامّ لا يدخله.
    """
    fit = test_proposal_fit
    server["writer"].queue(ok(fit.TITLE, description, fit.NOTE))
    page = sized_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/new")
    flow.screen("photo")
    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    flow.press("#photo-generate", lambda: flow.until("!document.querySelector('#proposal-copy').hidden"),
               "اكتب لي العنوان والوصف")
    alert = page.locator(".screen[data-screen='proposal'] .alert")
    if alert.is_visible():
        assert fit.NOTE in alert.inner_text()
        inside = alert.evaluate("(a) => a.scrollHeight <= a.clientHeight + 1")
        assert inside, "الملاحظة أطول من مكانها"
        flow.press(".screen[data-screen='proposal'] [data-ack]", lambda: flow.until(
            "document.querySelector('.screen[data-screen=proposal] .alert').hidden"), "حسناً")
    else:
        assert fit.NOTE in page.inner_text("#proposal-note")
    audit = flow.audit("proposal")
    assert not audit["clipped"] and not audit["vertical"], audit
    assert page.inner_text("#proposal-description").replace("\n", "") == description.replace("\n", "")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_the_worst_wrapping_copy_at_each_text_size(sized_factory, server, width, height):
    test_proposal_fit.test_the_worst_wrapping_copy_is_never_clipped(sized_factory, server, width, height, 100)


def _alert_fits(page) -> None:
    """نصّ التنبيه داخل مكانه: التنبيه يغطّي المحتوى، وفحص القصّ العامّ لا يدخله."""
    inside = page.evaluate("() => { const a = document.querySelector('.screen:not([hidden]) .alert');"
                           " return a.scrollHeight <= a.clientHeight + 1; }")
    assert inside, "نصّ التنبيه أطول من مكانه"


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_the_sign_in_screen_with_and_without_its_alert_at_each_text_size(sized_factory, server, width, height):
    """
    شاشة الدخول وفيها صفّ «ادخل» و«ادخل بمفتاح المرور»، وتحته سطر المساعدة كاملاً؛
    ثم أطول تنبيهٍ فيها: مفتاح مرورٍ لم يكتمل الدخول به.
    """
    page = sized_factory(width, height, session=False)
    test_passkeys._device(page, [], "refuse")
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    test_passkeys._ready(flow)
    flow.audit("login")
    flow.press("#login-passkey", lambda: test_passkeys._alert(flow), "ادخل بمفتاح المرور")
    assert test_passkeys._alert(flow) == test_passkeys.NOT_SIGNED_IN
    flow.audit("login alert")
    _alert_fits(page)
    test_passkeys._acknowledge(flow)
    flow.audit("login after the alert")
    failures = test_portals._failures(flow) + flow.landings
    assert not failures, "\n".join(failures)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_the_activation_screen_with_and_without_its_alert_at_each_text_size(sized_factory, server, width, height):
    page = sized_factory(width, height, session=False)
    flow = Flow(page, server["base"])
    page.goto(f"{server['base']}/#activate={auth.new_token()}&u={LOGIN}")
    flow.screen("activate")
    flow.audit("activate")
    page.fill("#activate-password", "Activated-Password-2026-z")
    flow.press(".screen[data-screen='activate'] [type='submit']", lambda: flow.until(
        "document.querySelector('.screen[data-screen=activate] .alert:not([hidden])') !== null"), "فعّل حسابي")
    flow.audit("activate alert")
    _alert_fits(page)
    failures = test_portals._failures(flow) + flow.landings
    assert not failures, "\n".join(failures)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
def test_signing_out_at_each_text_size(sized_factory, server, width, height):
    test_portals.test_signing_out_takes_two_steps(sized_factory, server, width, height)


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=TIGHTEST_IDS)
@pytest.mark.parametrize("profession", list(professions.Profession), ids=lambda p: p.value)
def test_the_sources_screen_at_each_text_size(sized_factory, server, owner, profession, width, height):
    test_portals.test_the_sources_screen_gives_the_full_onet_notice(
        sized_factory, server, owner, profession, width, height)
