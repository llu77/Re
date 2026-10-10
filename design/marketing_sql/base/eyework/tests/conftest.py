"""
تجهيزات اختبارات «صياغة»
========================
اختبارات القاعدة تعمل مقابل قاعدة اختبارٍ مستقلّة (`EYEWORK_TEST_DATABASE_URL`،
باسمٍ ينتهي بـ`_test`) لا تشترك في شيءٍ مع قاعدة المنصّة.

**قاعدة اختبارٍ حصراً.** كل اختبارٍ يبدأ بـTRUNCATE؛ ولذلك يرفض هذا الملف أيّ
قاعدةٍ لا ينتهي اسمها بـ`_test` — خطأٌ في متغيّرٍ واحد لا يمسح بيانات أحد.

**الغياب فشلٌ في CI لا تجاوز.** `EYEWORK_REQUIRE_DB=1` يجعل غياب القاعدة
فشلاً. فحصٌ يُتجاوز بصمت يبدو أخضر وهو لم يفحص شيئاً.

الاختبارات النقية (`unit/`، `architecture/`) لا تعتمد على شيءٍ هنا.
"""

from __future__ import annotations

import os
from uuid import UUID

import pytest

psycopg = pytest.importorskip("psycopg", reason="psycopg غير مثبّت")

OWNER_URL = os.environ.get("EYEWORK_TEST_DATABASE_URL")
APP_PASSWORD = os.environ.get("EYEWORK_APP_PASSWORD", "eyework_dev_app")
REQUIRE_DB = os.environ.get("EYEWORK_REQUIRE_DB") == "1"

#: TRUNCATE على users يمتدّ بـCASCADE إلى كل ما يرجع إليه: الجلسات، ورموز
#: التفعيل، والحملات، والمحاولات، والنسخ، والصور.
# أثر المحاولات المحذوفة بلا مفتاحٍ إلى المستخدمين، فيُذكر وحده.
_CLEAN = "TRUNCATE users, attempt_tombstones RESTART IDENTITY CASCADE"


def app_url_for(owner_url: str) -> str:
    """القاعدة نفسها بدور الويب — هكذا تُختبر الصلاحيات كما تعمل في الإنتاج."""
    parsed = psycopg.conninfo.conninfo_to_dict(owner_url)
    parsed.update(user="eyework_app", password=APP_PASSWORD)
    return psycopg.conninfo.make_conninfo(**parsed)


@pytest.fixture(scope="session")
def owner_url() -> str:
    if not OWNER_URL:
        message = "EYEWORK_TEST_DATABASE_URL غير مضبوط"
        if REQUIRE_DB:
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    name = psycopg.conninfo.conninfo_to_dict(OWNER_URL).get("dbname", "")
    if not name.endswith("_test"):
        pytest.fail(f"أرفض العمل على قاعدةٍ لا ينتهي اسمها بـ_test: {name}", pytrace=False)
    with psycopg.connect(OWNER_URL) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.campaigns')")
        if cursor.fetchone()[0] is None:
            pytest.fail(
                "المخطّط غير مُرحَّل. شغّل: EYEWORK_OWNER_DATABASE_URL=$EYEWORK_TEST_DATABASE_URL"
                " python -m eyework.migrations.run up",
                pytrace=False,
            )
    return OWNER_URL


@pytest.fixture(scope="session")
def app_url(owner_url) -> str:
    return app_url_for(owner_url)


