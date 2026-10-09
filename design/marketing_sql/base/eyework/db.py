"""
الوصول إلى قاعدة البيانات
=========================
تجمّعٌ واحد بدور `eyework_app` — الدور الوحيد الذي يحمله خادم الويب. لا
يملك هذا الدور قراءة جداول الهوية ولا الحذف من أيّ جدول؛ وكل ما يخصّ
مستخدماً يمرّ بعزل الصفوف (RLS) على `eyework.user_id`.

**داخل معاملةٍ حصراً.** التجمّع يعيد استخدام الاتصالات بين الطلبات، فهويّةٌ
تُضبط خارج معاملة قد يرثها الطلب التالي — أي مستخدمٌ آخر.
`set_config(..., true)` يُلغى عند نهاية المعاملة تلقائياً.

**حدٌّ زمني لكل عبارة.** خمس ثوانٍ: لا استعلام في هذا التطبيق يحتاج أكثر،
واستعلامٌ عالق يحجز اتصالاً من تجمّعٍ صغير.

Prepared statements حصراً: psycopg 3 يربط المعاملات على الخادم، واختبارٌ
معماري يرفض أي `execute` نصُّه مركّبٌ بدمج.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

__all__ = ["Database", "UnsafeRole"]

_SET_CONTEXT = "SELECT set_config('eyework.user_id', %s, true), set_config('statement_timeout', '5s', true)"


_ROLE_CHECK = """
SELECT r.rolsuper, r.rolbypassrls,
       (SELECT count(*) FROM pg_class c WHERE c.relowner = r.oid
          AND c.relnamespace = 'public'::regnamespace) AS owned,
       has_table_privilege(current_user, 'public.users', 'SELECT') AS reads_users
  FROM pg_roles r WHERE r.rolname = current_user
"""


class UnsafeRole(RuntimeError):
    """دور الاتصال يتجاوز العزل أو يملك الجداول. لا يُقلع التطبيق به."""


class Database:
    """تجمّع اتصالاتٍ بدور التطبيق. يُنشأ مرة عند الإقلاع ويُغلق عند الإيقاف."""

    def __init__(self, conninfo: str, *, min_size: int = 1, max_size: int = 8) -> None:
        # autocommit والمعاملات صريحة: بدونها يعود الاتصال إلى التجمّع
        # «idle in transaction» فيحجز أقفالاً تمنع الترحيلات.
        self._pool = ConnectionPool(
            conninfo,
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": True},
            open=True,
        )

    def close(self) -> None:
        self._pool.close()

    def verify_role(self) -> None:
        """
        يرفض دوراً يتجاوز العزل: superuser أو BYPASSRLS، أو مالكاً لجدول
        (المالك يتجاوز سياسات جدوله إلا بـFORCE)، أو قادراً على قراءة الهوية.
        خطأٌ في متغيّر بيئةٍ واحد كان سيُبطل كل ضمانةٍ في القاعدة بلا أي خطأ.
        """
        with self.session() as cursor:
            cursor.execute(_ROLE_CHECK)
            row = cursor.fetchone()
        if row is None or row["rolsuper"] or row["rolbypassrls"] or row["owned"] or row["reads_users"]:
            raise UnsafeRole("دور قاعدة البيانات يتجاوز العزل. استخدم eyework_app.")

    @contextmanager
    def session(self, user_id: UUID | None = None) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
        """
        معاملةٌ واحدة بهويةٍ محدّدة، أو بلا هوية لمسارات الدخول.

        الهوية تأتي من جلسةٍ موثَّقة في طبقة الويب، لا من جسم الطلب.
        بلا هوية لا يرى الدور أيّ صفٍّ في جداول البيانات: سياسة RLS تقارن
        بقيمةٍ فارغة فتفشل مغلقة.
        """
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(_SET_CONTEXT, ("" if user_id is None else str(user_id),))
                    yield cursor
