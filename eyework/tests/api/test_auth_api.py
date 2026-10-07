"""
الدخول والجلسات عبر الواجهة البرمجية
====================================
الجلسة ملفّ تعريفٍ واحد بشروط البادئة `__Host-` كاملة — `HttpOnly` فلا تقرؤه
شيفرة الصفحة، و`Secure` و`SameSite=Strict` و`Path=/` بلا `Domain` فلا يضعه
نطاقٌ فرعي ولا يُرسل من موقعٍ آخر — وعمره ثلاثون يوماً لا أكثر.

وكل فشلٍ في الدخول بالجواب نفسه حرفاً بحرف: اسمٌ غير مسجّل، وكلمةٌ خاطئة،
وحسابٌ موقوف، لا يفرّق بينها شيء — فالاستجابة لا تكشف من يستخدم التطبيق،
وقائمة مستخدميه معلومةٌ صحّية. والتخمين محدودٌ لكل اسم، والدخول الناجح يُلغي
الجلسة السابقة على الجهاز نفسه، والخروج يُبطل الرمز في القاعدة لا في المتصفّح
وحده.

ولا يعرض التطبيق وصفاً لواجهته (`/docs` وأخواتها): خريطة المسارات لا تخدم
مستخدماً، وتخدم من يبحث عن ثغرة.
"""

from __future__ import annotations

import hashlib

import pytest

from eyework import auth
from eyework.tests.api.conftest import (
    COOKIE,
    INTRUDER,
    LOGIN_KEY,
    PASSWORD,
    SELLER,
    add_user,
    log_in,
    with_cookie,
)

LOGIN_FAILED = {"code": "LOGIN", "detail": "بيانات الدخول غير صحيحة."}
ACTIVATION_FAILED = {
    "code": "ACTIVATION",
    "detail": "رابط التفعيل غير صالح أو منتهٍ. اطلب رابطاً جديداً ممن دعاك.",
}
THIRTY_DAYS = 30 * 24 * 3600


def _session_cookie(response) -> tuple[str, dict[str, str]]:
    """القيمة والصفات (بأسماء صغيرة) من ترويسة `Set-Cookie` الوحيدة."""
    headers = response.headers.get_list("set-cookie")
    assert len(headers) == 1, headers
    pair, *attributes = (part.strip() for part in headers[0].split(";"))
    name, _, value = pair.partition("=")
    assert name == COOKIE
    parsed = {}
    for attribute in attributes:
        key, _, setting = attribute.partition("=")
        parsed[key.lower()] = setting
    return value, parsed


def _invite(owner, username: str, *, hours: int = 24) -> str:
    """دعوةٌ كما يُنشئها المشغّل: حسابٌ بلا كلمة مرور، ورمزٌ مجزّأ له مهلة."""
    token = auth.new_token()
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac) VALUES (%s) RETURNING id",
            (auth.login_hmac(LOGIN_KEY, username),),
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
            " VALUES (%s, %s, now() + make_interval(hours => %s))",
            (hashlib.sha256(token.encode()).digest(), user_id, hours),
        )
    return token


# ── الدخول ─────────────────────────────────────────────────────────────
def test_login_sets_a_host_only_session_cookie(owner, browser):
    """ملفٌّ تقرؤه الصفحة، أو يُرسل عبر http، أو يضعه نطاقٌ فرعي، جلسةٌ تُسرق."""
    add_user(owner, SELLER)
    client = browser()
    response = log_in(client)
    assert response.status_code == 204

    token, attributes = _session_cookie(response)
    assert len(token) == 43
    assert "httponly" in attributes
    assert "secure" in attributes
    assert attributes["samesite"].lower() == "strict"
    assert attributes["path"] == "/"
    assert attributes["max-age"] == str(THIRTY_DAYS)
    assert "domain" not in attributes

    # الرمز الخام يغادر في الملفّ وحده؛ القاعدة تحفظ تجزئته.
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM sessions WHERE token_hash = %s",
                       (hashlib.sha256(token.encode()).digest(),))
        assert cursor.fetchone()[0] == 1
    assert client.get("/api/me").status_code == 200


def test_every_login_failure_looks_the_same(owner, browser):
    """جوابٌ يختلف بين «اسمٌ غير موجود» و«كلمةٌ خاطئة» يكشف من يستخدم التطبيق."""
    add_user(owner, SELLER)
    add_user(owner, "suspended@example.sa", active=False)
    client = browser()

    unknown = log_in(client, "nobody@example.sa", PASSWORD)
    wrong = log_in(client, SELLER, PASSWORD + "-wrong")
    inactive = log_in(client, "suspended@example.sa", PASSWORD)

    for response in (unknown, wrong, inactive):
        assert response.status_code == 401
        assert response.json() == LOGIN_FAILED
        assert "set-cookie" not in response.headers
    assert unknown.content == wrong.content == inactive.content


def test_sixth_login_for_one_name_within_a_minute_is_refused(owner, browser):
    """بلا حدٍّ لكل اسم يُخمَّن كلمة مرورٍ بلا نهاية."""
    add_user(owner, SELLER)
    client = browser()
    for _ in range(5):
        assert log_in(client, SELLER, "wrong-password-123").status_code == 401

    refused = log_in(client, SELLER, PASSWORD)
    assert refused.status_code == 429
    assert 1 <= int(refused.headers["retry-after"]) <= 61
    assert "set-cookie" not in refused.headers


