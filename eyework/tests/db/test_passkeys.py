"""
مفاتيح المرور — في القاعدة
==========================
ما تفرضه القاعدة وحدها، بدور الويب نفسه الذي يحمله الخادم:

  • الجدولان مغلقان أمام دور الويب كجداول الهوية؛ يصلهما عبر دوالّ.
  • مفاتيح كل حسابٍ له وحده: الإضافة والقراءة لصاحب الجلسة، لا لحسابٍ يسمّيه الطلب.
  • الإضافة لجلسة الطلب نفسها، قائمةً، وفُتحت بكلمة المرور قبل خمس دقائق على الأكثر:
    عند التحدّي، ثم في معاملة الحفظ نفسها.
  • التحدّي لغرضه، ومرةً واحدة، وفي مهلته؛ وتحدّي الإضافة لصاحبه وحده. وكل تحدٍّ
    جديد يحذف ما انتهى، وتحدّيات الدخول السارية لها سقف.
  • العدّاد لا يرجع، والحساب الموقوف لا يُدخَل إليه بمفتاحه.
  • السقف عشرة مفاتيح؛ والاسترداد والحذف يمحوانها.

وما يتزامن يُختبر باتصالين، كلٌّ في معاملته: الأولى تقفل وتبقى مفتوحة، والثانية
في خيطٍ يُنتظر حتى تقف على القفل، ثم تُنهى الأولى.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
from datetime import timedelta
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework.tests.conftest import UNUSABLE_HASH, as_user, make_user
from eyework.tests.db.test_state_machine import blocked_on_a_lock


def _hash(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()


CHALLENGE = _hash("challenge")
KEY = b"\xa5\x01\x02\x03\x26"
NEW_HASH = "scrypt$" + "1" * 32 + "$" + "1" * 128
LOGIN_CHALLENGES_MAX = 10_000

_TAKE = "SELECT ew_passkey_take_challenge(%s, %s)"
_ADD = "SELECT ew_passkey_add(%s, %s, %s, %s, %s)"
_SIGNED_IN = "SELECT ew_passkey_signed_in(%s, %s)"
_ACTIVATE = "SELECT ew_activate(%s, %s, %s)"


def scalar(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


def run(connection, statement: str, params: tuple = ()) -> None:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)


def login_of(user_label: bytes) -> bytes:
    """اسم الدخول (HMAC) كما يحفظه `make_user` لاسمه القصير."""
    return user_label.ljust(32, b"\0")[:32]


LOGINS = {b"user-a": login_of(b"user-a"), b"user-b": login_of(b"user-b")}


def password_session(app, user: UUID) -> bytes:
    """جلسةٌ فُتحت بكلمة المرور الآن، كما يفتحها `auth.login`. تُرجع تجزئة رمزها."""
    token = secrets.token_bytes(32)
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_open_password_session(%s, %s)", (user, token))
    return token


def issue_login(app, challenge: bytes = CHALLENGE, user: UUID | None = None) -> None:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_passkey_login_challenge(%s)", (challenge,))


def issue_add(app, user: UUID | None, session: bytes, login: bytes, challenge: bytes = CHALLENGE) -> None:
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_passkey_add_challenge(%s, %s, %s)", (challenge, session, login))


def take(app, user: UUID | None, purpose: str, challenge: bytes = CHALLENGE) -> bool:
    as_user(app, user)
    return scalar(app, _TAKE, (challenge, purpose))


def add(app, user: UUID | None, credential: bytes, *, session: bytes | None = None, sign_count: int = 0,
        transports: list[str] | None = None) -> bool:
    """يحفظ مفتاحاً بجلسة كلمة مرورٍ جديدة لصاحبه، ما لم تُعطَ جلسةٌ بعينها."""
    if session is None:
        session = password_session(app, user) if user is not None else _hash("no-session")
    as_user(app, user)
    return scalar(app, _ADD, (session, credential, KEY, sign_count, ["internal"] if transports is None else transports))


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
    return scalar(app, _SIGNED_IN, (credential, sign_count))


def stored(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT user_id, credential_id, sign_count, transports FROM passkeys"
                       " ORDER BY created_at, id")
        return cursor.fetchall()


def challenges(owner) -> list[tuple]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT purpose, expires_at > now() FROM passkey_challenges ORDER BY created_at")
        return cursor.fetchall()


def web(app_url: str, user: UUID | None = None) -> psycopg.Connection:
    """اتصالٌ بدور الويب في معاملةٍ تبقى مفتوحة حتى commit أو rollback، كمعاملة طلب."""
    connection = psycopg.connect(app_url)
    connection.execute("SELECT set_config('eyework.user_id', %s, true)", ("" if user is None else str(user),))
    return connection


def race(watcher, second: psycopg.Connection, work) -> tuple[threading.Thread, dict]:
    """يشغّل `work(second)` في خيط، ويُرجع بعد أن يقف على قفلٍ (أو ينتهي)."""
    outcome: dict = {}

    def run() -> None:
        try:
            outcome["value"] = work(second)
            second.commit()
        except psycopg.Error as exc:
            second.rollback()
            outcome["error"] = (type(exc).__name__, exc.diag.constraint_name)

    racer = threading.Thread(target=run)
    racer.start()
    outcome["waited"] = blocked_on_a_lock(watcher, second.info.backend_pid, racer)
    return racer, outcome


def activation_token(owner, user: UUID) -> bytes:
    token = _hash(f"recovery-{user}")
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (%s, %s, now() + interval '1 hour')", (token, user))
    return token


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
        add(app, user, b"blocked-key", session=_hash("any"))
    with pytest.raises(errors.InsufficientPrivilege):
        issue_add(app, user, _hash("any"), login_of(b"blocked"))
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
    session = password_session(app, a)
    for n in range(10):
        assert add(app, a, b"key-%d" % n, session=session)
    with pytest.raises(errors.CheckViolation) as caught:
        add(app, a, b"key-10", session=session)
    assert caught.value.diag.constraint_name == "passkey_cap"
    with pytest.raises(errors.CheckViolation) as caught:
        issue_add(app, a, session, LOGINS[b"user-a"])
    assert caught.value.diag.constraint_name == "passkey_cap"
    # السقف للحساب لا للجميع.
    assert add(app, b, b"key-of-b")
    issue_add(app, b, password_session(app, b), LOGINS[b"user-b"])


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


# ── الإضافة لجلسة كلمة مرورٍ قائمةٍ حديثة ──────────────────────────────
def _age(owner, session: bytes, **moves: timedelta) -> None:
    """يحرّك أوقات الجلسة إلى الوراء معاً (القيود تربط بعضها ببعض)."""
    with owner.cursor() as cursor:
        cursor.execute("UPDATE sessions SET created_at = created_at - %(created)s,"
                       " password_at = password_at - %(password)s, expires_at = expires_at - %(expires)s"
                       " WHERE token_hash = %(token)s", {"token": session, **moves})


SESSION_FAULTS = ["stale", "revoked", "expired", "passkey-session", "another-account", "unknown", "another-login"]


@pytest.mark.parametrize("fault", ["none", *SESSION_FAULTS])
def test_only_a_fresh_password_session_of_the_request_adds_a_passkey(app, owner, two_users, fault):
    """
    ملفّ جلسةٍ وحده لا يكفي: من وجد جهازاً مفتوحاً على حسابٍ أضاف مفتاحاً على
    جهازه هو. فالتحدّي والحفظ لجلسة الطلب نفسها، قائمةً، فتحتها كلمة المرور قبل
    خمس دقائق على الأكثر — وباسم الدخول نفسه.
    """
    a, b = two_users
    session, login = password_session(app, a), LOGINS[b"user-a"]
    minute = timedelta(minutes=1)
    if fault == "stale":
        _age(owner, session, created=6 * minute, password=6 * minute, expires=6 * minute)
    elif fault == "revoked":
        as_user(app, None)
        run(app, "SELECT ew_revoke_session(%s)", (session,))
    elif fault == "expired":
        _age(owner, session, created=2 * minute, password=minute, expires=timedelta(days=30, seconds=1))
    elif fault == "passkey-session":
        session = _hash("passkey-session")
        as_user(app, None)
        run(app, "SELECT ew_open_session(%s, %s)", (a, session))
    elif fault == "another-account":
        session = password_session(app, b)
    elif fault == "unknown":
        session = _hash("unknown")
    elif fault == "another-login":
        login = LOGINS[b"user-b"]

    if fault == "none":
        issue_add(app, a, session, login)
        assert add(app, a, b"fresh", session=session)
        assert [row[1] for row in stored(owner)] == [b"fresh"]
        return
    with pytest.raises(errors.InsufficientPrivilege) as caught:
        issue_add(app, a, session, login)
    assert caught.value.diag.constraint_name == "passkey_needs_password_sign_in"
    if fault != "another-login":
        with pytest.raises(errors.InsufficientPrivilege) as caught:
            add(app, a, b"late", session=session)
        assert caught.value.diag.constraint_name == "passkey_needs_password_sign_in"
    assert stored(owner) == []


@pytest.mark.parametrize(("age", "accepted"), [(timedelta(minutes=4, seconds=50), True),
                                               (timedelta(minutes=5, seconds=1), False)])
def test_a_password_sign_in_adds_for_five_minutes(app, owner, two_users, age, accepted):
    a, _ = two_users
    session = password_session(app, a)
    _age(owner, session, created=age, password=age, expires=age)
    if accepted:
        assert add(app, a, b"in-time", session=session)
    else:
        with pytest.raises(errors.InsufficientPrivilege):
            add(app, a, b"too-late", session=session)


def test_a_session_signed_out_after_its_challenge_adds_nothing(app, owner, two_users):
    """
    الجلسة تُفحص ثانيةً في معاملة الحفظ، لا عند التحدّي وحده: خروجٌ أو استردادٌ
    بين التحدّي والحفظ يمنع المفتاح.
    """
    a, _ = two_users
    session = password_session(app, a)
    issue_add(app, a, session, LOGINS[b"user-a"])
    assert take(app, a, "ADD") is True
    as_user(app, None)
    run(app, "SELECT ew_revoke_session(%s)", (session,))
    with pytest.raises(errors.InsufficientPrivilege):
        add(app, a, b"after-sign-out", session=session)
    assert stored(owner) == []


def test_a_sign_out_waits_for_an_add_in_progress(app, app_url, owner, two_users):
    """الحفظ يقفل جلسته (FOR SHARE): إبطالها ينتظر حتى يكتمل، فلا يُحفظ مفتاحٌ لجلسةٍ أُبطلت قبله."""
    a, _ = two_users
    session = password_session(app, a)
    adding, signing_out = web(app_url, a), web(app_url)
    try:
        assert scalar(adding, _ADD, (session, b"in-progress", KEY, 0, ["internal"])) is True
        racer, outcome = race(app, signing_out, lambda c: run(c, "SELECT ew_revoke_session(%s)", (session,)))
        adding.commit()
        racer.join(timeout=10)
    finally:
        adding.close()
        signing_out.close()
    assert outcome["waited"], outcome
    assert [row[1] for row in stored(owner)] == [b"in-progress"]


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
    """الشرط نفسه على اتصالٍ واحد: عدّادٌ مساوٍ أو أصغر يُرفض، ولا يُكتب. ودخولان معاً في الاختبار التالي."""
    a, _ = two_users
    add(app, a, b"counted", sign_count=before)
    assert signed_in(app, b"counted", after) == (a if accepted else None)
    with owner.cursor() as cursor:
        cursor.execute("SELECT sign_count, last_used_at IS NOT NULL FROM passkeys")
        assert cursor.fetchone() == ((after, True) if accepted else (before, False))


def test_two_sign_ins_with_the_same_count_at_once_let_one_in(app, app_url, owner, two_users):
    """
    نسخةٌ منسوخة من المفتاح توقّع بالعدّاد نفسه في اللحظة نفسها: الثانية تنتظر
    الأولى، ثم ترى ما كتبته فتُرفض — ولو مرّ فحص بايثون للاثنتين قبلهما.
    """
    a, _ = two_users
    add(app, a, b"counted", sign_count=5)
    first, second = web(app_url), web(app_url)
    try:
        assert scalar(first, _SIGNED_IN, (b"counted", 6)) == a
        racer, outcome = race(app, second, lambda c: scalar(c, _SIGNED_IN, (b"counted", 6)))
        first.commit()
        racer.join(timeout=10)
    finally:
        first.close()
        second.close()
    assert outcome == {"waited": True, "value": None}, outcome
    assert [row[2] for row in stored(owner)] == [6]


# ── التحدّي ────────────────────────────────────────────────────────────
def test_a_login_challenge_is_taken_once(app, owner):
    issue_login(app)
    assert take(app, None, "LOGIN") is True
    assert take(app, None, "LOGIN") is False


@pytest.mark.parametrize("first_ends", ["commit", "rollback"])
def test_two_requests_taking_one_challenge_at_once_take_it_once(app, app_url, owner, first_ends):
    """ردٌّ واحد يصل مرتين معاً: الثاني ينتظر الأول، فيأخذه إن تراجع الأول ولا يأخذه إن اكتمل."""
    issue_login(app)
    first, second = web(app_url), web(app_url)
    try:
        assert scalar(first, _TAKE, (CHALLENGE, "LOGIN")) is True
        racer, outcome = race(app, second, lambda c: scalar(c, _TAKE, (CHALLENGE, "LOGIN")))
        getattr(first, first_ends)()
        racer.join(timeout=10)
    finally:
        first.close()
        second.close()
    assert outcome == {"waited": True, "value": first_ends == "rollback"}, outcome


def test_a_login_challenge_has_no_owner_even_from_a_session(app, owner, two_users):
    """تحدّي دخولٍ يحمل صاحب الجلسة التي طلبته يربط جهازاً بحسابٍ قبل أن يدخل."""
    a, b = two_users
    issue_login(app, user=a)
    assert scalar(owner, "SELECT user_id FROM passkey_challenges") is None
    assert take(app, b, "LOGIN") is True


def test_a_challenge_serves_its_purpose_only(app, owner, two_users):
    a, _ = two_users
    issue_login(app, _hash("login"))
    issue_add(app, a, password_session(app, a), LOGINS[b"user-a"], _hash("add"))
    assert take(app, a, "ADD", _hash("login")) is False
    assert take(app, None, "LOGIN", _hash("add")) is False
    assert take(app, a, "LOGIN", _hash("add")) is False
    assert take(app, None, "SIGN", _hash("login")) is False
    assert take(app, None, "LOGIN", _hash("login")) is True
    assert take(app, a, "ADD", _hash("add")) is True


def test_an_add_challenge_is_taken_by_its_owner_alone(app, owner, two_users):
    a, b = two_users
    issue_add(app, a, password_session(app, a), LOGINS[b"user-a"])
    assert scalar(owner, "SELECT user_id FROM passkey_challenges") == a
    assert take(app, b, "ADD") is False
    assert take(app, None, "ADD") is False
    assert take(app, a, "ADD") is True


@pytest.mark.parametrize(("age", "accepted"), [
    (timedelta(minutes=4, seconds=50), True),
    (timedelta(minutes=5, seconds=1), False),
])
def test_a_challenge_lasts_five_minutes(app, owner, age, accepted):
    issue_login(app)
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


# ── الجدول لا يكبر بلا حدّ ─────────────────────────────────────────────
_LIVE = (timedelta(0), timedelta(minutes=5))
_EXPIRED = (timedelta(minutes=-10), timedelta(minutes=-5))


def _insert_challenges(owner, count: int, *, purpose: str = "LOGIN", expired: bool = False,
                       user: UUID | None = None, label: str = "bulk") -> None:
    created, expires = _EXPIRED if expired else _LIVE
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO passkey_challenges (challenge_hash, purpose, user_id, created_at, expires_at)"
            " SELECT sha256(convert_to(%s || i::text, 'UTF8')), %s, %s, now() + %s, now() + %s"
            " FROM generate_series(1, %s) AS i", (label, purpose, user, created, expires, count))


@pytest.mark.parametrize("kind", ["LOGIN", "ADD"])
def test_each_new_challenge_deletes_up_to_ten_expired_ones(app, owner, two_users, kind):
    """
    طلب خيارات الدخول بلا جلسة، وكل طلبٍ صفّ: ما انتهى يُحذف مع كل صفٍّ جديد، عشرةً
    على الأكثر فلا يطول طلبٌ واحد. فلا يكبر الجدول بالمنتهي أسرع مما يُنشأ فيه.
    """
    a, _ = two_users
    _insert_challenges(owner, 15, expired=True)

    def issue(challenge: bytes) -> None:
        if kind == "LOGIN":
            issue_login(app, challenge)
        else:
            issue_add(app, a, password_session(app, a), LOGINS[b"user-a"], challenge)

    issue(_hash("one"))
    assert sorted(challenges(owner), key=str) == sorted([("LOGIN", False)] * 5 + [(kind, True)], key=str)
    issue(_hash("two"))
    assert [live for _, live in challenges(owner)] == [True, True]


def test_an_expired_challenge_another_request_holds_is_skipped_not_waited_for(app, owner, owner_url):
    """طلبان معاً يحذفان المنتهي نفسه: الثاني يتخطّى ما يقفله الأول ولا ينتظره."""
    _insert_challenges(owner, 1, expired=True, label="held")
    with psycopg.connect(owner_url) as holder:
        holder.execute("SELECT 1 FROM passkey_challenges FOR UPDATE")
        done = threading.Event()

        def issue() -> None:
            issue_login(app, _hash("not-blocked"))
            done.set()

        worker = threading.Thread(target=issue)
        worker.start()
        worker.join(timeout=5)
        assert done.is_set(), "طلب الخيارات انتظر قفل صفٍّ منتهٍ"
        holder.rollback()
    assert sorted(challenges(owner)) == [("LOGIN", False), ("LOGIN", True)]


def test_live_login_challenges_have_a_ceiling(app, owner, two_users):
    """
    طلب خيارات الدخول لا يحتاج جلسة، وحدّ العنوان في ذاكرة العملية: سقفٌ في القاعدة
    على تحدّيات الدخول السارية يمنع ملء القرص من عناوين كثيرة. والمنتهي وتحدّي
    الإضافة لا يُعدّان.
    """
    a, _ = two_users
    _insert_challenges(owner, LOGIN_CHALLENGES_MAX - 1)
    _insert_challenges(owner, 50, expired=True, label="old")
    _insert_challenges(owner, 3, purpose="ADD", user=a, label="add")
    issue_login(app, _hash("last"))
    with pytest.raises(errors.CheckViolation) as caught:
        issue_login(app, _hash("one-too-many"))
    assert caught.value.diag.constraint_name == "passkey_login_ceiling"
    # ما تعدّه السقف يسقط حين ينتهي.
    with owner.cursor() as cursor:
        cursor.execute("UPDATE passkey_challenges SET created_at = created_at - interval '5 minutes',"
                       " expires_at = expires_at - interval '5 minutes'"
                       " WHERE challenge_hash = %s", (_hash("last"),))
    issue_login(app, _hash("one-too-many"))


def test_the_challenges_of_an_account_are_found_by_an_index(owner, two_users):
    """حذف الحساب والاسترداد يحذفان تحدّياته؛ بلا فهرسٍ يمرّان على الجدول كلّه."""
    with owner.cursor() as cursor:
        cursor.execute("SET enable_seqscan = off")
        cursor.execute("EXPLAIN DELETE FROM passkey_challenges WHERE user_id = %s", (two_users[0],))
        plan = "\n".join(row[0] for row in cursor.fetchall())
        cursor.execute("RESET enable_seqscan")
    assert "passkey_challenges_user_idx" in plan, plan


# ── الاسترداد والحذف ───────────────────────────────────────────────────
def test_activation_removes_the_passkeys_and_challenges_of_that_account_only(app, owner, two_users):
    """مفتاحٌ أضافه من سرق الجلسة يبقى باباً له بعد الاسترداد إن لم يُحذف معه."""
    a, b = two_users
    add(app, a, b"key-of-a")
    add(app, b, b"key-of-b")
    issue_add(app, b, password_session(app, b), LOGINS[b"user-b"], _hash("add-of-b"))
    token = activation_token(owner, a)
    as_user(app, None)
    # رمزٌ لا يطابق لا يمحو شيئاً.
    assert scalar(app, _ACTIVATE, (_hash("guess"), LOGINS[b"user-a"], NEW_HASH)) is None
    assert len(stored(owner)) == 2
    assert scalar(app, _ACTIVATE, (token, LOGINS[b"user-a"], NEW_HASH)) == a
    assert stored(owner) == [(b, b"key-of-b", 0, ["internal"])]
    assert challenges(owner) == [("ADD", True)]


def test_an_add_challenge_issued_before_a_recovery_is_useless_after_it(app, owner, two_users):
    """طلب إضافةٍ اجتاز فحص الجلسة قبل الاسترداد يبلغ القاعدة بعده: تحدّيه ذهب معه."""
    a, _ = two_users
    issue_add(app, a, password_session(app, a), LOGINS[b"user-a"])
    as_user(app, None)
    assert scalar(app, _ACTIVATE, (activation_token(owner, a), LOGINS[b"user-a"], NEW_HASH)) == a
    assert take(app, a, "ADD") is False


def test_a_recovery_during_a_passkey_sign_in_revokes_the_session_it_opens(app, app_url, owner, two_users):
    """
    من سرق الجلسة وأضاف مفتاحاً يدخل به مرةً بعد مرة. دخولٌ في منتصفه حين يُستردّ
    الحساب يقفل صفّ المفتاح: الاسترداد ينتظره ليحذف المفتاح، ثم يُبطل الجلسة التي
    فتحها — لا يُبطل الجلسات أولاً فتنجو جلسةٌ فُتحت بعد ذلك.
    """
    a, _ = two_users
    add(app, a, b"stolen-key")
    token, attacker = activation_token(owner, a), _hash("attacker-session")
    signing_in, recovering = web(app_url), web(app_url)
    try:
        assert scalar(signing_in, _SIGNED_IN, (b"stolen-key", 0)) == a
        racer, outcome = race(app, recovering, lambda c: scalar(c, _ACTIVATE, (token, LOGINS[b"user-a"], NEW_HASH)))
        signing_in.execute("SELECT ew_open_session(%s, %s)", (a, attacker))
        signing_in.commit()
        racer.join(timeout=10)
    finally:
        signing_in.close()
        recovering.close()
    assert outcome == {"waited": True, "value": a}, outcome
    assert stored(owner) == []
    as_user(app, None)
    assert scalar(app, "SELECT ew_resolve_session(%s)", (attacker,)) is None


def test_a_recovery_during_a_passkey_add_removes_the_key_it_saves(app, app_url, owner, two_users):
    """إضافةٌ أخذت تحدّيها قبل الاسترداد: يقفل صفّ التحدّي، فينتظرها الاسترداد ثم يحذف مفتاحها."""
    a, _ = two_users
    session = password_session(app, a)
    issue_add(app, a, session, LOGINS[b"user-a"])
    token = activation_token(owner, a)
    adding, recovering = web(app_url, a), web(app_url)
    try:
        assert scalar(adding, _TAKE, (CHALLENGE, "ADD")) is True
        racer, outcome = race(app, recovering, lambda c: scalar(c, _ACTIVATE, (token, LOGINS[b"user-a"], NEW_HASH)))
        assert scalar(adding, _ADD, (session, b"in-flight", KEY, 0, ["internal"])) is True
        adding.commit()
        racer.join(timeout=10)
    finally:
        adding.close()
        recovering.close()
    assert outcome == {"waited": True, "value": a}, outcome
    assert stored(owner) == []
    as_user(app, None)
    assert scalar(app, "SELECT ew_resolve_session(%s)", (session,)) is None


def test_two_adds_at_once_stop_at_ten(app, app_url, owner, two_users):
    """
    القفل على صفّ الحساب (FOR UPDATE) هو ما يمنع إضافتين متزامنتين من تجاوز السقف
    معاً: الثانية تنتظر الأولى، ثم تعدّ ما حفظته.
    """
    a, _ = two_users
    session = password_session(app, a)
    for n in range(9):
        assert add(app, a, b"key-%d" % n, session=session)
    first, second = web(app_url, a), web(app_url, a)
    try:
        assert scalar(first, _ADD, (session, b"first", KEY, 0, ["internal"])) is True
        racer, outcome = race(app, second, lambda c: scalar(c, _ADD, (session, b"second", KEY, 0, ["internal"])))
        first.commit()
        racer.join(timeout=10)
    finally:
        first.close()
        second.close()
    assert outcome == {"waited": True, "error": ("CheckViolation", "passkey_cap")}, outcome
    assert len(stored(owner)) == 10


def test_deleting_an_account_deletes_its_passkeys_and_challenges(app, owner, two_users):
    a, b = two_users
    add(app, a, b"key-of-a")
    add(app, b, b"key-of-b")
    issue_add(app, a, password_session(app, a), LOGINS[b"user-a"])
    as_user(app, a)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")
    assert stored(owner) == [(b, b"key-of-b", 0, ["internal"])]
    assert scalar(owner, "SELECT count(*) FROM passkey_challenges") == 0
