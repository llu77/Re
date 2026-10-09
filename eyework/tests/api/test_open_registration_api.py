"""
التسجيل بلا رابط عبر الواجهة البرمجية
======================================
الوضع `open` (الافتراض) من الطلب إلى القاعدة، بالترويسات التي يرسلها العميل:

  • بلا رابط حسابٌ «مفتوح» بمهنته وطريقة استخدامه وموافقته، وله في أسبوعه الأول
    عشرة طلبات كتابةٍ في اليوم وثلاث حملاتٍ مفتوحة؛ والرابط يعمل معه وحسابه ليس
    مفتوحاً.
  • الوضعان الآخران يرفضان قبل أن يمسّا شيئاً.
  • «البريد مأخوذ» جوابٌ صادق يُحسب: ثلاثٌ للشبكة في اليوم ثم لا تسجيل منها،
    وستّون للتطبيق توقف الطريق كلّه؛ وعلى يومٍ ممتلئ أو موقوف يصل الجواب نفسه
    لكل بريد.
  • حدود الشبكة (عنوان IPv4، أو /64 من IPv6) بعد فحص النسخة والحقول: الخطأ
    المطبعي لا يُحسب.
  • طريقة الاستخدام يغيّرها صاحبها، والموافقة على النسخة الحالية وحدها، وبوّابة
    الموافقة تردّ من لم يوافق عليها. في هذه الحزمة البوّابة لمسارات الذكاء وحدها
    وتُضاف إلى `/copy` مع تسلسل البدء في حزمة التبديل (القرار D1)، فتُختبر هنا كما
    يستدعيها FastAPI لأيّ مسارٍ يعتمدها.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from eyework import auth, rate_limit, terms, ui_size
from eyework.tests.api.conftest import (
    COOKIE,
    JPEG,
    LOGIN_KEY,
    ORIGIN,
    PASSWORD,
    SELLER,
    SUPPORT_CONTACT,
    WRITE_HEADERS,
    add_user,
    expect,
    generate,
    issue_code,
    log_in,
    noise_jpeg,
    path,
    serve,
    upload,
)
from eyework.tests.fakes import FakeCopywriter
from eyework.web.deps import require_current_terms

EMAIL = "Sara.Worker@Example.SA"
#: شبكتان: الحدود لكل شبكة، والمتصفّح الافتراضي شبكةٌ ثالثة اسمها «testclient».
NET_A, NET_B = "10.0.0.1", "10.0.0.2"
#: نسخةٌ أقدم من الحالية لها بصمةٌ في tests/unit/test_terms.py.
OLDER_VERSION = "2026-10-08"


# ── التجهيزات ──────────────────────────────────────────────────────────
@pytest.fixture
def code_server(owner, owner_url):
    with serve(owner_url, FakeCopywriter(), registration="code", support_contact=None) as app:
        yield app


@pytest.fixture
def closed_server(owner, owner_url):
    with serve(owner_url, FakeCopywriter(), registration="closed") as app:
        yield app


@pytest.fixture
def clock(monkeypatch):
    """يقدّم ساعة حدود المعدّل الرتيبة: الساعة والأربع والعشرون لا تُنتظران."""
    offset = 0.0
    real = rate_limit.monotonic
    monkeypatch.setattr(rate_limit, "monotonic", lambda: real() + offset)

    def advance(seconds: float) -> None:
        nonlocal offset
        offset += seconds

    return advance


def _body(**overrides) -> dict:
    body = {"name": "سارة  العتيبي ", "birth_date": "1994-03-21", "email": EMAIL, "password": PASSWORD,
            "profession": "MARKETING", "ui_size": "GAZE", "accept_terms": True,
            "terms_version": terms.TERMS_VERSION}
    body.update(overrides)
    return body


def _register(client: TestClient, **overrides):
    return client.post("/api/auth/register", json=_body(**overrides))


def _users(owner) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        return cursor.fetchone()[0]


def _ledger(owner) -> list[tuple[str, str]]:
    """(الطريق، النتيجة) لكل صفٍّ في دفتر التسجيل، بترتيب وقوعه."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT via, outcome FROM registration_ledger ORDER BY occurred_at")
        return [tuple(row) for row in cursor.fetchall()]


def _seed_ledger(owner, count: int, *, outcome: str = "OK") -> None:
    """صفوفٌ بلا رابط في آخر يوم: منها تُعدّ السقوف، لا من الحسابات."""
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO registration_ledger (occurred_at, via, outcome)"
                       " SELECT now() - interval '1 hour', 'OPEN', %s FROM generate_series(1, %s)",
                       (outcome, count))


