"""
بوابة الممارس
==============
طابور المراجعة وثلاثة إجراءات فقط: اعتماد · تعديل واعتماد · رفض مع سبب.

**لا إجراءات جماعية على المحتوى السريري.** لا توجد هنا نقطة نهاية تقبل مصفوفة
معرّفات؛ كل قرار على مقترح واحد يحمل معرّفه في المسار. هذا قيد مقصود لا سهو:
الموافقة بالجملة تُفرغ المراجعة من معناها.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.deps import enforce_auth_rate_limit, practitioner
from core import caregivers, escalation, proposals
from core.identity import AuthenticationFailed, Principal, authenticate, revoke_session
from core.caregivers import CaregiverLink, ConsentSource
from core.types import AffectedSide, InvalidTransition, Proposal, ProposalKind

router = APIRouter(prefix="/practitioner", tags=["practitioner"])


# ── العقود ──────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    token: str
    role: str


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def reason_is_not_blank(cls, value: str) -> str:
        """الرفض يتطلب سبباً نصياً — مسافات فقط ليست سبباً."""
        if not value.strip():
            raise ValueError("الرفض يتطلب سبباً نصياً")
        return value.strip()


class EditAndApproveRequest(BaseModel):
    payload: dict[str, Any]
    affected_side: AffectedSide | None = None


class CreateProposalRequest(BaseModel):
    patient_id: UUID
    kind: ProposalKind
    payload: dict[str, Any]
    provenance: dict[str, Any] = Field(default_factory=dict)
    affected_side: AffectedSide | None = None
    priority: int = Field(default=5, ge=0, le=9)
    is_red_flag: bool = False


class ProposalView(BaseModel):
    id: UUID
    patient_id: UUID
    kind: str
    status: str
    payload: dict[str, Any]
    provenance: dict[str, Any]
    affected_side: str | None
    priority: int
    is_red_flag: bool
    version: int
    created_at: Any
    queued_at: Any
    expires_at: Any
    reviewer_id: UUID | None
    decision_at: Any
    rejection_reason: str | None

    @classmethod
    def of(cls, proposal: Proposal) -> "ProposalView":
        return cls(
            id=proposal.id,
            patient_id=proposal.patient_id,
            kind=proposal.kind,
            status=proposal.status,
            payload=dict(proposal.payload),
            provenance=dict(proposal.provenance),
            affected_side=proposal.affected_side,
            priority=getattr(proposal, "priority", 5),
            is_red_flag=getattr(proposal, "is_red_flag", False),
            version=proposal.version,
            created_at=proposal.created_at,
            queued_at=proposal.queued_at,
            expires_at=proposal.expires_at,
            reviewer_id=proposal.reviewer_id,
            decision_at=proposal.decision_at,
            rejection_reason=proposal.rejection_reason,
        )


# ── المصادقة ────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    enforce_auth_rate_limit(f"practitioner:{body.email}")
    try:
        token, principal = authenticate(body.email, body.password, "PRACTITIONER")
    except AuthenticationFailed as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="بيانات اعتماد غير صحيحة") from exc
    return LoginResponse(token=token, role=principal.actor.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(principal: Annotated[Principal, practitioner]) -> None:
    revoke_session(principal.session_id)


# ── الطابور والمراجعة ───────────────────────────────────────────────────
@router.get("/queue", response_model=list[ProposalView])
def review_queue(
    principal: Annotated[Principal, practitioner], limit: int = 50
) -> list[ProposalView]:
    """العلامات الحمراء أولاً، ثم الأولوية، ثم زمن الانتظار."""
    queue = proposals.review_queue(principal.actor, limit=min(limit, 200))
    return [ProposalView.of(proposal) for proposal in queue]


@router.post("/proposals", response_model=ProposalView, status_code=status.HTTP_201_CREATED)
def create_proposal(
    principal: Annotated[Principal, practitioner], body: CreateProposalRequest
) -> ProposalView:
    proposal = proposals.create(
        principal.actor,
        patient_id=body.patient_id,
        kind=body.kind,
        payload=body.payload,
        provenance=body.provenance,
        affected_side=body.affected_side,
        priority=body.priority,
        is_red_flag=body.is_red_flag,
    )
    return ProposalView.of(proposal)


@router.get("/proposals/{proposal_id}", response_model=ProposalView)
def read_proposal(
    principal: Annotated[Principal, practitioner], proposal_id: UUID
) -> ProposalView:
    return ProposalView.of(_or_404(proposals.get, proposal_id, principal))


@router.post("/proposals/{proposal_id}/submit", response_model=ProposalView)
def submit_proposal(
    principal: Annotated[Principal, practitioner], proposal_id: UUID
) -> ProposalView:
    return ProposalView.of(_or_404(proposals.submit, proposal_id, principal))


@router.post("/proposals/{proposal_id}/approve", response_model=ProposalView)
def approve_proposal(
    principal: Annotated[Principal, practitioner], proposal_id: UUID
) -> ProposalView:
    """قرار واحد لمقترح واحد."""
    return ProposalView.of(_or_404(proposals.approve, proposal_id, principal))


@router.post("/proposals/{proposal_id}/edit-and-approve", response_model=ProposalView)
def edit_and_approve_proposal(
    principal: Annotated[Principal, practitioner],
    proposal_id: UUID,
    body: EditAndApproveRequest,
) -> ProposalView:
    """التعديل يُحفظ كنسخة جديدة ولا يطمس الأصل."""
    try:
        proposal = proposals.edit_and_approve(
            proposal_id, principal.actor,
            payload=body.payload, affected_side=body.affected_side,
        )
    except proposals.ProposalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="المقترح غير موجود") from exc
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="حالة المقترح لا تسمح بذلك") from exc
    return ProposalView.of(proposal)


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalView)
def reject_proposal(
    principal: Annotated[Principal, practitioner],
    proposal_id: UUID,
    body: Annotated[RejectRequest, Body()],
) -> ProposalView:
    """الرفض يتطلب سبباً نصياً إلزامياً — يفرضه العقد وقيد قاعدة البيانات معاً."""
    try:
        proposal = proposals.reject(proposal_id, principal.actor, body.reason)
    except proposals.ProposalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="المقترح غير موجود") from exc
    except (InvalidTransition, ValueError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="حالة المقترح لا تسمح بذلك") from exc
    return ProposalView.of(proposal)


def _or_404(action, proposal_id: UUID, principal: Principal) -> Proposal:
    try:
        return action(proposal_id, principal.actor)
    except proposals.ProposalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="المقترح غير موجود") from exc
    except InvalidTransition as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="حالة المقترح لا تسمح بذلك") from exc


# ── العلامات الحمراء ────────────────────────────────────────────────────
class RedFlagView(BaseModel):
    id: UUID
    patient_id: UUID
    body: str
    reported_at: Any
    acknowledged_at: Any
    escalation_seconds: float | None


class AcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@router.get("/red-flags", response_model=list[RedFlagView])
def open_red_flags(
    principal: Annotated[Principal, practitioner], limit: int = 50
) -> list[RedFlagView]:
    """البلاغات غير المستلَمة، الأقدم أولاً. تتصدّر ما يراه الممارس."""
    return [
        RedFlagView(
            id=flag.id, patient_id=flag.patient_id, body=flag.body,
            reported_at=flag.reported_at, acknowledged_at=flag.acknowledged_at,
            escalation_seconds=flag.escalation_seconds,
        )
        for flag in escalation.open_reports(principal.actor, limit=limit)
    ]


@router.post("/red-flags/{report_id}/acknowledge", response_model=RedFlagView)
def acknowledge_red_flag(
    principal: Annotated[Principal, practitioner],
    report_id: UUID,
    body: AcknowledgeRequest | None = None,
) -> RedFlagView:
    """يسجّل الاستلام مرة واحدة، ومنه يُحسب زمن التصعيد."""
    try:
        flag = escalation.acknowledge(
            report_id, principal.actor, note=body.note if body else None
        )
    except escalation.AlreadyAcknowledged as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="البلاغ مُستلَم بالفعل"
        ) from exc
    return RedFlagView(
        id=flag.id, patient_id=flag.patient_id, body=flag.body,
        reported_at=flag.reported_at, acknowledged_at=flag.acknowledged_at,
        escalation_seconds=flag.escalation_seconds,
    )


# ── موافقة المرافق ──────────────────────────────────────────────────────
class GrantCaregiverRequest(BaseModel):
    """
    توثيق موافقة ومنح وصول في فعل واحد.

    الحقلان معاً إلزاميان: لا يوجد منحٌ بلا نصّ موافقة، ولا توثيقُ موافقة
    بلا منح — فالصفّ الواحد هو الاثنان.
    """

    caregiver_user_id: UUID
    relationship: str = Field(min_length=1, max_length=200)
    consent_text: str = Field(min_length=1, max_length=8000)
    consent_given_by: ConsentSource

    @field_validator("relationship", "consent_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("الحقل لا يكون مسافات")
        return value.strip()


class CaregiverLinkView(BaseModel):
    id: UUID
    patient_id: UUID
    caregiver_user_id: UUID
    relationship: str
    consent_text: str
    consent_given_by: str
    granted_by: UUID
    granted_at: Any
    revoked_at: Any
    is_active: bool

    @classmethod
    def of(cls, link: CaregiverLink) -> "CaregiverLinkView":
        return cls(
            id=link.id,
            patient_id=link.patient_id,
            caregiver_user_id=link.caregiver_user_id,
            relationship=link.relationship,
            consent_text=link.consent_text,
            consent_given_by=link.consent_given_by,
            granted_by=link.granted_by,
            granted_at=link.granted_at,
            revoked_at=link.revoked_at,
            is_active=link.is_active,
        )


@router.get("/patients/{patient_id}/caregivers", response_model=list[CaregiverLinkView])
def patient_caregivers(
    principal: Annotated[Principal, practitioner], patient_id: UUID
) -> list[CaregiverLinkView]:
    """الموافقات الفاعلة أولاً، والمسحوبة بعدها — السجل كله مرئي للممارس."""
    return [
        CaregiverLinkView.of(link)
        for link in caregivers.for_patient(principal.actor, patient_id)
    ]


@router.post(
    "/patients/{patient_id}/caregivers",
    response_model=CaregiverLinkView,
    status_code=status.HTTP_201_CREATED,
)
def grant_caregiver(
    principal: Annotated[Principal, practitioner],
    patient_id: UUID,
    body: GrantCaregiverRequest,
) -> CaregiverLinkView:
    try:
        link = caregivers.grant(
            principal.actor,
            patient_id=patient_id,
            caregiver_user_id=body.caregiver_user_id,
            relationship=body.relationship,
            consent_text=body.consent_text,
            consent_given_by=body.consent_given_by,
        )
    except caregivers.LinkRefused as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="تعذّر منح المرافق: الحساب ليس بدور مرافق، أو من مستأجر آخر،"
                   " أو مرتبط بمريض آخر بموافقة سارية.",
        ) from exc
    return CaregiverLinkView.of(link)


@router.post("/caregivers/{link_id}/revoke", response_model=CaregiverLinkView)
def revoke_caregiver(
    principal: Annotated[Principal, practitioner], link_id: UUID
) -> CaregiverLinkView:
    """
    يسحب الموافقة. الوصول ينقطع في اللحظة نفسها: جلسات المرافق المفتوحة
    تُبطَل بمحفّز، واشتقاق سياق المريض يقرأ الصفّ في كل طلب.
    """
    link = caregivers.revoke(principal.actor, link_id)
    if link is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="الموافقة مسحوبة أصلاً أو غير موجودة"
        )
    return CaregiverLinkView.of(link)
