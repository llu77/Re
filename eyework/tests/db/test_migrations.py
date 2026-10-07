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
def connection(owner_url):
    """اتصالٌ مستقلّ بوضع autocommit، يبدأ والمخطّط كاملٌ ويُترك كاملاً ولو فشل الاختبار."""
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
