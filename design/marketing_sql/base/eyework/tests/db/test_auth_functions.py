"""
دوالّ الهوية
============
دور الويب لا يقرأ جداول الهوية ولا يكتبها: لا منح ولا سياسة. يصلها عبر دوالّ
SECURITY DEFINER، كلٌّ تفعل شيئاً واحداً، فلا حاجز بعد أيٍّ منها إن أخطأت:
رمز تفعيلٍ يُستعمل مرّتين يسلّم الحساب لمن التقط الرابط، والاسترداد الذي لا
يُبطل الجلسات القائمة يُبقي السارق داخلاً، وجلسةٌ لا تنتهي أو لا تموت مع تعطيل
صاحبها تُبقي بابها مفتوحاً، وبحثٌ يُرجع تجزئة حسابٍ معطَّل أو لم يُفعَّل يقبل
دخولاً لم يُؤذن به.

يثبت هذا الملف ما تعِد به كل دالّة باستدعائها بدور الويب كما يستدعيها الخادم،
وأن الجداول خلفها مغلقةٌ أمامه، وأن قيدَي العمر في الجداول يرفضان جلسةً أطول
من ثلاثين يوماً ورمزاً أطول من اثنتين وسبعين ساعة ولو كتبهما المالك.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from psycopg import errors

from eyework.tests.conftest import as_user, make_user



def fake_hash(label: str) -> str:
    """تجزئةٌ بصيغة `eyework.passwords` التي يقبلها الجدول، ولا تطابق كلمةً ما."""
    data = label.encode()
    return f"scrypt${hashlib.sha256(data).hexdigest()[:32]}${hashlib.sha512(data).hexdigest()}"


OLD_HASH = fake_hash("old")
NEW_HASH = fake_hash("new")
OTHER_HASH = fake_hash("other")
UNKNOWN_USER = UUID("00000000-0000-4000-8000-0000000000aa")
SESSION_LIFETIME = timedelta(days=30)
TOKEN_LIFETIME = timedelta(hours=72)


def digest(label: str) -> bytes:
    return hashlib.sha256(label.encode()).digest()


def login_hmac(login: bytes) -> bytes:
    """كما يحفظها `make_user`."""
    return login.ljust(32, b"\0")[:32]


TOKEN = digest("activation-token")
SESSION = digest("session-token")


@contextmanager
def rejected(error: type[Exception], constraint: str | None = None):
    with pytest.raises(error) as caught:
        yield caught
    if constraint is not None:
        assert caught.value.diag.constraint_name == constraint


def scalar(connection, statement: str, params: tuple):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


def activate(app, token: bytes, password_hash: str, *, login: bytes) -> UUID | None:
    """NULL لكل فشل: الخادم يعرض رسالةً واحدة، فلا يُعرف أيّ الشروط لم يتحقّق."""
    return scalar(app, "SELECT ew_activate(%s, %s, %s)", (token, login_hmac(login), password_hash))


def login_lookup(app, login: bytes) -> list[tuple[UUID, str]]:
    with app.cursor() as cursor:
        cursor.execute("SELECT user_id, password_hash FROM ew_login_lookup(%s)", (login_hmac(login),))
        return cursor.fetchall()


def open_session(app, user: UUID, token: bytes) -> None:
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_open_session(%s, %s)", (user, token))


def resolve(app, token: bytes) -> UUID | None:
    return scalar(app, "SELECT ew_resolve_session(%s)", (token,))


def revoke(app, token: bytes) -> None:
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_revoke_session(%s)", (token,))


def seed_token(owner, user: UUID, token: bytes, *, age: timedelta = timedelta(0),
               lifetime: timedelta = TOKEN_LIFETIME) -> None:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO activation_tokens (token_hash, user_id, created_at, expires_at)"
            " VALUES (%s, %s, now() - %s, now() - %s + %s)",
            (token, user, age, age, lifetime),
        )


def seed_session(owner, user: UUID, token: bytes, *, age: timedelta = timedelta(0),
                 lifetime: timedelta = SESSION_LIFETIME) -> None:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at)"
            " VALUES (%s, %s, now() - %s, now() - %s + %s)",
            (user, token, age, age, lifetime),
        )


def credentials(owner, user: UUID) -> tuple[str | None, datetime | None]:
    with owner.cursor() as cursor:
        cursor.execute("SELECT password_hash, activated_at FROM users WHERE id = %s", (user,))
        return cursor.fetchone()


def session_revoked(owner, token: bytes) -> bool:
    return scalar(owner, "SELECT revoked_at IS NOT NULL FROM sessions WHERE token_hash = %s", (token,))


def token_used(owner, token: bytes) -> bool:
    return scalar(owner, "SELECT used_at IS NOT NULL FROM activation_tokens WHERE token_hash = %s", (token,))


def session_count(owner) -> int:
    return scalar(owner, "SELECT count(*) FROM sessions", ())


# ── ew_activate ─────────────────────────────────────────────────────────


def test_activation_sets_the_password_and_returns_the_user(app, owner):
    """تفعيلٌ لا يضع الكلمة يترك الحساب بلا دخول، وتفعيلٌ يُرجع غير صاحبه أو يكتب كلمته على غيره يفتح حساباً لغيره."""
    invited = make_user(owner, login=b"invited", password_hash=None)
    bystander = make_user(owner, login=b"bystander", password_hash=None)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET created_at = now() - interval '2 days' WHERE id = %s", (invited,))
    seed_token(owner, invited, TOKEN)
    assert activate(app, TOKEN, NEW_HASH, login=b"invited") == invited
    assert credentials(owner, invited)[0] == NEW_HASH
    assert scalar(owner, "SELECT activated_at > now() - interval '1 minute' FROM users WHERE id = %s", (invited,))
    assert token_used(owner, TOKEN)
    assert credentials(owner, bystander) == (None, None)


def test_activation_token_is_single_use(app, owner):
    """رمزٌ يُستعمل مرّتين يسلّم الحساب لكل من رأى الرابط بعد صاحبه."""
    invited = make_user(owner, login=b"invited", password_hash=None)
    seed_token(owner, invited, TOKEN)
    assert activate(app, TOKEN, NEW_HASH, login=b"invited") == invited
    assert activate(app, TOKEN, OTHER_HASH, login=b"invited") is None
    assert credentials(owner, invited)[0] == NEW_HASH


@pytest.mark.parametrize(("age", "accepted"), [
    (timedelta(hours=71), True),
    (timedelta(hours=72, minutes=1), False),
    (timedelta(days=10), False),
], ids=["71h", "72h01m", "10d"])
def test_expired_token_is_refused(app, owner, age, accepted):
    """رابطٌ قديم في بريدٍ مخترق أو سجلّ متصفّحٍ مشترك يبقى مفتاحاً للحساب إلى الأبد."""
    invited = make_user(owner, login=b"invited", password_hash=None)
    seed_token(owner, invited, TOKEN, age=age, lifetime=TOKEN_LIFETIME)
    if accepted:
        assert activate(app, TOKEN, NEW_HASH, login=b"invited") == invited
    else:
        assert activate(app, TOKEN, NEW_HASH, login=b"invited") is None
        assert credentials(owner, invited) == (None, None)
        assert not token_used(owner, TOKEN)


@pytest.mark.parametrize("password_hash", [None, OLD_HASH], ids=["invited", "activated"])
def test_token_of_an_inactive_user_is_refused(app, owner, password_hash):
    """تعطيل الحساب لا يعني شيئاً إن أعاد رمزٌ صادرٌ قبله كلمة مرورٍ جديدة."""
    disabled = make_user(owner, login=b"disabled", password_hash=password_hash, active=False)
    seed_token(owner, disabled, TOKEN)
    before = credentials(owner, disabled)
    assert activate(app, TOKEN, NEW_HASH, login=b"disabled") is None
    assert credentials(owner, disabled) == before
    assert not token_used(owner, TOKEN)


def test_unknown_token_is_refused(app, owner):
    """رمزٌ مخمَّن يُقبل فيضع كلمة مرورٍ لحسابٍ ما."""
    invited = make_user(owner, login=b"invited", password_hash=None)
    seed_token(owner, invited, TOKEN)
    assert activate(app, digest("guessed"), NEW_HASH, login=b"invited") is None
    assert credentials(owner, invited) == (None, None)
    assert not token_used(owner, TOKEN)


def test_activation_revokes_every_session(app, owner):
    """الاسترداد بعد سرقة الكلمة لا ينفع إن بقيت جلسة السارق مفتوحة."""
    user = make_user(owner, login=b"recovering", password_hash=OLD_HASH)
    bystander = make_user(owner, login=b"bystander", password_hash=OLD_HASH)
    sessions = [digest("session-laptop"), digest("session-phone")]
    for token in sessions:
        seed_session(owner, user, token)
    seed_token(owner, user, TOKEN)
    seed_session(owner, bystander, digest("bystander-session"))
    seed_token(owner, bystander, digest("bystander-token"))

    assert activate(app, TOKEN, NEW_HASH, login=b"recovering") == user

    assert all(session_revoked(owner, token) for token in sessions)
    assert all(resolve(app, token) is None for token in sessions)
    assert credentials(owner, user)[0] == NEW_HASH
    assert credentials(owner, bystander)[0] == OLD_HASH
    assert not session_revoked(owner, digest("bystander-session"))
    assert resolve(app, digest("bystander-session")) == bystander
    assert not token_used(owner, digest("bystander-token"))


def test_reactivation_replaces_the_hash_and_keeps_the_first_activation_time(app, owner):
    """«وقت التفعيل» شاهدٌ على بداية الحساب؛ استردادٌ يعيد ضبطه يمحو ذلك الأثر."""
    user = make_user(owner, login=b"returning", password_hash=OLD_HASH)
    original = scalar(
        owner,
        "UPDATE users SET activated_at = now() - interval '10 days' WHERE id = %s RETURNING activated_at",
        (user,),
    )
    seed_token(owner, user, TOKEN)
    assert activate(app, TOKEN, NEW_HASH, login=b"returning") == user
    assert credentials(owner, user) == (NEW_HASH, original)


# ── ew_login_lookup ─────────────────────────────────────────────────────


def test_login_lookup_returns_the_hash_of_an_active_activated_user(app, owner):
    """بحثٌ لا يجد صاحب الحساب يغلقه أمامه، وبحثٌ يُرجع تجزئة غيره يُدخله باسم غيره."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    make_user(owner, login=b"neighbour", password_hash=OTHER_HASH)
    assert login_lookup(app, b"member") == [(user, OLD_HASH)]


