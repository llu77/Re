"""
التسجيل برابطٍ عبر الواجهة البرمجية
====================================
من الطلب إلى القاعدة، بالترويسات التي يرسلها `app.js`، في الوضع `code`: هذا
الملف يختبر طريق الرابط وحده، والتسجيل بلا رابط في `test_open_registration_api.py`.

  • رابط تسجيلٍ صالح ⇒ حسابٌ بمهنته وطريقة استخدامه وجلسة، و`/api/me` يعيد
    المهنة والاسم والحدّ — لا البريد ولا التاريخ.
  • بلا رمزٍ صالح لا حساب، ولا يُعرف إن كان البريد مسجّلاً.
  • كل حقلٍ خاطئ يعود باسم حقله، فتفتح الواجهة خطوته.
  • التسجيل المغلق 403، وحدّ العنوان الواحد 429.
  • الأداة لمهنتها: حساب المخزون لا يصل مسارات الحملة.
  • صاحب الحساب يحذفه بنفسه.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from eyework import auth, terms
from eyework.tests.api.conftest import (
    COOKIE,
    LOGIN_KEY,
    ORIGIN,
    PASSWORD,
    WRITE_HEADERS,
    issue_code,
    noise_jpeg,
    serve,
)
from eyework.tests.fakes import FakeCopywriter

EMAIL = "Sara.Worker@Example.SA"


@pytest.fixture
def server(owner, owner_url, writer):
    """الوضع `code`: التسجيل برابط المشغّل وحده، وبريد المشغّل اختياريٌّ فيه."""
    with serve(owner_url, writer, registration="code", support_contact=None) as app:
        yield app


def _body(code: str | None = None, **overrides) -> dict:
    body = {"name": "سارة  العتيبي ", "birth_date": "1994-03-21", "email": EMAIL, "password": PASSWORD,
            "profession": "STOREKEEPER", "ui_size": "GAZE", "accept_terms": True,
            "terms_version": terms.TERMS_VERSION}
    if code is not None:
        body["code"] = code
    body.update(overrides)
    return body


def _register(client, owner, **overrides):
    code = overrides.pop("code", None) or issue_code(owner)
    return client.post("/api/auth/register", json=_body(code, **overrides))


def _users(owner) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        return cursor.fetchone()[0]


def test_registering_signs_in_and_opens_the_professions_portal(browser, owner):
    client = browser()
    response = _register(client, owner)
    assert response.status_code == 204, response.text
    assert COOKIE in client.cookies

    me = client.get("/api/me")
    assert me.json() == {"generations_left": 40, "generation_limit": 40, "display_name": "سارة العتيبي",
                         "profession": "STOREKEEPER", "ui_size": "GAZE", "terms_current": True}
    # ما يعود للواجهة لا يحمل البريد ولا تاريخ الميلاد.
    assert "1994" not in me.text and "example" not in me.text.lower()

    with owner.cursor() as cursor:
        cursor.execute("SELECT login_hmac, birth_date::text, profession, ui_size, self_registered, open_registered,"
                       " terms_version FROM users")
        login, birth, profession, size, self_registered, open_registered, version = cursor.fetchone()
    # البريد موحّداً ثم HMAC: الاسم نفسه بحروفٍ كبيرة أو صغيرة حسابٌ واحد.
    assert bytes(login) == auth.login_hmac(LOGIN_KEY, "sara.worker@example.sa")
    # حساب الرابط ذاتيٌّ لكنه ليس «مفتوحاً»: له حدود الحساب القائم.
    assert (birth, profession, size, self_registered, open_registered, version) == (
        "1994-03-21", "STOREKEEPER", "GAZE", True, False, auth.TERMS_VERSION)


def test_a_registered_account_signs_in_again_with_its_email(browser, owner):
    assert _register(browser(), owner).status_code == 204
    response = browser().post("/api/auth/login", json={"username": "sara.worker@example.sa", "password": PASSWORD})
    assert response.status_code == 204


def test_the_signup_code_can_be_checked_before_the_first_step(browser, owner):
    client = browser()
    code = issue_code(owner)
    assert client.post("/api/auth/signup-code", json={"code": code}).status_code == 204
    assert _register(client, owner, code=code).status_code == 204
    used = client.post("/api/auth/signup-code", json={"code": code})
    assert used.status_code == 410
    assert used.json()["code"] == "REGISTER_CODE"


def test_without_a_usable_code_nothing_is_said_about_the_email(browser, owner):
    assert _register(browser(), owner).status_code == 204
    unknown = auth.new_token()
    for email in ("sara.worker@example.sa", "nobody@example.sa"):
        response = browser().post("/api/auth/register", json=_body(unknown, email=email))
        assert response.status_code == 410
        assert response.json()["code"] == "REGISTER_CODE"
    assert _users(owner) == 1


@pytest.mark.parametrize(("overrides", "field"), [
    ({"name": "سارة 2"}, "NAME"),
    ({"name": "   "}, "NAME"),
    ({"name": "س" * 31}, "NAME"),
    ({"birth_date": "1994-02-30"}, "BIRTH"),
    ({"birth_date": "21-03-1994"}, "BIRTH"),
    ({"birth_date": "1899-12-31"}, "BIRTH"),
    ({"birth_date": "٢٠٠٠-٠١-٠١"}, "BIRTH"),
    ({"email": "not-an-email"}, "EMAIL"),
    ({"email": "سارة@example.sa"}, "EMAIL"),
    ({"password": "short"}, "PASSWORD"),
])
def test_each_invalid_field_names_itself(browser, owner, overrides, field):
    response = _register(browser(), owner, **overrides)
    assert response.status_code == 422, response.text
    assert response.json()["field"] == field
    assert response.json()["code"] == "REGISTER_INVALID"
    assert _users(owner) == 0


def test_persian_keyboard_letters_are_read_as_arabic(browser, owner):
    assert _register(browser(), owner, name="علی کریم").status_code == 204
    with owner.cursor() as cursor:
        cursor.execute("SELECT display_name FROM users")
        assert cursor.fetchone()[0] == "علي كريم"


def test_a_future_birth_date_is_refused_by_the_databases_date(browser, owner):
    with owner.cursor() as cursor:
        cursor.execute("SELECT ((now() AT TIME ZONE 'Asia/Riyadh')::date + 1)::text")
        tomorrow = cursor.fetchone()[0]
    response = _register(browser(), owner, birth_date=tomorrow)
    assert response.status_code == 422
    assert response.json()["field"] == "BIRTH"
    assert _users(owner) == 0


def test_consent_is_required(browser, owner):
    response = _register(browser(), owner, accept_terms=False)
    assert response.status_code == 422
    assert _users(owner) == 0


def test_a_taken_email_is_refused_without_touching_the_account(browser, owner):
    assert _register(browser(), owner).status_code == 204
    response = _register(browser(), owner, name="ليلى", profession="SUPPORT", email="sara.worker@example.sa")
    assert response.status_code == 409
    assert response.json()["code"] == "REGISTER_TAKEN"
    assert response.json()["field"] == "TAKEN"
    with owner.cursor() as cursor:
        cursor.execute("SELECT display_name, profession FROM users")
        assert cursor.fetchall() == [("سارة العتيبي", "STOREKEEPER")]
        # جواب «مأخوذ» برمزٍ يُعدّ على الرمز لا في الدفتر.
        cursor.execute("SELECT via, outcome FROM registration_ledger")
        assert cursor.fetchall() == [("CODE", "OK")]


def test_an_unknown_profession_is_a_plain_invalid_request(browser, owner):
    response = _register(browser(), owner, profession="ASTRONAUT")
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID"


def test_registration_from_one_address_is_limited_and_field_errors_do_not_count(browser, owner):
    """عشرون تسجيلاً في الساعة من عنوانٍ واحد كما تُجريها الواجهة: فحص الرمز ثم إنشاء الحساب."""
    client = browser()
    for _ in range(5):
        assert _register(client, owner, name="سارة 2").status_code == 422
    for i in range(20):
        code = issue_code(owner)
        assert client.post("/api/auth/signup-code", json={"code": code}).status_code == 204, i
        assert _register(client, owner, code=code, email=f"worker{i}@example.sa").status_code == 204, i
    code = issue_code(owner)
    assert client.post("/api/auth/signup-code", json={"code": code}).status_code == 429
    assert _register(client, owner, code=code, email="worker20@example.sa").status_code == 429


def test_registration_needs_the_write_headers(browser, owner):
    response = browser(write_headers=False).post("/api/auth/register", json=_body(issue_code(owner)))
    assert response.status_code == 403
    assert _users(owner) == 0


@pytest.fixture
def closed_server(owner, owner_url):
    with serve(owner_url, FakeCopywriter(), registration="closed") as app:
        yield app


def test_a_closed_registration_refuses_and_says_so_in_the_choices(closed_server, owner):
    code = issue_code(owner)
    with TestClient(closed_server, base_url=ORIGIN, headers=WRITE_HEADERS) as client:
        assert client.get("/api/choices").json()["registration"]["mode"] == "closed"
        assert client.get("/api/auth/registration").status_code == 403
        assert client.post("/api/auth/signup-code", json={"code": code}).status_code == 403
        response = client.post("/api/auth/register", json=_body(code))
    assert response.status_code == 403
    assert response.json()["code"] == "REGISTER_CLOSED"
    assert _users(owner) == 0


def test_the_choices_list_the_professions_and_name_the_link_only_mode(browser):
    choices = browser().get("/api/choices").json()
    assert choices["registration"]["mode"] == "code"
    assert choices["support_contact"] is None
    assert "registration_open" not in choices
    assert [(p["code"], p["name"]) for p in choices["professions"]] == [
        ("MARKETING", "التسويق"), ("STOREKEEPER", "أمين المخزون"), ("SUPPORT", "الدعم الفني")]
    assert all(p["tagline"] for p in choices["professions"])
    assert choices["registration"]["terms_version"] == auth.TERMS_VERSION


@pytest.mark.parametrize("profession", ["STOREKEEPER", "SUPPORT"])
def test_another_professions_account_cannot_reach_the_campaign_tool(browser, owner, profession):
    client = browser()
    assert _register(client, owner, profession=profession).status_code == 204
    for method, path, kwargs in (
        ("GET", "/api/campaigns", {}),
        ("POST", "/api/campaigns", {"content": noise_jpeg(), "headers": {"Content-Type": "image/jpeg"}}),
    ):
        response = client.request(method, path, **kwargs)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["code"] == "PROFESSION"


def test_a_marketing_account_reaches_the_campaign_tool(browser, owner):
    client = browser()
    assert _register(client, owner, profession="MARKETING").status_code == 204
    assert client.get("/api/campaigns").status_code == 200


def test_the_owner_deletes_the_account_and_is_signed_out(browser, owner):
    client = browser()
    assert _register(client, owner, profession="MARKETING").status_code == 204
    assert client.post("/api/campaigns", content=noise_jpeg(),
                       headers={"Content-Type": "image/jpeg"}).status_code == 201
    response = client.post("/api/me/delete")
    assert response.status_code == 204
    assert COOKIE not in client.cookies
    assert client.get("/api/me").status_code == 401
    with owner.cursor() as cursor:
        cursor.execute("SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM campaigns)")
        assert cursor.fetchone() == (0, 0)


def test_deleting_needs_a_session_and_the_write_headers(browser, owner):
    assert browser().post("/api/me/delete").status_code == 401
    client = browser()
    assert _register(client, owner).status_code == 204
    stripped = TestClient(client.app, base_url=ORIGIN)
    stripped.cookies = client.cookies
    assert stripped.post("/api/me/delete").status_code == 403
    assert _users(owner) == 1
