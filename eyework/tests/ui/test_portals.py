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
from eyework.tests.ui.test_gaze import HOVER_OR_GESTURE

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


def _gaze_safe(page) -> None:
    """عقد النظر على ما رُسم في هذا المسار: لا مؤقّت، ولا مستمعَ مرورٍ أو إيماءة."""
    log = page.evaluate("() => ({ timers: window.__eyework.timers, listeners: window.__eyework.listeners })")
    assert log["timers"] == [], log["timers"]
    assert not [t for t in log["listeners"] if HOVER_OR_GESTURE.match(t)], log["listeners"]


def _posts(page, base: str) -> list[str]:
    return [url.removeprefix(base) for method, url in page.requests if method != "GET"]


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
    # لا شيء يُرسل قبل الخطوة الأخيرة: فحص الرمز وحده.
    assert _posts(page, server["base"]) == ["/api/auth/signup-code"]
    # قبل «أنشئ حسابي»: نجاحه يحمّل الصفحة من جديد فيمحو سجلّ المؤقّتات والمستمعين.
    _gaze_safe(page)
    flow.press("#signup-create", lambda: flow.until(
        "document.querySelector('#home-portal') && document.querySelector('#home-portal').textContent"
        " === 'بوابة أمين المخزون'"), "أنشئ حسابي")
    flow.audit("home-storekeeper")
    assert _posts(page, server["base"]) == ["/api/auth/signup-code", "/api/auth/register"]
    _gaze_safe(page)

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


LOGIN_ALERT = ".screen[data-screen='login'] .alert"


@pytest.mark.parametrize("failure", ["offline", "busy"])
def test_a_failed_code_check_keeps_the_link_and_tries_again(page_factory, server, owner, failure):
    """انقطاعٌ أو حدٌّ عند فحص الرمز لا يُضيّع الرابط وقد مُحي من شريط العنوان: «حسناً» تعيد الفحص."""
    left = {"failures": 1}

    def check(route):
        if not left["failures"]:
            route.continue_()
        elif failure == "offline":
            left["failures"] -= 1
            route.abort("connectionreset")
        else:
            left["failures"] -= 1
            route.fulfill(status=429, content_type="application/json",
                          body='{"code": "RATE", "detail": "طلباتٌ كثيرة. حاول بعد قليل."}')

    page = page_factory(session=False)
    page.route("**/api/auth/signup-code", check)
    page.goto(f"{server['base']}/#signup={_issue_code(owner)}")
    flow = Flow(page, server["base"])
    flow.screen("login")
    page.wait_for_selector(f"{LOGIN_ALERT}:not([hidden])")
    assert "تعيد المحاولة" in page.text_content(f"{LOGIN_ALERT} .alert__text")
    page.click(f"{LOGIN_ALERT} [data-ack]")
    flow.screen("signup-notice")
    assert not page.errors, page.errors


def test_a_malformed_link_says_the_link_is_invalid(page_factory, server, owner):
    """حرفٌ زائد ألصقه تطبيق محادثةٍ بالرابط: يُقال إن الرابط لا يصلح، لا «قيمةٌ غير صالحة في الطلب»."""
    page = page_factory(session=False)
    page.goto(f"{server['base']}/#signup={_issue_code(owner)}.")
    Flow(page, server["base"]).screen("login")
    page.wait_for_selector(f"{LOGIN_ALERT}:not([hidden])")
    assert page.text_content(f"{LOGIN_ALERT} .alert__text").startswith("رابط التسجيل غير صالح")
    assert not page.errors, page.errors


def test_a_link_opened_where_the_app_is_already_open_starts_signing_up(page_factory, server, owner):
    """الرابط يُلصق في تبويبٍ فيه التطبيق: لا تحميل جديد، فيُلتقط الرمز عند تغيّر الوسم."""
    page = page_factory(session=False)
    page.goto(f"{server['base']}/#/login")
    flow = Flow(page, server["base"])
    flow.screen("login")
    code = _issue_code(owner)
    page.evaluate("(code) => { location.hash = `#signup=${code}`; }", code)
    flow.screen("signup-notice")
    assert code not in page.url
    assert not page.errors, page.errors


