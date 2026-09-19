"""
مُشغّل الترحيلات
================
أزواج `NNNN_name.up.sql` و`NNNN_name.down.sql`. كل ترحيل يعمل داخل معاملة
واحدة، ويُسجَّل في `schema_migrations`.

كل ترحيل قابل للتراجع ومُختبَر في الاتجاهين — معيار القبول 10. لا Alembic:
لا ORM في هذه الطبقة، والـSQL صريح ومقروء كما هو.

    python -m migrations.run up      [--to 0002]
    python -m migrations.run down    [--to 0001] [--all]
    python -m migrations.run status
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent
NAME_PATTERN = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.(?P<direction>up|down)\.sql$")

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text        PRIMARY KEY,
    name        text        NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    up: Path
    down: Path

    @property
    def label(self) -> str:
        return f"{self.version}_{self.name}"


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """كل الترحيلات مرتّبة تصاعدياً. ترحيل بلا نظير تراجع خطأ صريح."""
    halves: dict[tuple[str, str], dict[str, Path]] = {}
    for path in sorted(directory.glob("*.sql")):
        match = NAME_PATTERN.match(path.name)
        if not match:
            raise ValueError(f"اسم ترحيل غير صالح: {path.name}")
        key = (match["version"], match["name"])
        halves.setdefault(key, {})[match["direction"]] = path

    migrations = []
    for (version, name), pair in sorted(halves.items()):
        missing = {"up", "down"} - pair.keys()
        if missing:
            raise ValueError(
                f"الترحيل {version}_{name} ينقصه {sorted(missing)} — كل ترحيل قابل للتراجع"
            )
        migrations.append(Migration(version, name, pair["up"], pair["down"]))
    return migrations


def applied_versions(connection: psycopg.Connection) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(BOOTSTRAP)
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [row[0] for row in cursor.fetchall()]


def _apply(connection: psycopg.Connection, migration: Migration, direction: str) -> None:
    script = (migration.up if direction == "up" else migration.down).read_text(encoding="utf-8")
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(script)
        if direction == "up":
            cursor.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                (migration.version, migration.name),
            )
        else:
            cursor.execute(
                "DELETE FROM schema_migrations WHERE version = %s", (migration.version,)
            )
    print(f"  {'▲' if direction == 'up' else '▼'} {migration.label}")


def migrate_up(connection: psycopg.Connection, target: str | None = None) -> int:
    done = set(applied_versions(connection))
    pending = [m for m in discover() if m.version not in done]
    if target:
        pending = [m for m in pending if m.version <= target]
    for migration in pending:
        _apply(connection, migration, "up")
    return len(pending)


def migrate_down(
    connection: psycopg.Connection, target: str | None = None, everything: bool = False
) -> int:
    done = set(applied_versions(connection))
    candidates = [m for m in reversed(discover()) if m.version in done]

    if everything:
        rollback = candidates
    elif target:
        rollback = [m for m in candidates if m.version > target]
    else:
        rollback = candidates[:1]  # آخر ترحيل فقط

    for migration in rollback:
        _apply(connection, migration, "down")
    return len(rollback)


def show_status(connection: psycopg.Connection) -> None:
    done = set(applied_versions(connection))
    for migration in discover():
        mark = "مُطبَّق" if migration.version in done else "معلّق"
        print(f"  [{mark:>7}] {migration.label}")


def dsn() -> str:
    value = os.environ.get("SYMBOL_DATABASE_URL")
    if not value:
        raise SystemExit(
            "SYMBOL_DATABASE_URL غير مضبوط. مثال:\n"
            "  export SYMBOL_DATABASE_URL=$(scripts/dev_db.sh dsn)"
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("up", "down", "status"))
    parser.add_argument("--to", dest="target", help="نسخة الهدف (مثل 0001)")
    parser.add_argument("--all", action="store_true", help="مع down: تراجَع عن الكل")
    args = parser.parse_args(argv)

    # autocommit: كل ترحيل يفتح معاملته صراحةً في `_apply`. بدونها تبقى
    # معاملة ضمنية مفتوحة بعد قراءة `schema_migrations`، فيحتجز الاتصال أقفالاً
    # تمنع أي أداة أخرى — رُصد ذلك حين علّق `pg_dump` ينتظرها.
    with psycopg.connect(dsn(), autocommit=True) as connection:
        if args.command == "status":
            show_status(connection)
            return 0

        if args.command == "up":
            count = migrate_up(connection, args.target)
            print(f"طُبِّق {count} ترحيل" if count else "لا ترحيلات معلّقة")
        else:
            count = migrate_down(connection, args.target, args.all)
            print(f"تُراجع عن {count} ترحيل" if count else "لا شيء للتراجع عنه")
    return 0


if __name__ == "__main__":
    sys.exit(main())