def _answer(response) -> tuple[int, dict, str | None]:
    return response.status_code, response.json(), response.headers.get("Retry-After")


def _gate(server, user_id: UUID) -> UUID:
    """بوّابة الموافقة كما يستدعيها FastAPI لمسارٍ يعتمدها: بطلبٍ على التطبيق وبصاحب الجلسة."""
    return require_current_terms(SimpleNamespace(app=server), user_id)


# ── الحساب المفتوح ─────────────────────────────────────────────────────
def test_registering_without_a_link_signs_in_with_the_new_account_limits_and_size(browser, owner):
    client = browser()
    response = _register(client)
    assert response.status_code == 204, response.text
    assert COOKIE in client.cookies

    me = client.get("/api/me")
    assert me.json() == {"generations_left": 10, "generation_limit": 10, "display_name": "سارة العتيبي",
                         "profession": "MARKETING", "ui_size": "GAZE", "terms_current": True,
                         # الحساب المفتوح الجديد: حصّة الأسبوع الأول من أسئلة المساعد (ai_features).
                         "ai": {"assistant": {"per_day": 15, "used_today": 0}}}
    # ما يعود للواجهة لا يحمل البريد ولا تاريخ الميلاد.
    assert "1994" not in me.text and "example" not in me.text.lower()

    with owner.cursor() as cursor:
        cursor.execute("SELECT login_hmac, birth_date::text, profession, ui_size, self_registered, open_registered,"
                       " terms_version FROM users")
        login, birth, profession, size, self_registered, open_registered, version = cursor.fetchone()
    assert bytes(login) == auth.login_hmac(LOGIN_KEY, "sara.worker@example.sa")
    assert (birth, profession, size, self_registered, open_registered, version) == (
        "1994-03-21", "MARKETING", "GAZE", True, True, terms.TERMS_VERSION)
    assert _ledger(owner) == [("OPEN", "OK")]


def test_a_link_still_works_in_open_mode_and_its_account_is_not_new(browser, owner):
    client = browser()
    code = issue_code(owner)
    assert client.post("/api/auth/signup-code", json={"code": code}).status_code == 204
    assert _register(client, code=code, ui_size="COMPACT").status_code == 204
    me = client.get("/api/me").json()
    assert (me["generation_limit"], me["generations_left"], me["ui_size"]) == (40, 40, "COMPACT")
    with owner.cursor() as cursor:
        cursor.execute("SELECT self_registered, open_registered FROM users")
        assert cursor.fetchone() == (True, False)
        cursor.execute("SELECT used_at IS NOT NULL FROM signup_codes")
        assert cursor.fetchone() == (True,)
    assert _ledger(owner) == [("CODE", "OK")]


def test_an_unusable_link_is_refused_even_in_open_mode(browser, owner):
    """رابطٌ غير صالح لا يتحوّل إلى تسجيلٍ بلا رابط: من أرسل رمزاً أراد طريق الرمز."""
    response = _register(browser(), code=auth.new_token())
    assert response.status_code == 410
    assert response.json()["code"] == "REGISTER_CODE"
    assert _users(owner) == 0
    assert _ledger(owner) == []


def test_code_mode_refuses_registration_without_a_link_before_anything_else(code_server, owner):
    with TestClient(code_server, base_url=ORIGIN, headers=WRITE_HEADERS) as client:
        assert client.get("/api/choices").json()["registration"]["mode"] == "code"
        check = client.get("/api/auth/registration")
        assert (check.status_code, check.json()["code"]) == (403, "REGISTER_LINK")
        # قبل النسخة والحقول: لا يُعرف من الجواب شيءٌ عن النسخة ولا عن البريد.
        response = _register(client, name="سارة 2", terms_version="2000-01-01")
        assert (response.status_code, response.json()["code"]) == (403, "REGISTER_LINK")
        assert _register(client, code=issue_code(owner)).status_code == 204
    assert _users(owner) == 1
    assert _ledger(owner) == [("CODE", "OK")]


def test_closed_mode_refuses_every_route(closed_server, owner):
    code = issue_code(owner)
    with TestClient(closed_server, base_url=ORIGIN, headers=WRITE_HEADERS) as client:
        assert client.get("/api/choices").json()["registration"]["mode"] == "closed"
        for response in (client.get("/api/auth/registration"),
                         client.post("/api/auth/signup-code", json={"code": code}),
                         client.post("/api/auth/register", json=_body()),
                         client.post("/api/auth/register", json=_body(code=code))):
            assert (response.status_code, response.json()["code"]) == (403, "REGISTER_CLOSED")
    assert _users(owner) == 0
    assert _ledger(owner) == []


