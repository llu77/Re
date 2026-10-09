"""
التسجيل برمز والمهن — في القاعدة
================================
ما تفرضه القاعدة وحدها، بدور الويب نفسه الذي يحمله الخادم:

  • لا حساب بهذا الطريق بلا رمز تسجيلٍ صالح؛ والرمز لحسابٍ واحد، وينتهي، ويُقفل
    بعد ثلاث إجابات «البريد مأخوذ». (التسجيل المفتوح بلا رمز في
    `test_open_registration.py`.)
  • حساب التسجيل مفعَّلٌ بمهنته واسمه وتاريخ ميلاده وموافقته وطريقة استخدامه،
    والبريد HMAC لا غير.
  • تاريخ الميلاد ليس في المستقبل بتاريخ الرياض، ولا قبل 1900.
  • سقفٌ يومي للحسابات الجديدة يجمع الجميع، يُعدّ من دفتر التسجيل (0008) فلا
    يُفرغه حذف الحساب.
  • الحملة لحساب التسويق وحده — عند الإنشاء وعند كل كتابةٍ تكلّف.
  • صاحب الحساب يحذفه بنفسه وكل ما يتبعه.
"""

from __future__ import annotations

import datetime
import hashlib

import pytest
from psycopg import errors

from eyework.professions import NAMES, Profession
from eyework.tests.conftest import UNUSABLE_HASH, as_user, create_campaign, make_user

# 0008: ثمانية معاملات، آخرها طريقة الاستخدام.
_REGISTER = "SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s, %s)"
TERMS = "2026-10-08"


def _hash(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def issue_code(owner, code: str = "code-1", *, hours: int = 72, label: str | None = None) -> bytes:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO signup_codes (code_hash, label, expires_at)"
            " VALUES (%s, %s, now() + make_interval(hours => %s))", (_hash(code), label, hours))
    return _hash(code)


def _riyadh_today(owner) -> datetime.date:
    with owner.cursor() as cursor:
        cursor.execute("SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date")
        return cursor.fetchone()[0]


def _register(app, code: bytes, login: str = "new@example.sa", *, name: str | None = "سارة",
              birth: datetime.date = datetime.date(1994, 3, 21), profession: str = "STOREKEEPER",
              terms: str | None = TERMS, ui_size: str | None = "GAZE"):
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute(_REGISTER, (code, _hash(login), UNUSABLE_HASH, name, birth, profession, terms, ui_size))
        return cursor.fetchone()


def test_registration_creates_an_active_account_and_uses_the_code(owner, app):
    code = issue_code(owner, label="riyadh-oct")
    user_id, outcome = _register(app, code)
    assert outcome == "OK"
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT login_hmac, password_hash, is_active, activated_at IS NOT NULL, display_name,"
            " birth_date, profession, self_registered, terms_version, terms_accepted_at IS NOT NULL"
            " FROM users WHERE id = %s", (user_id,))
        assert cursor.fetchone() == (_hash("new@example.sa"), UNUSABLE_HASH, True, True, "سارة",
                                     datetime.date(1994, 3, 21), "STOREKEEPER", True, TERMS, True)
        cursor.execute("SELECT used_at IS NOT NULL, user_id, taken_count FROM signup_codes")
        assert cursor.fetchone() == (True, user_id, 0)


@pytest.mark.parametrize("state", ["missing", "used", "expired", "locked"])
def test_no_account_without_a_usable_code(owner, app, state):
    code = issue_code(owner)
    with owner.cursor() as cursor:
        if state == "missing":
            code = _hash("never-issued")
        elif state == "used":
            cursor.execute("UPDATE signup_codes SET used_at = now()")
        elif state == "expired":
            cursor.execute("UPDATE signup_codes SET created_at = now() - interval '4 days',"
                           " expires_at = now() - interval '1 hour'")
        else:
            cursor.execute("UPDATE signup_codes SET taken_count = 3")
    assert _register(app, code) == (None, "CODE")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 0


