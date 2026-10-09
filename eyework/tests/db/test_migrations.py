"""
الترحيلات
=========
كل ترحيلٍ قابلٌ للتراجع، والتراجع يُعيد القاعدة إلى ما كانت عليه بالضبط:
صعودٌ ثم نزولٌ كامل ثم صعودٌ يُنتج مخطّطاً مطابقاً سطراً بسطر — جداول ومنحاً
وسياساتٍ ومحفّزاتٍ وصلاحيات القاعدة نفسها. ترحيلٌ يترك أثراً بعد تراجعه، أو
يُطبَّق نصفه، يجعل كل إعادة تشغيلٍ تبني على قاعدةٍ غير التي اختُبرت.

تعمل هذه الاختبارات على اتصالٍ خاصٍّ بها، لا على تجهيزة المالك: النزول
يُسقط الجداول، واتصالٌ آخر يحمل قفلاً عليها يعلّقه.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
from pathlib import Path

import psycopg
import pytest

from eyework.migrations import run
from eyework.migrations.run import migrate_down, migrate_up

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
FILE_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.(up|down)\.sql$")
VARYING_LINE = re.compile(r"^\\(un)?restrict ")
SNAPSHOT_MUST_COVER = (
    "GRANT CONNECT ON DATABASE",
    "GRANT USAGE ON SCHEMA public TO eyework_app;",
    "GRANT INSERT(user_id) ON TABLE public.campaigns TO eyework_app;",
    "ALTER TABLE ONLY public.campaigns FORCE ROW LEVEL SECURITY;",
    "CREATE POLICY campaigns_own ON public.campaigns",
    "CREATE TRIGGER trg_campaign_guard",
    # 0008 و0009: العزل مفروضٌ على الدفترين — على المالك أيضاً.
    "ALTER TABLE ONLY public.registration_ledger FORCE ROW LEVEL SECURITY;",
    "ALTER TABLE ONLY public.ai_requests FORCE ROW LEVEL SECURITY;",
    # 0010: دفتر المشتريات مفروضٌ عزله، ونسيان تنبيهات سيمبول مع المسودة المنبوذة.
    "ALTER TABLE ONLY public.inv_ledger FORCE ROW LEVEL SECURITY;",
    "CREATE TRIGGER trg_inv_purchases_forget_ai",
)


def _stems(direction: str) -> set[str]:
    return {path.name.removesuffix(f".{direction}.sql") for path in MIGRATIONS.glob(f"*.{direction}.sql")}


def _schema_snapshot(url: str) -> list[str]:
    if shutil.which("pg_dump") is None:
        message = "pg_dump غير متاح"
        if os.environ.get("EYEWORK_REQUIRE_DB") == "1":
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    dump = subprocess.run(
        ["pg_dump", "--schema-only", "--create", "--dbname", url],
        check=True, capture_output=True, text=True,
    ).stdout
    return [line for line in dump.splitlines() if not VARYING_LINE.match(line)]


def _ledger(connection) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version")
        return cursor.fetchall()


def _all_versions() -> list[str]:
    return sorted(stem[:4] for stem in _stems("up"))


@pytest.fixture
def connection(owner_url, owner):
    """
    اتصالٌ مستقلّ بوضع autocommit، يبدأ والمخطّط كاملٌ ويُترك كاملاً ولو فشل الاختبار.

    بعد تنظيف القاعدة (`owner`): حسابٌ مفتوح بقي من اختبارٍ سابق يجعل تراجع 0008
    يرفض — عن حقّ — فلا يُقاس التراجع إلا على قاعدةٍ لا تحمل ما يرفضه.
    """
    with psycopg.connect(owner_url, autocommit=True) as own:
        assert [row[0] for row in _ledger(own)] == _all_versions()
        try:
            yield own
        finally:
            migrate_up(own)


def test_every_up_migration_has_a_down_and_vice_versa():
    """ترحيلٌ بلا تراجع لا يُعاد إلا بإسقاط القاعدة؛ وتراجعٌ بلا صعود يُسقط ما لم يُنشئه."""
    files = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert files
    assert [name for name in files if not FILE_PATTERN.match(name)] == []
    assert _stems("up") == _stems("down")
    assert len({stem[:4] for stem in _stems("up")}) == len(_stems("up"))


def test_up_down_up_reproduces_the_schema_exactly(connection, owner_url):
    """تراجعٌ ينسى منحاً أو سياسةً أو صلاحيةً على القاعدة يترك الصعود التالي فوق بقاياه."""
    before = _schema_snapshot(owner_url)
    assert [marker for marker in SNAPSHOT_MUST_COVER if not any(marker in line for line in before)] == []
    assert migrate_down(connection, everything=True) == len(_all_versions())
    assert migrate_up(connection) == len(_all_versions())
    after = _schema_snapshot(owner_url)
    difference = list(difflib.unified_diff(before, after, "before", "after", lineterm=""))
    assert difference == [], "\n".join(difference)


def test_each_down_restores_exactly_the_schema_before_its_up(connection, owner_url):
    """تراجعٌ يمسّ ما أنشأه ترحيلٌ أقدم يُصلحه ذاك في الدورة الكاملة فيمرّ، ويترك التراجع الجزئي قاعدةً لم تُختبر."""
    versions = _all_versions()
    assert migrate_down(connection, everything=True) == len(versions)
    snapshots = [_schema_snapshot(owner_url)]
    for version in versions:
        assert migrate_up(connection, version) == 1
        snapshots.append(_schema_snapshot(owner_url))
    assert len({tuple(snapshot) for snapshot in snapshots}) == len(snapshots)
    for version, expected in zip(reversed(versions), reversed(snapshots[:-1])):
        assert migrate_down(connection) == 1
        difference = list(difflib.unified_diff(
            expected, _schema_snapshot(owner_url), f"before {version} up", f"after {version} down",
            lineterm="",
        ))
        assert difference == [], "\n".join(difference)


def test_full_rollback_leaves_only_the_ledger(connection):
    """التراجع الكامل يعيد القاعدة كما وُجدت: لا جدول ولا دالّة ولا سياسة، وصلاحيات القاعدة والمخطّط الافتراضية."""
    assert migrate_down(connection, everything=True) == len(_all_versions())
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace ORDER BY relname"
        )
        assert [row[0] for row in cursor.fetchall()] == ["schema_migrations", "schema_migrations_pkey"]
        cursor.execute("SELECT oid::regprocedure::text FROM pg_proc WHERE pronamespace = 'public'::regnamespace")
        assert cursor.fetchall() == []
        cursor.execute(
            "SELECT a.grantee, a.privilege_type"
            "  FROM pg_database d CROSS JOIN LATERAL aclexplode(d.datacl) a WHERE d.datname = current_database()"
        )
        current = set(cursor.fetchall())
        cursor.execute(
            "SELECT a.grantee, a.privilege_type"
            "  FROM pg_database d CROSS JOIN LATERAL aclexplode(acldefault('d', d.datdba)) a"
            " WHERE d.datname = current_database()"
        )
        assert current == set(cursor.fetchall())
        cursor.execute(
            "SELECT a.grantee, a.privilege_type"
            "  FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a WHERE n.nspname = 'public'"
        )
        current = set(cursor.fetchall())
        cursor.execute(
            "SELECT a.grantee, a.privilege_type"
            "  FROM pg_init_privs i CROSS JOIN LATERAL aclexplode(i.initprivs) a"
            " WHERE i.objoid = 'public'::regnamespace AND i.classoid = 'pg_namespace'::regclass"
        )
        assert current == set(cursor.fetchall())
    assert _ledger(connection) == []
    assert migrate_down(connection, everything=True) == 0


def test_up_when_current_applies_nothing(connection):
    """صعودٌ يعيد تطبيق ما طُبِّق يفشل في منتصف النشر أو يكرّر منحاً."""
    ledger = _ledger(connection)
    assert migrate_up(connection) == 0
    assert _ledger(connection) == ledger


def test_a_failing_migration_leaves_no_trace(connection, tmp_path, monkeypatch):
    """ترحيلٌ يفشل في منتصفه ويُبقي نصفه يترك قاعدةً لا يصفها أيّ ملف."""
    up = tmp_path / "9999_broken.up.sql"
    down = tmp_path / "9999_broken.down.sql"
    up.write_text("CREATE TABLE ew_half_applied (x int);\nSELECT 1 / 0;\n", encoding="utf-8")
    down.write_text("DROP TABLE IF EXISTS ew_half_applied;\n", encoding="utf-8")
    real = run.discover()
    monkeypatch.setattr(run, "discover", lambda: [*real, run.Migration("9999", "broken", up, down)])
    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate_up(connection)
    monkeypatch.undo()
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.ew_half_applied')")
        assert cursor.fetchone()[0] is None
    assert [row[0] for row in _ledger(connection)] == _all_versions()


def test_0004_backfills_images_of_every_status_and_keeps_their_times(connection, owner, app):
    """
    التعبئة في 0004 تمرّ على صور الحملات المعتمدة أيضاً، ولا تعيد كتابة وقت
    إنشائها: الحارس الذي يرفض تعديل صورةٍ خارج المسودة لا يعني ترحيلاً.
    """
    from eyework.tests.conftest import UNUSABLE_HASH, add_version, create_campaign
    from eyework.tests.db.test_generation_caps import move_to

    # إلى ما قبل 0004 أيّاً كان ما بعده؛ و0004 وحده يُطبَّق ثم يُفحص.
    migrate_down(connection, target="0003")
    assert [row[0] for row in _ledger(connection)][-1] == "0003"
    # بأعمدة 0003 وحدها: ما أضافته ترحيلاتٌ لاحقة لا يوجد بعد.
    with owner.cursor() as cursor:
        cursor.execute("INSERT INTO users (login_hmac, password_hash, activated_at) VALUES (%s, %s, now())"
                       " RETURNING id", (b"m" * 32, UNUSABLE_HASH))
        user = cursor.fetchone()[0]
    ready = create_campaign(app, user)
    add_version(app, user, ready)
    move_to(app, user, ready, "READY")
    draft = create_campaign(app, user)
    with owner.cursor() as cursor:
        cursor.execute("ALTER TABLE campaign_images DISABLE TRIGGER trg_image_guard")
        cursor.execute("UPDATE campaign_images SET created_at = now() - interval '2 days'")
        cursor.execute("ALTER TABLE campaign_images ENABLE TRIGGER trg_image_guard")
        cursor.execute("SELECT campaign_id, created_at FROM campaign_images")
        before = dict(cursor.fetchall())

    assert migrate_up(connection, "0004") == 1

    with owner.cursor() as cursor:
        cursor.execute("SELECT campaign_id, created_at, updated_at FROM campaign_images")
        after = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    assert set(after) == {ready, draft}
    for campaign, created in before.items():
        assert after[campaign] == (created, created)


@pytest.mark.parametrize("profession, self_registered", [("STOREKEEPER", False), ("MARKETING", True)])
def test_0005_down_refuses_while_accounts_it_cannot_describe_exist(connection, owner, profession, self_registered):
    """
    بعد التراجع يصير الحساب المسجَّل ذاتياً، أو حساب مهنةٍ أخرى، حساب دعوةٍ
    يفتح أداة الحملات. فالتراجع يرفض ولا يغيّر شيئاً حتى يُحذف.
    """
    from eyework.tests.conftest import make_user

    make_user(owner, login=b"invited", profession="MARKETING")
    other = make_user(owner, login=b"other", profession=profession)
    if self_registered:
        with owner.cursor() as cursor:
            cursor.execute("UPDATE users SET self_registered = true, terms_version = '2026-10-01',"
                           " terms_accepted_at = now() WHERE id = %s", (other,))
    with pytest.raises(psycopg.errors.RaiseException, match="1 حساباً"):
        migrate_down(connection, target="0004")
    assert [row[0] for row in _ledger(connection)][-1] == "0005"

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (other,))
    assert migrate_down(connection, target="0004") == 1


def test_0005_down_waits_for_an_account_being_created_and_still_refuses(connection, owner_url):
    """
    حسابٌ من غير التسويق لم يُثبَّت بعد لا يراه العدّ. فالتراجع يقفل الجدول أولاً:
    ينتظر المعاملة، ثم يعدّه ويرفض، ولا يبقى حسابٌ لا يصفه 0004.
    """
    import threading

    from eyework.tests.db.test_state_machine import blocked_on_a_lock

    outcome = {}

    def roll_back() -> None:
        try:
            migrate_down(connection, target="0004")
            outcome["done"] = True
        except psycopg.errors.RaiseException as exc:
            outcome["refused"] = str(exc)

    with psycopg.connect(owner_url) as writer:
        writer.execute("INSERT INTO users (login_hmac, password_hash, activated_at, profession)"
                       " VALUES (%s, %s, now(), 'STOREKEEPER')", (b"w" * 32, "scrypt$" + "0" * 32 + "$" + "0" * 128))
        racer = threading.Thread(target=roll_back)
        racer.start()
        with psycopg.connect(owner_url, autocommit=True) as watcher:
            waited = blocked_on_a_lock(watcher, connection.info.backend_pid, racer)
        writer.commit()
        racer.join(timeout=10)
    assert waited
    assert "refused" in outcome, outcome
    assert [row[0] for row in _ledger(connection)][-1] == "0005"
    with psycopg.connect(owner_url, autocommit=True) as cleanup:
        cleanup.execute("DELETE FROM users")


def test_0008_backfills_the_ledger_from_codes_used_in_the_last_day(connection, owner):
    """
    السقف في 0007 يعدّ الرموز المستعملة في آخر يوم، وفي 0008 يعدّ الدفتر: فينقل
    الترحيل تلك الرموز إلى الدفتر بأوقاتها، ولا ينقل رمزاً لم يُستعمل أو استُعمل
    قبل أكثر من يوم. وإلا أفرغ النشرُ السقفَ ليومٍ كامل.
    """
    migrate_down(connection, target="0007")
    assert [row[0] for row in _ledger(connection)][-1] == "0007"
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO signup_codes (code_hash, created_at, expires_at, used_at) VALUES"
            " (sha256('a'::bytea), now() - interval '2 hours', now() + interval '1 day', now() - interval '1 hour'),"
            " (sha256('b'::bytea), now() - interval '24 hours', now() + interval '1 day', now() - interval '23 hours'),"
            " (sha256('c'::bytea), now() - interval '2 days', now() + interval '1 day', now() - interval '25 hours'),"
            " (sha256('d'::bytea), now() - interval '1 hour', now() + interval '1 day', NULL)")
        cursor.execute("SELECT used_at FROM signup_codes WHERE used_at > now() - interval '24 hours' ORDER BY used_at")
        expected = [(row[0], "CODE", "OK") for row in cursor.fetchall()]
    assert len(expected) == 2

    assert migrate_up(connection, "0008") == 1

    with owner.cursor() as cursor:
        cursor.execute("SELECT occurred_at, via, outcome FROM registration_ledger ORDER BY occurred_at")
        assert cursor.fetchall() == expected


def test_0008_down_refuses_while_open_accounts_exist(connection, owner, app):
    """
    0005 يضمن ألّا حساب بلا رمز. حسابٌ مفتوح بعد التراجع يخالف ما يصفه مخطّط 0007
    ويفقد حدود أسبوعه الأول بصمت؛ فالتراجع يرفض ولا يغيّر شيئاً، ويسمّي ما يُحذف.
    """
    from eyework.tests.conftest import register_open

    assert register_open(app, "blocker@example.sa")[1] == "OK"
    assert migrate_down(connection, target="0008") == 2   # 0010 ثم 0009
    with pytest.raises(psycopg.errors.RaiseException, match="1 حساباً") as caught:
        migrate_down(connection, target="0007")
    assert "DELETE FROM users WHERE open_registered" in (caught.value.diag.message_hint or "")
    assert [row[0] for row in _ledger(connection)][-1] == "0008"

    with owner.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE open_registered")
    assert migrate_down(connection, target="0007") == 1
    assert migrate_up(connection) == 3   # 0008 و0009 و0010


def test_0008_down_waits_for_an_open_account_being_created_and_still_refuses(connection, owner_url, app_url):
    """
    تسجيلٌ مفتوح لم يُثبَّت بعد لا يراه العدّ. فالتراجع يقفل الجدول أولاً: ينتظر
    المعاملة، ثم يعدّه ويرفض، ولا يبقى حسابٌ لا يصفه 0007.
    """
    import threading

    from eyework.tests.conftest import register_open
    from eyework.tests.db.test_state_machine import blocked_on_a_lock

    assert migrate_down(connection, target="0008") == 2   # 0010 ثم 0009
    outcome = {}

    def roll_back() -> None:
        try:
            migrate_down(connection, target="0007")
            outcome["done"] = True
        except psycopg.errors.RaiseException as exc:
            outcome["refused"] = str(exc)

    # بلا autocommit: التسجيل يبقى معاملةً مفتوحة تحمل قفل الصفّ حتى يُثبَّت.
    with psycopg.connect(app_url) as writer:
        assert register_open(writer, "pending@example.sa")[1] == "OK"
        racer = threading.Thread(target=roll_back)
        racer.start()
        with psycopg.connect(owner_url, autocommit=True) as watcher:
            waited = blocked_on_a_lock(watcher, connection.info.backend_pid, racer)
        writer.commit()
        racer.join(timeout=10)
    assert waited
    assert "refused" in outcome, outcome
    assert [row[0] for row in _ledger(connection)][-1] == "0008"
    with psycopg.connect(owner_url, autocommit=True) as cleanup:
        cleanup.execute("DELETE FROM users")


def test_0009_down_leaves_the_days_billable_requests_as_tombstones(connection, owner):
    """
    التراجع يحذف دفتر الاستدعاءات، ومحفّز حذفه يكتب أثر ما ربما فُوتر في آخر يوم
    (بعلامة الحساب الجديد): السقف العام في 0008 يعدّ الأثر، فلا يُفرغه التراجع.
    """
    from eyework.tests.conftest import make_user

    user = make_user(owner, login=b"keeper", profession="STOREKEEPER")
    with owner.cursor() as cursor:
        cursor.execute(
            "INSERT INTO ai_requests (user_id, feature, started_at, finished_at, outcome, new_account) VALUES"
            " (%s, 'ASSISTANT', now() - interval '1 hour', now() - interval '1 hour', 'OK', true),"
            " (%s, 'ASSISTANT', now() - interval '2 hours', now() - interval '2 hours', 'REFUSED', false),"
            " (%s, 'ASSISTANT', now() - interval '3 hours', now() - interval '3 hours', 'UPSTREAM_BUSY', false),"
            " (%s, 'ASSISTANT', now() - interval '25 hours', now() - interval '25 hours', 'OK', false)",
            (user, user, user, user))
        cursor.execute("SELECT started_at, outcome, new_account FROM ai_requests"
                       " WHERE ew_is_billable(outcome) AND started_at > now() - interval '24 hours'"
                       " ORDER BY started_at")
        expected = cursor.fetchall()
    assert [row[1] for row in expected] == ["REFUSED", "OK"]

    assert migrate_down(connection, target="0008") == 2   # 0010 ثم 0009

    with owner.cursor() as cursor:
        cursor.execute("SELECT started_at, outcome, new_account FROM attempt_tombstones ORDER BY started_at")
        assert cursor.fetchall() == expected