def test_the_choices_name_the_mode_contact_sizes_and_notice(browser):
    choices = browser().get("/api/choices").json()
    assert choices["registration"]["mode"] == "open"
    assert choices["registration"]["terms_version"] == terms.TERMS_VERSION
    assert choices["support_contact"] == SUPPORT_CONTACT
    assert choices["ui_sizes"] == [{"code": size.value, "name": name, "detail": detail}
                                   for size, (name, detail) in ui_size.CHOICES.items()]
    assert choices["notice"] == terms.notice()
    assert choices["registration_open"] is True


# ── البريد المأخوذ ─────────────────────────────────────────────────────
def test_a_taken_email_is_refused_without_touching_the_account_and_counted(browser, owner):
    assert _register(browser()).status_code == 204
    response = _register(browser(), name="ليلى", profession="SUPPORT", email="sara.worker@example.sa")
    assert response.status_code == 409
    assert response.json()["code"] == "REGISTER_TAKEN"
    assert response.json()["field"] == "TAKEN"
    with owner.cursor() as cursor:
        cursor.execute("SELECT display_name, profession FROM users")
        assert cursor.fetchall() == [("سارة العتيبي", "MARKETING")]
    # الجواب صفٌّ في الدفتر: منه يُعدّ إيقاف اليوم بعد ستّين.
    assert _ledger(owner) == [("OPEN", "OK"), ("OPEN", "TAKEN")]


def test_three_taken_answers_close_the_open_path_for_that_network(browser, owner):
    assert _register(browser(address=NET_A)).status_code == 204
    for _ in range(3):
        assert _register(browser(address=NET_A), name="ليلى").status_code == 409
    # الرابعة لا تصل القاعدة — ولا بريدٌ حرٌّ من الشبكة نفسها: لا جوابين يُقارَنان.
    for email in ("sara.worker@example.sa", "free@example.sa"):
        response = _register(browser(address=NET_A), name="ليلى", email=email)
        assert response.status_code == 429, response.text
        assert response.json()["code"] == "RATE"
        assert int(response.headers["Retry-After"]) > 0
    assert _ledger(owner) == [("OPEN", "OK"), ("OPEN", "TAKEN"), ("OPEN", "TAKEN"), ("OPEN", "TAKEN")]
    assert _users(owner) == 1
    # شبكةٌ أخرى تسجّل؛ والرابط من الشبكة المغلقة يعمل: حدّه على العنوان لا على الشبكة.
    assert _register(browser(address=NET_B), email="free@example.sa").status_code == 204
    assert _register(browser(address=NET_A), code=issue_code(owner), email="linked@example.sa").status_code == 204


# ── حدود الشبكة ────────────────────────────────────────────────────────
def test_open_registrations_are_limited_per_network_and_field_errors_do_not_count(browser, owner):
    client = browser(address=NET_A)
    for _ in range(5):
        assert _register(client, name="سارة 2").status_code == 422
    for i in range(5):
        assert _register(client, email=f"worker{i}@example.sa").status_code == 204, i
    sixth = _register(client, email="worker5@example.sa")
    assert (sixth.status_code, sixth.json()["code"]) == (429, "RATE")
    assert _users(owner) == 5
    assert _register(browser(address=NET_B), email="worker5@example.sa").status_code == 204
    # ما رُدّ بالحدّ لم يصل القاعدة: لا صفّ له في الدفتر.
    assert _ledger(owner) == [("OPEN", "OK")] * 6


def test_the_daily_per_network_limit_holds_after_the_hourly_one_resets(browser, owner, clock):
    client = browser(address=NET_A)
    for i in range(5):
        assert _register(client, email=f"a{i}@example.sa").status_code == 204, i
    assert _register(client, email="a5@example.sa").status_code == 429
    clock(3601)
    for i in range(5, 10):
        assert _register(client, email=f"a{i}@example.sa").status_code == 204, i
    clock(3601)
    eleventh = _register(client, email="a10@example.sa")
    assert eleventh.status_code == 429
    # الانتظار حتى يفرغ مكانٌ في اليوم، لا في الساعة.
    assert int(eleventh.headers["Retry-After"]) > 3600
    clock(86400)
    assert _register(client, email="a10@example.sa").status_code == 204
    assert _users(owner) == 11


