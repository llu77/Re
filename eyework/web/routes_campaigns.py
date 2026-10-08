"""
مسارات الحملة
=============
كل مسارٍ يسمّي حملةً واحدة في مساره، ولا مسار يقبل قائمة: لا قرار جماعي.
وكل كتابةٍ تحمل `expected_row_version` — ما رآه صاحبها — فالضغطة المكرّرة
بالعين تُرفض بـ409 بدل أن تُطبَّق مرتين.

حملة غيرك ⇒ 404 لا 403: لا يُكشف أنها موجودة.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from eyework import campaigns, images
from eyework.professions import Profession
from eyework.web.deps import enforce, require_profession, require_user
from eyework.web.errors import UNUSABLE
from eyework.web.schemas import (
    ApproveBody,
    BudgetBody,
    ConfirmBody,
    DaysBody,
    EditBody,
    RestoreBody,
    RowVersionBody,
)

__all__ = ["router"]

#: الحملة أداة بوابة التسويق وحدها.
router = APIRouter(prefix="/api/campaigns", dependencies=[Depends(require_profession(Profession.MARKETING))])

_CHUNK = 64 * 1024


async def _read_image(request: Request) -> images.ProcessedImage:
    """
    الجسم الخام بحدٍّ صلب، في الذاكرة لا على القرص.

    لا multipart: محلّل Starlette يكتب ما يتجاوز ميغابايتاً إلى ملفٍّ مؤقت —
    أي النسخة الأصلية بموقع التقاطها على قرص الخادم. والطول يُفحص من
    الترويسة قبل أن يُقرأ بايتٌ واحد.
    """
    if request.headers.get("content-type", "").split(";")[0].strip() not in images.ACCEPTED_TYPES:
        raise images.ImageRejected("UNSUPPORTED_TYPE")
    declared = request.headers.get("content-length")
    if declared is None or not declared.isdigit():
        raise HTTPException(status.HTTP_411_LENGTH_REQUIRED,
                            detail={"code": "LENGTH", "detail": "حجم الصورة مطلوب."})
    if int(declared) > images.MAX_UPLOAD_BYTES:
        raise images.ImageRejected("TOO_LARGE")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > images.MAX_UPLOAD_BYTES:
            raise images.ImageRejected("TOO_LARGE")
    return await run_in_threadpool(images.process, bytes(body))


def _generation_result(result) -> dict:
    if isinstance(result, campaigns.Unusable):
        return {"result": "UNUSABLE_PHOTO", "reason": result.reason,
                "message": UNUSABLE.get(result.reason, UNUSABLE["NO_PRODUCT"]),
                "assistant_note": result.note, "campaign": result.view}
    return {"result": "OK", "message": None, "campaign": result}


@router.get("")
def list_campaigns(request: Request, page: int = Query(1, ge=1, le=campaigns.MAX_PAGE),
                   user_id: UUID = Depends(require_user)) -> dict:
    return campaigns.list_page(request.app.state.db, user_id, page)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.upload, str(user_id))
    image = await _read_image(request)
    return await run_in_threadpool(campaigns.create, request.app.state.db, user_id, image)


@router.get("/{campaign_id}")
def get(campaign_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> dict:
    return campaigns.get(request.app.state.db, user_id, campaign_id)


@router.get("/{campaign_id}/image")
def image(campaign_id: UUID, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    enforce(request.app.state.limiters.image, str(user_id))
    jpeg = campaigns.image_bytes(request.app.state.db, user_id, campaign_id)
    return Response(content=jpeg, media_type="image/jpeg", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": 'inline; filename="product.jpg"',
    })


@router.put("/{campaign_id}/image")
async def replace_image(campaign_id: UUID, request: Request,
                        expected_row_version: int = Query(..., ge=1, le=2_000_000_000),
                        user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.upload, str(user_id))
    image = await _read_image(request)
    return await run_in_threadpool(
        campaigns.replace_image, request.app.state.db, user_id, campaign_id, expected_row_version, image)


@router.post("/{campaign_id}/copy")
def generate(campaign_id: UUID, body: RowVersionBody, request: Request,
             user_id: UUID = Depends(require_user)) -> dict:
    state = request.app.state
    enforce(state.limiters.mutation, str(user_id))
    return _generation_result(campaigns.generate(
        state.db, state.copywriter, user_id, campaign_id, body.expected_row_version))


@router.post("/{campaign_id}/copy/edit")
def edit(campaign_id: UUID, body: EditBody, request: Request,
         user_id: UUID = Depends(require_user)) -> dict:
    state = request.app.state
    enforce(state.limiters.mutation, str(user_id))
    return _generation_result(campaigns.edit(
        state.db, state.copywriter, user_id, campaign_id, body.expected_row_version,
        body.expected_version_id, list(body.presets), body.note))


@router.post("/{campaign_id}/copy/approve")
def approve(campaign_id: UUID, body: ApproveBody, request: Request,
            user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.approve(request.app.state.db, user_id, campaign_id,
                             body.expected_row_version, body.version_id)


@router.post("/{campaign_id}/copy/restore")
def restore(campaign_id: UUID, body: RestoreBody, request: Request,
            user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.restore(request.app.state.db, user_id, campaign_id,
                             body.expected_row_version, body.expected_version_id, body.target)


@router.post("/{campaign_id}/copy/unapprove")
def unapprove(campaign_id: UUID, body: RowVersionBody, request: Request,
              user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.unapprove(request.app.state.db, user_id, campaign_id, body.expected_row_version)


@router.put("/{campaign_id}/budget")
def set_budget(campaign_id: UUID, body: BudgetBody, request: Request,
               user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.set_budget(request.app.state.db, user_id, campaign_id,
                                body.expected_row_version, body.budget_sar)


@router.put("/{campaign_id}/days")
def set_days(campaign_id: UUID, body: DaysBody, request: Request,
             user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.set_days(request.app.state.db, user_id, campaign_id, body.expected_row_version, body.days)


@router.post("/{campaign_id}/confirm")
def confirm(campaign_id: UUID, body: ConfirmBody, request: Request,
            user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.confirm(request.app.state.db, user_id, campaign_id, body.expected_row_version,
                             body.version_id, body.budget_sar, body.days)


@router.post("/{campaign_id}/cancel")
def cancel(campaign_id: UUID, body: RowVersionBody, request: Request,
           user_id: UUID = Depends(require_user)) -> dict:
    enforce(request.app.state.limiters.mutation, str(user_id))
    return campaigns.cancel(request.app.state.db, user_id, campaign_id, body.expected_row_version)