@pytest.mark.parametrize(("password_hash", "active"), [
    (None, True),
    (OLD_HASH, False),
    (None, False),
], ids=["unactivated", "inactive", "inactive-unactivated"])
def test_login_lookup_hides_users_who_may_not_log_in(app, owner, password_hash, active):
    """حسابٌ معطَّل يبقى يدخل، أو مدعوٌّ لم يضع كلمته يُفتح بغيرها."""
    make_user(owner, login=b"member", password_hash=password_hash, active=active)
    assert login_lookup(app, b"member") == []


def test_login_lookup_of_an_unknown_login_is_empty(app, owner):
    """اسمٌ غير موجود يطابق حساباً ما فيُجرَّب عليه أيّ كلمة."""
    make_user(owner, login=b"member", password_hash=OLD_HASH)
    assert login_lookup(app, b"stranger") == []


# ── ew_open_session ─────────────────────────────────────────────────────


@pytest.mark.parametrize(("password_hash", "active"), [
    (None, True),
    (OLD_HASH, False),
], ids=["unactivated", "inactive"])
def test_session_needs_an_active_activated_user(app, owner, password_hash, active):
    """جلسةٌ لحسابٍ معطَّل أو لم يُفعَّل تتجاوز قرار التعطيل ودعوة التفعيل معاً."""
    user = make_user(owner, login=b"member", password_hash=password_hash, active=active)
    with rejected(errors.CheckViolation, "session_needs_active_user"):
        open_session(app, user, SESSION)
    assert session_count(owner) == 0