def test_ipv6_addresses_in_one_64_share_a_budget(browser, owner):
    for i in range(5):
        assert _register(browser(address=f"2001:db8:1:2::{i + 1}"), email=f"v6-{i}@example.sa").status_code == 204
    blocked = _register(browser(address="2001:db8:1:2:ffff:ffff:ffff:ffff"), email="v6-5@example.sa")
    assert blocked.status_code == 429
    assert _register(browser(address="2001:db8:1:3::1"), email="v6-5@example.sa").status_code == 204
    # وIPv4 المغلَّف في IPv6 هو عنوان IPv4 نفسه.
    for i in range(5):
        assert _register(browser(address="10.0.0.9"), email=f"v4-{i}@example.sa").status_code == 204
    assert _register(browser(address="::ffff:10.0.0.9"), email="v4-5@example.sa").status_code == 429
    assert _users(owner) == 11


# ── اليوم الممتلئ واليوم الموقوف ──────────────────────────────────────
def test_a_full_day_answers_the_same_for_taken_and_free_emails(browser, owner):
    assert _register(browser(address=NET_A)).status_code == 204
    # مع التسجيل أعلاه: مئةٌ وخمسون بلا رابط في أربعٍ وعشرين ساعة.
    _seed_ledger(owner, 149)
    check = browser(address=NET_B).get("/api/auth/registration")
    assert (check.status_code, check.json()["code"]) == (503, "REGISTER_FULL")
    taken, free = (_answer(_register(browser(address=NET_B), name="ليلى", email=email))
                   for email in ("sara.worker@example.sa", "free@example.sa"))
    assert taken == free
    assert (taken[0], taken[1]["code"], taken[2]) == (503, "REGISTER_FULL", "3600")
    assert _users(owner) == 1
    assert len(_ledger(owner)) == 150
    # الرابط يعمل: للروابط خمسون على الأقل من مئتي اليوم.
    assert _register(browser(address=NET_B), code=issue_code(owner), email="linked@example.sa").status_code == 204


def test_a_paused_day_answers_the_same_for_taken_and_free_emails_and_links_still_work(browser, owner):
    assert _register(browser(address=NET_A)).status_code == 204
    _seed_ledger(owner, 60, outcome="TAKEN")
    check = browser(address=NET_B).get("/api/auth/registration")
    assert (check.status_code, check.json()["code"]) == (503, "REGISTER_PAUSED")
    taken, free = (_answer(_register(browser(address=NET_B), name="ليلى", email=email))
                   for email in ("sara.worker@example.sa", "free@example.sa"))
    assert taken == free
    assert (taken[0], taken[1]["code"], taken[2]) == (503, "REGISTER_PAUSED", "3600")
    assert _users(owner) == 1
    assert len(_ledger(owner)) == 61
    assert _register(browser(address=NET_B), code=issue_code(owner), email="linked@example.sa").status_code == 204


# ── سؤال التوفّر ───────────────────────────────────────────────────────
def test_the_availability_check_is_limited_per_network(browser):
    client = browser(address=NET_A)
    for _ in range(30):
        assert client.get("/api/auth/registration").status_code == 204
    blocked = client.get("/api/auth/registration")
    assert (blocked.status_code, blocked.json()["code"]) == (429, "RATE")
    assert browser(address=NET_B).get("/api/auth/registration").status_code == 204


def test_the_availability_check_changes_nothing_and_needs_no_write_headers(browser, owner):
    client = browser(write_headers=False, address=NET_A)
    for _ in range(30):
        assert client.get("/api/auth/registration").status_code == 204
    assert _users(owner) == 0
    assert _ledger(owner) == []
    # ولا يُحسب على حدود التسجيل نفسها: الخمسة في الساعة كلّها باقية.
    for i in range(5):
        assert _register(browser(address=NET_A), email=f"w{i}@example.sa").status_code == 204, i


# ── الحقول والترويسات ─────────────────────────────────────────────────
@pytest.mark.parametrize(("overrides", "field"), [
    ({"name": "سارة 2"}, "NAME"),
    ({"name": "   "}, "NAME"),
    ({"name": "س" * 31}, "NAME"),
    ({"birth_date": "1994-02-30"}, "BIRTH"),
    ({"birth_date": "21-03-1994"}, "BIRTH"),
    ({"birth_date": "1899-12-31"}, "BIRTH"),
    ({"email": "not-an-email"}, "EMAIL"),
    ({"email": "سارة@example.sa"}, "EMAIL"),
    ({"password": "short"}, "PASSWORD"),
])
def test_each_invalid_field_names_itself_without_a_link(browser, owner, overrides, field):
    response = _register(browser(), **overrides)
    assert response.status_code == 422, response.text
    assert response.json()["field"] == field
    assert response.json()["code"] == "REGISTER_INVALID"
    assert _users(owner) == 0
    assert _ledger(owner) == []


