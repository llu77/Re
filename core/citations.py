"""
الاستشهادات
============
ربط مقترح بمصدر استُرجع فعلاً. ثلاثة قيود تفرضها قاعدة البيانات لا هذا الملف:

  • المصدر يجب أن يكون صفّاً في `evidence_sources` — والمفتاح الخارجي يرفض
    معرّفاً مختلَقاً.
  • المقترح يجب أن يكون في حالة غير نهائية — فلا يُلفَّق دليلٌ بعد الاعتماد.
  • المقترح من نوع مُلزِم لا ينتقل إلى `PENDING` بلا استشهاد واحد على الأقل.

الثالث هو البوابة نفسها، ومحلّها محفّز الانتقالات لا هذه الوحدة: المرور من
هنا ليس شرطاً لدخول الطابور، والمنع يجب أن يصمد لأي مسار.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from psycopg import errors as pg_errors

from core import db
from core.types import Actor

__all__ = ["Citation", "CitationRefused", "cite", "for_proposal"]


class CitationRefused(Exception):
    """رفضت قاعدة البيانات الاستشهاد: مصدر غير موجود، أو مقترح حالته نهائية."""


@dataclass(frozen=True, slots=True)
class Citation:
    proposal_id: UUID
    source_id: UUID
    locator: str | None
    added_by: UUID
    added_at: datetime
    external_id: str
    title: str
    url: str
    published_year: int | None


_INSERT = """
INSERT INTO proposal_citations (proposal_id, source_id, locator, added_by)
VALUES (%s, %s, %s, %s)
ON CONFLICT (proposal_id, source_id) DO NOTHING
"""

_FOR_PROPOSAL = """
SELECT c.proposal_id, c.source_id, c.locator, c.added_by, c.added_at,
       s.external_id, s.title, s.url, s.published_year
FROM proposal_citations c
JOIN evidence_sources s ON s.id = c.source_id
WHERE c.proposal_id = %s
ORDER BY c.added_at
"""

_ONE = """
SELECT c.proposal_id, c.source_id, c.locator, c.added_by, c.added_at,
       s.external_id, s.title, s.url, s.published_year
FROM proposal_citations c
JOIN evidence_sources s ON s.id = c.source_id
WHERE c.proposal_id = %s AND c.source_id = %s
"""


def _to_citation(row) -> Citation:
    return Citation(
        proposal_id=row["proposal_id"],
        source_id=row["source_id"],
        locator=row["locator"],
        added_by=row["added_by"],
        added_at=row["added_at"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        published_year=row["published_year"],
    )


def cite(
    actor: Actor,
    *,
    proposal_id: UUID,
    source_id: UUID,
    locator: str | None = None,
) -> Citation:
    """
    يربط مقترحاً بمصدر. آمن للتكرار: الاستشهاد نفسه مرتين يُعيد الصفّ نفسه.
    """
    clean = (locator or "").strip() or None
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        try:
            cursor.execute(_INSERT, (proposal_id, source_id, clean, actor.id))
        except (
            pg_errors.ForeignKeyViolation,
            pg_errors.CheckViolation,
            pg_errors.InsufficientPrivilege,
        ) as exc:
            raise CitationRefused(str(exc)) from exc

        cursor.execute(_ONE, (proposal_id, source_id))
        row = cursor.fetchone()

    if row is None:
        # لا صفّ بعد الإدراج: المقترح خارج نطاق هذا المستأجر، فعزل الصفوف
        # ابتلع الكتابة. نُبلّغ رفضاً لا نجاحاً صامتاً.
        raise CitationRefused("تعذّر الاستشهاد: المقترح أو المصدر خارج النطاق")
    return _to_citation(row)


def for_proposal(actor: Actor, proposal_id: UUID) -> Sequence[Citation]:
    """أدلّة مقترح، بترتيب إضافتها. يراها الممارس بجانب ما يراجعه."""
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_FOR_PROPOSAL, (proposal_id,))
        return [_to_citation(row) for row in cursor.fetchall()]