@pytest.fixture
def owner(owner_url):
    """اتصال المالك بعد تنظيف القاعدة. للتهيئة ولفحص ما يفرضه FORCE على المالك."""
    with psycopg.connect(owner_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(_CLEAN)
        yield connection


@pytest.fixture
def app(owner, app_url):
    """اتصال دور الويب، بعد تنظيف القاعدة عبر `owner`."""
    with psycopg.connect(app_url, autocommit=True) as connection:
        yield connection


def as_user(connection, user_id: UUID | None) -> None:
    """يضبط هوية الجلسة كما تضبطها `eyework.db` — لكن لمدّة الاتصال كلّه."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('eyework.user_id', %s, false)",
            ("" if user_id is None else str(user_id),),
        )


#: تجزئةٌ بصيغة scrypt الصحيحة (ملحٌ 16 بايتاً، وناتجٌ 64) لا تطابق كلمة مرور.
UNUSABLE_HASH = "scrypt$" + "0" * 32 + "$" + "0" * 128


def make_user(owner, *, login: bytes, password_hash: str | None = UNUSABLE_HASH,
              active: bool = True, profession: str = "MARKETING") -> UUID:
    """مستخدمٌ مفعَّل افتراضاً. `password_hash=None` ⇒ مدعوٌّ لم يُفعِّل بعد."""
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (login_hmac, password_hash, is_active, activated_at, profession)"
            " VALUES (%s, %s, %s, CASE WHEN %s::text IS NULL THEN NULL ELSE now() END, %s) RETURNING id",
            (login.ljust(32, b"\0")[:32], password_hash, active, password_hash, profession),
        )
        return cursor.fetchone()[0]


@pytest.fixture
def two_users(owner) -> tuple[UUID, UUID]:
    return make_user(owner, login=b"user-a"), make_user(owner, login=b"user-b")


# ── بيانات الحملة ──────────────────────────────────────────────────────
TITLE = "حقيبة جلدية بنية أنيقة"
DESCRIPTION = "حقيبة يد من الجلد البني بتصميمٍ بسيط وأنيق، تتّسع للأغراض اليومية ولها حزام كتف."


def sample_jpeg() -> bytes:
    """صورةٌ نظيفة كما يُخرجها مسار التطبيق نفسه."""
    import io

    from PIL import Image

    from eyework.images import process

    buffer = io.BytesIO()
    Image.effect_noise((400, 400), 40).convert("RGB").save(buffer, "JPEG")
    return process(buffer.getvalue()).jpeg


def create_campaign(app, user_id: UUID, *, with_image: bool = True) -> UUID:
    """حملةٌ مسودة لمستخدم، بصورتها افتراضاً — بدور الويب وعبر العزل."""
    import hashlib

    as_user(app, user_id)
    with app.cursor() as cursor:
        cursor.execute("INSERT INTO campaigns (user_id) VALUES (%s) RETURNING id", (user_id,))
        campaign = cursor.fetchone()[0]
        if with_image:
            jpeg = sample_jpeg()
            cursor.execute(
                "INSERT INTO campaign_images (campaign_id, user_id, jpeg, width, height, sha256)"
                " VALUES (%s, %s, %s, 400, 400, %s)",
                (campaign, user_id, jpeg, hashlib.sha256(jpeg).digest()),
            )
    return campaign


def row_version(app, campaign: UUID) -> int:
    with app.cursor() as cursor:
        cursor.execute("SELECT row_version FROM campaigns WHERE id = %s", (campaign,))
        return cursor.fetchone()[0]


def add_version(app, user_id: UUID, campaign: UUID, *, title: str = TITLE,
                description: str = DESCRIPTION, presets: tuple[str, ...] = (),
                note: str | None = None) -> UUID:
    """
    نسخةٌ بالمسار الإنتاجي نفسه: محاولةٌ محسوبة، ثم النسخة، ثم إغلاق المحاولة.

    الأولى INITIAL من مسودة، وما بعدها EDIT على النسخة الحالية.
    """
    as_user(app, user_id)
    with app.transaction(), app.cursor() as cursor:
        cursor.execute("SELECT status, current_version_id FROM campaigns WHERE id = %s", (campaign,))
        status, current = cursor.fetchone()
        kind = "INITIAL" if status == "DRAFT" else "EDIT"
        cursor.execute(
            "SELECT ew_begin_generation(%s, %s, %s, %s)",
            (campaign, kind, row_version(app, campaign), current),
        )
        attempt = cursor.fetchone()[0]
    with app.transaction(), app.cursor() as cursor:
        cursor.execute(
            "INSERT INTO copy_versions (campaign_id, user_id, attempt_id, title, description,"
            " edit_presets, edit_note, served_model, prompt_version)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, 'claude-opus-5-5', 'test') RETURNING id",
            (campaign, user_id, attempt, title, description, list(presets), note),
        )
        version = cursor.fetchone()[0]
        cursor.execute("SELECT ew_finish_generation(%s, 'OK', 0, 0)", (attempt,))
    return version