def test_registering_without_a_link_needs_the_write_headers(browser, owner):
    response = browser(write_headers=False).post("/api/auth/register", json=_body())
    assert response.status_code == 403
    assert _users(owner) == 0


# ── حدود الحساب المفتوح في أسبوعه الأول ───────────────────────────────
def test_a_new_open_marketing_account_writes_ten_times_a_day(browser, owner):
    client = browser()
    assert _register(client).status_code == 204
    view = upload(client)
    # تسع محاولاتٍ محسوبة في يومه، متباعدةً ساعةً فلا يمسّها حدّ الدقائق العشر، كما تتركها القاعدة.
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at,"
            " outcome, new_account)"
            " SELECT c.id, c.user_id, 'INITIAL', i.sha256, s.at, s.at + interval '20 seconds', 'UPSTREAM_TIMEOUT', true"
            "   FROM campaigns c JOIN campaign_images i ON i.campaign_id = c.id,"
            "        generate_series(1, 9) AS g, LATERAL (SELECT now() - g * interval '1 hour' AS at) AS s"
            "  WHERE c.id = %s", (view["id"],))
    me = client.get("/api/me").json()
    assert (me["generation_limit"], me["generations_left"]) == (10, 1)
    proposed = generate(client, view)
    assert client.get("/api/me").json()["generations_left"] == 0
    eleventh = client.post(path(proposed, "/copy/edit"), json={
        "expected_row_version": proposed["row_version"], "expected_version_id": proposed["copy"]["version_id"],
        "presets": ["SHORTER"]})
    assert (eleventh.status_code, eleventh.json()["code"]) == (429, "AI_NEW_DAILY"), eleventh.text
    assert eleventh.headers["Retry-After"] == "3600"


def test_a_new_open_account_opens_three_campaigns(browser, owner):
    client = browser()
    assert _register(client).status_code == 204
    for _ in range(3):
        upload(client)
    fourth = client.post("/api/campaigns", content=noise_jpeg(), headers=JPEG)
    assert (fourth.status_code, fourth.json()["code"]) == (409, "NEW_OPEN_CAP")
    # حساب الرابط ليس «مفتوحاً»: له العشرون.
    linked = browser(address=NET_B)
    assert _register(linked, code=issue_code(owner), email="linked@example.sa").status_code == 204
    for _ in range(4):
        upload(linked)


# ── طريقة الاستخدام والنسخة ───────────────────────────────────────────
def test_registration_without_a_size_or_with_an_unknown_one_is_refused(browser, owner):
    without = _body()
    del without["ui_size"]
    for payload in (without, _body(ui_size="HUGE"), _body(ui_size=None), _body(ui_size="gaze")):
        response = browser().post("/api/auth/register", json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "INVALID"
    assert _users(owner) == 0
    assert _ledger(owner) == []


def test_registration_with_a_stale_terms_version_is_refused_before_anything_else(browser, owner):
    client = browser(address=NET_A)
    for _ in range(6):
        # حتى مع حقلٍ خاطئ: النسخة قبل الحقول، وقبل أيّ حدّ.
        response = _register(client, terms_version=OLDER_VERSION, name="سارة 2")
        assert (response.status_code, response.json()["code"]) == (409, "REGISTER_TERMS")
    assert _users(owner) == 0
    assert _ledger(owner) == []
    # لم يُستهلك حدٌّ: الخمسة في الساعة باقية.
    for i in range(5):
        assert _register(client, email=f"w{i}@example.sa").status_code == 204, i


def test_a_user_changes_their_own_size(browser, owner):
    client = browser()
    assert _register(client).status_code == 204
    assert client.put("/api/me/ui-size", json={"ui_size": "COMPACT"}).status_code == 204
    assert client.get("/api/me").json()["ui_size"] == "COMPACT"
    with owner.cursor() as cursor:
        cursor.execute("SELECT ui_size FROM users")
        assert cursor.fetchone() == ("COMPACT",)
    unknown = client.put("/api/me/ui-size", json={"ui_size": "HUGE"})
    assert (unknown.status_code, unknown.json()["code"]) == (422, "INVALID")
    assert browser().put("/api/me/ui-size", json={"ui_size": "GAZE"}).status_code == 401
    stripped = TestClient(client.app, base_url=ORIGIN)
    stripped.cookies = client.cookies
    assert stripped.put("/api/me/ui-size", json={"ui_size": "GAZE"}).status_code == 403
    # ثلاثون في الساعة تُعدّ على الطلبات التي بلغت المسار: الأولى أعلاه وتسعٌ وعشرون هنا.
    for _ in range(29):
        assert client.put("/api/me/ui-size", json={"ui_size": "GAZE"}).status_code == 204
    blocked = client.put("/api/me/ui-size", json={"ui_size": "GAZE"})
    assert (blocked.status_code, blocked.json()["code"]) == (429, "RATE")
    assert client.get("/api/me").json()["ui_size"] == "GAZE"


# ── بوّابة الموافقة ───────────────────────────────────────────────────
def test_an_account_without_current_consent_cannot_reach_the_model(browser, owner, server):
    invited = add_user(owner, "invited@example.sa", terms_version=None)
    older = add_user(owner, "older@example.sa", terms_version=OLDER_VERSION)
    for user_id in (invited, older):
        with pytest.raises(HTTPException) as caught:
            _gate(server, user_id)
        assert caught.value.status_code == 403
        assert caught.value.detail["code"] == "TERMS"
    client = browser()
    assert log_in(client, "older@example.sa").status_code == 204
    assert client.get("/api/me").json()["terms_current"] is False
    assert client.post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION}).status_code == 204
    assert _gate(server, older) == older
    assert client.get("/api/me").json()["terms_current"] is True


