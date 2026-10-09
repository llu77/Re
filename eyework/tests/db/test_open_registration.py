"""
التسجيل المفتوح وطريقة الاستخدام والموافقة — في القاعدة (0008)
=============================================================
ما تفرضه القاعدة وحدها، بدور الويب نفسه الذي يحمله الخادم:

  • الزائر يُنشئ حسابه بلا رمز: مفعَّلٌ بمهنته واسمه وتاريخ ميلاده وموافقته وطريقة
    استخدامه، معلَّمٌ `open_registered`. ولا يُستولى على بريدٍ قائم ولا على دعوةٍ لم
    تُفعَّل.
  • الدفتر: صفٌّ لكل تسجيلٍ نجح ولكل جواب «مأخوذ» بلا رمز — وقتٌ وطريقٌ ونتيجة لا
    غير. منه تُعدّ السقوف (مئتان في اليوم للطريقين، مئةٌ وخمسون للمفتوح، وستّون
    «مأخوذ» توقفه)، فلا يُفرغها حذف الحساب، ولا يراها دور الويب.
  • الحساب المفتوح الجديد (سبعة أيام بساعة القاعدة): عشر كتاباتٍ في اليوم، وأربعمئة
    للجدد كلّهم من ألفي التطبيق، وثلاث حملاتٍ مفتوحة.
  • طريقة الاستخدام لصاحب الجلسة وحده قراءةً وكتابة، وفارغةٌ حتى يختار.
  • الموافقة على نسخةٍ أحدث لصاحب الجلسة وحده، ولا رجوع إلى أقدم.
"""

from __future__ import annotations

import datetime
import re
import threading
from uuid import UUID

import psycopg
import pytest
from psycopg import errors

from eyework import campaigns
from eyework.tests.conftest import (
    BIRTH_DATE,
    TERMS_VERSION,
    UNUSABLE_HASH,
    as_user,
    create_campaign,
    hashed_login,
    make_user,
    register_open,
    row_version,
)
from eyework.tests.db.test_state_machine import blocked_on_a_lock
from eyework.ui_size import UiSize

_REGISTER_CODE = "SELECT new_user, outcome FROM ew_register(%s, %s, %s, %s, %s, %s, %s, %s)"
_LEDGER = "SELECT via, outcome, count(*)::int FROM registration_ledger GROUP BY 1, 2 ORDER BY 1, 2"


def _scalar(connection, statement: str, params: tuple = ()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


def _rows(connection, statement: str, params: tuple = ()) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall()


def constraint_of(attempt) -> str | None:
    """اسم القيد الذي رُفضت به المحاولة، أو None إن مرّت."""
    try:
        attempt()
    except (errors.CheckViolation, errors.InsufficientPrivilege) as exc:
        return exc.diag.constraint_name
    return None


def ledger(owner) -> list[tuple]:
    return _rows(owner, _LEDGER)


def seed_ledger(owner, count: int, via: str, outcome: str, *, age: str = "1 hour") -> None:
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO registration_ledger (occurred_at, via, outcome)"
            " SELECT now() - %s::interval, %s, %s FROM generate_series(1, %s)", (age, via, outcome, count))


def issue_code(owner, code: str) -> bytes:
    digest = hashed_login(code)
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO signup_codes (code_hash, expires_at) VALUES (%s, now() + interval '1 day')",
                       (digest,))
    return digest


def register_code(app, code: bytes, login: str, *, ui_size: str | None = "GAZE"):
    """تسجيلٌ برمز، بدور الويب وبلا هوية."""
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute(_REGISTER_CODE, (code, hashed_login(login), UNUSABLE_HASH, "ليلى", BIRTH_DATE, "SUPPORT",
                                        TERMS_VERSION, ui_size))
        return cursor.fetchone()


