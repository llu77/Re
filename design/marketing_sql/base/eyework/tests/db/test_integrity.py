"""
ضماناتٌ أُضيفت بعد المراجعة
===========================
كلٌّ منها جاء من خللٍ وُجد في التصميم قبل البناء، فيُختبر هنا بالطريقة التي
كان سيظهر بها:

  • المجال المغلق للميزانية في القاعدة هو مجال بايثون نفسه، عدداً عدداً.
  • صورةٌ فيها أيّ مقطع تطبيقٍ غير JFIF أو تعليقٌ لا تُخزَّن.
  • استبدال الصورة وبدء التوليد لا يتداخلان: ينتظر أحدهما الآخر.
  • لا يُكتب نصٌّ عن صورةٍ تغيّرت منذ أُرسلت.
  • المحاولة تُغلق مرةً واحدة.
  • النسخة المعروضة لا تُوجَّه إلا إلى الأحدث أو إلى أساس الحالية.
  • حدّ اليوم يحسب ما ربما فُوتر وحده.
  • رمز تفعيلٍ مفتوحٌ واحد لكل حساب.
  • FORCE RLS على كل جدولٍ فيه بيانات.
"""

from __future__ import annotations

import hashlib
import threading

import psycopg
import pytest

from eyework.money import BUDGET_VALUES
from eyework.tests.conftest import (
    DESCRIPTION,
    TITLE,
    add_version,
    as_user,
    create_campaign,
    make_user,
    row_version,
    sample_jpeg,
)


def _scalar(connection, statement, params=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


# ── المجالات ────────────────────────────────────────────────────────────
def test_budget_domain_in_the_database_equals_python(owner):
    with owner.cursor() as cursor:
        cursor.execute("SELECT v FROM generate_series(0, 6000) AS v WHERE ew_budget_allowed(v) ORDER BY v")
        allowed = tuple(row[0] for row in cursor.fetchall())
    assert allowed == BUDGET_VALUES


# ── الصورة ──────────────────────────────────────────────────────────────
def _insert_image(connection, campaign, user, jpeg):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, 400, 400, %s)",
            (campaign, user, jpeg, hashlib.sha256(jpeg).digest()),
        )


@pytest.mark.parametrize("marker", [*range(0xE1, 0xF0), 0xFE], ids=lambda m: f"FF{m:02X}")
def test_any_metadata_segment_is_refused_even_for_the_owner(owner, two_users, app, marker):
    """APP1–APP15 (EXIF وICC وXMP وغيرها) وCOM: حاجزٌ خلف التنظيف في التطبيق."""
    user = two_users[0]
    campaign = create_campaign(app, user, with_image=False)
    clean = sample_jpeg()
    tainted = clean[:2] + bytes([0xFF, marker, 0x00, 0x04, 0x00, 0x00]) + clean[2:]
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        _insert_image(owner, campaign, user, tainted)
    assert caught.value.diag.constraint_name in ("image_has_no_metadata", "image_has_no_exif")


def test_the_clean_output_of_the_pipeline_is_accepted(app, two_users):
    user = two_users[0]
    campaign = create_campaign(app, user, with_image=False)
    _insert_image(app, campaign, user, sample_jpeg())


def test_replacing_the_image_waits_for_a_generation_that_is_starting(owner_url, app_url, two_users, app):
    """
    التوليد يبدأ في معاملةٍ تحجز صفّ الحملة؛ واستبدال الصورة يحجز الصفّ نفسه
    أولاً، فينتظر — ثم يرى المحاولة ويُرفض. بلا القفل كان الاستبدال يمرّ بين
    قراءة النموذج للصورة وكتابة نصّه.
    """
    user = two_users[0]
    campaign = create_campaign(app, user)
    version = row_version(app, campaign)

    with psycopg.connect(app_url) as starter, psycopg.connect(app_url) as replacer:
        as_user(starter, user)
        as_user(replacer, user)
        with starter.cursor() as cursor:
            cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, version))
        # المعاملة الأولى مفتوحة: الاستبدال ينتظر قفلها.
        with replacer.cursor() as cursor:
            cursor.execute("SET lock_timeout = '500ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                cursor.execute(
                    "UPDATE campaign_images SET jpeg = jpeg WHERE campaign_id = %s", (campaign,))
        replacer.rollback()
        starter.commit()
        # التراجع أعاد ضبط الهوية أيضاً (ضُبطت داخل المعاملة نفسها): تُضبط ثانيةً،
        # وإلا لم يرَ العزلُ صفّاً ولم يعمل المحفّز أصلاً.
        as_user(replacer, user)
        with replacer.cursor() as cursor, pytest.raises(psycopg.errors.CheckViolation) as caught:
            cursor.execute("UPDATE campaign_images SET jpeg = jpeg WHERE campaign_id = %s", (campaign,))
        assert caught.value.diag.constraint_name == "image_locked_during_generation"