def test_session_for_an_unknown_user_is_refused(app, owner):
    """جلسةٌ لمعرّفٍ لا يملكه أحد تُفتح لمن يُنشأ به لاحقاً."""
    with rejected(errors.CheckViolation, "session_needs_active_user"):
        open_session(app, UNKNOWN_USER, SESSION)
    assert session_count(owner) == 0


def test_open_session_lasts_exactly_thirty_days(app, owner):
    """جلسةٌ أطول أو بلا نهاية تبقى صالحةً على جهازٍ ضائع."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    open_session(app, user, SESSION)
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT user_id, expires_at - created_at, revoked_at, created_at > now() - interval '1 minute'"
            " FROM sessions WHERE token_hash = %s",
            (SESSION,),
        )
        assert cursor.fetchone() == (user, SESSION_LIFETIME, None, True)
    assert resolve(app, SESSION) == user


# ── ew_resolve_session ──────────────────────────────────────────────────


def test_resolve_returns_the_user_of_a_valid_session(app, owner):
    """جلسةٌ صالحة تُرجع غير صاحبها فيرى حملات غيره."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    other = make_user(owner, login=b"other", password_hash=OLD_HASH)
    seed_session(owner, user, SESSION)
    seed_session(owner, other, digest("other-session"))
    assert resolve(app, SESSION) == user


@pytest.mark.parametrize("statement", [
    "UPDATE sessions SET revoked_at = now() WHERE token_hash = %s",
    "UPDATE sessions SET created_at = now() - interval '31 days', expires_at = now() - interval '1 day'"
    " WHERE token_hash = %s",
    "UPDATE sessions SET created_at = now() - interval '30 days', expires_at = now() WHERE token_hash = %s",
    "UPDATE users SET is_active = false WHERE id = (SELECT user_id FROM sessions WHERE token_hash = %s)",
], ids=["revoked", "expired", "expiring-now", "inactive-user"])
def test_resolve_returns_nothing_for_a_dead_session(app, owner, statement):
    """جلسةٌ أُلغيت أو انتهت أو عُطّل صاحبها وما زالت تفتح الحساب تُبطل كل وسيلة إيقاف."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    seed_session(owner, user, SESSION)
    assert resolve(app, SESSION) == user
    with owner.cursor() as cursor:
        cursor.execute(statement, (SESSION,))
        assert cursor.rowcount == 1
    assert resolve(app, SESSION) is None


def test_resolve_returns_nothing_for_an_unknown_token(app, owner):
    """رمزٌ مخمَّن يُطابق جلسةً ما فيدخل باسم صاحبها."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    seed_session(owner, user, SESSION)
    assert resolve(app, digest("guessed")) is None