def test_a_successful_login_resets_the_counter_for_that_name(owner, browser):
    """صاحب الحساب الذي أخطأ مرّاتٍ ثم دخل لا يُحبس خارجه بأخطائه السابقة."""
    add_user(owner, SELLER)
    client = browser()
    for _ in range(4):
        assert log_in(client, SELLER, "wrong-password-123").status_code == 401
    assert log_in(client).status_code == 204

    for _ in range(5):
        assert log_in(client, SELLER, "wrong-password-123").status_code == 401
    assert log_in(client, SELLER, "wrong-password-123").status_code == 429


# ── التفعيل ────────────────────────────────────────────────────────────
def test_activation_sets_the_password_and_signs_in_once(owner, browser):
    """رابط دعوةٍ يعمل مرتين يسلّم الحساب لكل من رأى الرابط بعد صاحبه."""
    token = _invite(owner, SELLER)
    client = browser()
    body = {"token": token, "username": SELLER, "password": PASSWORD}

    activated = client.post("/api/auth/activate", json=body)
    assert activated.status_code == 204
    session, attributes = _session_cookie(activated)
    assert attributes["max-age"] == str(THIRTY_DAYS)
    assert client.get("/api/me").status_code == 200

    again = browser().post("/api/auth/activate", json={**body, "password": "Another-Password-2026"})
    assert again.status_code == 422
    assert again.json() == ACTIVATION_FAILED
    assert "set-cookie" not in again.headers

    # الكلمة الأولى هي التي بقيت.
    assert log_in(browser()).status_code == 204
    assert log_in(browser(), SELLER, "Another-Password-2026").status_code == 401


def test_activation_with_another_username_is_refused(owner, browser):
    """رابطٌ عُبث باسمه يجعل المتصفّح يحفظ كلمة المرور تحت اسمٍ غير اسم الحساب."""
    token = _invite(owner, SELLER)
    client = browser()
    response = client.post("/api/auth/activate",
                           json={"token": token, "username": INTRUDER, "password": PASSWORD})
    assert response.status_code == 422
    assert response.json() == ACTIVATION_FAILED
    assert "set-cookie" not in response.headers
    assert client.get("/api/me").status_code == 401


# ── الخروج وتبديل الجلسة ───────────────────────────────────────────────
def test_logout_revokes_the_session_in_the_database(seller, browser):
    """خروجٌ يمحو الملفّ من المتصفّح وحده يترك نسخةً منسوخةً منه جلسةً عاملة."""
    token = seller.cookies.get(COOKIE)
    assert seller.post("/api/auth/logout").status_code == 204
    assert seller.get("/api/me").status_code == 401

    replay = browser(write_headers=False).get("/api/me", headers=with_cookie(token))
    assert replay.status_code == 401
    assert replay.json()["code"] == "SESSION"


def test_signing_in_again_revokes_the_previous_session(owner, seller, browser):
    """دخولٌ ثانٍ على الجهاز نفسه لا يترك الجلسة الأولى قائمةً بلا صاحب."""
    first = seller.cookies.get(COOKIE)
    assert log_in(seller).status_code == 204
    second = seller.cookies.get(COOKIE)
    assert second != first

    bare = browser(write_headers=False)
    assert bare.get("/api/me", headers=with_cookie(first)).status_code == 401
    assert bare.get("/api/me", headers=with_cookie(second)).status_code == 200
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM sessions WHERE revoked_at IS NULL")
        assert cursor.fetchone()[0] == 1


# ── ما يعرضه التطبيق عن نفسه ───────────────────────────────────────────
def test_me_returns_nothing_but_the_generations_left(seller):
    """معرّف المستخدم أو اسمه في الاستجابة يصل كل سجلٍّ وكل إضافةٍ في المتصفّح."""
    response = seller.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"generations_left": 40}


def test_me_without_a_session_is_refused(browser):
    """`/api/me` بلا جلسة يجب ألّا يجيب بشيء."""
    response = browser().get("/api/me")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION"


@pytest.mark.parametrize("route", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_the_api_does_not_describe_itself(browser, route):
    """خريطة المسارات المولّدة تخدم من يبحث عن ثغرة لا من يستخدم التطبيق."""
    assert browser().get(route).status_code == 404


def test_choices_come_from_the_server_with_their_words(browser):
    """قيمةٌ تحسبها الواجهة بنفسها قد تختلف عمّا تقبله القاعدة."""
    choices = browser().get("/api/choices")
    assert choices.status_code == 200
    body = choices.json()

    budgets = body["budget"]["values"]
    assert len(budgets) == 36
    assert len({value["sar"] for value in budgets}) == 36
    assert all(isinstance(value["words"], str) and value["words"].strip() for value in budgets)
    assert set(body["budget"]["presets"]) <= {value["sar"] for value in budgets}

    days = body["days"]["values"]
    assert [value["n"] for value in days] == list(range(1, 31))
    assert all(isinstance(value["words"], str) and value["words"].strip() for value in days)