def test_copy_is_never_recorded_for_an_image_that_changed(owner, app, two_users):
    """
    دفاعٌ ثانٍ: لو تغيّرت الصورة رغم القفل (بيد المالك وقد عطّل المحفّز)،
    لا تُقبل نسخةٌ كُتبت عن الصورة السابقة.
    """
    user = two_users[0]
    campaign = create_campaign(app, user)
    as_user(app, user)
    attempt = _scalar(app, "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)",
                      (campaign, row_version(app, campaign)))
    other = sample_jpeg()[:-2] + b"\x00\x00\xff\xd9"
    with owner.cursor() as cursor:
        cursor.execute("ALTER TABLE campaign_images DISABLE TRIGGER trg_image_guard")
        try:
            cursor.execute("UPDATE campaign_images SET jpeg = %s, sha256 = %s WHERE campaign_id = %s",
                           (other, hashlib.sha256(other).digest(), campaign))
        finally:
            cursor.execute("ALTER TABLE campaign_images ENABLE TRIGGER trg_image_guard")
    with pytest.raises(psycopg.errors.CheckViolation) as caught, app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
            " served_model, prompt_version) VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test')",
            (campaign, user, attempt, TITLE, DESCRIPTION),
        )
    assert caught.value.diag.constraint_name == "version_image_changed"


def test_a_version_records_the_image_it_describes(app, two_users):
    user = two_users[0]
    campaign = create_campaign(app, user)
    version = add_version(app, user, campaign)
    stored = _scalar(app, "SELECT sha256 FROM campaign_images WHERE campaign_id = %s", (campaign,))
    described = _scalar(app, "SELECT image_sha256 FROM copy_versions WHERE id = %s", (version,))
    assert bytes(described) == bytes(stored)


# ── المحاولات ───────────────────────────────────────────────────────────
def test_an_attempt_settles_once(owner, app, two_users):
    user = two_users[0]
    campaign = create_campaign(app, user)
    as_user(app, user)
    attempt = _scalar(app, "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)",
                      (campaign, row_version(app, campaign)))
    with app.cursor() as cursor:
        cursor.execute("SELECT ew_finish_generation(%s, 'REFUSED', 0, 0)", (attempt,))
        with pytest.raises(psycopg.errors.NoDataFound):
            cursor.execute("SELECT ew_finish_generation(%s, 'UPSTREAM_BUSY', 0, 0)", (attempt,))
    with pytest.raises(psycopg.errors.CheckViolation) as caught, owner.cursor() as cursor:
        cursor.execute("UPDATE generation_attempts SET outcome = 'UPSTREAM_BUSY' WHERE id = %s", (attempt,))
    assert caught.value.diag.constraint_name == "attempt_settled"


