"""
مفاتيح المرور عبر الواجهة البرمجية
==================================
جهازٌ مصطنع (`tests/authenticator.py`) يوقّع كما يوقّع iPhone، والخادم يتحقّق
منه بالمكتبة نفسها، من الطلب إلى القاعدة:

  • يُنشئ المتصفّح المفتاح بعد الدخول بكلمة المرور مباشرةً (الإنشاء المشروط: بلا
    علَمَي الحضور والتحقّق)، لجلسة ذلك الدخول وحدها في دقائقها الخمس الأولى؛ ثم
    يُدخَل به بلا اسمٍ ولا كلمة إلى الجلسة نفسها التي تفتحها كلمة المرور.
  • كل فشلٍ في الدخول بالجواب نفسه حرفاً بحرف: أصلٌ آخر، ومعرّف طرفٍ آخر، وعلَمٌ
    غائب، وتوقيعٌ خاطئ، وعدّادٌ رجع، وتحدٍّ مستعمل أو منتهٍ، ومفتاحٌ مجهول أو
    لحسابٍ محذوف — لا يفرّق بينها شيء.
  • التحدّي يُستهلك مرةً واحدة ولو فشل التحقّق، ومهلته في القاعدة.
  • لكل عنوانٍ حدّ، ولكل حسابٍ حدّ، وكل كتابةٍ تحمل ترويستي الكتابة.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from eyework import auth, passkeys
from eyework.tests.api.conftest import (
    COOKIE,
    INTRUDER,
    LOGIN_KEY,
    ORIGIN,
    SELLER,
    WRITE_HEADERS,
    add_user,
    expect,
    log_in,
    signed_in,
    with_cookie,
)
from eyework.tests.authenticator import UP, UV, SoftwareAuthenticator, b64, unb64
from eyework.tests.conftest import make_user
from eyework.web import deps

PASSKEY_FAILED = {"code": "PASSKEY", "detail": "تعذّر الدخول بمفتاح المرور. حاول مرة أخرى، أو ادخل بكلمة المرور."}
NOT_ADDED = {"code": "PASSKEY_ADD", "detail": "لم يُحفظ مفتاح المرور. حاول مرة أخرى."}
NEEDS_PASSWORD = {"code": "PASSKEY_UPGRADE", "detail": "يُنشأ مفتاح المرور بعد الدخول بكلمة المرور مباشرةً."}
#: ردّ الإنشاء المشروط: المتصفّح يضع علَمَي الحضور والتحقّق صفراً (WebAuthn L3 §5.1.3).
CONDITIONAL = 0
LOGIN_OPTIONS = "/api/auth/passkey/options"
LOGIN = "/api/auth/passkey"
ADD_OPTIONS = "/api/me/passkeys/options"
ADD = "/api/me/passkeys"


def _device(**options) -> SoftwareAuthenticator:
    return SoftwareAuthenticator(ORIGIN, **options)


def _user_id(owner, username: str = SELLER) -> UUID:
    with owner.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE login_hmac = %s", (auth.login_hmac(LOGIN_KEY, username),))
        return cursor.fetchone()[0]


def add_options(client: TestClient, username: str = SELLER):
    return client.post(ADD_OPTIONS, json={"username": username})


def add_passkey(client: TestClient, device: SoftwareAuthenticator | None = None, *,
                username: str = SELLER) -> SoftwareAuthenticator:
    """ما تفعله الواجهة بعد الدخول بكلمة المرور: خيارات، ثم إنشاءٌ مشروط، ثم حفظ."""
    device = device or _device()
    options = expect(add_options(client, username))
    response = client.post(ADD, json=device.create(options, flags=CONDITIONAL))
    assert response.status_code == 204, response.text
    return device


def _age_sessions(owner, minutes: float) -> None:
    """يُرجع أوقات كل جلسةٍ معاً: كأن الدخول كان قبل هذه الدقائق."""
    with owner.cursor() as cursor:
        cursor.execute("UPDATE sessions SET created_at = created_at - make_interval(secs => %(s)s),"
                       " password_at = password_at - make_interval(secs => %(s)s),"
                       " expires_at = expires_at - make_interval(secs => %(s)s)", {"s": minutes * 60})


def _needs_password(response) -> None:
    assert response.status_code == 403, response.text
    assert response.json() == NEEDS_PASSWORD


def sign_in(client: TestClient, device: SoftwareAuthenticator, options: dict | None = None, **assertion):
    options = options or expect(client.post(LOGIN_OPTIONS))
    return client.post(LOGIN, json=device.get(options, **assertion))


def _passkeys(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT user_id, credential_id, sign_count, transports, last_used_at IS NOT NULL"
                       " FROM passkeys ORDER BY created_at")
        return cursor.fetchall()


def _refused(response) -> None:
    assert response.status_code == 401, response.text
    assert response.json() == PASSKEY_FAILED
    assert "set-cookie" not in response.headers


def _not_added(response) -> None:
    assert response.status_code == 422, response.text
    assert response.json() == NOT_ADDED


# ── الطريق كاملاً ──────────────────────────────────────────────────────
def test_a_passkey_created_after_a_password_sign_in_signs_in_without_a_name_or_a_password(owner, seller,
                                                                                         browser):
    device = add_passkey(seller)
    user = _user_id(owner)
    assert _passkeys(owner) == [(user, device.credential_id, 0, ["hybrid", "internal"], False)]

    phone = browser()
    response = sign_in(phone, device)
    assert response.status_code == 204, response.text
    # الجلسة نفسها التي تفتحها كلمة المرور: الملفّ نفسه بشروطه كلها.
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 1
    attributes = {part.strip().split("=")[0].lower() for part in cookies[0].split(";")}
    assert {COOKIE.lower(), "httponly", "secure", "samesite", "path", "max-age"} <= attributes
    assert "domain" not in attributes
    assert phone.get("/api/me").json()["profession"] == "MARKETING"
    assert _passkeys(owner) == [(user, device.credential_id, 0, ["hybrid", "internal"], True)]

    # مفتاحٌ لا يعدّ يبقى عدّاده صفراً، ويُدخَل به مرةً بعد مرة.
    assert sign_in(browser(), device).status_code == 204


def test_signing_in_with_a_passkey_revokes_the_previous_session_on_that_device(owner, seller, browser):
    """كالدخول بكلمة المرور: الجلسة السابقة على الجهاز لا تبقى قائمةً بلا صاحب."""
    device = add_passkey(seller)
    first = seller.cookies.get(COOKIE)
    assert sign_in(seller, device).status_code == 204
    second = seller.cookies.get(COOKIE)
    assert second != first
    bare = browser(write_headers=False)
    assert bare.get("/api/me", headers=with_cookie(first)).status_code == 401
    assert bare.get("/api/me", headers=with_cookie(second)).status_code == 200


def test_login_options_ask_for_no_name_and_require_verification(owner, browser):
    """قائمة مفاتيح في الخيارات تحتاج اسماً أولاً — فيُكتب، ويُعرف من الجواب أن له حساباً."""
    client = browser()
    options = expect(client.post(LOGIN_OPTIONS))
    assert options["rpId"] == "testserver"
    assert options["allowCredentials"] == []
    assert options["userVerification"] == "required"
    assert options["timeout"] == passkeys.CHALLENGE_SECONDS * 1000
    challenge = unb64(options["challenge"])
    assert len(challenge) == 32
    assert unb64(expect(client.post(LOGIN_OPTIONS))["challenge"]) != challenge

    # القاعدة تحفظ تجزئة التحدّي، بلا صاحب، ومهلتها فيها.
    with owner.cursor() as cursor:
        cursor.execute("SELECT purpose, user_id, expires_at - created_at FROM passkey_challenges"
                       " WHERE challenge_hash = %s", (hashlib.sha256(challenge).digest(),))
        purpose, user, window = cursor.fetchone()
    assert (purpose, user, window.total_seconds()) == ("LOGIN", None, passkeys.CHALLENGE_SECONDS)


def test_add_options_ask_for_a_saved_key_named_by_the_login_without_attestation(owner, seller):
    """
    `user.name` اسم الدخول كما كُتب: Safari يُنشئ المفتاح حين ملأ للتوّ كلمة المرور
    لحسابٍ بالاسم نفسه. و`userVerification: preferred`: مع `required` يرفض المتصفّح
    الإنشاء المشروط.
    """
    options = expect(add_options(seller, "Seller@Example.SA"))
    user = _user_id(owner)
    assert options["rp"] == {"id": "testserver", "name": "صياغة"}
    # معرّف المستخدم في المفتاح ليس رقم الحساب.
    assert unb64(options["user"]["id"]) == passkeys.user_handle(LOGIN_KEY, user)
    assert unb64(options["user"]["id"]) != user.bytes
    assert options["user"]["name"] == options["user"]["displayName"] == "Seller@Example.SA"
    assert options["authenticatorSelection"] == {
        "residentKey": "required", "requireResidentKey": True, "userVerification": "preferred"}
    assert options["attestation"] == "none"
    assert [param["alg"] for param in options["pubKeyCredParams"]] == [-7, -257]
    assert options["excludeCredentials"] == []
    assert len(unb64(options["challenge"])) == 32
    # الدخول ينتظر الإنشاء: مهلةٌ قصيرة يفرضها المتصفّح، لا مهلة التحدّي.
    assert options["timeout"] == passkeys.UPGRADE_TIMEOUT_SECONDS * 1000 == 5000

    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = 'علي' WHERE id = %s", (user,))
    device = add_passkey(seller)
    again = expect(add_options(seller))
    assert (again["user"]["name"], again["user"]["displayName"]) == (SELLER, "علي")
    assert again["user"]["id"] == options["user"]["id"]
    assert again["excludeCredentials"] == [
        {"id": b64(device.credential_id), "type": "public-key", "transports": ["hybrid", "internal"]}]


def test_adding_a_passkey_needs_a_session(owner, browser):
    client = browser()
    for route, body in ((ADD_OPTIONS, {"username": SELLER}),
                        (ADD, _device().create({"challenge": b64(bytes(32)), "user": {"id": b64(bytes(32))}}))):
        response = client.post(route, json=body)
        assert response.status_code == 401
        assert response.json()["code"] == "SESSION"
    assert _passkeys(owner) == []


# ── الإضافة بعد الدخول بكلمة المرور وحده ───────────────────────────────
def test_a_session_cookie_alone_no_longer_adds_a_passkey(owner, seller, browser):
    """
    من وجد جهازاً مفتوحاً على حساب غيره (جلسةٌ تبقى ثلاثين يوماً) كان يضيف مفتاحاً
    على جهازه هو ويدخل به بعد خروج صاحبه. الآن لا إضافة بعد الدقائق الخمس الأولى من
    الدخول بكلمة المرور — في الخيارات، ولا بخياراتٍ أُخذت قبلها.
    """
    pending = expect(add_options(seller))
    _age_sessions(owner, passkeys.UPGRADE_SECONDS / 60 + 0.1)
    _needs_password(add_options(seller))
    _needs_password(seller.post(ADD, json=_device().create(pending, flags=CONDITIONAL)))
    assert _passkeys(owner) == []
    # كلمة المرور من جديد تفتح جلسةً تُنشئ مفتاحاً.
    assert log_in(seller).status_code == 204
    add_passkey(seller)


@pytest.mark.parametrize("past", [-0.2, 0.1], ids=["just-before", "just-after"])
def test_a_password_sign_in_creates_a_passkey_for_five_minutes(owner, seller, past):
    assert passkeys.UPGRADE_SECONDS == 300
    options = expect(add_options(seller))
    _age_sessions(owner, passkeys.UPGRADE_SECONDS / 60 + past)
    response = seller.post(ADD, json=_device().create(options, flags=CONDITIONAL))
    if past < 0:
        assert response.status_code == 204, response.text
    else:
        _needs_password(response)


def test_a_session_opened_by_a_passkey_creates_no_passkey(owner, seller, browser):
    """المفتاح لا يُنشئ مفتاحاً: من يملك مفتاحاً لا يضيف به غيره، وكلمة المرور شرط."""
    device = add_passkey(seller)
    phone = browser()
    assert sign_in(phone, device).status_code == 204
    _needs_password(add_options(phone))


def test_a_session_opened_by_an_activation_link_creates_no_passkey(owner, browser):
    """الواجهة لا تطلبه بعد التفعيل، والخادم لا يقبله: الشرط دخولٌ بكلمة المرور."""
    user = _user_id_after_invite(owner)
    token = auth.new_token()
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (%s, %s, now() + interval '1 hour')", (auth.hash_token(token), user))
    client = browser()
    assert client.post("/api/auth/activate", json={
        "token": token, "username": SELLER, "password": "Activated-Password-2026-z"}).status_code == 204
    _needs_password(add_options(client))


def _user_id_after_invite(owner) -> UUID:
    return make_user(owner, login=auth.login_hmac(LOGIN_KEY, SELLER), password_hash=None)


def test_the_login_named_in_the_options_must_be_the_accounts(owner, seller, intruder):
    """الاسم الذي يُعرض في المفتاح يطابق الحساب؛ لا يُعرض فيه اسمُ غيره."""
    _needs_password(add_options(seller, INTRUDER))
    assert expect(add_options(seller, " SELLER@example.sa"))["user"]["name"] == " SELLER@example.sa"


def test_a_session_signed_out_while_its_key_is_verified_saves_nothing(owner, seller, browser, monkeypatch):
    """
    الجلسة يفحصها `require_user` في معاملة، والحفظ في معاملةٍ بعدها: خروجٌ أو استردادٌ
    بينهما يُبطلها. فالقاعدة تفحصها ثانيةً في معاملة الحفظ نفسها، بعد قفل الحساب.
    """
    options = expect(add_options(seller))
    token = seller.cookies.get(COOKIE)
    real = passkeys.verify_registration_response

    def sign_out_first(**kwargs):
        response = browser(write_headers=False).post(
            "/api/auth/logout", headers={**WRITE_HEADERS, **with_cookie(token)})
        assert response.status_code == 204
        return real(**kwargs)

    monkeypatch.setattr(passkeys, "verify_registration_response", sign_out_first)
    _needs_password(seller.post(ADD, json=_device().create(options, flags=CONDITIONAL)))
    assert _passkeys(owner) == []


@pytest.mark.parametrize("flags", [CONDITIONAL, UP, UV, UP | UV], ids=["conditional", "up", "uv", "up-uv"])
def test_a_created_key_need_not_carry_presence_or_verification(owner, seller, browser, flags):
    """
    الإنشاء المشروط بلا نافذة: المتصفّح يضع العلَمين صفراً، والخادم لا يشترطهما عند
    الإنشاء (WebAuthn L3 §7.1). ويشترطهما عند كل دخولٍ بالمفتاح.
    """
    device = _device()
    options = expect(add_options(seller))
    assert seller.post(ADD, json=device.create(options, flags=flags)).status_code == 204
    _refused(sign_in(browser(), device, flags=UP))
    assert sign_in(browser(), device).status_code == 204


# ── فشل الدخول ─────────────────────────────────────────────────────────
ASSERTION_FAULTS = [
    pytest.param({"origin": "https://testserver.evil.example"}, id="foreign-origin"),
    pytest.param({"origin": "http://testserver"}, id="http-origin"),
    pytest.param({"rp_id": "evil.example"}, id="foreign-rp-id"),
    pytest.param({"flags": UP}, id="no-user-verification"),
    pytest.param({"flags": UV}, id="no-user-presence"),
    pytest.param({"kind": "webauthn.create"}, id="creation-type"),
    pytest.param({"cross_origin": True}, id="in-a-frame"),
    pytest.param({"corrupt_signature": True}, id="bad-signature"),
    pytest.param({"user_handle": b"\x01" * 32}, id="another-user-handle"),
    pytest.param({"challenge": b64(bytes(32))}, id="unissued-challenge"),
]


@pytest.mark.parametrize("fault", ASSERTION_FAULTS)
def test_a_faulty_assertion_signs_in_no_one(owner, seller, browser, fault):
    """كلٌّ من هذه وحده يكفي لرفض الدخول؛ ولا يُكتب وقت استعمالٍ لمفتاحٍ لم يُدخَل به."""
    device = add_passkey(seller)
    client = browser()
    _refused(sign_in(client, device, **fault))
    assert client.get("/api/me").status_code == 401
    assert _passkeys(owner)[0][4] is False
    # الجهاز نفسه بلا عيب يدخل: الرفض كان للعيب وحده.
    assert sign_in(client, device).status_code == 204


def test_an_assertion_without_a_user_handle_is_refused(seller, browser):
    """مفتاحٌ يُدخَل به بلا اسم يُعيد معرّف صاحبه؛ غيابه لا يُفهم إلا رداً من غير هذا المفتاح."""
    device = add_passkey(seller)
    options = expect(browser().post(LOGIN_OPTIONS))
    body = device.get(options)
    del body["response"]["userHandle"]
    _refused(browser().post(LOGIN, json=body))


def test_every_passkey_login_failure_looks_the_same(owner, browser):
    """
    مفتاحٌ مجهول، وتوقيعٌ خاطئ، ومفتاح حسابٍ حُذف — جوابٌ يفرّق بينها يقول
    للسائل إن كان المفتاح لحسابٍ قائم.
    """
    removed = signed_in(owner, browser, INTRUDER)
    gone = add_passkey(removed, username=INTRUDER)
    assert removed.post("/api/me/delete").status_code == 204
    kept = add_passkey(signed_in(owner, browser, SELLER))

    unknown = sign_in(browser(), _device())
    wrong = sign_in(browser(), kept, corrupt_signature=True)
    deleted = sign_in(browser(), gone)
    for response in (unknown, wrong, deleted):
        _refused(response)
    assert unknown.content == wrong.content == deleted.content


def test_the_passkey_of_a_deleted_account_signs_in_no_one(owner, seller, browser):
    """الحذف يمحو المفاتيح مع الحساب؛ مفتاحٌ يبقى في سلسلة مفاتيح صاحبه لا يفتح شيئاً."""
    device = add_passkey(seller)
    assert seller.post("/api/me/delete").status_code == 204
    assert _passkeys(owner) == []
    _refused(sign_in(browser(), device))
    # ولا يعود الحساب بالبريد نفسه ليرث المفتاح.
    add_user(owner, SELLER)
    _refused(sign_in(browser(), device))


def test_the_passkey_of_a_deactivated_account_signs_in_no_one(owner, seller, browser):
    device = add_passkey(seller)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET is_active = false WHERE id = %s", (_user_id(owner),))
    _refused(sign_in(browser(), device))


def test_a_recovery_link_removes_every_passkey(owner, seller, browser):
    """مفتاحٌ أضافه من سرق الجلسة يبقى باباً له بعد الاسترداد إن لم يُحذف معه."""
    device = add_passkey(seller)
    token = auth.new_token()
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (%s, %s, now() + interval '1 hour')", (auth.hash_token(token), _user_id(owner)))
    recovered = browser().post("/api/auth/activate", json={
        "token": token, "username": SELLER, "password": "Recovered-Password-2026-y"})
    assert recovered.status_code == 204
    assert _passkeys(owner) == []
    _refused(sign_in(browser(), device))


# ── التحدّي ────────────────────────────────────────────────────────────
def test_a_challenge_signs_in_once(seller, browser):
    """ردٌّ التُقط مرةً — من سجلٍّ أو وكيل — لا يفتح جلسةً ثانية."""
    device = add_passkey(seller)
    client = browser()
    body = device.get(expect(client.post(LOGIN_OPTIONS)))
    assert client.post(LOGIN, json=body).status_code == 204
    _refused(browser().post(LOGIN, json=body))


def test_a_failed_attempt_uses_up_its_challenge(seller, browser):
    """تحدٍّ يبقى بعد الفشل يقبل محاولةً بعد محاولةٍ عليه."""
    device = add_passkey(seller)
    client = browser()
    options = expect(client.post(LOGIN_OPTIONS))
    _refused(sign_in(client, device, options, corrupt_signature=True))
    _refused(sign_in(client, device, options))
    assert sign_in(client, device).status_code == 204


@pytest.mark.parametrize(("age_seconds", "accepted"), [(290, True), (301, False)])
def test_a_challenge_expires_after_five_minutes_in_the_database(owner, seller, browser, age_seconds, accepted):
    """المهلة في القاعدة: `timeout` في الخيارات تلميحٌ للمتصفّح، يتجاهله من شاء."""
    device = add_passkey(seller)
    client = browser()
    options = expect(client.post(LOGIN_OPTIONS))
    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkey_challenges SET created_at = created_at - make_interval(secs => %s),"
                       " expires_at = expires_at - make_interval(secs => %s) WHERE purpose = 'LOGIN'",
                       (age_seconds, age_seconds))
    response = sign_in(client, device, options)
    if accepted:
        assert response.status_code == 204
    else:
        _refused(response)


def test_a_sign_count_that_goes_back_is_refused(owner, seller, browser):
    """عدّادٌ يرجع علامةُ نسخةٍ منسوخة من المفتاح: لا تدخل، ولا يُكتب عدّادها."""
    device = add_passkey(seller, _device(counting=True, sign_count=5))
    assert _passkeys(owner)[0][2] == 5
    assert sign_in(browser(), device).status_code == 204
    assert _passkeys(owner)[0][2] == 6

    _refused(sign_in(browser(), device, sign_count=6))
    _refused(sign_in(browser(), device, sign_count=3))
    _refused(sign_in(browser(), device, sign_count=0))
    assert _passkeys(owner)[0][2] == 6
    assert sign_in(browser(), device, sign_count=9).status_code == 204
    assert _passkeys(owner)[0][2] == 9


# ── فشل الإضافة ────────────────────────────────────────────────────────
ATTESTATION_FAULTS = [
    pytest.param({"origin": "https://evil.example"}, id="foreign-origin"),
    pytest.param({"rp_id": "evil.example"}, id="foreign-rp-id"),
    pytest.param({"kind": "webauthn.get"}, id="assertion-type"),
    pytest.param({"cross_origin": True}, id="in-a-frame"),
    pytest.param({"challenge": b64(bytes(32))}, id="unissued-challenge"),
]


@pytest.mark.parametrize("fault", ATTESTATION_FAULTS)
def test_a_faulty_attestation_adds_nothing(owner, seller, fault):
    options = expect(add_options(seller))
    _not_added(seller.post(ADD, json=_device().create(options, flags=CONDITIONAL, **fault)))
    assert _passkeys(owner) == []


def test_an_add_challenge_belongs_to_the_session_that_asked_for_it(owner, seller, intruder):
    """تحدٍّ يُستعمل من حسابٍ آخر يلصق مفتاح المهاجم بحساب الضحية أو العكس."""
    options = expect(add_options(seller))
    device = _device()
    _not_added(intruder.post(ADD, json=device.create(options, flags=CONDITIONAL)))
    assert _passkeys(owner) == []
    # لم يستهلكه الدخيل: صاحبه يكمل به.
    assert seller.post(ADD, json=device.create(options, flags=CONDITIONAL)).status_code == 204
    assert [row[0] for row in _passkeys(owner)] == [_user_id(owner)]


def test_a_login_challenge_does_not_add_a_passkey(owner, seller):
    options = expect(seller.post(LOGIN_OPTIONS))
    _not_added(seller.post(ADD, json=_device().create(
        {"challenge": options["challenge"], "user": {"id": b64(bytes(32))}})))
    assert _passkeys(owner) == []


def test_an_add_challenge_is_used_once(owner, seller):
    options = expect(add_options(seller))
    first, second = _device(), _device()
    assert seller.post(ADD, json=first.create(options, flags=CONDITIONAL)).status_code == 204
    _not_added(seller.post(ADD, json=second.create(options, flags=CONDITIONAL)))
    assert [row[1] for row in _passkeys(owner)] == [first.credential_id]


def test_a_key_saved_for_one_account_is_not_added_to_another(owner, seller, intruder, browser):
    """
    المعرّف فريد: مفتاحٌ يُضاف لحسابين يُدخِل صاحبه إلى أحدهما بلا قرار. والجواب
    جوابُ أيّ فشلٍ آخر، فلا يُعرف منه أن المفتاح لغيره.
    """
    device = add_passkey(seller)
    options = expect(add_options(intruder, INTRUDER))
    _not_added(intruder.post(ADD, json=device.create(options, flags=CONDITIONAL)))
    assert [row[0] for row in _passkeys(owner)] == [_user_id(owner)]
    device.user_handle = passkeys.user_handle(LOGIN_KEY, _user_id(owner))
    phone = browser()
    assert sign_in(phone, device).status_code == 204
    assert phone.get("/api/me").status_code == 200


#: clientDataJSON متداخلٌ بعمق في حدود طول الحقل (4000 حرفٍ من 4096): json.loads يرفع
#: RecursionError، لا خطأ تحليل.
DEEP = b64(b"[" * 1500 + b"]" * 1500)


@pytest.mark.parametrize(("part", "value"), [
    ("attestationObject", b64(b"\xa1\x01\x02" + bytes(40))),
    ("clientDataJSON", b64(b"\xa1\x01\x02" + bytes(40))),
    ("clientDataJSON", DEEP),
], ids=["attestation", "client-data", "deeply-nested-client-data"])
def test_a_malformed_response_is_a_refusal_not_a_server_error(owner, seller, part, value):
    options = expect(add_options(seller))
    body = _device().create(options, flags=CONDITIONAL)
    body["response"][part] = value
    _not_added(seller.post(ADD, json=body))


@pytest.mark.parametrize(("part", "value"), [
    ("authenticatorData", b64(b"\x00" * 10)),
    ("clientDataJSON", DEEP),
], ids=["authenticator-data", "deeply-nested-client-data"])
def test_a_malformed_assertion_is_a_refusal_not_a_server_error(seller, browser, part, value):
    device = add_passkey(seller)
    body = device.get(expect(browser().post(LOGIN_OPTIONS)))
    body["response"][part] = value
    _refused(browser().post(LOGIN, json=body))


@pytest.mark.parametrize("change", [
    pytest.param(lambda body: body.update(extra=True), id="unknown-field"),
    pytest.param(lambda body: body.update(rawId=body["rawId"] + "="), id="padded"),
    pytest.param(lambda body: body.update(type="password"), id="wrong-type"),
    pytest.param(lambda body: body["response"].update(signature="x" * 2049), id="oversized"),
])
def test_a_body_out_of_shape_is_refused_before_the_database(owner, seller, browser, change):
    device = add_passkey(seller)
    client = browser()
    body = device.get(expect(client.post(LOGIN_OPTIONS)))
    change(body)
    response = client.post(LOGIN, json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID"
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM passkey_challenges WHERE purpose = 'LOGIN' AND used_at IS NULL")
        assert cursor.fetchone()[0] == 1


def test_the_eleventh_passkey_is_refused_before_the_device_is_asked(owner, seller):
    """والسقف يُفحص ثانيةً عند الحفظ: خياراتٌ صدرت قبل بلوغه لا تتجاوزه."""
    add_passkey(seller)
    pending = expect(add_options(seller))
    with owner.cursor() as cursor:
        for n in range(passkeys.MAX_PASSKEYS - 1):
            cursor.execute("INSERT INTO passkeys (user_id, credential_id, public_key) VALUES (%s, %s, '\\x01')",
                           (_user_id(owner), bytes([n]) * 16))
    cap = {"code": "PASSKEY_CAP", "detail": "لهذا الحساب عشرة مفاتيح مرور، وهو الحدّ."}
    response = add_options(seller)
    assert response.status_code == 409
    assert response.json() == cap
    late = seller.post(ADD, json=_device().create(pending, flags=CONDITIONAL))
    assert late.status_code == 409
    assert late.json() == cap
    assert len(_passkeys(owner)) == passkeys.MAX_PASSKEYS


# ── الحدود والترويسات ──────────────────────────────────────────────────
def test_passkey_sign_in_is_limited_per_address(owner, server):
    """كل طلب خياراتٍ صفٌّ في القاعدة، وكل تحقّقٍ عملٌ في الخادم: بلا حدٍّ يملؤها عنوانٌ واحد."""
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=("203.0.113.9", 50000)) as one:
        options = [expect(one.post(LOGIN_OPTIONS)) for _ in range(19)]
        _refused(one.post(LOGIN, json=_device().get(options[0])))
        refused = one.post(LOGIN_OPTIONS)
        assert refused.status_code == 429
        assert refused.json()["code"] == "RATE"
        assert 1 <= int(refused.headers["retry-after"]) <= 61
        assert one.post(LOGIN, json=_device().get(options[1])).status_code == 429
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM passkey_challenges")
        assert cursor.fetchone()[0] == 19
    # عنوانٌ آخر يُجاب كالمعتاد.
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=("198.51.100.7", 50000)) as two:
        assert two.post(LOGIN_OPTIONS).status_code == 200


def test_adding_passkeys_is_limited_per_account(owner, seller, intruder):
    for _ in range(20):
        assert add_options(seller).status_code == 200
    refused = add_options(seller)
    assert refused.status_code == 429
    assert refused.json()["code"] == "RATE"
    assert seller.post(ADD, json=_device().create(
        {"challenge": b64(bytes(32)), "user": {"id": b64(bytes(32))}})).status_code == 429
    # الحدّ للحساب لا للخادم.
    assert add_options(intruder, INTRUDER).status_code == 200


@pytest.mark.parametrize(("first", "second", "shared"), [
    ("2001:db8:0:1::1", "2001:db8:0:1:ffff:ffff:ffff:fffe", True),
    ("2001:db8:0:1::1", "2001:db8:0:2::1", False),
    ("::ffff:203.0.113.9", "203.0.113.9", True),
    ("203.0.113.9", "203.0.113.10", False),
], ids=["same-ipv6-64", "another-ipv6-64", "ipv4-mapped", "another-ipv4"])
def test_the_passkey_limit_counts_an_ipv6_slash_64_as_one_address(owner, server, first, second, shared):
    """
    المشترك الواحد يُعطى عادةً /64 كاملة من IPv6: عنوانٌ جديد منها لكل طلبٍ كان
    يتجاوز حدّ العنوان، وكل طلب خياراتٍ صفٌّ في القاعدة.
    """
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=(first, 50000)) as one:
        for _ in range(20):
            assert one.post(LOGIN_OPTIONS).status_code == 200
    with TestClient(server, base_url=ORIGIN, headers=dict(WRITE_HEADERS), client=(second, 50000)) as two:
        assert two.post(LOGIN_OPTIONS).status_code == (429 if shared else 200)


@pytest.mark.parametrize(("host", "network"), [
    ("2001:db8:0:1:2:3:4:5", "2001:db8:0:1::/64"),
    ("::ffff:198.51.100.7", "198.51.100.7"),
    ("198.51.100.7", "198.51.100.7"),
    ("testclient", "testclient"),
])
def test_client_network(host, network):
    request = type("Request", (), {"client": type("Client", (), {"host": host})()})()
    assert deps.client_network(request) == network


def test_live_login_challenges_have_a_ceiling_in_the_database(owner, browser):
    """
    حدّ العنوان في ذاكرة كل عملية، وعناوين كثيرة تتجاوزه معاً. والقاعدة تسقف
    تحدّيات الدخول السارية: فوقها 503 بمهلةٍ معلنة، وكلمة المرور تعمل كالمعتاد.
    """
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO passkey_challenges (challenge_hash, purpose, expires_at)"
            " SELECT sha256(convert_to('flood' || i::text, 'UTF8')), 'LOGIN', now() + interval '5 minutes'"
            " FROM generate_series(1, %s) AS i", (passkeys.LOGIN_CHALLENGES_MAX - 1,))
    client = browser()
    assert client.post(LOGIN_OPTIONS).status_code == 200
    busy = client.post(LOGIN_OPTIONS)
    assert busy.status_code == 503
    assert busy.json() == {"code": "PASSKEY_BUSY",
                           "detail": "الدخول بمفتاح المرور مشغولٌ الآن. ادخل بكلمة المرور، أو حاول بعد قليل."}
    assert busy.headers["retry-after"] == "60"
    add_user(owner, SELLER)
    assert log_in(client).status_code == 204


@pytest.mark.parametrize("route", [LOGIN_OPTIONS, LOGIN, ADD_OPTIONS, ADD])
@pytest.mark.parametrize("forgery", [
    pytest.param({"X-Eyework": "0", "Origin": ORIGIN}, id="x-eyework-not-1"),
    pytest.param({"X-Eyework": "1", "Origin": "https://evil.example"}, id="foreign-origin"),
])
def test_passkey_routes_refuse_writes_from_elsewhere(owner, seller, browser, route, forgery):
    """صفحةٌ أجنبية تطلب تحدّياً أو تُرسل ردّاً باسم المستخدم — كأيّ كتابةٍ أخرى."""
    response = seller.post(route, headers=forgery, json={})
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN"
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM passkey_challenges")
        assert cursor.fetchone()[0] == 0


def test_a_passkey_never_replaces_the_password(owner, seller, browser):
    """iCloud Keychain والمصادقة بخطوتين شرطان لمفاتيح المرور؛ كلمة المرور تبقى لمن لا يملكهما."""
    add_passkey(seller)
    assert log_in(browser()).status_code == 204
