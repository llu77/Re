"""
أنواع المجال — مصدر الحقيقة الوحيد
===================================
كل مخرج ذكاء اصطناعي قابل للاعتماد هو `Proposal`. لا شيء يصل المريض إلا عبر
`core.delivery`، ولا يُسلَّم إلا ما حالته في `DELIVERABLE_STATUSES`.

`ALLOWED_TRANSITIONS` هنا هو المصدر الوحيد لآلة الحالات: الترحيل يملأ منه جدول
`proposal_transition`، والمحفّز في قاعدة البيانات يقرأ ذلك الجدول. اختبار يقارن
الاثنين فيمنع انحرافهما.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping
from uuid import UUID

__all__ = [
    "ALLOWED_TRANSITIONS",
    "Actor",
    "AffectedSide",
    "DELIVERABLE_STATUSES",
    "EVIDENCE_REQUIRED_KINDS",
    "Deliverable",
    "Gate",
    "PROPOSAL_TTL",
    "Proposal",
    "ProposalKind",
    "ProposalStatus",
    "Role",
    "TERMINAL_STATUSES",
    "SIDE_REQUIRED_KINDS",
    "InvalidTransition",
]

ProposalKind = Literal[
    "PLAN", "PLAN_UPDATE", "ILLUSTRATION_SET", "READINESS", "DOCUMENTATION"
]
ProposalStatus = Literal[
    "DRAFT", "PENDING", "APPROVED", "EDITED_APPROVED", "REJECTED", "EXPIRED"
]
Role = Literal["PRACTITIONER", "ADMIN", "PATIENT", "CAREGIVER"]

#: بوابتان بمصادقة مستقلة. جلسة إحداهما لا تصلح للأخرى.
Gate = Literal["PRACTITIONER", "PATIENT"]

AffectedSide = Literal["LEFT", "RIGHT", "BILATERAL"]

#: مقترح لم يُراجع خلال هذه المدة يصبح EXPIRED ولا يُسلَّم أبداً.
PROPOSAL_TTL = timedelta(hours=48)

#: الحالتان الوحيدتان القابلتان للتسليم للمريض.
DELIVERABLE_STATUSES: frozenset[str] = frozenset({"APPROVED", "EDITED_APPROVED"})

#: أنواع لا تدخل طابور المراجعة بلا استشهاد واحد على الأقل — القاعدة 3.
#:
#: نظيرها في قاعدة البيانات جدول `evidence_required_kind`، والمحفّز هو الذي
#: يفرض المنع لا هذا الثابت؛ واختبار يقارن الاثنين فيمنع انحرافهما.
#:
#: خارج القائمة عمداً: `ILLUSTRATION_SET` يرث دليل الخطة التي يتبعها، و
#: `DOCUMENTATION` يسجّل ما جرى فعلاً لا توصية — وإلزامه باستشهاد يُنتج
#: استشهاداً شكلياً يُضعف معنى البوابة بدل أن يقوّيها.
EVIDENCE_REQUIRED_KINDS: frozenset[str] = frozenset(
    {"PLAN", "PLAN_UPDATE", "READINESS"}
)

#: أنواع يستحيل تمثيلها بلا جانب مصاب — مفروض أيضاً بقيد CHECK في المخطط.
SIDE_REQUIRED_KINDS: frozenset[str] = frozenset({"ILLUSTRATION_SET"})

#: آلة الحالات. الانتقال غير المسموح يرمي خطأ، ولا يوجد انتقال خارج هذا الجدول.
ALLOWED_TRANSITIONS: Mapping[ProposalStatus, frozenset[ProposalStatus]] = {
    "DRAFT": frozenset({"PENDING"}),
    "PENDING": frozenset({"APPROVED", "EDITED_APPROVED", "REJECTED", "EXPIRED"}),
    "APPROVED": frozenset(),
    "EDITED_APPROVED": frozenset(),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
}

#: حالات نهائية — لا تُعدَّل بعدها.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    status for status, onward in ALLOWED_TRANSITIONS.items() if not onward
)


class InvalidTransition(Exception):
    """انتقال حالة غير مسموح. يُرفع قبل بلوغ قاعدة البيانات وتُرفعه هي أيضاً."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"انتقال غير مسموح: {current} ← {target}")
        self.current = current
        self.target = target


@dataclass(frozen=True, slots=True)
class Actor:
    """من ينفّذ الفعل. كل كتابة تُنسب إلى فاعل، ولا فعل بلا فاعل."""

    id: UUID
    role: Role
    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class Proposal:
    """مخرج قابل للاعتماد. لا يصل المريض إلا بعد قرار ممارس مسمّى."""

    id: UUID
    patient_id: UUID
    tenant_id: UUID
    kind: ProposalKind
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    queued_at: datetime | None = None
    reviewer_id: UUID | None = None
    decision_at: datetime | None = None
    rejection_reason: str | None = None
    affected_side: AffectedSide | None = None
    version: int = 1

    @property
    def is_deliverable(self) -> bool:
        """الحالة وحدها لا تكفي — الصلاحية شرط مستقل يُفحص عند التسليم."""
        return self.status in DELIVERABLE_STATUSES


@dataclass(frozen=True, slots=True)
class Deliverable:
    """ما يصل المريض فعلاً. لا يُبنى إلا داخل `core.delivery`."""

    proposal_id: UUID
    patient_id: UUID
    kind: ProposalKind
    payload: Mapping[str, Any]
    affected_side: AffectedSide | None
    approved_at: datetime


def can_transition(current: str, target: str) -> bool:
    """هل الانتقال مسموح؟ نفس الجدول الذي يفرضه المحفّز في قاعدة البيانات."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
