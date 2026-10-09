"""
عزل الصفوف
==========
كل صفٍّ في جداول البيانات لصاحبه وحده، ولو نسي الخادم شرط WHERE: السياسة
تقارن `user_id` بهوية المعاملة (`eyework.user_id`)، والقاعدة تفرضها على كل
استعلامٍ وكل دالّة. بلا هويةٍ لا صفّ، وجداول الهوية مغلقةٌ أمام دور الويب
كلّياً. والهوية تُضبط داخل المعاملة فتموت معها: اتصالٌ يعود إلى التجمّع لا
يحمل هويّة الطلب الذي سبقه.
"""

from __future__ import annotations

import functools
import hashlib
import io

import psycopg
import pytest
from PIL import Image

from eyework.images import process
from eyework.tests.conftest import (
    DESCRIPTION,
    TITLE,
    add_version,
    as_user,
    create_campaign,
    row_version,
)

RLS_TABLES = (
    "public.users", "public.sessions", "public.activation_tokens", "public.campaigns",
    "public.generation_attempts", "public.copy_versions", "public.campaign_images",
    "public.passkeys", "public.passkey_challenges",
    # 0008: دفتر التسجيل للمالك وحده، ومفروضٌ عليه أيضاً.
    "public.registration_ledger",
    # 0009: أدوات النموذج وسقوفها، ودفتر استدعاءاته، وتنبيهات المراجِع وقراراتها.
    "public.ai_features", "public.ai_requests", "public.ai_flags", "public.ai_flag_decisions",
    # 0010: المخزون كلّه، وعدّاداته للمالك وحده.
    "public.inv_settings", "public.inv_counters", "public.inv_suppliers", "public.inv_supplier_reps", "public.inv_categories",
    "public.inv_items", "public.inv_purchases", "public.inv_purchase_lines", "public.inv_returns", "public.inv_return_lines",
    "public.inv_count_sessions", "public.inv_vouchers", "public.inv_count_lines", "public.inv_movements", "public.inv_ledger",
    "public.inv_review_flags",
)
OWNERS_PER_TABLE = [
    "SELECT DISTINCT user_id FROM campaigns",
    "SELECT DISTINCT user_id FROM generation_attempts",
    "SELECT DISTINCT user_id FROM copy_versions",
    "SELECT DISTINCT user_id FROM campaign_images",
]
COUNT_PER_TABLE = [
    "SELECT count(*) FROM campaigns",
    "SELECT count(*) FROM generation_attempts",
    "SELECT count(*) FROM copy_versions",
    "SELECT count(*) FROM campaign_images",
]


def _assert_rls_rejected(caught: pytest.ExceptionInfo, table: str) -> None:
    message = caught.value.diag.message_primary or ""
    assert "row-level security" in message and table in message, message


@functools.cache
def _clean_jpeg() -> tuple[bytes, int, int]:
    buffer = io.BytesIO()
    Image.effect_noise((640, 480), 40).convert("RGB").save(buffer, "JPEG")
    image = process(buffer.getvalue())
    return image.jpeg, image.width, image.height


def _attach_image(app, user_id, campaign) -> None:
    jpeg, width, height = _clean_jpeg()
    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (campaign, user_id, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )


def _campaign(app, user_id, *, with_image: bool = True):
    campaign = create_campaign(app, user_id, with_image=False)
    if with_image:
        _attach_image(app, user_id, campaign)
    return campaign


def _open_attempt(app, user_id, campaign):
    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute(
            "SELECT ew_begin_generation(%s, 'INITIAL', %s, NULL)",
            (campaign, row_version(app, campaign)),
        )
        return cursor.fetchone()[0]


@pytest.fixture
def populated(app, two_users):
    """لكلٍّ من المستخدمَين حملةٌ بصورتها ونسختها الأولى ومحاولتها المحسوبة."""
    a, b = two_users
    campaigns = {}
    for user in (a, b):
        campaigns[user] = _campaign(app, user)
        add_version(app, user, campaigns[user])
    return a, b, campaigns[a], campaigns[b]


@pytest.mark.parametrize("table", RLS_TABLES)
def test_row_security_is_enabled_and_forced(owner, table):
    """بلا ENABLE لا تُطبَّق السياسات أصلاً، وبلا FORCE يتخطّاها المالك — ودوالّ SECURITY DEFINER تعمل بصلاحيته."""
    with owner.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass", (table,)
        )
        assert cursor.fetchone() == (True, True)


@pytest.mark.parametrize("statement", OWNERS_PER_TABLE)
def test_each_user_sees_only_own_rows(app, owner, populated, statement):
    """استعلامٌ نسي شرط المستخدم يُرجع حملات الجميع وصورهم ونصوصهم."""
    a, b, _, _ = populated
    with owner.cursor() as cursor:
        cursor.execute(statement)
        assert {row[0] for row in cursor.fetchall()} == {a, b}
    for user in (a, b):
        as_user(app, user)
        with app.cursor() as cursor:
            cursor.execute(statement)
            assert cursor.fetchall() == [(user,)]


