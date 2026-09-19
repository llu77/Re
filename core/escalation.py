"""
تصعيد العلامات الحمراء
=======================
بلاغ المريض يصل طابور الممارس فوراً بطابع زمني، ويُقاس زمن وصوله إليه.

تدقيق المرحلة 0: إنذار الانتحار في PHQ-9 كان يضبط `result["URGENT"] = True`
ولا يقرؤه أحد — صفر نتائج بحث في `app.py`. ولم تكن في المستودع أي قدرة على
إبلاغ إنسان.

**الرد على البلاغ تأكيد استلام فقط.** لا تشخيص ولا طمأنة ولا نصيحة طبية،
ولا يمر نصّ الرد بنموذج لغوي: هو ثابت في `ACKNOWLEDGEMENT`. مريض يسأل «هل
هذا طبيعي؟» لا يتلقى جواباً سريرياً من النظام.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from core import db
from core.types import Actor

__all__ = [
    "ACKNOWLEDGEMENT",
    "RedFlag",
    "acknowledge",
    "open_reports",
    "report",
]

#: نص ثابت. لا يُولَّد ولا يُعدَّل حسب محتوى البلاغ.
ACKNOWLEDGEMENT = (
    "وصل بلاغك وسُجِّل وقته. أُبلِغ الممارس المسؤول عن حالتك. "
    "إن كانت حالتك طارئة فاتصل بالإسعاف فوراً."
)


class AlreadyAcknowledged(Exception):
    """البلاغ استُلم من قبل. الاستلام يحدث مرة واحدة ويُقاس زمنه."""


@dataclass(frozen=True, slots=True)
class RedFlag:
    id: UUID
    patient_id: UUID
    body: str
    reported_at: datetime
    reported_by: UUID
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    escalation_seconds: float | None = None


_COLUMNS = (
    "id, patient_id, body, reported_at, reported_by, acknowledged_at,"
    " acknowledged_by, escalation_seconds"
)

_INSERT = (
    "INSERT INTO red_flag_reports (tenant_id, patient_id, body, reported_by)"
    f" VALUES (%s, %s, %s, %s) RETURNING {_COLUMNS}"
)

_OPEN_QUEUE = (
    f"SELECT {_COLUMNS} FROM red_flag_reports"
    " WHERE acknowledged_at IS NULL ORDER BY reported_at ASC LIMIT %s"
)

_ACKNOWLEDGE = (
    "UPDATE red_flag_reports SET acknowledged_by = %s, acknowledged_at = now(),"
    " resolution_note = %s WHERE id = %s AND acknowledged_at IS NULL"
    f" RETURNING {_COLUMNS}"
)


def _to_red_flag(row) -> RedFlag:
    return RedFlag(
        id=row["id"],
        patient_id=row["patient_id"],
        body=row["body"],
        reported_at=row["reported_at"],
        reported_by=row["reported_by"],
        acknowledged_at=row["acknowledged_at"],
        acknowledged_by=row["acknowledged_by"],
        escalation_seconds=row["escalation_seconds"],
    )


def report(
    *, tenant_id: UUID, patient_id: UUID, body: str, reported_by: UUID
) -> tuple[RedFlag, str]:
    """
    يرفع بلاغاً ويُعيده مع نص تأكيد الاستلام الثابت.

    لا يُرفض البلاغ لأي سبب عدا كونه فارغاً: مريض يبلّغ عن شيء يقلقه يجب أن
    يصل بلاغه، لا أن يُصنَّف أولاً.
    """
    if not body or not body.strip():
        raise ValueError("البلاغ يحتاج نصاً")

    with db.session("patient", patient_id=patient_id, actor_id=reported_by) as cursor:
        cursor.execute(_INSERT, (tenant_id, patient_id, body.strip(), reported_by))
        flag = _to_red_flag(cursor.fetchone())
    return flag, ACKNOWLEDGEMENT


def open_reports(actor: Actor, limit: int = 50) -> Sequence[RedFlag]:
    """البلاغات غير المستلَمة، الأقدم أولاً. تتصدّر طابور الممارس."""
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(_OPEN_QUEUE, (min(limit, 200),))
        return [_to_red_flag(row) for row in cursor.fetchall()]


def acknowledge(report_id: UUID, actor: Actor, note: str | None = None) -> RedFlag:
    """
    يسجّل استلام الممارس. الشرط `acknowledged_at IS NULL` يجعلها ذرّية، فلا
    يتسابق ممارسان على البلاغ نفسه ويُستبدل زمن التصعيد الأول.
    """
    with db.session("practitioner", tenant_id=actor.tenant_id, actor_id=actor.id) as cursor:
        cursor.execute(_ACKNOWLEDGE, (actor.id, note, report_id))
        row = cursor.fetchone()
    if row is None:
        raise AlreadyAcknowledged(str(report_id))
    return _to_red_flag(row)
