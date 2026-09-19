"""
موافقة المرافق
===============
مرافق واحد، مريض واحد، صفّ موافقة واحد — والوصول **هو** ذلك الصفّ. لا يوجد
في هذا الملف ولا في المخطط مسارٌ يمنح مرافقاً وصولاً بلا توثيق موافقة، لأن
`core.identity` يشتقّ سياق المريض من الصفّ نفسه لا من إعداد جانبي.

السحب فوريّ: الاشتقاق يقرأ الجدول في كل طلب، ومحفّز في قاعدة البيانات يُبطل
جلسات المرافق المفتوحة في لحظة السحب.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence
from uuid import UUID

from psycopg import errors as pg_errors

from core import db
from core.types import Actor

__all__ = [
    "CaregiverLink",
    "ConsentSource",
    "LinkRefused",
    "for_patient",
    "grant",
    "revoke",
]

#: من أعطى الموافقة: المريض نفسه أو وليّه حين لا يملك المريض الأهلية.
ConsentSource = Literal["PATIENT", "GUARDIAN"]


class LinkRefused(Exception):
    """قاعدة البيانات رفضت الصفّ: دور خاطئ، أو مستأجر مختلف، أو ارتباط قائم."""


@dataclass(frozen=True, slots=True)
class CaregiverLink:
    id: UUID
    tenant_id: UUID
    patient_id: UUID
    caregiver_user_id: UUID
    relationship: str
    consent_text: str
    consent_given_by: ConsentSource
    granted_by: UUID
    granted_at: datetime
    revoked_at: datetime | None
    revoked_by: UUID | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


#: نصّ كل استعلام ثابت وحرفي — لا تركيب ولا تنسيق، ولو لقائمة أعمدة. الصرامة
#: هنا تجعل مراجعة SQL بنظرة ممكنة، وهي أهم من تجنّب التكرار.
_INSERT = """
INSERT INTO caregiver_links
    (tenant_id, patient_id, caregiver_user_id, relationship,
     consent_text, consent_given_by, granted_by)
VALUES (%s, %s, %s, %s, %s, %s, %s)
RETURNING id, tenant_id, patient_id, caregiver_user_id, relationship, consent_text,
          consent_given_by, granted_by, granted_at, revoked_at, revoked_by
"""

_FOR_PATIENT = """
SELECT id, tenant_id, patient_id, caregiver_user_id, relationship, consent_text,
       consent_given_by, granted_by, granted_at, revoked_at, revoked_by
FROM caregiver_links
WHERE patient_id = %s
ORDER BY revoked_at NULLS FIRST, granted_at DESC
"""

_REVOKE = """
UPDATE caregiver_links
SET revoked_at = now(), revoked_by = %s
WHERE id = %s AND revoked_at IS NULL
RETURNING id, tenant_id, patient_id, caregiver_user_id, relationship, consent_text,
          consent_given_by, granted_by, granted_at, revoked_at, revoked_by
"""


def _to_link(row) -> CaregiverLink:
    return CaregiverLink(
        id=row["id"],
        tenant_id=row["tenant_id"],
        patient_id=row["patient_id"],
        caregiver_user_id=row["caregiver_user_id"],
        relationship=row["relationship"],
        consent_text=row["consent_text"],
        consent_given_by=row["consent_given_by"],
        granted_by=row["granted_by"],
        granted_at=row["granted_at"],
        revoked_at=row["revoked_at"],
        revoked_by=row["revoked_by"],
    )


def grant(
    actor: Actor,
    *,
    patient_id: UUID,
    caregiver_user_id: UUID,
    relationship: str,
    consent_text: str,
    consent_given_by: ConsentSource,
) -> CaregiverLink:
    """
    يوثّق موافقة ويمنح المرافق وصولاً إلى بوابة مريض واحد.

    `consent_text` هو النصّ كما عُرض ووُقِّع لا إشارة إلى سياسة: نسخة السياسة
    تتغيّر، وما وافق عليه صاحب الموافقة لا يتغيّر بتغيّرها.
    """
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        try:
            cursor.execute(
                _INSERT,
                (actor.tenant_id, patient_id, caregiver_user_id, relationship,
                 consent_text, consent_given_by, actor.id),
            )
        except (
            pg_errors.CheckViolation,
            pg_errors.ForeignKeyViolation,
            pg_errors.UniqueViolation,
        ) as exc:
            raise LinkRefused(str(exc)) from exc
        return _to_link(cursor.fetchone())


def for_patient(actor: Actor, patient_id: UUID) -> Sequence[CaregiverLink]:
    """كل صفوف الموافقة لمريض، الفاعلة أولاً. المسحوبة تبقى ظاهرة للتدقيق."""
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_FOR_PATIENT, (patient_id,))
        return [_to_link(row) for row in cursor.fetchall()]


def revoke(actor: Actor, link_id: UUID) -> CaregiverLink | None:
    """
    يسحب الموافقة. يُعيد `None` إن كانت مسحوبة أصلاً — لا خطأ: السحب نيّة
    نهائية، وتكرارها لا يغيّر شيئاً.
    """
    with db.session(
        "practitioner", tenant_id=actor.tenant_id, actor_id=actor.id
    ) as cursor:
        cursor.execute(_REVOKE, (actor.id, link_id))
        row = cursor.fetchone()
        return _to_link(row) if row else None