def test_a_birth_date_in_the_future_never_reaches_the_review(page_factory, server, owner):
    """تاريخٌ في المستقبل لا تصل به المراجعة؛ وتغيير الشهر إلى المستقبل يُسقط اليوم المختار."""
    page = page_factory(session=False)
    page.goto(f"{server['base']}/#signup={_issue_code(owner)}")
    flow = Flow(page, server["base"])
    flow.screen("signup-notice")
    page.evaluate("""() => {
        const later = new Date(Date.now() + 2 * 86400000);
        Object.assign(state.signup, { agreed: true, name: 'سارة', year: later.getFullYear(),
            month: later.getMonth() + 1, day: later.getDate(), profession: 'STOREKEEPER', email: 'sara@example.sa' });
        location.hash = '#/signup/review';
    }""")
    flow.screen("signup-day")
    assert page.evaluate("""() => {
        const later = new Date(Date.now() + 40 * 86400000);
        Object.assign(state.signup, { year: later.getFullYear(), month: 1, day: later.getDate() });
        setMonth(later.getMonth() + 1);
        return state.signup.day;
    }""") is None
    assert not page.errors, page.errors


# ── البوابات ─────────────────────────────────────────────────────────────
def _walk(flow: Flow, kind: str, view: dict, label: str) -> None:
    """كل بندٍ بترتيبه، وعلى الشاشة ما في البيانات نفسها: النصّ والملاحظة والنوع والمصدر."""
    page = flow.page
    items = view[kind]
    count = len(items)
    flow.press(f"#home-{kind}", lambda: flow.screen("portal-item"), kind)
    for n in range(1, count + 1):
        flow.until(f"document.querySelector('#portal-item-position').textContent.endsWith('{n} من {count}')")
        flow.audit(f"{label} {kind} {n}")
        item = items[n - 1]
        assert page.text_content("#portal-item-text") == item["text"]
        assert page.is_visible("#portal-item-note") == bool(item["note"])
        if item["note"]:
            assert page.text_content("#portal-item-note") == item["note"]
        if kind == "tasks":
            assert page.get_attribute("#portal-item-mode", "data-mode") == item["mode"]
            assert page.is_visible("#portal-item-mode")
        else:
            assert page.is_hidden("#portal-item-mode")
        assert page.text_content("#portal-item-source") == view["sources"][kind]
        # «في هذه البوابة» لا يدّعي أن التطبيق يؤدّي المهمّة: جزءٌ منها، والملاحظة تسمّيه.
        if page.get_attribute("#portal-item-mode", "data-mode") == "IN_APP":
            assert "جزءٌ منها" in page.text_content("#portal-item-mode")
            assert page.is_visible("#portal-item-note")
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
    campaigns = "CAMPAIGN" in professions.PORTALS[profession].tools
    assert page.is_visible("#home-new") == campaigns
    portal = professions.view(profession)
    # التعريف مترجمٌ عن المصدر: مصدره تحته حين يُعرض.
    assert page.is_visible("#home-about-source") == (not campaigns)
    if not campaigns:
        assert page.text_content("#home-about") == portal["summary"]
        assert page.text_content("#home-about-source") == portal["sources"]["summary"]

    _walk(flow, "tasks", portal, profession.value)
    page.goto(server["base"] + "/#/")
    flow.screen("home")
    _walk(flow, "skills", portal, profession.value)

    assert not _failures(flow), "\n".join(_failures(flow))
    _gaze_safe(page)
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
    # نظرٌ باقٍ بعد «حسابي» ينتقل إلى «رجوع»، لا إلى الخروج: الدخول من جديد بالنظر أغلى خطوة.
    assert {n["name"] for n in flow.nearest[-1][1]} == {"رجوع"}, flow.nearest[-1]
    flow.press("#account-delete", lambda: flow.screen("account-delete"), "احذف حسابي")
    flow.audit("account-delete")
    flow.press("#account-delete-back", lambda: flow.screen("account"), "رجوع دون حذف")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 1
    flow.press("#account-delete", lambda: flow.screen("account-delete"), "احذف حسابي")
    # قبل الحذف: نجاحه يحمّل الصفحة من جديد فيمحو سجلّ المؤقّتات والمستمعين.
    _gaze_safe(page)
    flow.press("#account-delete-yes", lambda: flow.screen("login"), "نعم، احذف")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 0
    assert not _failures(flow), "\n".join(_failures(flow))
    assert not flow.landings, "\n".join(flow.landings)
    _gaze_safe(page)
    assert not page.errors, page.errors


def test_the_portal_follows_a_profession_change_while_the_app_is_open(page_factory, server, owner):
    """المشغّل ينقل الحساب والتطبيق مفتوح: الرئيسية تقرأ البوابة من جديد، وكذلك الحساب."""
    page = page_factory()
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    # قائمة الحملات استقرّت قبل النقل: طلبٌ في الطريق قد يُرفض بالمهنة الجديدة.
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة التسويق'"
               " && !document.querySelector('#home-empty').hidden")
    assert page.is_visible("#home-new")
    _set_profession(owner, "STOREKEEPER")
    # إلى الرئيسية دون شاشة الحساب: من المهامّ ثم «رجوع».
    page.click("#home-tasks")
    flow.screen("portal-item")
    page.click(".screen[data-screen='portal-item'] [data-back]")
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة أمين المخزون'")
    assert page.is_hidden("#home-new")
    assert page.is_hidden(".screen[data-screen='home'] .alert")
    _set_profession(owner, "SUPPORT")
    page.click("#home-account")
    flow.until("document.querySelector('#account-profession').textContent === 'المهنة: الدعم الفني'")
    assert not page.errors, page.errors