def test_updating_another_users_campaign_touches_nothing(app, owner, populated):
    """معرّف حملةٍ مسروق من رابطٍ يكفي لإلغائها وحذف صورتها لو مرّ التحديث."""
    a, _, _, theirs = populated
    with owner.cursor() as cursor:
        cursor.execute("SELECT status, row_version FROM campaigns WHERE id = %s", (theirs,))
        before = cursor.fetchone()
    as_user(app, a)
    with app.cursor() as cursor:
        cursor.execute("UPDATE campaigns SET status = 'CANCELLED' WHERE id = %s", (theirs,))
        assert cursor.rowcount == 0
    with owner.cursor() as cursor:
        cursor.execute("SELECT status, row_version FROM campaigns WHERE id = %s", (theirs,))
        assert cursor.fetchone() == before
        cursor.execute("SELECT count(*) FROM campaign_images WHERE campaign_id = %s", (theirs,))
        assert cursor.fetchone()[0] == 1


def test_campaign_carrying_another_users_id_is_rejected(app, owner, two_users):
    """حملةٌ تُنشأ باسم غيرك تُحسب في سقفه وتظهر في قائمته."""
    a, b = two_users
    as_user(app, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("INSERT INTO campaigns (user_id) VALUES (%s)", (b,))
    _assert_rls_rejected(caught, "campaigns")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaigns")
        assert cursor.fetchone()[0] == 0


def test_image_carrying_another_users_id_is_rejected(app, owner, two_users):
    """صورةٌ يضعها غير صاحب الحملة تصير ما يصفه النموذج باسم صاحبها."""
    a, b = two_users
    theirs = _campaign(app, b, with_image=False)
    jpeg, width, height = _clean_jpeg()
    as_user(app, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (theirs, b, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )
    _assert_rls_rejected(caught, "campaign_images")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaign_images")
        assert cursor.fetchone()[0] == 0


def test_image_claiming_own_id_on_another_users_campaign_is_rejected(app, owner, two_users):
    """تجاوز السياسة بادّعاء الملكية يصطدم بالمفتاح المركّب (الحملة، المستخدم)."""
    a, b = two_users
    theirs = _campaign(app, b, with_image=False)
    jpeg, width, height = _clean_jpeg()
    as_user(app, a)
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as caught, app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (theirs, a, jpeg, width, height, hashlib.sha256(jpeg).digest()),
        )
    assert caught.value.diag.constraint_name == "campaign_images_campaign_id_user_id_fkey"
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaign_images")
        assert cursor.fetchone()[0] == 0


def test_version_carrying_another_users_id_is_rejected(app, owner, two_users):
    """نسخةٌ يكتبها غير صاحب الحملة على محاولته المفتوحة تصير النصّ الذي يُعرض عليه ويعتمده."""
    a, b = two_users
    theirs = _campaign(app, b)
    attempt = _open_attempt(app, b, theirs)
    as_user(app, a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
            " served_model, prompt_version) VALUES (%s, %s, %s, %s, %s, 'claude-opus-5-5', 'test')",
            (theirs, b, attempt, TITLE, DESCRIPTION),
        )
    _assert_rls_rejected(caught, "copy_versions")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM copy_versions WHERE campaign_id = %s", (theirs,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT status, current_version_id FROM campaigns WHERE id = %s", (theirs,))
        assert cursor.fetchone() == ("DRAFT", None)


def test_another_users_campaign_cannot_start_a_generation(app, owner, two_users):
    """محاولةٌ على حملة غيرك تستهلك من سقفه وتفتح له توليداً لم يطلبه."""
    a, b = two_users
    theirs = _campaign(app, b)
    as_user(app, a)
    with pytest.raises(psycopg.errors.NoDataFound), app.cursor() as cursor:
        cursor.execute("SELECT ew_begin_generation(%s, 'INITIAL', 1, NULL)", (theirs,))
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM generation_attempts")
        assert cursor.fetchone()[0] == 0


def test_another_users_attempt_cannot_be_finished(app, owner, two_users):
    """إغلاق محاولة غيرك يُسقط النسخة التي ينتظرها ويفتح له محاولةً لم يطلبها."""
    a, b = two_users
    theirs = _campaign(app, b)
    attempt = _open_attempt(app, b, theirs)
    as_user(app, a)
    with pytest.raises(psycopg.errors.NoDataFound), app.cursor() as cursor:
        cursor.execute("SELECT ew_finish_generation(%s, 'UPSTREAM_ERROR', 0, 0)", (attempt,))
    with owner.cursor() as cursor:
        cursor.execute("SELECT finished_at, outcome FROM generation_attempts WHERE id = %s", (attempt,))
        assert cursor.fetchone() == (None, None)


