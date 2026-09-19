"""
نقطة العبور الوحيدة إلى المريض
===============================
هذه الوحدة هي المسار الوحيد الذي يصل به محتوى سريري إلى مريض. كل قراءة مباشرة
من جداول المحتوى في مسار المريض خطأ معماري.

الضمانة مفروضة على مستويين مستقلين، فلا يكفي خرق أحدهما:

1. **الصلاحيات.** دور `app_patient` لا يملك أي صلاحية على `proposals` ولا على
   أي جدول محتوى — `REVOKE ALL` في الترحيل 0001. يرى العرض
   `patient_deliverable_v` فقط، وهو يرشّح الحالة والصلاحية وهوية المريض.
   المسار الالتفافي **مستحيل**، لا ممنوع.
2. **الاستيراد.** اختبار معماري يمسح `api/patient/**` ويفشل إن استورد أي
   مستودع بيانات عدا هذه الوحدة.

لا تضف هنا دالة تقرأ بدور غير `patient`.
"""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from core import db
from core.types import Deliverable, ProposalKind

__all__ = ["get_deliverable", "list_deliverables"]

_COLUMNS = "proposal_id, patient_id, kind, payload, affected_side, approved_at"

# استعلامات كاملة كثوابت: لا نصّ SQL يُركَّب عند نقطة الاستدعاء إطلاقاً،
# فيصير فحص «لا دمج نصي في SQL» صارماً وبسيطاً بدل أن يكون تخمينياً.
_LATEST_OF_KIND = (
    f"SELECT {_COLUMNS} FROM patient_deliverable_v"
    " WHERE kind = %s ORDER BY approved_at DESC LIMIT 1"
)
_ALL_FOR_PATIENT = f"SELECT {_COLUMNS} FROM patient_deliverable_v ORDER BY approved_at DESC"


def _row_to_deliverable(row: dict) -> Deliverable:
    return Deliverable(
        proposal_id=row["proposal_id"],
        patient_id=row["patient_id"],
        kind=row["kind"],
        payload=row["payload"],
        affected_side=row["affected_side"],
        approved_at=row["approved_at"],
    )


def get_deliverable(patient_id: UUID, kind: ProposalKind) -> Deliverable | None:
    """
    آخر محتوى معتمد وسارٍ من هذا النوع لهذا المريض، أو `None`.

    `None` تعني «لا يوجد ما يُسلَّم» — مسوّدة، أو في الطابور، أو مرفوض، أو
    منتهي الصلاحية. لا تميّز الدالة بينها عمداً: مسار المريض لا يعرف بوجود
    محتوى غير معتمد أصلاً.
    """
    with db.session("patient", patient_id=patient_id) as cursor:
        cursor.execute(_LATEST_OF_KIND, (kind,))
        row = cursor.fetchone()
    return _row_to_deliverable(row) if row else None


def list_deliverables(patient_id: UUID) -> Sequence[Deliverable]:
    """كل ما يجوز تسليمه لهذا المريض الآن. قد تكون فارغة، وهذا وضع صحيح."""
    with db.session("patient", patient_id=patient_id) as cursor:
        cursor.execute(_ALL_FOR_PATIENT)
        rows = cursor.fetchall()
    return [_row_to_deliverable(row) for row in rows]
