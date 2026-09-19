"""
الوصول إلى قاعدة البيانات
=========================
تجمّع اتصالات لكل دور، وسياق جلسة يضبط متغيّرات RLS **داخل معاملة** حصراً.

لماذا داخل معاملة: التجمّع يُعيد استخدام الاتصالات بين الطلبات. إعداد جلسة
يبقى بعد انتهاء الطلب يعني أن الطلب التالي قد يرث هوية مريض آخر — وهو تحديداً
تسريب البيانات بين المرضى الذي يمنعه القسم 1. `set_config(..., is_local => true)`
يُلغى تلقائياً عند نهاية المعاملة.

Prepared Statements حصراً: psycopg3 يربط المعاملات على الخادم. لا يوجد في هذه
الوحدة ولا في أي مستدعٍ لها بناء SQL بدمج نصي — اختبار معماري يفرض ذلك.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Literal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

__all__ = ["DbRole", "configure", "session", "shutdown"]

DbRole = Literal["owner", "practitioner", "patient"]

_ROLE_ENV = {
    "owner": ("SYMBOL_DATABASE_URL", None, None),
    "practitioner": ("SYMBOL_DATABASE_URL", "app_practitioner", "SYMBOL_PRACTITIONER_PASSWORD"),
    "patient": ("SYMBOL_DATABASE_URL", "app_patient", "SYMBOL_PATIENT_PASSWORD"),
}

_pools: dict[DbRole, ConnectionPool] = {}


def _conninfo(role: DbRole) -> str:
    url_var, db_role, password_var = _ROLE_ENV[role]
    url = os.environ.get(url_var)
    if not url:
        raise RuntimeError(f"{url_var} غير مضبوط")
    if db_role is None:
        return url

    password = os.environ.get(password_var or "")
    if not password:
        raise RuntimeError(f"{password_var} غير مضبوط للدور {db_role}")

    parsed = psycopg.conninfo.conninfo_to_dict(url)
    parsed.update(user=db_role, password=password)
    return psycopg.conninfo.make_conninfo(**parsed)


def configure(*, min_size: int = 1, max_size: int = 8) -> None:
    """يفتح تجمّعاً لكل دور. يُستدعى مرة عند إقلاع التطبيق."""
    for role in _ROLE_ENV:
        if role not in _pools:
            _pools[role] = _new_pool(role, min_size=min_size, max_size=max_size)


def shutdown() -> None:
    for pool in _pools.values():
        pool.close()
    _pools.clear()


def _new_pool(role: DbRole, *, min_size: int, max_size: int) -> ConnectionPool:
    """
    اتصالات التجمّع بـ`autocommit=True`، والمعاملات صريحة عبر `transaction()`.

    بدونها يعود الاتصال إلى التجمّع في حالة «idle in transaction»: يحجز أقفالاً
    تمنع أي DDL — ومنه الترحيلات — وتُبقي نسخ الصفوف القديمة. رُصد ذلك فعلياً
    حين علّق `pg_dump` ينتظر اتصالاً خاملاً داخل معاملة.
    """
    return ConnectionPool(
        _conninfo(role),
        min_size=min_size,
        max_size=max_size,
        kwargs={"autocommit": True},
        open=True,
    )


def _pool(role: DbRole) -> ConnectionPool:
    if role not in _pools:
        _pools[role] = _new_pool(role, min_size=1, max_size=4)
    return _pools[role]


@contextmanager
def session(
    role: DbRole,
    *,
    tenant_id: UUID | None = None,
    actor_id: UUID | None = None,
    patient_id: UUID | None = None,
) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
    """
    معاملة واحدة بهوية محددة. متغيّرات RLS محلية لها فلا تتسرب بين الطلبات.

    الهوية تأتي من الجلسة الموثَّقة في طبقة الـAPI، لا من العميل.
    """
    with _pool(role).connection() as connection:
        with connection.transaction():
            with connection.cursor(row_factory=dict_row) as cursor:
                for key, value in (
                    ("app.tenant_id", tenant_id),
                    ("app.actor_id", actor_id),
                    ("app.patient_id", patient_id),
                ):
                    cursor.execute(
                        "SELECT set_config(%s, %s, true)",
                        (key, "" if value is None else str(value)),
                    )
                yield cursor
