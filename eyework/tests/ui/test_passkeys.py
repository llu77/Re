"""
مفاتيح المرور في الواجهة — في متصفّحٍ حقيقي
=============================================
«ادخل بمفتاح المرور» في شاشة الدخول وحده؛ ولا شيء لمفتاح المرور في «حسابي». المفتاح
يُنشئه المتصفّح بعد الدخول بكلمة المرور مباشرةً (الإنشاء المشروط)، بلا زرٍّ ولا
شاشة. يقودهما المُصادِق الافتراضي في Chromium (WebAuthn عبر CDP): مفتاحٌ داخلي
(`internal`) يحفظه الجهاز ويتحقّق من صاحبه — أداة اختبارٍ تقوم مقام Face ID، لا
شيفرة إنتاج. والخادم يتحقّق من ردّه كما يتحقّق من iPhone.

والإنشاء المشروط لا يُجريه Chromium هنا: شرطه مدير كلمات مرورٍ ملأ كلمة المرور للتوّ.
فنصٌّ مُهيّأ يقول ما يقوله المتصفّح — `getClientCapabilities().conditionalCreate` —
ويُجري الطلب المشروط على المُصادِق الافتراضي نفسه، أو يرفضه كما يرفضه المتصفّح.

  • بعد الدخول بكلمة المرور: حيث يُدعم الإنشاء المشروط وحده يُطلب، بلا نافذةٍ ولا
    تنبيه؛ والرفض أو الغياب صامت، والدخول يمضي إلى الرئيسية كما كان.
  • الجهاز يُستدعى للدخول داخل الضغطة نفسها، قبل أيّ انتظار: الخيارات جُلبت حين
    عُرضت الشاشة، ولا حقل مركَّز. وخياراتٌ أقدم من أربع دقائق لا تُعطى للجهاز، وتُجلب
    خياراتٌ جديدة كلما عادت الصفحة ظاهرة.
  • كل محاولةٍ — نجحت أو فشلت — تجلب تحدّياً جديداً، والفشل يُقال بتنبيه.
  • عقد النظر على شاشة الدخول وشاشة الحساب عند كل إطار، وقاعدة الهبوط والأقرب إلى
    النظر بعد كل ضغطة (flow.py).
  • كلمة المرور باقيةٌ بجانب المفتاح، وبلا WebAuthn لا يُعرض زرٌّ ولا يُطلب تحدٍّ.
"""

from __future__ import annotations

import json
import re
import time

import pytest

from eyework import auth, passkeys
from eyework.tests.ui.conftest import HANDHELD, LOGIN, LOGIN_KEY, PASSWORD, VIEWPORTS
from eyework.tests.ui.flow import Flow

IDS = [f"{w}x{h}" for w, h in VIEWPORTS]
HANDHELD_IDS = [f"{w}x{h}" for w, h in HANDHELD]
HOVER_OR_GESTURE = re.compile(r"^(pointer|mouse|touch|drag|wheel|contextmenu)")
LOGIN_OPTIONS = "/api/auth/passkey/options"
ADD_OPTIONS = "/api/me/passkeys/options"
ADD = "/api/me/passkeys"
NOT_READY = "لم يجهز مفتاح المرور بعد. حاول مرة أخرى."
NOT_SIGNED_IN = ("لم يكتمل الدخول بمفتاح المرور. ادخل بكلمة المرور؛ وإن ملأها جهازك من سلسلة المفاتيح"
                 " فقد يُنشئ لك مفتاح مرورٍ بعدها.")
REFUSED = "تعذّر الدخول بمفتاح المرور. حاول مرة أخرى، أو ادخل بكلمة المرور."