def test_replacing_another_users_image_touches_nothing(app, owner, two_users):
    """صورةٌ تُستبدل تحت مسودة غيرك تصير ما يصفه النموذج باسمه، ويعتمده هو دون أن يرى أنها تغيّرت."""
    a, b = two_users
    theirs = _campaign(app, b)
    with owner.cursor() as cursor:
        cursor.execute("SELECT sha256 FROM campaign_images WHERE campaign_id = %s", (theirs,))
        before = cursor.fetchone()[0]
    as_user(app, a)
    with app.cursor() as cursor:
        cursor.execute(
            "UPDATE campaign_images SET sha256 = %s WHERE campaign_id = %s", (bytes(32), theirs)
        )
        assert cursor.rowcount == 0
    with owner.cursor() as cursor:
        cursor.execute("SELECT sha256 FROM campaign_images WHERE campaign_id = %s", (theirs,))
        assert cursor.fetchone()[0] == before


@pytest.mark.parametrize("statement", COUNT_PER_TABLE)
def test_without_identity_no_data_row_is_visible(app, app_url, owner, populated, statement):
    """مسارٌ نسي ضبط الهوية — أو مسار الدخول نفسه — يرى صفوف الجميع لو فشلت المقارنة مفتوحةً."""
    with owner.cursor() as cursor:
        cursor.execute(statement)
        assert cursor.fetchone()[0] == 2
    as_user(app, None)
    with app.cursor() as cursor:
        cursor.execute(statement)
        assert cursor.fetchone()[0] == 0
    with psycopg.connect(app_url, autocommit=True) as fresh, fresh.cursor() as cursor:
        cursor.execute("SELECT current_setting('eyework.user_id', true)")
        assert cursor.fetchone()[0] is None
        cursor.execute(statement)
        assert cursor.fetchone()[0] == 0


def test_without_identity_nothing_can_be_written(app, owner, two_users):
    """بلا هويةٍ لا يُنسب صفٌّ جديد إلى أحد."""
    as_user(app, None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute("INSERT INTO campaigns (user_id) VALUES (%s)", (two_users[0],))
    _assert_rls_rejected(caught, "campaigns")
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM campaigns")
        assert cursor.fetchone()[0] == 0


@pytest.mark.parametrize("statement", [
    "SELECT count(*) FROM users",
    "SELECT count(*) FROM sessions",
    "SELECT count(*) FROM activation_tokens",
])
def test_app_cannot_read_identity_tables(app, two_users, statement):
    """قائمة المستخدمين نفسها معلومةٌ صحّية؛ دور الويب يصلها عبر الدوالّ المحدّدة وحدها."""
    as_user(app, two_users[0])
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as caught, app.cursor() as cursor:
        cursor.execute(statement)
    message = caught.value.diag.message_primary or ""
    assert "permission denied" in message and statement.split()[-1] in message, message


@pytest.mark.parametrize("ending", ["commit", "rollback"])
def test_transaction_local_identity_does_not_reach_the_next_transaction(app, app_url, two_users, ending):
    """اتصالٌ يعود إلى التجمّع حاملاً هويّة طلبٍ سابق يعرض على التالي حملات غيره."""
    a, _ = two_users
    _campaign(app, a, with_image=False)
    with psycopg.connect(app_url, autocommit=True) as connection:
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute("SELECT set_config('eyework.user_id', %s, true)", (str(a),))
            cursor.execute("SELECT count(*) FROM campaigns")
            assert cursor.fetchone()[0] == 1
            if ending == "rollback":
                raise psycopg.Rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT nullif(current_setting('eyework.user_id', true), '')")
            assert cursor.fetchone()[0] is None
            cursor.execute("SELECT count(*) FROM campaigns")
            assert cursor.fetchone()[0] == 0


def test_production_sessions_on_one_connection_do_not_share_identity(app, app_url, two_users):
    """
    `Database.session` يعيد الاتصال نفسه للطلب التالي؛ الهوية لا تعبر معه.

    كل جلسةٍ تضبط هويّتها أولاً فتحجب أيّ بقيّة، ولذلك يُفحص الاتصال نفسه بعد
    عودته إلى التجمّع: هويّةٌ مضبوطة على مستوى الاتصال تبقى عليه لأيّ مسارٍ
    يستعمله دون `session`.
    """
    from eyework.db import Database

    a, b = two_users
    _campaign(app, a, with_image=False)
    database = Database(app_url, min_size=1, max_size=1)
    try:
        with database.session(a) as cursor:
            cursor.execute("SELECT pg_backend_pid() AS pid, count(*) AS visible FROM campaigns")
            first = cursor.fetchone()
        with database._pool.connection() as returned, returned.cursor() as cursor:
            cursor.execute(
                "SELECT pg_backend_pid(), nullif(current_setting('eyework.user_id', true), ''),"
                "       count(*) FROM campaigns"
            )
            leftover = cursor.fetchone()
        with database.session(None) as cursor:
            cursor.execute("SELECT pg_backend_pid() AS pid, count(*) AS visible FROM campaigns")
            anonymous = cursor.fetchone()
        with database.session(b) as cursor:
            cursor.execute("SELECT pg_backend_pid() AS pid, count(*) AS visible FROM campaigns")
            other = cursor.fetchone()
    finally:
        database.close()
    assert leftover == (first["pid"], None, 0)
    assert first["pid"] == anonymous["pid"] == other["pid"]
    assert (first["visible"], anonymous["visible"], other["visible"]) == (1, 0, 0)