def test_a_code_makes_one_account_only(owner, app):
    code = issue_code(owner)
    assert _register(app, code, "first@example.sa")[1] == "OK"
    assert _register(app, code, "second@example.sa") == (None, "CODE")


def test_a_taken_login_is_counted_on_the_code_and_locks_it_at_three(owner, app):
    first = issue_code(owner, "first")
    _register(app, first, "taken@example.sa")
    code = issue_code(owner, "probe")
    for expected in (1, 2, 3):
        assert _register(app, code, "taken@example.sa", name="ليلى", profession="SUPPORT") == (None, "TAKEN")
        with owner.cursor() as cursor:
            cursor.execute("SELECT taken_count FROM signup_codes WHERE code_hash = %s", (code,))
            assert cursor.fetchone()[0] == expected
    # مقفلٌ الآن، ولو ببريدٍ جديد.
    assert _register(app, code, "free@example.sa") == (None, "CODE")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*), min(display_name), min(profession) FROM users")
        assert cursor.fetchone() == (1, "سارة", "STOREKEEPER")


def test_registration_never_takes_over_a_pending_invitation(owner, app):
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO users (login_hmac, profession) VALUES (%s, 'MARKETING')",
                       (_hash("invited@example.sa"),))
    assert _register(app, issue_code(owner), "invited@example.sa") == (None, "TAKEN")
    with owner.cursor() as cursor:
        cursor.execute("SELECT password_hash, self_registered, profession FROM users")
        assert cursor.fetchone() == (None, False, "MARKETING")


def test_birth_date_today_in_riyadh_is_accepted_and_tomorrow_is_not(owner, app):
    today = _riyadh_today(owner)
    assert _register(app, issue_code(owner, "a"), "a@example.sa", birth=today)[1] == "OK"
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner, "b"), "b@example.sa", birth=today + datetime.timedelta(days=1))
    assert caught.value.diag.constraint_name == "registration_birth_date"


def test_a_birth_date_before_1900_is_refused(owner, app):
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner), birth=datetime.date(1899, 12, 31))
    assert caught.value.diag.constraint_name == "birth_date_range"


@pytest.mark.parametrize("name", [None, "سارة2", "  سارة", "ab@c", "س" * 31])
def test_registration_needs_a_proper_name(owner, app, name):
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner), name=name)
    assert caught.value.diag.constraint_name in ("registration_needs_name", "display_name_shape")


def test_registration_needs_consent(owner, app):
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner), terms=None)
    assert caught.value.diag.constraint_name == "registration_needs_consent"


def test_an_unknown_profession_is_refused(owner, app):
    with pytest.raises(errors.ForeignKeyViolation):
        _register(app, issue_code(owner), profession="ASTRONAUT")


def test_a_failed_registration_leaves_the_code_unused(owner, app):
    code = issue_code(owner)
    with pytest.raises(errors.CheckViolation):
        _register(app, code, name="سارة2")
    assert _register(app, code)[1] == "OK"


