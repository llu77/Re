"""
التسجيل والبوابات والحساب — في متصفّحٍ حقيقي
=============================================
عقد النظر نفسه (انظر test_gaze.py) على الشاشات الجديدة، عند كل إطار:

  • التسجيل من رابط المشغّل إلى بوابة المهنة، شاشةً شاشة، بقاعدة الهبوط.
  • رئيسية كل بوابة، وكل مهمّةٍ وكل مهارةٍ فيها — أطولها في أصغر إطار.
  • رئيسية التسويق بصفحة حملاتٍ كاملة.
  • حذف الحساب بخطوتين، والرجوع دون حذف.
  • بوابةٌ بلا أداة الحملة لا تفتح شاشاتها.
"""

from __future__ import annotations

import pytest

from eyework import auth, campaigns, professions
from eyework.tests.conftest import add_version, create_campaign
from eyework.tests.ui.conftest import LOGIN, LOGIN_KEY, VIEWPORTS
from eyework.tests.ui.flow import Flow

IDS = [f"{w}x{h}" for w, h in VIEWPORTS]


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


def _user_id(owner):
    with owner.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE login_hmac = %s", (auth.login_hmac(LOGIN_KEY, LOGIN),))
        return cursor.fetchone()[0]


def _set_profession(owner, profession: str) -> None:
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET profession = %s, display_name = 'سارة'", (profession,))


def _issue_code(owner) -> str:
    code = auth.new_token()
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO signup_codes (code_hash, expires_at) VALUES (%s, now() + interval '1 day')",
                       (auth.hash_token(code),))
    return code


# ── التسجيل ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_signing_up_from_the_link_to_the_portal(page_factory, server, owner, width, height):
    code = _issue_code(owner)
    page = page_factory(width, height, session=False)
    flow = Flow(page, server["base"])
    page.goto(f"{server['base']}/#signup={code}")
    flow.screen("signup-notice")
    # الرمز يُمحى من شريط العنوان قبل أيّ شيء.
    assert code not in page.url
    flow.audit("signup-notice")

    flow.press("#signup-agree", lambda: flow.screen("signup-name"), "أوافق وأتابع")
    flow.audit("signup-name")
    page.fill("#signup-name-input", "سارة  العتيبي")
    flow.press("#signup-name-next", lambda: flow.screen("signup-year"), "التالي: السنة")
    flow.audit("signup-year-empty")
    flow.press("#signup-year-presets .chip >> nth=3", lambda: flow.until(
        "!document.querySelector('#signup-year-next').disabled"), "سنة جاهزة")
    flow.press("#signup-year-up", lambda: flow.until(
        "document.querySelector('#signup-year-value').textContent.includes('1991')"), "أحدث")
    flow.audit("signup-year")
    flow.press("#signup-year-next", lambda: flow.screen("signup-month"), "التالي: الشهر")
    flow.audit("signup-month-empty")
    flow.press("#signup-month-presets .chip >> nth=1", lambda: flow.until(
        "!document.querySelector('#signup-month-next').disabled"), "شهر جاهز")
    flow.audit("signup-month")
    flow.press("#signup-month-next", lambda: flow.screen("signup-day"), "التالي: اليوم")
    flow.audit("signup-day-empty")
    flow.press("#signup-day-presets .chip >> nth=4", lambda: flow.until(
        "!document.querySelector('#signup-day-next').disabled"), "يوم جاهز")
    flow.press("#signup-day-up", lambda: flow.until(
        "document.querySelector('#signup-day-value').textContent.includes('21')"), "أحدث")
    flow.audit("signup-day")
    flow.press("#signup-day-next", lambda: flow.screen("signup-profession"), "التالي: المهنة")
    flow.audit("signup-profession-empty")
    flow.press("#signup-professions [data-key='STOREKEEPER']", lambda: flow.until(
        "!document.querySelector('#signup-profession-next').disabled"), "مهنة")
    flow.audit("signup-profession")
    flow.press("#signup-profession-next", lambda: flow.screen("signup-email"), "التالي: البريد")
    flow.audit("signup-email")
    page.fill("#signup-email-input", "Sara.Worker@Example.SA")
    flow.press("#signup-email-next", lambda: flow.screen("signup-review"), "التالي: المراجعة")
    flow.audit("signup-review")
    assert page.text_content("#signup-review-birth") == "تاريخ الميلاد: 21 مارس 1991"
    assert page.text_content("#signup-review-email") == "sara.worker@example.sa"
    flow.press("#signup-review-next", lambda: flow.screen("signup-password"), "التالي: كلمة المرور")
    flow.audit("signup-password")
    page.fill("#signup-password-input", "Strong-Password-2026-y")
    flow.press("#signup-create", lambda: flow.until(
        "document.querySelector('#home-portal') && document.querySelector('#home-portal').textContent"
        " === 'بوابة أمين المخزون'"), "أنشئ حسابي")
    flow.audit("home-storekeeper")

    assert not _failures(flow), "\n".join(_failures(flow))
    if (width, height) != VIEWPORTS[-1]:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    with owner.cursor() as cursor:
        cursor.execute("SELECT display_name, birth_date::text, profession, self_registered FROM users"
                       " WHERE login_hmac = %s", (auth.login_hmac(LOGIN_KEY, "sara.worker@example.sa"),))
        assert cursor.fetchone() == ("سارة العتيبي", "1991-03-21", "STOREKEEPER", True)