def test_a_profession_refusal_forgets_the_portal(page_factory, server, owner, app):
    """ردّ PROFESSION من الخادم يعني أن البوابة المحفوظة لم تعد صحيحة: ما بعده يقرؤها من جديد."""
    campaign = create_campaign(app, _user_id(owner))
    page = page_factory()
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelectorAll('#home-list li').length === 1")
    _set_profession(owner, "STOREKEEPER")
    with page.expect_response(lambda response: f"/api/campaigns/{campaign}" in response.url
                              and response.status == 403):
        page.evaluate("(id) => { location.hash = `#/c/${id}`; }", str(campaign))
    page.wait_for_function("() => state.portal === null")
    # مسار البند يقرأ البوابة المحفوظة إن وُجدت: بعد النسيان يقرؤها من الخادم.
    page.evaluate("() => { location.hash = '#/tasks/1'; }")
    flow.until("document.querySelector('#portal-item-heading').textContent === 'مهامّ أمين المخزون'")
    assert not page.errors, page.errors


def test_home_buttons_are_not_drawn_before_the_portal_is_known(page_factory, server):
    """قبل البوابة لا أزرار في موضعٍ مؤقّت: لا يبدأ نظرٌ على زرٍّ ينتقل حين تصل."""
    page = page_factory()
    held = []
    page.route("**/api/portal", lambda route: held.append(route))
    page.goto(server["base"] + "/#/")
    flow = Flow(page, server["base"])
    flow.screen("home")
    for _ in range(200):
        if held:
            break
        page.wait_for_timeout(25)
    assert held
    assert page.is_hidden("#home-tasks") and page.is_hidden("#home-skills")
    held[0].continue_()
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة التسويق'")
    assert page.is_visible("#home-tasks") and page.is_visible("#home-new")
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_an_alert_on_the_delete_screen_keeps_its_distance(page_factory, server, owner, width, height):
    """الحذف فشل (انقطاعٌ أو عطل): «حسناً» لا تجاور زرّاً، والحساب باقٍ."""
    page = page_factory(width, height)
    page.route("**/api/me/delete", lambda route: route.fulfill(
        status=503, content_type="application/json", body='{"code": "UNAVAILABLE", "detail": "الخدمة غير متاحة."}'))
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/account/delete")
    flow.screen("account-delete")
    page.click("#account-delete-yes")
    page.wait_for_selector(".screen[data-screen='account-delete'] .alert:not([hidden])")
    flow.audit("account-delete alert")
    # بعد «حسناً» لا يبقى «نعم، احذف حسابي» أقرب ما إلى نظرٍ باقٍ: العودة إلى «حسابي».
    flow.press(".screen[data-screen='account-delete'] [data-ack]", lambda: flow.screen("account"), "حسناً")
    assert not _failures(flow), "\n".join(_failures(flow))
    if (width, height) != VIEWPORTS[-1]:
        assert not flow.landings, "\n".join(flow.landings)
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 1
    assert not page.errors, page.errors


