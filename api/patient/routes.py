"""
بوابة المريض
=============
كل قراءة هنا تمر عبر `core.delivery` — نقطة العبور الوحيدة. لا تستورد هذه
الوحدة `core.db` ولا `core.proposals`، واختبار معماري يفشل إن فعلت.

المريض لا يرى المحتوى غير المعتمد ولا يعرف بوجوده: لا حالة «قيد المراجعة» في
أي استجابة هنا، فالغياب والغياب-قيد-المراجعة يبدوان سواء.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from api.deps import enforce_auth_rate_limit, patient
from core import delivery, escalation, sessions
from core.identity import AuthenticationFailed, Principal, authenticate, revoke_session
from core.types import Deliverable, ProposalKind

router = APIRouter(prefix="/patient", tags=["patient"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    token: str


class DeliverableView(BaseModel):
    """ما يصل المريض. لا حالة ولا مراجِع ولا سبب رفض — لا شيء من ذلك يخصه."""

    id: UUID
    kind: str
    content: dict[str, Any]
    affected_side: str | None
    approved_at: Any

    @classmethod
    def of(cls, item: Deliverable) -> "DeliverableView":
        return cls(
            id=item.proposal_id,
            kind=item.kind,
            content=dict(item.payload),
            affected_side=item.affected_side,
            approved_at=item.approved_at,
        )


def _patient_id(principal: Principal) -> UUID:
    if principal.patient_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="هذا الحساب غير مرتبط بملف مريض"
        )
    return principal.patient_id


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    enforce_auth_rate_limit(f"patient:{body.email}")
    try:
        token, _ = authenticate(body.email, body.password, "PATIENT")
    except AuthenticationFailed as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="بيانات اعتماد غير صحيحة") from exc
    return LoginResponse(token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(principal: Annotated[Principal, patient]) -> None:
    revoke_session(principal.session_id)


class ActingAsView(BaseModel):
    """
    من يستخدم البوابة الآن: المريض نفسه أم مرافقه.

    لا معرّف ولا اسم ولا شيء سريري — الغرض الوحيد أن تُظهر الواجهة الصفة،
    فلا يُسجَّل أداءٌ باسم المريض وأحدهما يظن أنه الآخر.
    """

    acting_as: Literal["PATIENT", "CAREGIVER"]


@router.get("/session", response_model=ActingAsView)
def current_session(principal: Annotated[Principal, patient]) -> ActingAsView:
    _patient_id(principal)   # حساب بلا سياق مريض لا جلسة له
    acting = "CAREGIVER" if principal.actor.role == "CAREGIVER" else "PATIENT"
    return ActingAsView(acting_as=acting)


@router.get("/plan", response_model=DeliverableView | None)
def current_plan(principal: Annotated[Principal, patient]) -> DeliverableView | None:
    """
    الخطة المعتمدة السارية، أو لا شيء.

    `null` لا تكشف إن كانت هناك خطة قيد المراجعة — المريض يبقى على آخر نسخة
    معتمدة، ولا يرى ما لم يُعتمد بعد.
    """
    item = delivery.get_deliverable(_patient_id(principal), "PLAN")
    return DeliverableView.of(item) if item else None


@router.get("/content/{kind}", response_model=DeliverableView | None)
def current_content(
    principal: Annotated[Principal, patient], kind: ProposalKind
) -> DeliverableView | None:
    item = delivery.get_deliverable(_patient_id(principal), kind)
    return DeliverableView.of(item) if item else None


@router.get("/content", response_model=list[DeliverableView])
def all_content(principal: Annotated[Principal, patient]) -> list[DeliverableView]:
    items = delivery.list_deliverables(_patient_id(principal))
    return [DeliverableView.of(item) for item in items]


# ── تسجيل الجلسة ────────────────────────────────────────────────────────
class SessionRequest(BaseModel):
    """
    تسجيلة جلسة من الجهاز.

    `client_uuid` و`occurred_at` من الجهاز عمداً: العمل دون اتصال يعني أن
    المريض سجّل قبل أن يصل الخادم. الأول يمنع تكرار المزامنة، والثاني يجعل
    الجلسة تُحسب في يومها لا في يوم وصولها.
    """

    plan_id: UUID
    outcome: Literal["DONE", "PARTIAL", "UNABLE"]
    client_uuid: UUID
    occurred_at: datetime | None = None
    step_index: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=2000)
    difficulty: int | None = Field(default=None, ge=0, le=10)
    pain: int | None = Field(default=None, ge=0, le=10)


class SessionView(BaseModel):
    id: UUID
    outcome: str
    occurred_at: Any
    day: Any


class DayView(BaseModel):
    day: Any
    sessions: int
    completed: int


class ProgressView(BaseModel):
    """تقدّم المريض بلغته هو: أيام سجّل فيها، لا مصطلحات سريرية."""

    since: Any
    until: Any
    total_days: int
    adherent_days: int
    percentage: float
    days: list[DayView]
    done_today: bool


class RedFlagRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def body_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("البلاغ يحتاج نصاً")
        return value.strip()


class RedFlagView(BaseModel):
    """
    استلام فقط.

    لا حقل هنا يحمل تقييماً ولا طمأنة ولا نصيحة: النص ثابت في
    `core.escalation.ACKNOWLEDGEMENT` ولا يمر بأي نموذج لغوي.
    """

    id: UUID
    reported_at: Any
    acknowledgement: str


@router.post("/sessions", response_model=SessionView, status_code=status.HTTP_201_CREATED)
def record_session(
    principal: Annotated[Principal, patient], body: SessionRequest
) -> SessionView:
    """
    يسجّل أداء المريض. إعادة الإرسال بنفس `client_uuid` تُعيد نفس التسجيلة.
    """
    try:
        recorded = sessions.record(
            tenant_id=principal.actor.tenant_id,
            patient_id=_patient_id(principal),
            plan_id=body.plan_id,
            outcome=body.outcome,
            recorded_by=principal.actor.id,
            client_uuid=body.client_uuid,
            occurred_at=body.occurred_at,
            step_index=body.step_index,
            reason=body.reason,
            difficulty=body.difficulty,
            pain=body.pain,
        )
    except sessions.PlanNotDeliverable as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="لا يمكن تسجيل جلسة على هذه الخطة.",
        ) from exc

    return SessionView(
        id=recorded.id,
        outcome=recorded.outcome,
        occurred_at=recorded.occurred_at,
        day=recorded.local_day,
    )


@router.get("/progress", response_model=ProgressView)
def progress(principal: Annotated[Principal, patient], days: int = 30) -> ProgressView:
    patient_id = _patient_id(principal)
    window = sessions.adherence(patient_id, days=max(1, min(days, 365)))
    return ProgressView(
        since=window.since,
        until=window.until,
        total_days=window.total_days,
        adherent_days=window.adherent_days,
        percentage=window.percentage,
        days=[DayView(day=d.day, sessions=d.sessions, completed=d.completed)
              for d in window.days],
        done_today=sessions.did_session_today(patient_id),
    )


@router.post("/red-flag", response_model=RedFlagView, status_code=status.HTTP_201_CREATED)
def raise_red_flag(
    principal: Annotated[Principal, patient], body: RedFlagRequest
) -> RedFlagView:
    """
    يرفع بلاغاً إلى طابور الممارس فوراً.

    الاستجابة تأكيد استلام وحسب. لا يُصنَّف البلاغ ولا يُقيَّم هنا، ولا
    يتلقى المريض أي محتوى سريري رداً عليه.
    """
    flag, acknowledgement = escalation.report(
        tenant_id=principal.actor.tenant_id,
        patient_id=_patient_id(principal),
        body=body.body,
        reported_by=principal.actor.id,
    )
    return RedFlagView(
        id=flag.id, reported_at=flag.reported_at, acknowledgement=acknowledgement
    )