def _ledger_rows(owner, count: int, *, via: str = "CODE", outcome: str = "OK", age: str = "1 hour") -> None:
    """صفوفٌ في دفتر التسجيل (0008): منه يُعدّ السقف، لا من الرموز ولا من الحسابات."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO registration_ledger (occurred_at, via, outcome)"
            " SELECT now() - %s::interval, %s, %s FROM generate_series(1, %s)",
            (age, via, outcome, count))


def test_the_daily_cap_counts_the_ledger_of_the_last_day(owner, app):
    _ledger_rows(owner, 199)
    # الرموز غير المستعملة لا تُحسب، ولا صفوف الدفتر الأقدم من يوم.
    for n in range(50):
        issue_code(owner, f"unused-{n}")
    _ledger_rows(owner, 5, age="25 hours")
    assert _register(app, issue_code(owner, "a"), "the-200th@example.sa")[1] == "OK"
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner, "b"), "the-201st@example.sa")
    assert caught.value.diag.constraint_name == "registration_daily_cap"


def test_deleting_an_account_does_not_make_room_under_the_daily_cap(owner, app):
    """الحساب يُحذف بيد صاحبه، وصفّ الدفتر الذي كتبه تسجيله يبقى: لا تُفرغ الدورةُ السقفَ."""
    _ledger_rows(owner, 199)
    assert _register(app, issue_code(owner, "a"), "the-200th@example.sa")[1] == "OK"
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE self_registered")
    with pytest.raises(errors.CheckViolation) as caught:
        _register(app, issue_code(owner, "b"), "the-201st@example.sa")
    assert caught.value.diag.constraint_name == "registration_daily_cap"


def test_the_web_role_checks_a_code_without_reading_the_codes(owner, app):
    code = issue_code(owner)
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_signup_code_usable(%s), ew_signup_code_usable(%s)", (code, _hash("x")))
        assert cursor.fetchone() == (True, False)
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute("SELECT * FROM signup_codes")


def test_the_web_role_reads_only_its_own_profession(owner, app):
    keeper = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    make_user(owner, login=b"agent", profession="SUPPORT")
    as_user(app, keeper)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_my_profession()")
        assert cursor.fetchone()[0] == "STOREKEEPER"
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_my_profession()")
        assert cursor.fetchone()[0] is None


# ew_riyadh_today يستدعيه الويب منذ 0010 (تنبيه «تاريخٌ قديم» يقيس بيوم الرياض): لا يكشف إلا التاريخ.
@pytest.mark.parametrize("statement", ["SELECT * FROM professions", "SELECT birth_date FROM users"])
def test_the_web_role_cannot_read_professions_birth_dates_or_internal_helpers(owner, app, statement):
    as_user(app, make_user(owner, login=b"keeper", profession="STOREKEEPER"))
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute(statement)


@pytest.mark.parametrize("profession", ["STOREKEEPER", "SUPPORT"])
def test_only_a_marketing_account_can_create_a_campaign(owner, app, profession):
    other = make_user(owner, login=b"other", profession=profession)
    as_user(app, other)
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("INSERT INTO campaigns (user_id) VALUES (%s)", (other,))
    assert caught.value.diag.constraint_name == "campaign_needs_marketing"


def test_an_account_moved_out_of_marketing_cannot_spend_on_an_old_campaign(owner, app):
    marketer = make_user(owner, login=b"marketer", profession="MARKETING")
    campaign = create_campaign(app, marketer)
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET profession = 'SUPPORT' WHERE id = %s", (marketer,))
    as_user(app, marketer)
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (campaign,))
    assert caught.value.diag.constraint_name == "campaign_needs_marketing"


def test_the_owner_of_an_account_deletes_it_and_everything_it_holds(owner, app):
    marketer = make_user(owner, login=b"marketer", profession="MARKETING")
    other = make_user(owner, login=b"other", profession="MARKETING")
    create_campaign(app, marketer)
    create_campaign(app, other)
    as_user(app, marketer)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users WHERE id = %s", (marketer,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT count(*) FROM campaigns")
        assert cursor.fetchone()[0] == 1
    as_user(app, None)
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")


def test_deleting_an_account_keeps_the_code_used(owner, app):
    code = issue_code(owner)
    user_id, _ = _register(app, code)
    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")
    with owner.cursor() as cursor:
        cursor.execute("SELECT used_at IS NOT NULL, user_id FROM signup_codes")
        assert cursor.fetchone() == (True, None)
    assert _register(app, code) == (None, "CODE")


def test_existing_accounts_must_name_a_profession(owner):
    with pytest.raises(errors.NotNullViolation), owner.cursor() as cursor:
        cursor.execute("INSERT INTO users (login_hmac) VALUES (sha256('x'::bytea))")


def test_the_professions_table_matches_the_code(owner):
    with owner.cursor() as cursor:
        cursor.execute("SELECT code, name_ar FROM professions ORDER BY code")
        assert dict(cursor.fetchall()) == {p.value: NAMES[p] for p in Profession}
