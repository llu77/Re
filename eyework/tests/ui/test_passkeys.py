"""
مفاتيح المرور في الواجهة — في متصفّحٍ حقيقي
=============================================
«أضف مفتاح مرور» في الحساب و«ادخل بمفتاح المرور» في شاشة الدخول، يقودهما
المُصادِق الافتراضي في Chromium (WebAuthn عبر CDP): مفتاحٌ داخلي (`internal`)
يحفظه الجهاز ويتحقّق من صاحبه — أداة اختبارٍ تقوم مقام Face ID، لا شيفرة إنتاج.
والخادم يتحقّق من ردّه كما يتحقّق من iPhone.

  • الجهاز يُستدعى داخل الضغطة نفسها، قبل أيّ انتظار: الخيارات جُلبت حين عُرضت
    الشاشة، ولا حقل مركَّز.
  • كل محاولةٍ — نجحت أو فشلت — تجلب تحدّياً جديداً، والفشل يُقال بتنبيه.
  • عقد النظر على الشاشتين عند كل إطار، وقاعدة الهبوط والأقرب إلى النظر بعد كل
    ضغطة (flow.py).
  • كلمة المرور باقيةٌ بجانب المفتاح، وبلا WebAuthn لا يُعرض زرٌّ ولا يُطلب تحدٍّ.
"""

from __future__ import annotations

import re

import pytest

from eyework import auth
from eyework.tests.ui.conftest import LOGIN, LOGIN_KEY, PASSWORD, VIEWPORTS
from eyework.tests.ui.flow import Flow

IDS = [f"{w}x{h}" for w, h in VIEWPORTS]
HOVER_OR_GESTURE = re.compile(r"^(pointer|mouse|touch|drag|wheel|contextmenu)")
LOGIN_OPTIONS = "/api/auth/passkey/options"
ADD_OPTIONS = "/api/me/passkeys/options"
NOT_SIGNED_IN = ("لم يكتمل الدخول بمفتاح المرور. إن لم يُضَف لحسابك مفتاحٌ بعد، فادخل بكلمة المرور،"
                 " ثم أضفه من «حسابي».")
REFUSED = "تعذّر الدخول بمفتاح المرور. حاول مرة أخرى، أو ادخل بكلمة المرور."
ALREADY_HERE = "في هذا الجهاز مفتاح مرورٍ لهذا الحساب من قبل."
SAVED = "حُفظ مفتاح المرور. ادخل به في المرة القادمة من شاشة الدخول."

#: يسجّل كل استدعاءٍ للجهاز: أفي أثناء الضغطة كان (بين أول مستمعٍ لها وآخره)، وهل
#: كان حقلٌ مركَّزاً. والسجلّ عند الاختبار لا في الصفحة: الدخول يعيد تحميلها.
WATCH = """
(() => {
    let inClick = false;
    window.addEventListener('click', () => { inClick = true; }, true);
    window.addEventListener('click', () => { inClick = false; });
    if (!navigator.credentials) return;
    for (const name of ['get', 'create']) {
        const original = navigator.credentials[name].bind(navigator.credentials);
        navigator.credentials[name] = (options) => {
            const active = document.activeElement;
            window.__passkeyCall({ name, inClick, field: Boolean(active && active.matches('input, textarea')) });
            return original(options);
        };
    }
})();
"""


def _failures(flow: Flow) -> list[str]:
    failures = []
    for audit in flow.audits:
        for key in ("small", "close", "edge", "fonts", "clipped"):
            if audit[key]:
                failures.append(f"{audit['label']} {key}: {audit[key]}")
        if audit["enabled"] > 10:
            failures.append(f"{audit['label']}: {audit['enabled']} أهداف مفعّلة")
        if audit["vertical"] or audit["horizontal"]:
            failures.append(f"{audit['label']}: تمرير")
    return failures


def _device(page, calls: list) -> tuple:
    """مُصادِقٌ افتراضي لهذه الصفحة، ومراقبة استدعائه. قبل أوّل تحميل."""
    page.expose_function("__passkeyCall", lambda call: calls.append(call))
    page.add_init_script(WATCH)
    cdp = page.context.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    authenticator = cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
        "protocol": "ctap2", "transport": "internal", "hasResidentKey": True,
        "hasUserVerification": True, "isUserVerified": True, "automaticPresenceSimulation": True,
    }})["authenticatorId"]
    return cdp, authenticator


