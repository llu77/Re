"""
التسجيل بلا رابط على الواجهة الجديدة، بالحجمين وفي كل إطار
=========================================================
من الترحيب إلى الرئيسية شاشةً شاشة، بعقد النظر بقيم الحجم المختار؛ والحساب في القاعدة
بطريقة استخدامه ونسخة الإشعار التي عُرضت، وفي الدفتر صفّه بلا رابط.
"""

from __future__ import annotations

import pytest

from eyework import auth, terms
from eyework.tests.ui.conftest import LOGIN_KEY
from eyework.tests.ui.next.conftest import DESKTOP, PHONES, STRESS, TABLETS, frame_ids
from eyework.tests.ui.next.flow import Flow

#: أضيق هاتف، وهاتفٌ حديث، وأصغر آيباد، والحاسوب.
SIGNUP_FRAMES = [STRESS, PHONES[0], TABLETS[0], DESKTOP]


def walk_sign_up(flow: Flow, page, *, size: str, profession: str = "MARKETING", email: str = "Sara.Worker@Example.SA") -> None:
    """من «أنشئ حساباً» إلى «أنشئ حسابي» المكتوبة كلمةُ مروره، بفحص كل شاشة."""
    flow.screen("#welcome-signup")
    flow.audit("welcome")
    flow.press("#welcome-signup", lambda: flow.screen("#notice-next"), "أنشئ حساباً")
    flow.audit("notice-kept")
    flow.press("#notice-next", lambda: flow.screen("#signup-agree"), "التالي")
    flow.audit("notice-sent")
    flow.press("#signup-agree", lambda: flow.screen("#signup-use-next"), "أوافق وأتابع")
    flow.audit("use")
    flow.press(f"#signup-use-{'GAZE' if size == 'gaze' else 'COMPACT'}", lambda: None, "طريقة الاستخدام")
    flow.press("#signup-use-next", lambda: flow.screen("#signup-name-input"), "التالي: الاسم")
    flow.audit("name")
    page.fill("#signup-name-input", "سارة  العتيبي")
    flow.press("#signup-name-next", lambda: flow.screen("#signup-year-presets"), "التالي: السنة")
    flow.audit("year-empty")
    flow.press("#signup-year-presets [data-key='1990']", lambda: flow.until(
        "!document.querySelector('#signup-year-next').disabled"), "سنة جاهزة")
    flow.press("#signup-year-up", lambda: flow.until(
        "document.querySelector('#signup-year-value').textContent.includes('1991')"), "أحدث")
    flow.audit("year")
    flow.press("#signup-year-next", lambda: flow.screen("#signup-month-presets"), "التالي: الشهر")
    flow.press("#signup-month-presets [data-key='3']", lambda: flow.until(
        "!document.querySelector('#signup-month-next').disabled"), "شهر جاهز")
    flow.audit("month")
    flow.press("#signup-month-next", lambda: flow.screen("#signup-day-presets"), "التالي: اليوم")
    flow.press("#signup-day-presets [data-key='20']", lambda: flow.until(
        "!document.querySelector('#signup-day-next').disabled"), "يوم جاهز")
    flow.press("#signup-day-up", lambda: flow.until(
        "document.querySelector('#signup-day-value').textContent.includes('21')"), "التالي")
    flow.audit("day")
    flow.press("#signup-day-next", lambda: flow.screen(f"#signup-profession-{profession}"), "التالي: المهنة")
    flow.audit("profession-empty")
    flow.press(f"#signup-profession-{profession}", lambda: flow.until(
        "!document.querySelector('#signup-profession-next').disabled"), "مهنة")
    flow.audit("profession")
    flow.press("#signup-profession-next", lambda: flow.screen("#signup-email-input"), "التالي: البريد")
    flow.audit("email")
    page.fill("#signup-email-input", email)
    flow.press("#signup-email-next", lambda: flow.screen("#signup-review-next"), "التالي: المراجعة")
    flow.audit("review")
    assert page.text_content("#signup-review-birth") == "21 مارس 1991"
    assert page.text_content("#signup-review-email") == email.lower()
    flow.press("#signup-review-next", lambda: flow.screen("#signup-password-input"), "التالي: كلمة المرور")
    flow.audit("password")
    page.fill("#signup-password-input", "Strong-Password-2026-y")


