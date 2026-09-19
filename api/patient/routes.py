"""
بوابة المريض
=============
كل قراءة هنا تمر عبر `core.delivery` — نقطة العبور الوحيدة. لا تستورد هذه
الوحدة `core.db` ولا `core.proposals`، واختبار معماري يفشل إن فعلت.

المريض لا يرى المحتوى غير المعتمد ولا يعرف بوجوده: لا حالة «قيد المراجعة» في
أي استجابة هنا، فالغياب والغياب-قيد-المراجعة يبدوان سواء.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import enforce_auth_rate_limit, patient
from core import delivery
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