def _posts(page, path: str) -> int:
    return len([url for method, url in page.requests if method == "POST" and url.endswith(path)])


def _ready(flow: Flow, kind: str) -> None:
    flow.until(f"state.passkey.{kind} !== null && state.passkey.{kind}.options !== null")


def _alert(flow: Flow) -> str:
    flow.until("document.querySelector('.screen:not([hidden]) .alert:not([hidden])') !== null")
    return flow.page.inner_text(".screen:not([hidden]) .alert__text")


def _acknowledge(flow: Flow) -> None:
    flow.press(".screen:not([hidden]) .alert [data-ack]", lambda: flow.until(
        "document.querySelector('.screen:not([hidden]) .alert:not([hidden])') === null"), "حسناً")


def _passkeys(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT u.login_hmac = %s, p.transports, p.last_used_at IS NOT NULL"
                       " FROM passkeys p JOIN users u ON u.id = p.user_id", (auth.login_hmac(LOGIN_KEY, LOGIN),))
        return cursor.fetchall()


def _add_on_account_screen(flow: Flow) -> None:
    flow.page.goto(flow.base + "/#/")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    _ready(flow, "add")
    flow.audit("account")
    flow.press("#account-passkey", lambda: flow.until(
        "document.querySelector('#account-passkey-status').textContent !== ''"), "أضف مفتاح مرور")
    flow.audit("account-added")


def _log_out(flow: Flow) -> None:
    flow.press("#account-logout", lambda: flow.screen("account-logout"), "تسجيل الخروج")
    flow.audit("account-logout")
    flow.press("#account-logout-yes", lambda: flow.screen("login"), "نعم، اخرج")
    _ready(flow, "login")
    flow.audit("login")


# ── الطريق كاملاً ──────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_a_passkey_added_on_the_account_screen_signs_in_with_one_press(page_factory, server, owner,
                                                                         width, height):
    page = page_factory(width, height)
    calls: list = []
    cdp, authenticator = _device(page, calls)
    flow = Flow(page, server["base"])

    _add_on_account_screen(flow)
    assert page.inner_text("#account-passkey-status") == SAVED
    assert _passkeys(owner) == [(True, ["internal"], False)]
    stored = cdp.send("WebAuthn.getCredentials", {"authenticatorId": authenticator})["credentials"]
    assert len(stored) == 1 and stored[0]["isResidentCredential"] and stored[0]["rpId"] == "localhost"
    # تحدٍّ حين عُرضت الشاشة، وآخر بعد الإضافة للضغطة التالية.
    assert _posts(page, ADD_OPTIONS) == 2
    log = page.evaluate("() => window.__eyework")
    assert log["timers"] == [] and log["camera"] == 0, log
    assert not [t for t in log["listeners"] if HOVER_OR_GESTURE.match(t)], log["listeners"]

    _log_out(flow)
    assert _posts(page, LOGIN_OPTIONS) == 1
    flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
    flow.until("document.querySelector('#home-portal').textContent !== ''")

    # الجهاز استُدعي داخل الضغطة بخياراتٍ جاهزة، ولا حقل مركَّز، ولا كلمة مرور.
    assert calls == [{"name": "create", "inClick": True, "field": False},
                     {"name": "get", "inClick": True, "field": False}], calls
    assert _posts(page, LOGIN_OPTIONS) == 1
    assert _posts(page, "/api/auth/passkey") == 1 and _posts(page, "/api/auth/login") == 0
    assert _passkeys(owner) == [(True, ["internal"], True)]
    assert not _failures(flow), "\n".join(_failures(flow))
    if (width, height) != VIEWPORTS[-1]:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    foreign = [url for _, url in page.requests if not url.startswith(server["base"])]
    assert not foreign, foreign


# ── الفشل ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS[:3], ids=IDS[:3])
def test_a_key_the_device_does_not_hold_says_so_and_the_password_still_signs_in(page_factory, server, owner,
                                                                                 width, height):
    page = page_factory(width, height, session=False)
    calls: list = []
    _device(page, calls)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    _ready(flow, "login")
    flow.audit("login")

    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == NOT_SIGNED_IN
    flow.audit("login-alert")
    # تحدٍّ جديد للضغطة التالية، والحقلان كما كانا.
    assert _posts(page, LOGIN_OPTIONS) == 2
    assert page.input_value("#login-username") == "" and page.input_value("#login-password") == ""
    _acknowledge(flow)

    page.fill("#login-username", LOGIN)
    page.fill("#login-password", PASSWORD)
    flow.press("#login-submit", lambda: flow.screen("home"), "ادخل")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    assert calls == [{"name": "get", "inClick": True, "field": False}], calls
    assert _posts(page, "/api/auth/passkey") == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), VIEWPORTS[:3], ids=IDS[:3])
