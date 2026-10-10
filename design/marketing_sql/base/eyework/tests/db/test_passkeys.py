"""
مفاتيح المرور — في القاعدة
==========================
ما تفرضه القاعدة وحدها، بدور الويب نفسه الذي يحمله الخادم:

  • الجدولان مغلقان أمام دور الويب كجداول الهوية؛ يصلهما عبر دوالّ.
  • مفاتيح كل حسابٍ له وحده: الإضافة والقراءة لصاحب الجلسة، لا لحسابٍ يسمّيه الطلب.
  • التحدّي لغرضه، ومرةً واحدة، وفي مهلته؛ وتحدّي الإضافة لصاحبه وحده.
  • العدّاد لا يرجع، والحساب الموقوف لا يُدخَل إليه بمفتاحه.
  • السقف عشرة مفاتيح؛ والاسترداد والحذف يمحوانها.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from uuid import UUID

import pytest
from psycopg import errors

from eyework.tests.conftest import UNUSABLE_HASH, as_user, make_user


def _hash(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()


CHALLENGE = _hash("challenge")
KEY = b"\xa5\x01\x02\x03\x26"
NEW_HASH = "scrypt$" + "1" * 32 + "$" + "1" * 128


def scalar(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


def issue(app, user: UUID | None, purpose: str, challenge: bytes = CHALLENGE) -> None:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_passkey_challenge(%s, %s)", (challenge, purpose))


def take(app, user: UUID | None, purpose: str, challenge: bytes = CHALLENGE) -> bool:
    as_user(app, user)
    return scalar(app, "SELECT ew_passkey_take_challenge(%s, %s)", (challenge, purpose))


def add(app, user: UUID | None, credential: bytes, *, sign_count: int = 0,
        transports: list[str] | None = None) -> bool:
    as_user(app, user)
    return scalar(app, "SELECT ew_passkey_add(%s, %s, %s, %s)",
                  (credential, KEY, sign_count, ["internal"] if transports is None else transports))


def mine(app, user: UUID | None) -> list[tuple[bytes, list[str]]]:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT credential_id, transports FROM ew_my_passkeys()")
        return cursor.fetchall()


def lookup(app, credential: bytes) -> list[tuple]:
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT user_id, public_key, sign_count FROM ew_passkey_lookup(%s)", (credential,))
        return cursor.fetchall()


def signed_in(app, credential: bytes, sign_count: int) -> UUID | None:
    as_user(app, None)
    return scalar(app, "SELECT ew_passkey_signed_in(%s, %s)", (credential, sign_count))


def stored(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT user_id, credential_id, sign_count, transports FROM passkeys"
                       " ORDER BY created_at, id")
        return cursor.fetchall()


# ── المفاتيح لأصحابها ──────────────────────────────────────────────────
def test_a_passkey_is_added_to_the_session_user_and_read_back_by_them_alone(app, owner, two_users):
    """قراءةٌ تُرجع مفاتيح غيره تكشف من يستخدم التطبيق؛ وإضافةٌ تقبل حساباً من الطلب تلصق مفتاحاً بغير صاحبه."""
    a, b = two_users
    assert add(app, a, b"key-of-a")
    assert add(app, b, b"key-of-b", transports=[])
    assert stored(owner) == [(a, b"key-of-a", 0, ["internal"]), (b, b"key-of-b", 0, [])]
    assert mine(app, a) == [(b"key-of-a", ["internal"])]
    assert mine(app, b) == [(b"key-of-b", [])]
    assert mine(app, None) == []


def test_without_a_session_no_passkey_is_added(app, owner, two_users):
    with pytest.raises(errors.InsufficientPrivilege):
        add(app, None, b"orphan")
    assert stored(owner) == []


@pytest.mark.parametrize("state", ["inactive", "invited"])
def test_an_account_that_cannot_sign_in_cannot_add_a_passkey(app, owner, state):
    """مفتاحٌ لحسابٍ موقوف يعود به حين يُعاد تفعيله، ولحسابٍ لم يُفعَّل يتخطّى رابط الدعوة."""
    user = make_user(owner, login=b"blocked", active=state != "inactive",
                     password_hash=None if state == "invited" else UNUSABLE_HASH)
    with pytest.raises(errors.InsufficientPrivilege):
        add(app, user, b"blocked-key")
    with pytest.raises(errors.InsufficientPrivilege):
        issue(app, user, "ADD")
    assert stored(owner) == []


def test_a_credential_id_is_saved_once_across_accounts(app, owner, two_users):
    """false بلا فرقٍ بين «لهذا الحساب» و«لغيره»: الجواب لا يقول لمن المفتاح."""
    a, b = two_users
    assert add(app, a, b"shared")
    assert add(app, b, b"shared") is False
    assert add(app, a, b"shared") is False
    assert stored(owner) == [(a, b"shared", 0, ["internal"])]


def test_ten_passkeys_at_most(app, owner, two_users):
    a, b = two_users
    for n in range(10):
        assert add(app, a, b"key-%d" % n)
    with pytest.raises(errors.CheckViolation) as caught:
        add(app, a, b"key-10")
    assert caught.value.diag.constraint_name == "passkey_cap"
    with pytest.raises(errors.CheckViolation) as caught:
        issue(app, a, "ADD")
    assert caught.value.diag.constraint_name == "passkey_cap"
    # السقف للحساب لا للجميع.
    assert add(app, b, b"key-of-b")
    issue(app, b, "ADD")


@pytest.mark.parametrize(("column", "value", "constraint"), [
    ("credential_id", b"", "passkey_credential_id_shape"),
    ("credential_id", b"x" * 1024, "passkey_credential_id_shape"),
    ("public_key", b"x" * 2049, "passkey_public_key_shape"),
    ("sign_count", -1, "passkey_sign_count_range"),
    ("sign_count", 2**32, "passkey_sign_count_range"),
    ("transports", ["usb", "pigeon"], "passkey_transports_known"),
])
def test_what_is_stored_has_bounds_even_for_the_owner(owner, two_users, column, value, constraint):
    row = {"user_id": two_users[0], "credential_id": b"bounded", "public_key": KEY, "sign_count": 0,
           "transports": ["internal"]}
    row[column] = value
    with pytest.raises(errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, transports)"
                       " VALUES (%(user_id)s, %(credential_id)s, %(public_key)s, %(sign_count)s,"
                       "         %(transports)s)", row)
    assert caught.value.diag.constraint_name == constraint


# ── الدخول ─────────────────────────────────────────────────────────────
def test_lookup_finds_the_key_of_an_active_account_only(app, owner, two_users):
    a, b = two_users
    add(app, a, b"key-of-a", sign_count=7)
    add(app, b, b"key-of-b")
    assert lookup(app, b"key-of-a") == [(a, KEY, 7)]
    assert lookup(app, b"unknown") == []
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET is_active = false WHERE id = %s", (b,))
    assert lookup(app, b"key-of-b") == []
    assert signed_in(app, b"key-of-b", 1) is None


@pytest.mark.parametrize(("before", "after", "accepted"), [
    (0, 0, True),      # مفتاحٌ لا يعدّ
    (0, 1, True),
    (5, 6, True),
    (5, 5, False),
    (5, 4, False),
    (5, 0, False),
])
def test_the_sign_count_never_goes_back(app, owner, two_users, before, after, accepted):
    """دخولان متزامنان بالعدّاد نفسه: الثاني يرى ما كتبه الأول فيُرفض، ولو مرّ فحص بايثون قبله."""
    a, _ = two_users
    add(app, a, b"counted", sign_count=before)
    assert signed_in(app, b"counted", after) == (a if accepted else None)
    with owner.cursor() as cursor:
        cursor.execute("SELECT sign_count, last_used_at IS NOT NULL FROM passkeys")
        assert cursor.fetchone() == ((after, True) if accepted else (before, False))


# ── التحدّي ────────────────────────────────────────────────────────────
def test_a_login_challenge_is_taken_once(app, owner):
    issue(app, None, "LOGIN")
    assert take(app, None, "LOGIN") is True
    assert take(app, None, "LOGIN") is False


def test_a_login_challenge_has_no_owner_even_from_a_session(app, owner, two_users):
    """تحدّي دخولٍ يحمل صاحب الجلسة التي طلبته يربط جهازاً بحسابٍ قبل أن يدخل."""
    a, b = two_users
    issue(app, a, "LOGIN")
    assert scalar(owner, "SELECT user_id FROM passkey_challenges") is None
    assert take(app, b, "LOGIN") is True


def test_a_challenge_serves_its_purpose_only(app, owner, two_users):
    a, _ = two_users
    issue(app, None, "LOGIN", _hash("login"))
    issue(app, a, "ADD", _hash("add"))
    assert take(app, a, "ADD", _hash("login")) is False
    assert take(app, None, "LOGIN", _hash("add")) is False
    assert take(app, a, "LOGIN", _hash("add")) is False
    assert take(app, None, "LOGIN", _hash("login")) is True
    assert take(app, a, "ADD", _hash("add")) is True


def test_an_add_challenge_is_taken_by_its_owner_alone(app, owner, two_users):
    a, b = two_users
    issue(app, a, "ADD")
    assert scalar(owner, "SELECT user_id FROM passkey_challenges") == a
    assert take(app, b, "ADD") is False
    assert take(app, None, "ADD") is False
    assert take(app, a, "ADD") is True


@pytest.mark.parametrize(("age", "accepted"), [
    (timedelta(minutes=4, seconds=50), True),
    (timedelta(minutes=5, seconds=1), False),
])
def test_a_challenge_lasts_five_minutes(app, owner, age, accepted):
    issue(app, None, "LOGIN")
    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkey_challenges SET created_at = created_at - %s, expires_at = expires_at - %s",
                       (age, age))
    assert take(app, None, "LOGIN") is accepted


@pytest.mark.parametrize(("purpose", "with_user", "window", "constraint"), [
    ("LOGIN", False, timedelta(minutes=6), "passkey_challenge_window"),
    ("LOGIN", False, timedelta(0), "passkey_challenge_window"),
    ("LOGIN", True, timedelta(minutes=1), "passkey_challenge_owner"),
    ("ADD", False, timedelta(minutes=1), "passkey_challenge_owner"),
    ("SIGN", False, timedelta(minutes=1), "passkey_challenge_purpose"),
])
def test_a_challenge_row_has_its_shape_even_for_the_owner(owner, two_users, purpose, with_user, window,
                                                          constraint):
    with pytest.raises(errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, expires_at)"
                       " VALUES (%s, %s, %s, now() + %s)",
                       (CHALLENGE, purpose, two_users[0] if with_user else None, window))
    assert caught.value.diag.constraint_name == constraint


def test_an_unknown_purpose_is_refused(app):
    with pytest.raises(errors.CheckViolation) as caught:
        issue(app, None, "SIGN")
    assert caught.value.diag.constraint_name == "passkey_challenge_purpose"


# ── الاسترداد والحذف ───────────────────────────────────────────────────
def test_activation_removes_the_passkeys_of_that_account_only(app, owner, two_users):
    """مفتاحٌ أضافه من سرق الجلسة يبقى باباً له بعد الاسترداد إن لم يُحذف معه."""
    a, b = two_users
    add(app, a, b"key-of-a")
    add(app, b, b"key-of-b")
    token = _hash("recovery")
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (%s, %s, now() + interval '1 hour')", (token, a))
    login = b"user-a".ljust(32, b"\0")[:32]
    as_user(app, None)
    # رمزٌ لا يطابق لا يمحو شيئاً.
    assert scalar(app, "SELECT ew_activate(%s, %s, %s)", (_hash("guess"), login, NEW_HASH)) is None
    assert len(stored(owner)) == 2
    assert scalar(app, "SELECT ew_activate(%s, %s, %s)", (token, login, NEW_HASH)) == a
    assert stored(owner) == [(b, b"key-of-b", 0, ["internal"])]


def test_deleting_an_account_deletes_its_passkeys_and_challenges(app, owner, two_users):
    a, b = two_users
    add(app, a, b"key-of-a")
    add(app, b, b"key-of-b")
    issue(app, a, "ADD")
    as_user(app, a)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")
    assert stored(owner) == [(b, b"key-of-b", 0, ["internal"])]
    assert scalar(owner, "SELECT count(*) FROM passkey_challenges") == 0