# ── ew_revoke_session ───────────────────────────────────────────────────


def test_revoke_ends_that_session_and_only_that_session(app, owner):
    """خروجٌ لا يُبطل الجلسة يترك الجهاز المشترك مفتوحاً لمن يجلس بعده، وخروجٌ مكرّر يمحو متى أُغلقت فعلاً."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    phone = digest("session-phone")
    open_session(app, user, SESSION)
    open_session(app, user, phone)
    revoke(app, SESSION)
    assert resolve(app, SESSION) is None
    assert session_revoked(owner, SESSION)
    assert resolve(app, phone) == user
    revoked_at = scalar(owner, "SELECT revoked_at FROM sessions WHERE token_hash = %s", (SESSION,))
    revoke(app, SESSION)
    assert resolve(app, SESSION) is None
    assert scalar(owner, "SELECT revoked_at FROM sessions WHERE token_hash = %s", (SESSION,)) == revoked_at


# ── الجداول مغلقةٌ أمام دور الويب ───────────────────────────────────────


@pytest.mark.parametrize("statement", [
    "SELECT id FROM users",
    "SELECT password_hash FROM users",
    "SELECT token_hash FROM sessions",
    "SELECT token_hash FROM activation_tokens",
    "UPDATE users SET is_active = true",
    "UPDATE users SET password_hash = 'scrypt$forged'",
    "UPDATE sessions SET revoked_at = NULL",
    "UPDATE sessions SET expires_at = expires_at + interval '1 year'",
    "UPDATE activation_tokens SET used_at = NULL",
    "INSERT INTO users (login_hmac) SELECT sha256('forged'::bytea)",
    "INSERT INTO sessions (user_id, token_hash, expires_at)"
    " SELECT gen_random_uuid(), sha256('forged'::bytea), now() + interval '1 day'",
    "DELETE FROM sessions",
])
def test_app_cannot_touch_identity_tables(app, owner, statement):
    """دور الويب الذي يقرأ الجداول مباشرةً يكشف قائمة المستخدمين وتجزئاتهم، والذي يكتبها يتجاوز كل دالّة."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    seed_session(owner, user, SESSION)
    as_user(app, user)
    with rejected(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute(statement)
    assert credentials(owner, user)[0] == OLD_HASH
    assert resolve(app, SESSION) == user


# ── قيود العمر ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(("lifetime", "accepted"), [
    (SESSION_LIFETIME, True),
    (SESSION_LIFETIME + timedelta(seconds=1), False),
    (timedelta(days=365), False),
    (timedelta(0), False),
], ids=["30d", "30d+1s", "1y", "zero"])
def test_session_window_caps_lifetime_at_thirty_days(owner, lifetime, accepted):
    """جلسةٌ أطول من ثلاثين يوماً يكتبها خطأٌ في الخادم أو سكربتٌ صيانة تبقى بلا نهاية فعلية."""
    user = make_user(owner, login=b"member", password_hash=OLD_HASH)
    if accepted:
        seed_session(owner, user, SESSION, lifetime=lifetime)
        assert session_count(owner) == 1
    else:
        with rejected(errors.CheckViolation, "session_window"):
            seed_session(owner, user, SESSION, lifetime=lifetime)
        assert session_count(owner) == 0


@pytest.mark.parametrize(("lifetime", "accepted"), [
    (TOKEN_LIFETIME, True),
    (TOKEN_LIFETIME + timedelta(seconds=1), False),
    (timedelta(days=30), False),
    (timedelta(0), False),
], ids=["72h", "72h+1s", "30d", "zero"])
def test_activation_window_caps_lifetime_at_seventy_two_hours(owner, lifetime, accepted):
    """رابط تفعيلٍ يعيش أسابيع يبقى مفتاحاً للحساب في كل بريدٍ ونسخةٍ احتياطية مرّ بها."""
    user = make_user(owner, login=b"member", password_hash=None)
    if accepted:
        seed_token(owner, user, TOKEN, lifetime=lifetime)
        assert scalar(owner, "SELECT count(*) FROM activation_tokens WHERE user_id = %s", (user,)) == 1
    else:
        with rejected(errors.CheckViolation, "activation_window"):
            seed_token(owner, user, TOKEN, lifetime=lifetime)
        assert scalar(owner, "SELECT count(*) FROM activation_tokens WHERE user_id = %s", (user,)) == 0