def test_a_refused_key_says_so_and_the_next_press_uses_a_new_challenge(page_factory, server, owner,
                                                                       width, height):
    page = page_factory(width, height)
    _device(page, [])
    flow = Flow(page, server["base"])
    _add_on_account_screen(flow)
    _log_out(flow)

    # عدّادٌ رجع في الخادم: يرفض التوقيع، والتحدّي الذي وقّعه استُهلك.
    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkeys SET sign_count = 1000000")
    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == REFUSED
    assert _posts(page, LOGIN_OPTIONS) == 2
    flow.audit("login-refused")
    # التنبيه يغطّي الزرّين: نظرٌ باقٍ على أيٍّ منهما يقع على نصّه لا على زرّ.
    for button in ("#login-passkey", "#login-submit"):
        box = page.locator(button).bounding_box()
        covered = page.evaluate("([x, y]) => document.elementFromPoint(x, y).closest('.alert') !== null",
                                [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2])
        assert covered, button
    _acknowledge(flow)

    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkeys SET sign_count = 0")
    _ready(flow, "login")
    flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    assert _posts(page, "/api/auth/passkey") == 2
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


def test_a_second_key_from_the_same_device_is_not_added(page_factory, server, owner):
    """الخيارات تسمّي مفاتيح الحساب (excludeCredentials): الجهاز يرفض الثاني، ويُقال لماذا."""
    page = page_factory()
    calls: list = []
    _device(page, calls)
    flow = Flow(page, server["base"])
    _add_on_account_screen(flow)
    _ready(flow, "add")
    flow.press("#account-passkey", lambda: _alert(flow), "أضف مفتاح مرور")
    assert _alert(flow) == ALREADY_HERE
    flow.audit("account-twice")
    assert len(_passkeys(owner)) == 1
    assert _posts(page, ADD_OPTIONS) == 3
    _acknowledge(flow)
    assert [c["name"] for c in calls] == ["create", "create"]
    assert all(c["inClick"] for c in calls), calls
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


def test_a_press_before_the_options_arrive_says_so_and_asks_nothing_of_the_device(page_factory, server):
    """لا جلب داخل الضغطة: خياراتٌ لم تصل بعد تعني تنبيهاً، لا انتظاراً ثم نافذة."""
    page = page_factory(session=False)
    calls: list = []
    _device(page, calls)
    held: list = []
    page.route(f"**{LOGIN_OPTIONS}", lambda route: held.append(route))
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    page.wait_for_function("() => state.passkey.login !== null")
    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == "لم يجهز مفتاح المرور بعد. حاول مرة أخرى."
    assert calls == []
    assert len(held) == 1
    held[0].continue_()
    _ready(flow, "login")
    assert not page.errors, page.errors


# ── بلا WebAuthn ───────────────────────────────────────────────────────
def test_without_webauthn_no_button_is_offered_and_no_challenge_is_asked_for(page_factory, server):
    page = page_factory()
    page.add_init_script("delete window.PublicKeyCredential;")
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.audit("account")
    reserved = "(id) => getComputedStyle(document.getElementById(id)).visibility === 'hidden'" \
               " && document.getElementById(id).disabled"
    assert page.evaluate(reserved, "account-passkey")
    assert page.is_hidden("#account-passkey-help")
    flow.press("#account-logout", lambda: flow.screen("account-logout"), "تسجيل الخروج")
    flow.audit("account-logout")
    # مفتاح المرور بجانب «ادخل» مخفيّ هنا، فلا يقابل «نعم، اخرج» إلا حقلا الدخول.
    flow.press("#account-logout-yes", lambda: flow.screen("login"), "نعم، اخرج")
    flow.audit("login")
    assert page.evaluate(reserved, "login-passkey")
    assert _posts(page, LOGIN_OPTIONS) == 0 and _posts(page, ADD_OPTIONS) == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