#: يسجّل كل استدعاءٍ للجهاز: أفي أثناء الضغطة كان (بين أول مستمعٍ لها وآخره)، وهل
#: كان حقلٌ مركَّزاً، وبأيّ وساطة، وباسم أيّ حساب. والسجلّ عند الاختبار لا في الصفحة:
#: الدخول يعيد تحميلها. ثم يقول ما يقوله المتصفّح عن الإنشاء المشروط (`upgrade`):
#:   create      — مدعوم، ويُنشأ المفتاح على المُصادِق الافتراضي؛
#:   refuse      — مدعوم، والمتصفّح يرفض (`NotAllowedError`) كما يرفض حين لم يملأ كلمة المرور؛
#:   unsupported — `conditionalCreate: false`؛
#:   absent      — لا `getClientCapabilities` أصلاً.
WATCH = """
(() => {
    const upgrade = %s;
    let inClick = false;
    window.addEventListener('click', () => { inClick = true; }, true);
    window.addEventListener('click', () => { inClick = false; });
    if (!window.PublicKeyCredential || !navigator.credentials) return;
    if (upgrade === 'absent') {
        delete PublicKeyCredential.getClientCapabilities;
    } else {
        PublicKeyCredential.getClientCapabilities = async () => ({ conditionalCreate: upgrade !== 'unsupported' });
    }
    for (const name of ['get', 'create']) {
        const original = navigator.credentials[name].bind(navigator.credentials);
        navigator.credentials[name] = (options) => {
            const active = document.activeElement;
            const call = { name, inClick, field: Boolean(active && active.matches('input, textarea')),
                           mediation: options.mediation || null };
            if (name === 'create') call.user = options.publicKey.user.name;
            window.__passkeyCall(call);
            if (options.mediation !== 'conditional') return original(options);
            if (upgrade === 'refuse') return Promise.reject(new DOMException('no autofill', 'NotAllowedError'));
            return original({ publicKey: options.publicKey });
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


def _device(page, calls: list, upgrade: str = "create") -> tuple:
    """مُصادِقٌ افتراضي لهذه الصفحة، ومراقبة استدعائه. قبل أوّل تحميل."""
    page.expose_function("__passkeyCall", lambda call: calls.append(call))
    page.add_init_script(WATCH % json.dumps(upgrade))
    cdp = page.context.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    authenticator = cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
        "protocol": "ctap2", "transport": "internal", "hasResidentKey": True,
        "hasUserVerification": True, "isUserVerified": True, "automaticPresenceSimulation": True,
    }})["authenticatorId"]
    return cdp, authenticator


def _posts(page, path: str) -> int:
    return len([url for method, url in page.requests if method == "POST" and url.endswith(path)])


def _ready(flow: Flow) -> None:
    flow.until("state.passkey !== null && state.passkey.options !== null")


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


def _sign_in_with_password(flow: Flow) -> None:
    """شاشة الدخول، ثم كلمة المرور كما يملؤها النظام، ثم «ادخل» حتى الرئيسية."""
    flow.page.goto(flow.base + "/#/login")
    flow.screen("login")
    _ready(flow)
    flow.audit("login")
    flow.page.fill("#login-username", LOGIN)
    flow.page.fill("#login-password", PASSWORD)
    flow.press("#login-submit", lambda: flow.screen("home"), "ادخل")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.audit("home")


def _log_out(flow: Flow) -> None:
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.audit("account")
    flow.press("#account-logout", lambda: flow.screen("account-logout"), "تسجيل الخروج")
    flow.audit("account-logout")
    flow.press("#account-logout-yes", lambda: flow.screen("login"), "نعم، اخرج")
    _ready(flow)
    flow.audit("login")


def _no_alert_was_shown(page) -> None:
    assert page.evaluate("() => [...document.querySelectorAll('.alert')].every((a) => a.hidden)")


# ── الطريق كاملاً ──────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_a_password_sign_in_creates_the_passkey_and_the_passkey_signs_in_with_one_press(
        page_factory, server, owner, width, height):
    page = page_factory(width, height, session=False)
    calls: list = []
    cdp, authenticator = _device(page, calls)
    flow = Flow(page, server["base"])

    _sign_in_with_password(flow)
    # بعد الدخول بكلمة المرور: طلبٌ مشروط واحد باسم الدخول، خارج أيّ ضغطة، ولا نافذة.
    assert calls == [{"name": "create", "inClick": False, "field": False, "mediation": "conditional",
                      "user": LOGIN}], calls
    assert _posts(page, "/api/auth/login") == 1 and _posts(page, ADD_OPTIONS) == 1 and _posts(page, ADD) == 1
    assert _passkeys(owner) == [(True, ["internal"], False)]
    stored = cdp.send("WebAuthn.getCredentials", {"authenticatorId": authenticator})["credentials"]
    assert len(stored) == 1 and stored[0]["isResidentCredential"] and stored[0]["rpId"] == "localhost"
    log = page.evaluate("() => window.__eyework")
    assert log["timers"] == [] and log["camera"] == 0, log
    assert not [t for t in log["listeners"] if HOVER_OR_GESTURE.match(t)], log["listeners"]

    _log_out(flow)
    assert _posts(page, LOGIN_OPTIONS) == 2
    flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
    flow.until("document.querySelector('#home-portal').textContent !== ''")

    # الجهاز استُدعي داخل الضغطة بخياراتٍ جاهزة، ولا حقل مركَّز، ولا كلمة مرور.
    assert calls[1:] == [{"name": "get", "inClick": True, "field": False, "mediation": None}], calls
    assert _posts(page, LOGIN_OPTIONS) == 2
    assert _posts(page, "/api/auth/passkey") == 1 and _posts(page, "/api/auth/login") == 1
    assert _passkeys(owner) == [(True, ["internal"], True)]
    assert not _failures(flow), "\n".join(_failures(flow))
    if (width, height) != VIEWPORTS[-1]:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    foreign = [url for _, url in page.requests if not url.startswith(server["base"])]
    assert not foreign, foreign


def test_nothing_on_the_sign_in_screen_changes_while_the_passkey_is_created(page_factory, server, owner):
    """الإنشاء بين «ادخل» والرئيسية: لا تنبيه، ولا زرّ يتغيّر، ولا حقل يُمحى قبل الانتقال."""
    page = page_factory(session=False)
    calls: list = []
    _device(page, calls)
    held: list = []
    page.route(f"**{ADD_OPTIONS}", lambda route: held.append(route))
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    _ready(flow)
    page.fill("#login-username", LOGIN)
    page.fill("#login-password", PASSWORD)
    before = page.evaluate("() => document.querySelector('.screen[data-screen=login]').innerHTML")
    page.click("#login-submit")
    for _ in range(200):
        if held:
            break
        page.wait_for_timeout(25)
    assert held
    assert page.is_visible(".screen[data-screen='login']")
    assert page.evaluate("() => document.querySelector('.screen[data-screen=login]').innerHTML") == before
    assert page.input_value("#login-password") == PASSWORD
    _no_alert_was_shown(page)
    held[0].continue_()
    flow.screen("home")
    assert len(_passkeys(owner)) == 1
    assert not page.errors, page.errors


@pytest.mark.parametrize("upgrade", ["refuse", "unsupported", "absent"])
def test_without_the_conditional_create_the_password_sign_in_goes_home_as_before(page_factory, server, owner,
                                                                                 upgrade):
    """
    رفض المتصفّح (كلمة مرورٍ لم يملأها مديرها، أو تصفّحٌ خاص) أو غياب الدعم صامتٌ: لا
    تنبيه ولا نافذة، والرئيسية كما كانت. وحيث لا دعم لا يُطلب حتى تحدٍّ.
    """
    page = page_factory(session=False)
    calls: list = []
    _device(page, calls, upgrade)
    flow = Flow(page, server["base"])
    _sign_in_with_password(flow)
    _no_alert_was_shown(page)
    assert _passkeys(owner) == []
    if upgrade == "refuse":
        assert [(c["name"], c["mediation"]) for c in calls] == [("create", "conditional")]
        assert _posts(page, ADD_OPTIONS) == 1
    else:
        assert calls == []
        assert _posts(page, ADD_OPTIONS) == 0
    assert _posts(page, ADD) == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("authenticator", [False, True], ids=["no-authenticator", "authenticator-attached"])
def test_in_chromium_itself_a_typed_password_creates_no_passkey_and_the_sign_in_does_not_hang(
        page_factory, server, owner, authenticator):
    """
    بلا نصٍّ مُهيّأ: Chromium نفسه، وكلمة مرورٍ كُتبت ولم يملأها مديرها فلا يُنشئ مفتاحاً.
    بلا مُصادِقٍ يرفض فوراً؛ ومعه ينتظر مهلة الخيارات كلّها ثم يرفض. فالمهلة ثوانٍ
    (`UPGRADE_TIMEOUT_SECONDS`) لا مهلة التحدّي، والدخول يبلغ الرئيسية بعدها بلا تنبيه.
    """
    page = page_factory(session=False)
    if authenticator:
        cdp = page.context.new_cdp_session(page)
        cdp.send("WebAuthn.enable")
        cdp.send("WebAuthn.addVirtualAuthenticator", {"options": {
            "protocol": "ctap2", "transport": "internal", "hasResidentKey": True,
            "hasUserVerification": True, "isUserVerified": True, "automaticPresenceSimulation": True,
        }})
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    _ready(flow)
    page.fill("#login-username", LOGIN)
    page.fill("#login-password", PASSWORD)
    started = time.monotonic()
    flow.press("#login-submit", lambda: page.wait_for_selector(
        ".screen[data-screen='home']:not([hidden])", timeout=(passkeys.UPGRADE_TIMEOUT_SECONDS + 10) * 1000), "ادخل")
    assert time.monotonic() - started < passkeys.UPGRADE_TIMEOUT_SECONDS + 10
    _no_alert_was_shown(page)
    assert _posts(page, ADD_OPTIONS) == 1 and _posts(page, ADD) == 0
    assert _passkeys(owner) == []
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("failure", [ADD_OPTIONS, ADD])
def test_a_server_refusal_during_the_creation_is_silent_too(page_factory, server, owner, failure):
    page = page_factory(session=False)
    _device(page, [])
    page.route(f"**{failure}", lambda route: route.fulfill(
        status=503, content_type="application/json", body='{"code": "UNAVAILABLE", "detail": "الخدمة غير متاحة."}'))
    flow = Flow(page, server["base"])
    _sign_in_with_password(flow)
    _no_alert_was_shown(page)
    assert _passkeys(owner) == []
    assert not page.errors, page.errors


# ── «حسابي» بلا مفتاح المرور ───────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_the_account_screen_offers_nothing_for_passkeys(page_factory, server, width, height):
    """لا زرّ ولا سطر ولا طلب تحدٍّ في «حسابي»؛ وأقرب ما إلى نظرٍ باقٍ على «حسابي» «رجوع»."""
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.until("document.querySelector('#account-profession').textContent !== '\\u00a0'")
    flow.audit("account")
    screen = page.locator(".screen[data-screen='account']")
    assert "مفتاح" not in screen.inner_text()
    assert page.locator("[id^='account-passkey']").count() == 0
    labels = page.evaluate("() => [...document.querySelectorAll('.screen[data-screen=account] button')]"
                           ".filter((b) => b.closest('.alert') === null).map((b) => b.textContent.trim())")
    assert labels == ["رجوع", "المصادر", "احذف حسابي", "تسجيل الخروج"], labels
    assert _posts(page, ADD_OPTIONS) == 0 and _posts(page, LOGIN_OPTIONS) == 0
    if (width, height) != VIEWPORTS[-1]:
        assert {n["name"] for n in flow.nearest[-1][1]} == {"رجوع"}, flow.nearest[-1]
        assert not flow.landings, "\n".join(flow.landings)
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not page.errors, page.errors


# ── فشل الدخول ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), HANDHELD, ids=HANDHELD_IDS)
def test_a_key_the_device_does_not_hold_says_so_and_the_password_still_signs_in(page_factory, server, owner,
                                                                                 width, height):
    page = page_factory(width, height, session=False)
    calls: list = []
    _device(page, calls, "refuse")
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    _ready(flow)
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
    assert [(c["name"], c["inClick"], c["field"]) for c in calls] == [("get", True, False), ("create", False, False)]
    assert _posts(page, "/api/auth/passkey") == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), HANDHELD, ids=HANDHELD_IDS)
def test_a_refused_key_says_so_and_the_next_press_uses_a_new_challenge(page_factory, server, owner,
                                                                       width, height):
    page = page_factory(width, height, session=False)
    _device(page, [])
    flow = Flow(page, server["base"])
    _sign_in_with_password(flow)
    _log_out(flow)

    # عدّادٌ رجع في الخادم: يرفض التوقيع، والتحدّي الذي وقّعه استُهلك.
    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkeys SET sign_count = 1000000")
    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == REFUSED
    assert _posts(page, LOGIN_OPTIONS) == 3
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
    _ready(flow)
    flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    assert _posts(page, "/api/auth/passkey") == 2
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
    page.wait_for_function("() => state.passkey !== null")
    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == NOT_READY
    assert calls == []
    assert len(held) == 1
    held[0].continue_()
    _ready(flow)
    assert not page.errors, page.errors


# ── خياراتٌ قدمت ───────────────────────────────────────────────────────
#: يقدّم ساعة الصفحة (`Date.now`) دقائق: الخيارات جُلبت «قبلها».
LATER = "(ms) => { const now = Date.now.bind(Date); Date.now = () => now() + ms; }"


@pytest.mark.parametrize(("minutes", "fresh"), [(3.9, True), (4.1, False)])
def test_options_older_than_four_minutes_are_fetched_again_before_the_device_is_asked(
        page_factory, server, owner, minutes, fresh):
    """
    التحدّي ينتهي بعد خمس دقائق في الخادم. شاشة الدخول تُركت مفتوحة: ضغطةٌ بخياراتٍ
    قديمة كانت تطلب Face ID ثم يُرفض التحدّي. الآن: «لم يجهز بعد»، وخياراتٌ جديدة،
    ولا يُسأل الجهاز.
    """
    page = page_factory(session=False)
    calls: list = []
    _device(page, calls)
    flow = Flow(page, server["base"])
    _sign_in_with_password(flow)
    _log_out(flow)
    calls.clear()
    asked = _posts(page, LOGIN_OPTIONS)
    page.evaluate(LATER, minutes * 60 * 1000)
    if fresh:
        flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
        assert [c["name"] for c in calls] == ["get"]
        return
    flow.press("#login-passkey", lambda: _alert(flow), "ادخل بمفتاح المرور")
    assert _alert(flow) == NOT_READY
    assert calls == []
    flow.audit("login-not-ready")
    _acknowledge(flow)
    _ready(flow)
    assert _posts(page, LOGIN_OPTIONS) == asked + 1
    flow.press("#login-passkey", lambda: flow.screen("home"), "ادخل بمفتاح المرور")
    assert [(c["name"], c["inClick"]) for c in calls] == [("get", True)]
    assert _posts(page, "/api/auth/passkey") == 1
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


#: الصفحة عادت ظاهرة (من تطبيقٍ آخر أو من قفل الشاشة).
SHOWN_AGAIN = """() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    document.dispatchEvent(new Event('visibilitychange'));
}"""


def test_the_sign_in_screen_fetches_new_options_when_the_page_is_shown_again(page_factory, server):
    page = page_factory(session=False)
    _device(page, [])
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    _ready(flow)
    first = page.evaluate("() => state.passkey")
    assert _posts(page, LOGIN_OPTIONS) == 1
    page.evaluate(SHOWN_AGAIN)
    _ready(flow)
    assert _posts(page, LOGIN_OPTIONS) == 2
    assert page.evaluate("() => state.passkey.fetchedAt") >= first["fetchedAt"]
    _no_alert_was_shown(page)
    assert not page.errors, page.errors


def test_another_screen_shown_again_asks_for_no_sign_in_options(page_factory, server):
    page = page_factory()
    _device(page, [])
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    page.evaluate(SHOWN_AGAIN)
    page.evaluate("() => fetch('/api/me')")
    assert _posts(page, LOGIN_OPTIONS) == 0
    assert not page.errors, page.errors


# ── بلا WebAuthn ───────────────────────────────────────────────────────
def test_without_webauthn_no_button_is_offered_and_no_challenge_is_asked_for(page_factory, server, owner):
    page = page_factory(session=False)
    page.add_init_script("delete window.PublicKeyCredential;")
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/login")
    flow.screen("login")
    flow.audit("login")
    reserved = "(id) => getComputedStyle(document.getElementById(id)).visibility === 'hidden'" \
               " && document.getElementById(id).disabled"
    assert page.evaluate(reserved, "login-passkey")
    page.evaluate(SHOWN_AGAIN)
    page.fill("#login-username", LOGIN)
    page.fill("#login-password", PASSWORD)
    flow.press("#login-submit", lambda: flow.screen("home"), "ادخل")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.audit("account")
    flow.press("#account-logout", lambda: flow.screen("account-logout"), "تسجيل الخروج")
    flow.audit("account-logout")
    # مفتاح المرور بجانب «ادخل» مخفيٌّ هنا، فلا يقابل «نعم، اخرج» إلا حقلا الدخول.
    flow.press("#account-logout-yes", lambda: flow.screen("login"), "نعم، اخرج")
    flow.audit("login")
    assert page.evaluate(reserved, "login-passkey")
    assert _posts(page, LOGIN_OPTIONS) == 0 and _posts(page, ADD_OPTIONS) == 0
    assert _passkeys(owner) == []
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