def test_accepting_the_notice_takes_only_the_current_version(browser, owner):
    user_id = add_user(owner, SELLER, terms_version=OLDER_VERSION)
    client = browser()
    assert log_in(client).status_code == 204
    stale = client.post("/api/me/terms", json={"terms_version": OLDER_VERSION})
    assert (stale.status_code, stale.json()["code"]) == (409, "REGISTER_TERMS")
    malformed = client.post("/api/me/terms", json={"terms_version": "yesterday"})
    assert (malformed.status_code, malformed.json()["code"]) == (422, "INVALID")
    assert client.get("/api/me").json()["terms_current"] is False
    assert client.post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION}).status_code == 204
    assert client.get("/api/me").json()["terms_current"] is True
    with owner.cursor() as cursor:
        cursor.execute("SELECT terms_version, terms_accepted_at IS NOT NULL FROM users WHERE id = %s", (user_id,))
        assert cursor.fetchone() == (terms.TERMS_VERSION, True)
    assert browser().post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION}).status_code == 401
    # عشرٌ في الساعة: الجواب 409 أعلاه بلغ المسار فعُدّ، و422 لم يبلغه.
    for _ in range(8):
        assert client.post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION}).status_code == 204
    assert client.post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION}).status_code == 429


def test_routes_that_send_nothing_to_the_model_work_without_current_consent(browser, owner):
    add_user(owner, SELLER, terms_version=None)
    client = browser()
    assert log_in(client).status_code == 204
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["terms_current"] is False
    assert client.put("/api/me/ui-size", json={"ui_size": "COMPACT"}).status_code == 204
    assert expect(client.get("/api/campaigns")) == {"items": [], "has_more": False}
    assert client.post("/api/auth/logout").status_code == 204
    assert log_in(client).status_code == 204
    assert client.post("/api/me/delete").status_code == 204
    assert _users(owner) == 0


def test_a_newer_accepted_version_counts_as_current(browser, owner, server, monkeypatch):
    newer = "2027-01-01"
    assert newer > terms.TERMS_VERSION
    user_id = add_user(owner, SELLER, terms_version=newer)
    client = browser()
    assert log_in(client).status_code == 204
    assert _gate(server, user_id) == user_id
    assert client.get("/api/me").json()["terms_current"] is True
    # ولا تُمحى موافقته بموافقةٍ على الأقدم: القاعدة ترفض الرجوع.
    backwards = client.post("/api/me/terms", json={"terms_version": terms.TERMS_VERSION})
    assert (backwards.status_code, backwards.json()["code"]) == (409, "TERMS_STALE")
    # بعد تراجعٍ عن إصدار تكون نسخة الخادم أقدم ممّا وافق عليه، ولا يُحبس.
    monkeypatch.setattr(terms, "TERMS_VERSION", OLDER_VERSION)
    assert _gate(server, user_id) == user_id
    assert client.get("/api/me").json()["terms_current"] is True
