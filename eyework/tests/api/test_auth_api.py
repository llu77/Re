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

import dataclasses
import hashlib

import pytest
from fastapi.testclient import TestClient

from eyework import auth
from eyework.rate_limit import RateLimit, RateLimiter
from eyework.tests.api.conftest import (
    COOKIE,
    INTRUDER,
    LOGIN_KEY,
    ORIGIN,
    PASSWORD,
    SELLER,
    WRITE_HEADERS,
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
RECOVERED = "Recovered-Password-2026-y"


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


def _issue(owner, user_id, *, age_hours: int = 0) -> str:
    """
    رمز تفعيلٍ كما يُصدره المشغّل: مجزّأٌ في القاعدة، صالحٌ يوماً من إصداره.
    `age_hours` يُرجع لحظة الإصدار إلى الوراء — 25 ⇒ رابطٌ انتهى قبل ساعة.
    """
    token = auth.new_token()
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO activation_tokens (token_hash, user_id, created_at, expires_at)"
            " VALUES (%s, %s, now() - make_interval(hours => %s),"
            "         now() - make_interval(hours => %s) + interval '24 hours')",
            (hashlib.sha256(token.encode()).digest(), user_id, age_hours, age_hours),
        )
    return token


def _invite(owner, username: str, *, age_hours: int = 0) -> str:
    """دعوةٌ كما يُنشئها المشغّل: حسابٌ بلا كلمة مرور، ورمزٌ مجزّأ له مهلة."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac, profession) VALUES (%s, 'MARKETING') RETURNING id",
            (auth.login_hmac(LOGIN_KEY, username),),
        )
        user_id = cursor.fetchone()[0]
    return _issue(owner, user_id, age_hours=age_hours)


def _activate(client, token: str, username: str = SELLER, password: str = PASSWORD):
    return client.post("/api/auth/activate", json={"token": token, "username": username, "password": password})


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
    """
    بلا حدٍّ لكل اسم يُخمَّن كلمة مرورٍ بلا نهاية. والاسم بأشكاله التي يوحّدها
    الدخول (حالة الأحرف، والمسافات حوله) اسمٌ واحد: حدٌّ على النصّ الخام
    يُتجاوز بتبديل الحالة.
    """
    add_user(owner, SELLER)
    client = browser()
    for variant in (SELLER, SELLER.upper(), f" {SELLER} ", SELLER.title(), SELLER):
        assert log_in(client, variant, "wrong-password-123").status_code == 401

    refused = log_in(client, SELLER, PASSWORD)
    assert refused.status_code == 429
    assert refused.json()["code"] == "RATE"
    assert 1 <= int(refused.headers["retry-after"]) <= 61
    assert "set-cookie" not in refused.headers

    # الحدّ لكل اسم لا لكل جهاز: اسمٌ آخر من الجهاز نفسه يُجاب كالمعتاد.
    assert log_in(client, INTRUDER, PASSWORD).json() == LOGIN_FAILED


def test_guessing_from_elsewhere_does_not_lock_the_owner_out(owner, server):
    """
    أسماء الدخول عناوين بريد تُعرف: من يخمّن من عنوانه يُحبس في عنوانه، وصاحب
    الحساب من عنوانه يدخل. والسقف لكل اسم من كل العناوين يبقى للتخمين الموزّع.
    """
    add_user(owner, SELLER)
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=("203.0.113.9", 50000)) as attacker:
        for _ in range(5):
            assert log_in(attacker, SELLER, "wrong-password-123").status_code == 401
        assert log_in(attacker, SELLER, "wrong-password-123").status_code == 429
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=("198.51.100.7", 50000)) as device:
        assert log_in(device).status_code == 204


def test_distributed_guessing_still_meets_a_ceiling_per_name(owner, server):
    add_user(owner, SELLER)
    server.state.limiters = dataclasses.replace(server.state.limiters,
                                                login_name=RateLimiter(RateLimit(6, 3600.0)))
    for n in range(6):
        with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=(f"203.0.113.{n}", 50000)) as one:
            assert log_in(one, SELLER, "wrong-password-123").status_code == 401
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=("203.0.113.99", 50000)) as one:
        assert log_in(one, SELLER, "wrong-password-123").status_code == 429


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

    activated = _activate(client, token)
    assert activated.status_code == 204
    session, attributes = _session_cookie(activated)
    assert (attributes["max-age"], attributes["path"], attributes["samesite"].lower()) == (
        str(THIRTY_DAYS), "/", "strict")
    assert {"httponly", "secure"} <= attributes.keys() and "domain" not in attributes
    assert client.get("/api/me").status_code == 200

    again = _activate(browser(), token, password="Another-Password-2026")
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
    response = _activate(client, token, INTRUDER)
    assert response.status_code == 422
    assert response.json() == ACTIVATION_FAILED
    assert "set-cookie" not in response.headers
    assert client.get("/api/me").status_code == 401

    # لم يضع كلمةً لأيّ اسم، ولم يستهلك الرابط: صاحبه يفعّل به بعدها.
    assert log_in(browser(), SELLER).status_code == 401
    assert log_in(browser(), INTRUDER).status_code == 401
    assert _activate(browser(), token).status_code == 204


def test_an_expired_activation_link_is_refused(owner, browser):
    """رابطٌ منتهٍ يعمل يسلّم الحساب لكل من وجد رسالة دعوةٍ قديمة."""
    token = _invite(owner, SELLER, age_hours=25)
    response = _activate(browser(), token)
    assert response.status_code == 422
    assert response.json() == ACTIVATION_FAILED
    assert "set-cookie" not in response.headers
    assert log_in(browser()).status_code == 401


def test_a_recovery_link_signs_out_every_other_session(owner, seller, browser):
    """رابط استردادٍ بعد فقد جهازٍ يترك الجهاز المفقود داخل الحساب إن لم يُبطل جلساته."""
    lost = seller.cookies.get(COOKIE)
    bare = browser(write_headers=False)
    assert bare.get("/api/me", headers=with_cookie(lost)).status_code == 200

    with owner.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE login_hmac = %s", (auth.login_hmac(LOGIN_KEY, SELLER),))
        (user_id,) = cursor.fetchone()
    recovered = browser()
    assert _activate(recovered, _issue(owner, user_id), password=RECOVERED).status_code == 204

    assert recovered.get("/api/me").status_code == 200
    assert bare.get("/api/me", headers=with_cookie(lost)).status_code == 401
    assert log_in(browser(), SELLER, PASSWORD).status_code == 401
    assert log_in(browser(), SELLER, RECOVERED).status_code == 204


# ── الخروج وتبديل الجلسة ───────────────────────────────────────────────
def test_logout_revokes_the_session_in_the_database(seller, browser):
    """خروجٌ يمحو الملفّ من المتصفّح وحده يترك نسخةً منسوخةً منه جلسةً عاملة."""
    token = seller.cookies.get(COOKIE)
    bare = browser(write_headers=False)
    # الرمز المنسوخ يعمل قبل الخروج — فرفضه بعده من القاعدة لا من شكله.
    assert bare.get("/api/me", headers=with_cookie(token)).status_code == 200

    assert seller.post("/api/auth/logout").status_code == 204
    assert seller.get("/api/me").status_code == 401

    replay = bare.get("/api/me", headers=with_cookie(token))
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
def test_me_returns_the_generations_left_and_only_the_users_own_name(owner, seller, intruder):
    """
    لا معرّف ولا اسم دخول: يصلان كل سجلٍّ وكل إضافةٍ في المتصفّح. الاسم الذي
    يناديه به المساعد وحده، واسم صاحب الجلسة لا غيره.
    """
    assert seller.get("/api/me").json() == {"generations_left": 40, "generation_limit": 40, "display_name": None,
                                            "profession": "MARKETING", "ui_size": None, "terms_current": True,
                                            "ai": {"assistant": {"per_day": 60, "used_today": 0}}}

    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = 'عمر' WHERE login_hmac = %s",
                       (auth.login_hmac(LOGIN_KEY, SELLER),))
    assert seller.get("/api/me").json() == {"generations_left": 40, "generation_limit": 40, "display_name": "عمر",
                                            "profession": "MARKETING", "ui_size": None, "terms_current": True,
                                            "ai": {"assistant": {"per_day": 60, "used_today": 0}}}
    assert intruder.get("/api/me").json()["display_name"] is None


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
