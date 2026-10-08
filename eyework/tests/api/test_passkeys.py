"""
مفاتيح المرور عبر الواجهة البرمجية
==================================
جهازٌ مصطنع (`tests/authenticator.py`) يوقّع كما يوقّع iPhone، والخادم يتحقّق
منه بالمكتبة نفسها، من الطلب إلى القاعدة:

  • يُضاف المفتاح من حسابٍ دخله صاحبه، ثم يُدخَل به بلا اسمٍ ولا كلمة إلى الجلسة
    نفسها التي تفتحها كلمة المرور.
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

PASSKEY_FAILED = {"code": "PASSKEY", "detail": "تعذّر الدخول بمفتاح المرور. حاول مرة أخرى، أو ادخل بكلمة المرور."}
NOT_ADDED = {"code": "PASSKEY_ADD", "detail": "لم يُحفظ مفتاح المرور. حاول مرة أخرى."}
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


def add_passkey(client: TestClient, device: SoftwareAuthenticator | None = None) -> SoftwareAuthenticator:
    device = device or _device()
    options = expect(client.post(ADD_OPTIONS))
    response = client.post(ADD, json=device.create(options))
    assert response.status_code == 204, response.text
    return device


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
def test_a_passkey_added_by_its_owner_signs_in_without_a_name_or_a_password(owner, seller, browser):
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


def test_add_options_ask_for_a_saved_verified_key_without_attestation(owner, seller):
    options = expect(seller.post(ADD_OPTIONS))
    user = _user_id(owner)
    assert options["rp"] == {"id": "testserver", "name": "صياغة"}
    # معرّف المستخدم في المفتاح ليس رقم الحساب.
    assert unb64(options["user"]["id"]) == passkeys.user_handle(LOGIN_KEY, user)
    assert unb64(options["user"]["id"]) != user.bytes
    assert options["user"]["name"] == options["user"]["displayName"] == "صياغة"
    assert options["authenticatorSelection"] == {
        "residentKey": "required", "requireResidentKey": True, "userVerification": "required"}
    assert options["attestation"] == "none"
    assert [param["alg"] for param in options["pubKeyCredParams"]] == [-7, -257]
    assert options["excludeCredentials"] == []
    assert len(unb64(options["challenge"])) == 32

    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET display_name = 'علي' WHERE id = %s", (user,))
    device = add_passkey(seller)
    again = expect(seller.post(ADD_OPTIONS))
    assert again["user"]["name"] == "علي"
    assert again["user"]["id"] == options["user"]["id"]
    assert again["excludeCredentials"] == [
        {"id": b64(device.credential_id), "type": "public-key", "transports": ["hybrid", "internal"]}]


def test_adding_a_passkey_needs_a_session(owner, browser):
    client = browser()
    for route in (ADD_OPTIONS, ADD):
        response = client.post(route, json=_device().create(
            {"challenge": b64(bytes(32)), "user": {"id": b64(bytes(32))}}))
        assert response.status_code == 401
        assert response.json()["code"] == "SESSION"
    assert _passkeys(owner) == []


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
    gone = add_passkey(removed)
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
    pytest.param({"flags": UP}, id="no-user-verification"),
    pytest.param({"flags": UV}, id="no-user-presence"),
    pytest.param({"kind": "webauthn.get"}, id="assertion-type"),
    pytest.param({"cross_origin": True}, id="in-a-frame"),
    pytest.param({"challenge": b64(bytes(32))}, id="unissued-challenge"),
]


@pytest.mark.parametrize("fault", ATTESTATION_FAULTS)
def test_a_faulty_attestation_adds_nothing(owner, seller, fault):
    options = expect(seller.post(ADD_OPTIONS))
    _not_added(seller.post(ADD, json=_device().create(options, **fault)))
    assert _passkeys(owner) == []


def test_an_add_challenge_belongs_to_the_session_that_asked_for_it(owner, seller, intruder):
    """تحدٍّ يُستعمل من حسابٍ آخر يلصق مفتاح المهاجم بحساب الضحية أو العكس."""
    options = expect(seller.post(ADD_OPTIONS))
    device = _device()
    _not_added(intruder.post(ADD, json=device.create(options)))
    assert _passkeys(owner) == []
    # لم يستهلكه الدخيل: صاحبه يكمل به.
    assert seller.post(ADD, json=device.create(options)).status_code == 204
    assert [row[0] for row in _passkeys(owner)] == [_user_id(owner)]


def test_a_login_challenge_does_not_add_a_passkey(owner, seller):
    options = expect(seller.post(LOGIN_OPTIONS))
    _not_added(seller.post(ADD, json=_device().create(
        {"challenge": options["challenge"], "user": {"id": b64(bytes(32))}})))
    assert _passkeys(owner) == []


def test_an_add_challenge_is_used_once(owner, seller):
    options = expect(seller.post(ADD_OPTIONS))
    first, second = _device(), _device()
    assert seller.post(ADD, json=first.create(options)).status_code == 204
    _not_added(seller.post(ADD, json=second.create(options)))
    assert [row[1] for row in _passkeys(owner)] == [first.credential_id]


def test_a_key_saved_for_one_account_is_not_added_to_another(owner, seller, intruder, browser):
    """
    المعرّف فريد: مفتاحٌ يُضاف لحسابين يُدخِل صاحبه إلى أحدهما بلا قرار. والجواب
    جوابُ أيّ فشلٍ آخر، فلا يُعرف منه أن المفتاح لغيره.
    """
    device = add_passkey(seller)
    options = expect(intruder.post(ADD_OPTIONS))
    _not_added(intruder.post(ADD, json=device.create(options)))
    assert [row[0] for row in _passkeys(owner)] == [_user_id(owner)]
    device.user_handle = passkeys.user_handle(LOGIN_KEY, _user_id(owner))
    phone = browser()
    assert sign_in(phone, device).status_code == 204
    assert phone.get("/api/me").status_code == 200


@pytest.mark.parametrize("part", ["attestationObject", "clientDataJSON"])
def test_a_malformed_response_is_a_refusal_not_a_server_error(owner, seller, part):
    options = expect(seller.post(ADD_OPTIONS))
    body = _device().create(options)
    body["response"][part] = b64(b"\xa1\x01\x02" + bytes(40))
    _not_added(seller.post(ADD, json=body))


def test_a_malformed_assertion_is_a_refusal_not_a_server_error(seller, browser):
    device = add_passkey(seller)
    body = device.get(expect(browser().post(LOGIN_OPTIONS)))
    body["response"]["authenticatorData"] = b64(b"\x00" * 10)
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
    pending = expect(seller.post(ADD_OPTIONS))
    with owner.cursor() as cursor:
        for n in range(passkeys.MAX_PASSKEYS - 1):
            cursor.execute("INSERT INTO passkeys (user_id, credential_id, public_key) VALUES (%s, %s, '\\x01')",
                           (_user_id(owner), bytes([n]) * 16))
    cap = {"code": "PASSKEY_CAP", "detail": "لهذا الحساب عشرة مفاتيح مرور، وهو الحدّ."}
    response = seller.post(ADD_OPTIONS)
    assert response.status_code == 409
    assert response.json() == cap
    late = seller.post(ADD, json=_device().create(pending))
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
        assert seller.post(ADD_OPTIONS).status_code == 200
    refused = seller.post(ADD_OPTIONS)
    assert refused.status_code == 429
    assert refused.json()["code"] == "RATE"
    assert seller.post(ADD, json=_device().create(
        {"challenge": b64(bytes(32)), "user": {"id": b64(bytes(32))}})).status_code == 429
    # الحدّ للحساب لا للخادم.
    assert intruder.post(ADD_OPTIONS).status_code == 200


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