def _posts(page, base: str) -> list[str]:
    return [url.removeprefix(base) for method, url in page.requests if method != "GET"]


@pytest.mark.parametrize(("width", "height"), SIGNUP_FRAMES, ids=frame_ids(SIGNUP_FRAMES))
@pytest.mark.parametrize("size", ["compact", "gaze"])
def test_signing_up_without_a_link_reaches_the_home_at_each_size(next_page, server, owner, width, height, size):
    page = next_page(width, height, size=size)
    flow = Flow(page)
    page.goto(page.next)
    walk_sign_up(flow, page, size=size)
    assert page.evaluate("() => document.documentElement.dataset.size") == size
    # سؤال التوفّر وحده قبل الخطوة الأولى؛ ولا يُرسَل شيءٌ قبل الأخيرة.
    assert [url for _, url in page.requests if url.endswith("/api/auth/registration")] == [server["base"] + "/api/auth/registration"]
    assert _posts(page, server["base"]) == []
    flow.gaze_safe()
    flow.press("#signup-create", lambda: flow.screen("[aria-label='ابدأ عملاً']"), "أنشئ حسابي")
    flow.audit("home")
    assert page.evaluate("() => document.documentElement.dataset.size") == size

    assert not flow.failures(), "\n".join(flow.failures())
    # قاعدتا الهبوط والأقرب إلى النظر للحجم الكبير: باللمس لا تضغط نظرةٌ باقية شيئاً.
    if size == "gaze" and (width, height) != DESKTOP:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    with owner.cursor() as cursor:
        cursor.execute("SELECT display_name, birth_date::text, profession, open_registered, ui_size, terms_version"
                       " FROM users WHERE login_hmac = %s", (auth.login_hmac(LOGIN_KEY, "sara.worker@example.sa"),))
        assert cursor.fetchone() == ("سارة العتيبي", "1991-03-21", "MARKETING", True, size.upper() if size == "gaze" else "COMPACT",
                                     terms.TERMS_VERSION)
        cursor.execute("SELECT via, outcome FROM registration_ledger")
        assert cursor.fetchall() == [("OPEN", "OK")]


def test_a_storekeeper_lands_on_the_account_until_the_inventory_package(next_page, server, owner):
    """مهنةٌ بلا مساحة عملٍ في هذه الحزمة: «حسابي» هو الرئيسية، ولا زرٌّ يفتح ما ليس موجوداً."""
    page = next_page(size="compact")
    flow = Flow(page)
    page.goto(page.next)
    walk_sign_up(flow, page, size="compact", profession="STOREKEEPER")
    flow.press("#signup-create", lambda: flow.screen("#account-ui-size-apply"), "أنشئ حسابي")
    flow.audit("account-home")
    assert page.locator("[aria-label='ابدأ عملاً']").count() == 0
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_a_full_day_is_said_before_the_first_step(next_page, server, owner):
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO registration_ledger (occurred_at, via, outcome)"
                       " SELECT now() - interval '1 hour', 'OPEN', 'OK' FROM generate_series(1, 150)")
    page = next_page(size="gaze")
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#welcome-signup")
    flow.press("#welcome-signup", lambda: flow.screen("#notice-ack"), "أنشئ حساباً")
    flow.audit("full-day")
    assert "اكتمل عدد الحسابات الجديدة" in page.text_content("[role=alert]")
    flow.press("#notice-ack", lambda: flow.screen("input[name='username']"), "حسناً")
    assert _posts(page, server["base"]) == ["/api/auth/passkey/options"] or _posts(page, server["base"]) == []
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


def test_a_later_step_cannot_be_opened_before_the_earlier_ones(next_page, server, owner):
    page = next_page()
    page.goto(page.next + "#/signup/email")
    # في الوضع المفتوح تسجيلٌ من أوّله: الإشعار (وموافقته في شاشته الثانية) قبل أيّ خطوة.
    page.wait_for_selector("#signup-agree")
    assert page.url.endswith("#/signup/sent")
    assert not page.errors, page.errors