# نصٌّ لاتيني في سطرٍ عربي: كل رمزٍ محايد (® والقوسان) بجوار ما يخصّه، لا في طرف السطر.
BIDI = """
(selector) => {
    const node = document.querySelector(selector).firstChild;
    const text = node.textContent;
    const box = (i) => { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
                         return r.getBoundingClientRect(); };
    const gaps = [];
    for (let i = text.indexOf('®'); i > 0; i = text.indexOf('®', i + 1)) {
        gaps.push(['®', Math.abs(box(i).left - box(i - 1).right)]);
    }
    // القوسان حول نصٍّ لاتيني: كلٌّ عند أحد طرفيه، وكلٌّ عند طرفٍ غير طرف صاحبه
    // (في سطرٍ من اليمين إلى اليسار قد يقع قوس الفتح عند الطرف الأيمن، وهذا صحيح).
    for (let i = text.indexOf('('); i >= 0; i = text.indexOf('(', i + 1)) {
        const close = text.indexOf(')', i);
        if (!/^[A-Za-z]/.test(text[i + 1])) continue;
        const inner = []; for (let k = i + 1; k < close; k += 1) inner.push(box(k));
        const left = Math.min(...inner.map((r) => r.left)), right = Math.max(...inner.map((r) => r.right));
        const side = (r) => (Math.abs(r.right - left) <= 3 ? 'L' : Math.abs(r.left - right) <= 3 ? 'R' : '?');
        const sides = side(box(i)) + side(box(close));
        gaps.push(['()', sides === 'LR' || sides === 'RL' ? 0 : 99, sides]);
    }
    return gaps;
}
"""


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=IDS)
def test_the_sources_screen_gives_the_full_onet_notice(page_factory, server, owner, width, height):
    """نسبة O*NET كاملةً كما يطلبها ترخيصه، في شاشةٍ يصلها كل حساب من «حسابي»، ومصادر بوابته."""
    _set_profession(owner, "STOREKEEPER")
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة أمين المخزون'")
    flow.press("#home-account", lambda: flow.screen("account"), "حسابي")
    flow.press("#account-sources", lambda: flow.until(
        "document.querySelector('#account-attribution').textContent !== ''"), "المصادر")
    flow.audit("account-sources")
    assert page.text_content("#account-attribution") == professions.ATTRIBUTION
    portal = professions.view(professions.Profession.STOREKEEPER)
    assert page.locator("#account-source-lines p").all_text_contents() == [portal["sources"]["tasks"]]
    misplaced = [g for g in page.evaluate(BIDI, "#account-attribution") if g[1] > 3]
    assert not misplaced, misplaced
    flow.press(".screen[data-screen='account-sources'] [data-back]", lambda: flow.screen("account"), "رجوع")
    assert not _failures(flow), "\n".join(_failures(flow))
    if (width, height) != VIEWPORTS[-1]:
        assert not flow.landings, "\n".join(flow.landings)
    _gaze_safe(page)
    assert not page.errors, page.errors


@pytest.mark.parametrize("name", ["MOHAMMED ABDULLAH ALSHAMMARI", "عبدالرحمن بن عبدالعزيز الشمري"])
def test_the_account_screen_fits_a_name_on_two_lines(page_factory, server, owner, name):
    _set_profession(owner, "STOREKEEPER")
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = %s", (name,))
    page = page_factory(*VIEWPORTS[0])
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/account")
    flow.until("document.querySelector('#account-profession').textContent === 'المهنة: أمين المخزون'")
    flow.audit("account long name")
    assert not _failures(flow), "\n".join(_failures(flow))


@pytest.mark.parametrize("start", ["cold", "after-home"])
def test_nothing_moves_on_the_account_screen_when_the_portal_arrives(page_factory, server, start):
    """سطر المهنة يحجز مكانه: «تسجيل الخروج» لا ينتقل تحت نظرٍ باقٍ حين تصل البوابة."""
    page = page_factory()
    flow = Flow(page, server["base"])
    gate = {"held": [], "open": start == "after-home"}

    def hold(route):
        if gate["open"]:
            route.continue_()
        else:
            gate["held"].append(route)

    page.route("**/api/portal", hold)
    if start == "after-home":
        page.goto(server["base"] + "/#/")
        flow.until("document.querySelector('#home-portal').textContent === 'بوابة التسويق'")
        gate["open"] = False
        page.click("#home-account")
    else:
        page.goto(server["base"] + "/#/account")
    flow.screen("account")
    for _ in range(200):
        if gate["held"]:
            break
        page.wait_for_timeout(25)
    assert gate["held"]
    before = page.locator("#account-logout").bounding_box()
    gate["open"] = True
    for route in gate["held"]:
        route.continue_()
    flow.until("document.querySelector('#account-profession').textContent === 'المهنة: التسويق'")
    assert page.locator("#account-logout").bounding_box() == before


def test_a_failed_portal_read_on_home_is_retried_by_the_acknowledgement(page_factory, server):
    """بلا بوابةٍ لا زرّ في الرئيسية إلا «حسابي»: «حسناً» تقرؤها من جديد، ولا زرّ في موضعٍ مؤقّت."""
    page = page_factory()
    left = {"failures": 1}

    def portal(route):
        if left["failures"]:
            left["failures"] -= 1
            route.abort("connectionreset")
        else:
            route.continue_()

    page.route("**/api/portal", portal)
    page.goto(server["base"] + "/#/")
    flow = Flow(page, server["base"])
    alert = ".screen[data-screen='home'] .alert"
    page.wait_for_selector(f"{alert}:not([hidden])")
    assert "تعيد المحاولة" in page.text_content(f"{alert} .alert__text")
    assert page.is_hidden("#home-actions")
    assert page.evaluate("() => ['home-older', 'home-newer'].every((id) => document.getElementById(id).disabled)")
    page.click(f"{alert} [data-ack]")
    flow.until("document.querySelector('#home-portal').textContent === 'بوابة التسويق'")
    assert page.is_visible("#home-tasks") and page.is_visible("#home-new")
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