def seed_attempts(owner, user: UUID, campaign: UUID, count: int, *, outcome: str, new_account: bool) -> None:
    """محاولاتٌ منتهية خلال اليوم، أقدم من عشر دقائق فلا يطلقها حدّ الدقائق العشر."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at,"
            " outcome, new_account)"
            " SELECT %s, %s, 'INITIAL', sha256('seeded'::bytea), now() - interval '1 hour' - g * interval '1 second',"
            "        now() - interval '1 hour' - g * interval '1 second' + interval '1 second', %s, %s"
            "   FROM generate_series(1, %s) g",
            (campaign, user, outcome, new_account, count))


def begin(app, user: UUID, campaign: UUID) -> UUID:
    as_user(app, user)
    return _scalar(app, "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, row_version(app, campaign)))


def age_account(owner, user: UUID, *, days: int) -> None:
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET created_at = now() - make_interval(days => %s) WHERE id = %s", (days, user))


# ── الحساب المفتوح والدفتر ──────────────────────────────────────────────
def test_an_open_registration_creates_an_active_open_account_and_one_ledger_row(owner, app):
    user, outcome = register_open(app, "new@example.sa", ui_size="GAZE")
    assert outcome == "OK"
    assert _rows(owner,
                 "SELECT login_hmac, password_hash, is_active, activated_at IS NOT NULL, display_name, birth_date,"
                 " profession, self_registered, open_registered, terms_version, terms_accepted_at IS NOT NULL,"
                 " ui_size FROM users WHERE id = %s", (user,)) == [
        (hashed_login("new@example.sa"), UNUSABLE_HASH, True, True, "سارة", BIRTH_DATE, "MARKETING", True, True,
         TERMS_VERSION, True, "GAZE")]
    assert ledger(owner) == [("OPEN", "OK", 1)]


def test_an_open_registration_never_takes_over_an_account_or_a_pending_invitation(owner, app):
    """البريد المأخوذ جوابه «مأخوذ» وصفٌّ في الدفتر، ولا يُمسّ صاحبه: لا اسمه ولا مهنته ولا كلمة مروره."""
    user, _ = register_open(app, "taken@example.sa")
    invited = make_user(owner, login=b"invited", password_hash=None)
    taken = register_open(app, "taken@example.sa", name="ليلى", profession="SUPPORT", ui_size="GAZE")
    pending = register_open(app, b"invited".ljust(32, b"\0"), name="ليلى", profession="SUPPORT", ui_size="GAZE")
    assert (taken, pending) == ((None, "TAKEN"), (None, "TAKEN"))
    rows = {row[0]: row[1:] for row in _rows(
        owner, "SELECT id, display_name, profession, password_hash IS NULL, self_registered, open_registered, ui_size"
               " FROM users")}
    assert rows == {user: ("سارة", "MARKETING", False, True, True, "COMPACT"),
                    invited: (None, "MARKETING", True, False, False, None)}
    assert ledger(owner) == [("OPEN", "OK", 1), ("OPEN", "TAKEN", 2)]


@pytest.mark.parametrize(("field", "value", "constraint"), [
    ("name", None, "registration_needs_name"),
    ("name", "سارة2", "display_name_shape"),
    ("terms", None, "registration_needs_consent"),
    ("birth", datetime.date(1899, 12, 31), "birth_date_range"),
    ("birth", "tomorrow", "registration_birth_date"),
    ("ui_size", None, "registration_needs_ui_size"),
    ("ui_size", "LARGE", "ui_size_known"),
    ("profession", "ASTRONAUT", None),
], ids=["no-name", "bad-name-shape", "no-consent", "before-1900", "tomorrow-in-riyadh", "no-size", "unknown-size",
        "unknown-profession"])
def test_an_open_registration_checks_name_birth_consent_size_and_profession(owner, app, field, value, constraint):
    """كل فحوص التسجيل برمز، ومعها طريقة الاستخدام؛ المهنة المجهولة يرفضها المفتاح الأجنبي."""
    if value == "tomorrow":
        value = _scalar(owner, "SELECT (now() AT TIME ZONE 'Asia/Riyadh')::date + 1")
    if constraint is None:
        with pytest.raises(errors.ForeignKeyViolation):
            register_open(app, "a@example.sa", **{field: value})
    else:
        with pytest.raises(errors.CheckViolation) as caught:
            register_open(app, "a@example.sa", **{field: value})
        assert caught.value.diag.constraint_name == constraint
    assert _scalar(owner, "SELECT count(*) FROM users") == 0


def test_a_refused_open_registration_leaves_no_ledger_row(owner, app):
    """الدفتر يعدّ ما نجح وما أُجيب بـ«مأخوذ»؛ المحاولة المرفوضة قبل الإدراج لا أثر لها."""
    assert constraint_of(lambda: register_open(app, "a@example.sa", name="سارة2")) == "display_name_shape"
    assert constraint_of(lambda: register_open(app, "a@example.sa", ui_size=None)) == "registration_needs_ui_size"
    with pytest.raises(errors.ForeignKeyViolation):
        register_open(app, "a@example.sa", profession="ASTRONAUT")
    assert ledger(owner) == []


def test_the_open_daily_cap_counts_open_accounts_of_the_last_day(owner, app):
    """مئةٌ وخمسون حساباً مفتوحاً في اليوم؛ «مأخوذ» والأقدم من يوم لا يُعدّان، والرابط يعمل بعدها."""
    seed_ledger(owner, 149, "OPEN", "OK")
    seed_ledger(owner, 40, "OPEN", "TAKEN")
    seed_ledger(owner, 30, "OPEN", "OK", age="25 hours")
    assert register_open(app, "the-150th@example.sa")[1] == "OK"
    assert constraint_of(lambda: register_open(app, "the-151st@example.sa")) == "registration_open_daily_cap"
    assert register_code(app, issue_code(owner, "c1"), "coded@example.sa")[1] == "OK"


def test_the_total_daily_cap_counts_both_ways(owner, app):
    """مئتان في اليوم بالطريقين معاً؛ بعدها يُرفض كلاهما بالقيد نفسه."""
    seed_ledger(owner, 100, "OPEN", "OK")
    seed_ledger(owner, 99, "CODE", "OK")
    assert register_code(app, issue_code(owner, "c2"), "the-200th@example.sa")[1] == "OK"
    assert constraint_of(lambda: register_code(app, issue_code(owner, "c3"), "the-201st@example.sa")) \
        == "registration_daily_cap"
    assert constraint_of(lambda: register_open(app, "open-201st@example.sa")) == "registration_daily_cap"


@pytest.mark.parametrize(("via", "seeded", "constraint"), [
    ("OPEN", 149, "registration_open_daily_cap"),
    ("CODE", 199, "registration_daily_cap"),
])
def test_deleting_accounts_makes_no_room_under_either_cap(owner, app, via, seeded, constraint):
    """الحساب يُحذف بيد صاحبه أو بيد المالك، وصفّ الدفتر الذي كتبه تسجيله يبقى."""
    seed_ledger(owner, seeded, via, "OK")
    user, outcome = register_open(app, "last@example.sa")
    assert outcome == "OK"
    as_user(app, user)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_delete_me()")
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE open_registered")
    assert _scalar(owner, "SELECT count(*) FROM users") == 0
    assert constraint_of(lambda: register_open(app, "next@example.sa")) == constraint


def test_sixty_taken_answers_pause_open_registration_but_not_links(owner, app):
    """ستّون جواباً «مأخوذ» في يومٍ توقف التسجيل المفتوح للجميع: لا يصير أداة سؤالٍ عن الناس."""
    seed_ledger(owner, 59, "OPEN", "TAKEN")
    seed_ledger(owner, 10, "OPEN", "TAKEN", age="25 hours")
    assert register_open(app, "someone@example.sa")[1] == "OK"
    assert register_open(app, "someone@example.sa")[1] == "TAKEN"
    assert constraint_of(lambda: register_open(app, "free@example.sa")) == "registration_open_paused"
    as_user(app, None)
    assert _scalar(app, "SELECT ew_open_registration_blocker()") == "registration_open_paused"
    assert register_code(app, issue_code(owner, "c4"), "coded@example.sa")[1] == "OK"


def test_the_availability_check_names_the_blocker_or_nothing(owner, app):
    """تسألها الواجهة قبل الخطوة الأولى، بلا جلسة: حالُ التطبيق كلّه، لا شيء عن أحد."""
    as_user(app, None)
    assert _scalar(app, "SELECT ew_open_registration_blocker()") is None
    seed_ledger(owner, 200, "CODE", "OK")
    assert _scalar(app, "SELECT ew_open_registration_blocker()") == "registration_daily_cap"


def test_a_taken_answer_through_a_link_counts_on_the_link_only(owner, app):
    """«مأخوذ» برمزٍ يُعدّ على الرمز نفسه (0005) ولا يكتب في الدفتر: الرمز يُقفل بثلاث، لا التطبيق بستّين."""
    register_code(app, issue_code(owner, "c5"), "x@example.sa")
    probe = issue_code(owner, "c6")
    assert register_code(app, probe, "x@example.sa") == (None, "TAKEN")
    assert _scalar(owner, "SELECT taken_count FROM signup_codes WHERE code_hash = %s", (probe,)) == 1
    assert ledger(owner) == [("CODE", "OK", 1)]


def test_a_code_registration_writes_one_ledger_row_and_stores_the_size(owner, app):
    user, outcome = register_code(app, issue_code(owner, "c8"), "gaze@example.sa", ui_size="GAZE")
    assert outcome == "OK"
    assert _scalar(owner, "SELECT ui_size FROM users WHERE id = %s", (user,)) == "GAZE"
    assert ledger(owner) == [("CODE", "OK", 1)]
    assert constraint_of(lambda: register_code(app, issue_code(owner, "c9"), "nosize@example.sa", ui_size=None)) \
        == "registration_needs_ui_size"
    assert ledger(owner) == [("CODE", "OK", 1)]


def test_the_old_seven_argument_register_is_gone(app):
    """لا يبقى طريقٌ يُنشئ حساباً بلا طريقة استخدام."""
    as_user(app, None)
    with pytest.raises(errors.UndefinedFunction), app.cursor() as cursor:
        cursor.execute("SELECT * FROM ew_register(%s, %s, %s, %s, %s, %s, %s)",
                       (hashed_login("c10"), hashed_login("old@example.sa"), UNUSABLE_HASH, "ليلى", BIRTH_DATE,
                        "SUPPORT", TERMS_VERSION))


@pytest.mark.parametrize("statement", [
    "SELECT * FROM registration_ledger",
    "INSERT INTO registration_ledger (via, outcome) VALUES ('OPEN', 'OK')",
    "DELETE FROM registration_ledger",
    "TRUNCATE registration_ledger",
    "SELECT ew_registration_blocker('OPEN')",
    "SELECT ew_new_open_account(gen_random_uuid())",
    "SELECT open_registered FROM users",
    "SELECT ui_size FROM users",
    "UPDATE users SET ui_size = 'GAZE'",
])
def test_the_web_role_cannot_touch_the_ledger_or_the_internal_helpers_or_ui_size(owner, app, statement):
    """الدفتر والعدّ للمالك، وطريقة الاستخدام تُقرأ وتُكتب لصاحب الجلسة عبر دالّتيها وحدهما."""
    as_user(app, make_user(owner, login=b"signed-in"))
    with pytest.raises(errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement)
    assert "permission denied" in (caught.value.diag.message_primary or "")


def test_the_ledger_holds_no_identity(owner):
    """وقتٌ وطريقٌ ونتيجة لا غير؛ و«مأخوذ» برمزٍ لا صفّ له هنا."""
    assert [row[0] for row in _rows(owner, "SELECT column_name FROM information_schema.columns"
                                           " WHERE table_name = 'registration_ledger' ORDER BY column_name")] \
        == ["occurred_at", "outcome", "via"]
    with pytest.raises(errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("INSERT INTO registration_ledger (via, outcome) VALUES ('CODE', 'TAKEN')")
    assert caught.value.diag.constraint_name == "registration_ledger_taken_is_open"


def test_two_open_registrations_cannot_both_take_the_last_place(owner, app, app_url):
    """تسجيلان متزامنان يريان العدّ نفسه فيمرّان معاً لولا القفل الواحد؛ الثاني ينتظر الأول ثم يُرفض."""
    seed_ledger(owner, 149, "OPEN", "OK")
    outcome = {}
    with psycopg.connect(app_url) as first, psycopg.connect(app_url) as second:
        # بلا autocommit: الأول معاملةٌ مفتوحة تحمل القفل حتى تُثبَّت.
        assert register_open(first, "racer-1@example.sa")[1] == "OK"

        def register_second() -> None:
            try:
                register_open(second, "racer-2@example.sa")
                second.commit()
                outcome["registered"] = True
            except errors.CheckViolation as exc:
                second.rollback()
                outcome["constraint"] = exc.diag.constraint_name

        racer = threading.Thread(target=register_second)
        racer.start()
        waited = blocked_on_a_lock(app, second.info.backend_pid, racer)
        first.commit()
        racer.join(timeout=10)
    assert waited
    assert outcome == {"constraint": "registration_open_daily_cap"}
    assert ledger(owner) == [("OPEN", "OK", 150)]


# ── حدود الحساب المفتوح الجديد ──────────────────────────────────────────
def test_the_generation_limit_is_ten_for_a_new_open_account_and_forty_otherwise(owner, app):
    """حدّ صاحب الجلسة وحده، كما يفرضه ew_begin_generation، ونظيراه في campaigns.py."""
    fresh, _ = register_open(app, "fresh@example.sa")
    coded, _ = register_code(app, issue_code(owner, "c7"), "coded@example.sa")
    established = make_user(owner, login=b"established")
    limits = []
    for user in (fresh, coded, established, None):
        as_user(app, user)
        limits.append(_scalar(app, "SELECT ew_my_generation_limit()"))
    assert limits == [10, 40, 40, None]
    assert (campaigns.NEW_ACCOUNT_DAILY_GENERATIONS, campaigns.DAILY_GENERATIONS) == (10, 40)


@pytest.mark.parametrize(("minutes", "limit"), [(1, 10), (-1, 40)], ids=["a-minute-short-of-a-week", "a-minute-past"])
def test_the_new_account_week_is_measured_by_the_database(owner, app, minutes, limit):
    """سبعة أيام من إنشاء الحساب بساعة القاعدة لا بساعة الخادم."""
    user, _ = register_open(app, "fresh@example.sa")
    with owner.cursor() as cursor:
        cursor.execute("UPDATE users SET created_at = now() - interval '7 days' + make_interval(mins => %s)"
                       " WHERE id = %s", (minutes, user))
    as_user(app, user)
    assert _scalar(app, "SELECT ew_my_generation_limit()") == limit


def test_a_new_open_account_writes_ten_times_a_day_then_forty_after_its_first_week(owner, app):
    user, _ = register_open(app, "fresh@example.sa")
    campaign = create_campaign(app, user)
    seed_attempts(owner, user, campaign, 10, outcome="UPSTREAM_TIMEOUT", new_account=True)
    assert constraint_of(lambda: begin(app, user, campaign)) == "generation_new_account_cap"

    age_account(owner, user, days=8)
    attempt = begin(app, user, campaign)
    assert _scalar(owner, "SELECT new_account FROM generation_attempts WHERE id = %s", (attempt,)) is False
    assert _scalar(app, "SELECT ew_my_generation_limit()") == 40
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_finish_generation(%s, 'UPSTREAM_TIMEOUT', 0, 0)", (attempt,))
    # الأربعون بعد الأسبوع: عشرٌ مزروعة وواحدة حقيقية وتسعٌ وعشرون بعدها.
    seed_attempts(owner, user, campaign, 29, outcome="UPSTREAM_TIMEOUT", new_account=False)
    assert constraint_of(lambda: begin(app, user, campaign)) == "generation_daily_cap"


def test_unbilled_failures_do_not_count_toward_the_new_account_limits(owner, app):
    """انقطاع الخدمة لا يستهلك حصّة الحساب الجديد ولا حصّة الجدد كلّهم."""
    user, _ = register_open(app, "fresh@example.sa")
    other, _ = register_open(app, "other@example.sa")
    campaign = create_campaign(app, user)
    seed_attempts(owner, user, campaign, 10, outcome="UPSTREAM_BUSY", new_account=True)
    seed_attempts(owner, other, create_campaign(app, other, with_image=False), 400, outcome="UPSTREAM_UNREACHABLE",
                  new_account=True)
    assert begin(app, user, campaign) is not None


def test_new_open_accounts_share_four_hundred_a_day_counting_deleted_ones(owner, app):
    """حصّة الجدد من السقف العام، وأثر المحذوف منهم يُعدّ فيها؛ والحسابات القائمة لا تمسّها."""
    user, _ = register_open(app, "fresh@example.sa")
    gone, _ = register_open(app, "gone@example.sa")
    established = make_user(owner, login=b"established")
    seed_attempts(owner, gone, create_campaign(app, gone, with_image=False), 400, outcome="OUTPUT_INVALID",
                  new_account=True)
    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (gone,))
    assert _scalar(owner, "SELECT count(*) FROM attempt_tombstones WHERE new_account") == 400
    campaign = create_campaign(app, user)
    assert constraint_of(lambda: begin(app, user, campaign)) == "generation_new_accounts_cap"
    assert begin(app, established, create_campaign(app, established)) is not None


def test_a_new_open_account_opens_three_campaigns_and_others_twenty(owner, app):
    fresh, _ = register_open(app, "fresh@example.sa")
    for _ in range(3):
        create_campaign(app, fresh, with_image=False)
    assert constraint_of(lambda: create_campaign(app, fresh, with_image=False)) == "new_account_campaign_cap"
    established = make_user(owner, login=b"established")
    for _ in range(20):
        create_campaign(app, established, with_image=False)
    assert constraint_of(lambda: create_campaign(app, established, with_image=False)) == "open_campaign_cap"
    # وبعد أسبوعه يفتح الرابعة.
    age_account(owner, fresh, days=8)
    create_campaign(app, fresh, with_image=False)
    assert _scalar(owner, "SELECT count(*) FROM campaigns WHERE user_id = %s", (fresh,)) == 4


def test_open_registered_implies_self_registered(owner):
    """الحساب المفتوح لا يدّعي أنه دعوة: القيد يربط العلامتين."""
    with pytest.raises(errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("INSERT INTO users (login_hmac, profession, open_registered) VALUES (%s, 'MARKETING', true)",
                       (hashed_login("bad"),))
    assert caught.value.diag.constraint_name == "open_registered_is_self_registered"


# ── طريقة الاستخدام ─────────────────────────────────────────────────────
def test_existing_and_invited_accounts_have_no_size_until_chosen(owner, app):
    """لا افتراض: من لم يختر بعد تُسأل الواجهة؛ وew_my_ui_size لصاحب الجلسة وحده."""
    existing = make_user(owner, login=b"existing")
    invited = make_user(owner, login=b"invited", password_hash=None)
    fresh, _ = register_open(app, "fresh@example.sa", ui_size="GAZE")
    sizes = []
    for user in (existing, fresh, None):
        as_user(app, user)
        sizes.append(_scalar(app, "SELECT ew_my_ui_size()"))
    assert sizes == [None, "GAZE", None]
    assert _scalar(owner, "SELECT ui_size FROM users WHERE id = %s", (invited,)) is None


def test_a_user_sets_their_own_size_and_nobody_else_s(owner, app):
    existing = make_user(owner, login=b"existing")
    invited = make_user(owner, login=b"invited", password_hash=None)
    fresh, _ = register_open(app, "fresh@example.sa", ui_size="GAZE")
    inactive = make_user(owner, login=b"inactive", active=False)
    as_user(app, existing)
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_set_my_ui_size('COMPACT')")
    assert dict(_rows(owner, "SELECT id, ui_size FROM users")) == {
        existing: "COMPACT", invited: None, fresh: "GAZE", inactive: None}
    assert constraint_of(lambda: _scalar(app, "SELECT ew_set_my_ui_size(NULL)")) == "ui_size_known"
    assert constraint_of(lambda: _scalar(app, "SELECT ew_set_my_ui_size('HUGE')")) == "ui_size_known"
    for user in (None, inactive):
        as_user(app, user)
        with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
            cursor.execute("SELECT ew_set_my_ui_size('GAZE')")
    assert _scalar(owner, "SELECT count(*) FROM users WHERE ui_size IS NOT NULL") == 2


def test_ui_size_values_match_the_python_enum(owner):
    definition = _scalar(owner, "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ui_size_known'")
    assert set(re.findall(r"'([A-Z]+)'::text", definition)) == {size.value for size in UiSize}


# ── الموافقة على نسخةٍ أحدث ─────────────────────────────────────────────
def test_accepting_a_newer_notice_changes_the_session_users_row_only(owner, app):
    """الموافقة تضع النسخة ووقتها لصاحب الجلسة وحده، وتكرارها لا يضرّ، ولا رجوع، ولا بلا نسخةٍ أو جلسة."""
    newcomer, _ = register_open(app, "newcomer@example.sa")
    invited = make_user(owner, login=b"invited")
    bystander = make_user(owner, login=b"bystander")
    as_user(app, newcomer)
    assert _scalar(app, "SELECT ew_my_terms_version()") == TERMS_VERSION
    as_user(app, invited)
    assert _scalar(app, "SELECT ew_my_terms_version()") is None
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_accept_terms('2026-10-20')")
        cursor.execute("SELECT ew_accept_terms('2026-10-20')")
    assert _scalar(app, "SELECT ew_my_terms_version()") == "2026-10-20"
    assert constraint_of(lambda: _scalar(app, "SELECT ew_accept_terms('2026-10-01')")) == "terms_version_backwards"
    assert constraint_of(lambda: _scalar(app, "SELECT ew_accept_terms(NULL)")) == "registration_needs_consent"
    rows = {row[0]: row[1:] for row in _rows(owner, "SELECT id, terms_version, terms_accepted_at IS NOT NULL FROM users")}
    assert rows == {newcomer: (TERMS_VERSION, True), invited: ("2026-10-20", True), bystander: (None, False)}
    as_user(app, None)
    with pytest.raises(errors.InsufficientPrivilege), app.cursor() as cursor:
        cursor.execute("SELECT ew_accept_terms('2026-10-20')")