def test_a_used_link_says_so_on_the_sign_in_screen(page_factory, server, owner):
    code = _issue_code(owner)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE signup_codes SET used_at = now()")
    page = page_factory(session=False)
    page.goto(f"{server['base']}/#signup={code}")
    Flow(page, server["base"]).screen("login")
    page.wait_for_selector(".screen[data-screen='login'] .alert:not([hidden])")
    assert code not in page.url
    assert not page.errors, page.errors


def test_a_later_step_cannot_be_opened_before_the_earlier_ones(page_factory, server, owner):
    page = page_factory(session=False)
    page.goto(f"{server['base']}/#signup={_issue_code(owner)}")
    flow = Flow(page, server["base"])
    flow.screen("signup-notice")
    page.evaluate("() => { location.hash = '#/signup/password'; }")
    page.wait_for_function("() => location.hash === '#/signup'")
    flow.screen("signup-notice")


# ── البوابات ─────────────────────────────────────────────────────────────
def _walk(flow: Flow, kind: str, count: int, label: str) -> None:
    page = flow.page
    flow.press(f"#home-{kind}", lambda: flow.screen("portal-item"), kind)
    for n in range(1, count + 1):
        flow.until(f"document.querySelector('#portal-item-position').textContent.endsWith('{n} من {count}')")
        flow.audit(f"{label} {kind} {n}")
        assert page.is_visible("#portal-item-source")
        if n < count:
            flow.press("#portal-item-next", lambda: None, "التالي")
    page.go_back(wait_until="commit")


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
@pytest.mark.parametrize("profession", list(professions.Profession), ids=lambda p: p.value)
def test_every_portal_and_every_item_fit_one_screen(page_factory, server, owner, profession, width, height):
    _set_profession(owner, profession.value)
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until(f"document.querySelector('#home-portal').textContent === 'بوابة {professions.NAMES[profession]}'")
    flow.audit(f"home {profession.value}")
    assert page.is_visible("#home-new") == ("CAMPAIGN" in professions.PORTALS[profession].tools)

    portal = professions.view(profession)
    _walk(flow, "tasks", len(portal["tasks"]), profession.value)
    page.goto(server["base"] + "/#/")
    flow.screen("home")
    _walk(flow, "skills", len(portal["skills"]), profession.value)

    assert not _failures(flow), "\n".join(_failures(flow))
    assert not page.errors, page.errors


def test_an_item_number_past_the_end_lands_on_the_last(page_factory, server, owner):
    _set_profession(owner, "SUPPORT")
    page = page_factory()
    page.goto(server["base"] + "/#/tasks/999")
    count = len(professions.PORTALS[professions.Profession.SUPPORT].tasks)
    page.wait_for_function(f"() => location.hash === '#/tasks/{count}'")
    assert page.is_hidden("#portal-item-next") or page.get_attribute("#portal-item-next", "aria-hidden") == "true" \
        or page.evaluate("() => getComputedStyle(document.querySelector('#portal-item-next')).visibility") == "hidden"


