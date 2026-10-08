"""
مسارات الدخول
=============
لا تسجيل ولا «نسيت كلمة المرور»: الحساب بدعوة، ورابط تفعيلٍ جديد هو
الاسترداد. وكل فشلٍ برسالةٍ واحدة لا تقول أيّ الحقلين أخطأ.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from eyework import auth, campaigns, money
from eyework.copy_rules import EDIT_NOTE_MAX, MAX_PRESETS, PRESET_CONFLICTS, EditPreset
from eyework.web.deps import COOKIE, COOKIE_MAX_AGE, client_ip, enforce, require_user, session_token
from eyework.web.schemas import ActivateBody, LoginBody

__all__ = ["router"]

router = APIRouter(prefix="/api")

_FAILED = {"code": "LOGIN", "detail": "بيانات الدخول غير صحيحة."}
_ACTIVATION_FAILED = {"code": "ACTIVATION", "detail": "رابط التفعيل غير صالح أو منتهٍ. اطلب رابطاً جديداً ممن دعاك."}


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=COOKIE_MAX_AGE, path="/", secure=True, httponly=True, samesite="strict",
    )


@router.post("/auth/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginBody, request: Request) -> Response:
    state = request.app.state
    ip = client_ip(request)
    enforce(state.limiters.login_ip, ip)
    # المفتاح هو HMAC الاسم لا الاسم نفسه: الذاكرة لا تحمل أسماء الدخول.
    name = auth.login_hmac(state.settings.login_key, body.username).hex()
    enforce(state.limiters.login_name_ip, f"{name}:{ip}")
    enforce(state.limiters.login_name, name)
    try:
        token = await run_in_threadpool(
            auth.login, state.db, state.settings.login_key, body.username, body.password)
    except auth.AuthenticationFailed:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=_FAILED)
    # دخولٌ ناجح لا يترك الجلسة السابقة على هذا الجهاز قائمةً بلا صاحب.
    previous = session_token(request)
    if previous:
        await run_in_threadpool(auth.logout, state.db, previous)
    state.limiters.login_name_ip.reset(f"{name}:{ip}")
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_session(response, token)
    return response


@router.post("/auth/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate(body: ActivateBody, request: Request) -> Response:
    state = request.app.state
    enforce(state.limiters.activate_ip, client_ip(request))
    try:
        token = await run_in_threadpool(
            auth.activate, state.db, state.settings.login_key, body.token, body.username, body.password)
    except auth.AuthenticationFailed:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_ACTIVATION_FAILED)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _set_session(response, token)
    return response


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    token = session_token(request)
    if token:
        auth.logout(request.app.state.db, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return response


@router.get("/me")
def me(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    """لا معرّف ولا اسم: الواجهة لا تحتاج إلا ما تبقّى من طلبات اليوم."""
    db = request.app.state.db
    return {
        "generations_left": campaigns.remaining_generations(db, user_id),
        "display_name": campaigns.display_name(db, user_id),
    }


@router.get("/choices")
def choices() -> dict:
    """
    كل ما تعرضه الواجهة للاختيار، من الخادم وحده: قيم الميزانية والمدّة
    بكلماتها، وخيارات التعديل وتعارضاتها، والحدود.

    الواجهة تبحث في هذا الجدول ولا تحسب: لا كلمة ولا حدّ ولا خطوة تُشتقّ في
    المتصفّح، فلا تختلف الواجهة عن القاعدة.
    """
    return {
        **money.choices(),
        "edit_presets": [preset.value for preset in EditPreset],
        "preset_conflicts": [sorted(p.value for p in pair) for pair in PRESET_CONFLICTS],
        "limits": {
            "note_max": EDIT_NOTE_MAX,
            "presets_max": MAX_PRESETS,
            "versions_max": campaigns.VERSIONS_PER_CAMPAIGN,
            "page_size": campaigns.PAGE_SIZE,
        },
    }
