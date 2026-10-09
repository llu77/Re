"""
مسارات الذكاء الاصطناعي
=======================
ثلاثة مسارات: «راجع» (المراجِع عند ضغطة الاعتماد)، والقرار في ملاحظة، و«اسأل
سيمبول». الأوّل والثالث يرسلان شيئاً إلى مزوّد النموذج فيعتمدان بوّابة
الموافقة (`require_current_terms`) وحدّ المعدّل `ai`؛ والقرار لا يرسل شيئاً
فيكتفي بالجلسة.

حالة المراجعة ليست خطأً: السقوف والقاطع وانشغال المقاعد وأخطاء المزوّد كلها
200 «غير متاح» والعمل يتابع. الأخطاء هنا ما يسبق أيّ استدعاء: موضوعٌ ليس
لصاحب الجلسة (404)، أو صفٌّ تغيّر (409)، أو فحصٌ حتمي رفض حقلاً (422 بحقله)،
أو مهنةٌ أخرى (403).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from eyework import assistant, auth, reviewer
from eyework.service_errors import Invalid
from eyework.web.deps import enforce, require_current_terms, require_user
from eyework.web.errors import AI_INVALID, AI_REVIEW_INVALID, GENERIC, ErrorSpec
from eyework.web.schemas import AssistantBody, DecisionBody, ReviewBody

__all__ = ["router"]

router = APIRouter(prefix="/api/ai")

_PROFESSION = {"code": "PROFESSION", "detail": "هذه الأداة لبوابة مهنةٍ أخرى."}


def _invalid(spec: ErrorSpec, field: str | None) -> JSONResponse:
    content = {"code": spec.code, "detail": spec.detail}
    if field is not None:
        content["field"] = field
    return JSONResponse(status_code=spec.status, content=content)


@router.post("/review")
def review(body: ReviewBody, request: Request, user_id: UUID = Depends(require_current_terms)) -> dict:
    """
    ضغطة «راجع»: ينتظر المراجعة حتى `REVIEW_WAIT_SECONDS` ثم يجيب DONE أو PENDING
    أو UNAVAILABLE. المهنة تُفحص هنا أولاً (403) وفي القاعدة ثانيةً.
    """
    state = request.app.state
    enforce(state.limiters.ai, str(user_id))
    feature = reviewer.FEATURES.get(body.feature)
    if feature is not None and auth.profession_of(state.db, user_id) is not feature.profession:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=dict(_PROFESSION))
    try:
        return reviewer.review(state.db, state.review_runner, user_id, body.feature, body.kind,
                               body.subject_id, body.expected_row_version)
    except Invalid as exc:
        # الفحص الحتمي لمسار العمل: لا استدعاء ولا صفّ، والحقل يعود ليُفتح.
        return _invalid(AI_REVIEW_INVALID, exc.field or exc.code)


@router.post("/flags/{flag_id}/decision")
def decide(flag_id: UUID, body: DecisionBody, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    """«عدّل» أو «تابع رغم ذلك» أو «تراجع». لا يُرسَل شيء، فلا بوّابة موافقة."""
    state = request.app.state
    enforce(state.limiters.mutation, str(user_id))
    return reviewer.decide(state.db, user_id, flag_id, body.action, body.digest)


@router.post("/assistant")
def ask(body: AssistantBody, request: Request, user_id: UUID = Depends(require_current_terms)) -> dict:
    """سؤالٌ واحد عن العمل من شاشةٍ بعينها. الطلب كلّه ينتظر الجواب."""
    state = request.app.state
    enforce(state.limiters.ai, str(user_id))
    try:
        return assistant.ask(state.db, state.gateway, state.ai_guard, user_id, body.screen.kind, body.screen.id,
                             body.question, body.ready_question)
    except Invalid as exc:
        return _invalid(AI_INVALID.get(exc.code, GENERIC), exc.field)