@pytest.mark.parametrize("profession", ["STOREKEEPER", "SUPPORT"])
def test_a_portal_without_the_campaign_tool_never_opens_its_screens(page_factory, server, owner, profession):
    _set_profession(owner, profession)
    page = page_factory()
    page.goto(server["base"] + "/#/new")
    page.wait_for_function("() => location.hash === '#/'")
    Flow(page, server["base"]).screen("home")
    assert page.is_hidden("#home-new")
    assert not [url for method, url in page.requests if "/api/campaigns" in url]


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_a_full_page_of_campaigns_fits_the_home_screen(page_factory, server, owner, app, width, height):
    user = _user_id(owner)
    for _ in range(campaigns.PAGE_SIZE + 1):
        campaign = create_campaign(app, user)
        add_version(app, user, campaign, title="حقيبة يد جلدية بلون بنيّ داكن بتصميمٍ عملي")
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until(f"document.querySelectorAll('#home-list li').length === {campaigns.PAGE_SIZE}"
               " && !document.querySelector('#home-older').disabled")
    flow.audit("home-full")
    assert not _failures(flow), "\n".join(_failures(flow))


# ── الحساب ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("width", "height"), VIEWPORTS[:3], ids=IDS[:3])
def test_deleting_the_account_takes_two_steps(page_factory, server, owner, width, height):
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelector('#home-portal').textContent !== ''")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.audit("account")
    flow.press("#account-delete", lambda: flow.screen("account-delete"), "احذف حسابي")
    flow.audit("account-delete")
    flow.press("#account-delete-back", lambda: flow.screen("account"), "رجوع دون حذف")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 1
    flow.press("#account-delete", lambda: flow.screen("account-delete"), "احذف حسابي")
    flow.press("#account-delete-yes", lambda: flow.screen("login"), "نعم، احذف")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


# ── التحقّق في الصفحة كما في الخادم ─────────────────────────────────────
NAMES = ["سارة", "سارة  العتيبي ", "علی کریم", "Sara", "Ali Omar", "سارة2", "", "   ", "س" * 30, "س" * 31,
         "Ali-Omar", "سارةً", "ســارة", "سارة\tالعتيبي", "عبدالله بن محمد"]
EMAILS = ["Sara.Worker@Example.SA", " a@b.co ", "STRASSE@x.de", "straße@x.de", "a@b", "سارة@example.sa",
          "ａｌｉ@ｅｘａｍｐｌｅ.ｃｏ", "a@b..co", "a+b@c.d", "x" * 250 + "@a.co", "x" * 247 + "@a.co", "İ@x.co"]


def _server_says(check, raw):
    try:
        return check(raw)
    except auth.RegistrationInvalid:
        return None


def test_the_page_validates_names_and_emails_as_the_server_does(page_factory, server):
    page = page_factory(session=False)
    page.goto(server["base"] + "/#/login")
    Flow(page, server["base"]).screen("login")
    page_says = page.evaluate(
        """([names, emails]) => ({
            names: names.map((raw) => { const n = normalizeName(raw); return nameIsValid(n) ? n : null; }),
            emails: emails.map((raw) => { const e = normalizeEmail(raw); return emailIsValid(e) ? e : null; }),
        })""", [NAMES, EMAILS])
    assert page_says["names"] == [_server_says(auth.check_name, raw) for raw in NAMES]
    assert page_says["emails"] == [_server_says(auth.check_email, raw) for raw in EMAILS]


def test_every_row_on_the_home_screen_has_its_own_name(page_factory, server, owner, app):
    """«التحكم الصوتي» يضغط بالاسم: حملتان بلا عنوان لا تحملان الاسم نفسه."""
    user = _user_id(owner)
    for _ in range(2):
        create_campaign(app, user)
    page = page_factory()
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelectorAll('#home-list li').length === 2")
    names = [b.evaluate("(e) => e.textContent.replace(/\\s+/g, ' ').trim()")
             for b in page.locator("#home-list button").all()]
    assert len(set(names)) == len(names) == 2, names
    assert not any(name.startswith("مسودة") for name in names), names
