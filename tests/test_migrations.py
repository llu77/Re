"""
معيار القبول 10 — كل ترحيل قابل للتراجع ومُختبَر في الاتجاهين
================================================================
ترحيل لا يُختبر تراجعه ليس قابلاً للتراجع، هو فقط لم يُجرَّب.
"""

from __future__ import annotations

import os
import re
import subprocess

import pytest

from core import db
from migrations.run import discover, migrate_down, migrate_up
from tests.conftest import DATABASE_URL, requires_db

psycopg = pytest.importorskip("psycopg")

pytestmark = requires_db

#: pg_dump يُصدر رموز \restrict عشوائية لكل تشغيل — ليست من المخطط.
_NONCE = re.compile(r"^\\(?:un)?restrict\s+\S+$", re.MULTILINE)


def _schema_snapshot() -> str:
    dump = subprocess.run(
        ["pg_dump", "--schema-only", "--no-owner", "--no-privileges", DATABASE_URL],
        capture_output=True, text=True, check=True,
        # يفشل بدل أن يعلّق لو احتجز اتصالٌ آخر قفلاً على الجداول
        env={**os.environ, "PGOPTIONS": "-c lock_timeout=15s"},
    ).stdout
    dump = _NONCE.sub("", dump)
    return "\n".join(
        line for line in dump.splitlines() if line.strip() and not line.startswith("--")
    )


def test_every_migration_has_both_directions():
    migrations = discover()
    assert migrations, "لا ترحيلات"
    for migration in migrations:
        assert migration.up.exists() and migration.down.exists()


def test_migrations_are_reversible():
    """`up → down → up` يُعيد المخطط إلى ما كان عليه بالضبط."""
    db.shutdown()  # إسقاط الجداول يحتاج ألا يحتجز التجمّع أقفالاً عليها
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        before = _schema_snapshot()

        migrate_down(connection, everything=True)
        stripped = _schema_snapshot()
        assert "proposals" not in stripped, "التراجع لم يُسقط الجداول"

        migrate_up(connection)
        after = _schema_snapshot()

    assert after == before, "المخطط بعد إعادة الترحيل يخالف ما قبله"


def test_up_is_idempotent_when_already_applied():
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        assert migrate_up(connection) == 0, "أعاد تطبيق ترحيل مُطبَّق"