def _seed_attempts(owner, user, campaign, outcome, count):
    """محاولاتٌ منتهية خلال اليوم، أقدم من عشر دقائق: لا يطلقها حدّ الدقائق العشر."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO generation_attempts (campaign_id, user_id, kind, image_sha256, started_at, finished_at, outcome)"
            " SELECT %s, %s, 'INITIAL', sha256('x'::bytea), now() - interval '1 hour' - i * interval '1 minute',"
            "        now() - interval '1 hour' - i * interval '1 minute', %s"
            "   FROM generate_series(1, %s) AS i",
            (campaign, user, outcome, count),
        )


@pytest.mark.parametrize("outcome", ["UPSTREAM_BUSY", "UPSTREAM_UNREACHABLE", "UPSTREAM_ERROR"])
def test_attempts_that_were_not_billed_do_not_use_up_the_day(owner, app, two_users, outcome):
    """انقطاع الخدمة لا يستهلك حصّة صاحبها."""
    user = two_users[0]
    campaign = create_campaign(app, user)
    _seed_attempts(owner, user, campaign, outcome, 45)
    as_user(app, user)
    _scalar(app, "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, row_version(app, campaign)))


@pytest.mark.parametrize("outcome", ["REFUSED", "OUTPUT_INVALID", "UNUSABLE_PHOTO", "UPSTREAM_TIMEOUT", "DISCARDED"])
def test_attempts_that_may_have_been_billed_count_toward_the_day(owner, app, two_users, outcome):
    user = two_users[0]
    campaign = create_campaign(app, user)
    _seed_attempts(owner, user, campaign, outcome, 40)
    as_user(app, user)
    with pytest.raises(psycopg.errors.CheckViolation) as caught, app.cursor() as cursor:
        cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)", (campaign, row_version(app, campaign)))
    assert caught.value.diag.constraint_name == "generation_daily_cap"


# ── الاستعادة ───────────────────────────────────────────────────────────
def test_the_displayed_version_moves_only_to_the_newest_or_to_its_base(app, two_users):
    """
    ثلاث نسخ: الثانية على الأولى، والثالثة على الثانية. من الثالثة تُعرض
    الثانية (أساسها)؛ ومن الثانية الثالثة (الأحدث) أو الأولى (أساسها)؛ ولا
    يُقفز من الثالثة إلى الأولى.
    """
    user = two_users[0]
    campaign = create_campaign(app, user)
    first = add_version(app, user, campaign)
    second = add_version(app, user, campaign, presets=("SHORTER",))
    third = add_version(app, user, campaign, presets=("SIMPLER",))
    as_user(app, user)

    def point(target):
        with app.cursor() as cursor:
            cursor.execute("UPDATE campaigns SET current_version_id = %s WHERE id = %s", (target, campaign))

    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        point(first)
    assert caught.value.diag.constraint_name == "current_version_target"
    point(second)
    point(third)
    point(second)
    point(first)


# ── الهوية ──────────────────────────────────────────────────────────────
def test_one_open_activation_link_per_account(owner):
    user = make_user(owner, login=b"invited", password_hash=None)
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (sha256('a'::bytea), %s, now() + interval '1 hour')", (user,))
        with pytest.raises(psycopg.errors.UniqueViolation):
            cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                           " VALUES (sha256('b'::bytea), %s, now() + interval '1 hour')", (user,))


def test_activation_is_bound_to_the_login_name(owner, app):
    login = b"bound-login".ljust(32, b"\0")
    user = make_user(owner, login=b"bound-login", password_hash=None)
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO activation_tokens (token_hash, user_id, expires_at)"
                       " VALUES (sha256('t'::bytea), %s, now() + interval '1 hour')", (user,))
    hash_ = "scrypt$" + "1" * 32 + "$" + "1" * 128
    wrong = b"other-login".ljust(32, b"\0")
    assert _scalar(app, "SELECT ew_activate(sha256('t'::bytea), %s, %s)", (wrong, hash_)) is None
    assert _scalar(app, "SELECT ew_activate(sha256('t'::bytea), %s, %s)", (login, hash_)) == user


# ── العزل ───────────────────────────────────────────────────────────────
def test_every_data_table_forces_row_security(owner):
    """كل جدولٍ في المخطّط تحت FORCE RLS، إلا بيانات المرجع وسجلّ الترحيلات."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
            " AND NOT (relrowsecurity AND relforcerowsecurity) ORDER BY relname")
        unforced = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT has_table_privilege('eyework_app', 'public.schema_migrations', 'SELECT')")
        reads_migrations = cursor.fetchone()[0]
    assert unforced == ["campaign_transition", "schema_migrations"]
    assert reads_migrations is False


def test_the_app_role_cannot_create_temporary_objects(owner):
    """pg_temp لا يُستعمل لزرع دالّةٍ تسبق دوالّنا: لا صلاحية TEMP."""
    assert _scalar(owner, "SELECT has_database_privilege('eyework_app', current_database(), 'TEMP')") is False


def test_two_generations_cannot_start_at_once(app_url, two_users, app):
    """طلبان متزامنان بالنظر: يمرّ أحدهما، والآخر generation_in_progress."""
    user = two_users[0]
    first, second = create_campaign(app, user), create_campaign(app, user)
    results = []
    barrier = threading.Barrier(2)

    def start(campaign):
        with psycopg.connect(app_url, autocommit=True) as connection:
            as_user(connection, user)
            barrier.wait()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (campaign,))
                results.append("started")
            except psycopg.errors.CheckViolation as exc:
                results.append(exc.diag.constraint_name)

    threads = [threading.Thread(target=start, args=(c,)) for c in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["generation_in_progress", "started"]
