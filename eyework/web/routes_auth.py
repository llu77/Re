"""
مسارات الدخول
=============
الحساب بالتسجيل أو بالدعوة، ولا «نسيت كلمة المرور»: رابط تفعيلٍ جديد من
المشغّل هو الاسترداد. وكل فشلٍ في الدخول برسالةٍ واحدة لا تقول أيّ الحقلين
أخطأ؛ أما التسجيل فيقول أيّ حقلٍ يُصلَح، لأن صاحبه هو من كتبه.

ومفتاح المرور طريقٌ ثانٍ إلى الجلسة نفسها: بلا اسمٍ ولا كلمة، وكل فشلٍ فيه
برسالةٍ واحدة كذلك. يُضاف من حسابٍ دخله صاحبه، ولا يحلّ محلّ كلمة المرور.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from eyework import auth, campaigns, money, passkeys
from eyework.copy_rules import EDIT_NOTE_MAX, MAX_PRESETS, PRESET_CONFLICTS, EditPreset
from eyework.professions import NAMES, TAGLINES, Profession
from eyework.web.deps import COOKIE, COOKIE_MAX_AGE, client_ip, enforce, require_user, session_token
from eyework.web.errors import REGISTRATION
from eyework.web.schemas import (
    ActivateBody,
    LoginBody,
    PasskeyAddBody,
    PasskeyLoginBody,
    RegisterBody,
    SignupCodeBody,
)

__all__ = ["router"]

router = APIRouter(prefix="/api")

_FAILED = {"code": "LOGIN", "detail": "بيانات الدخول غير صحيحة."}
_ACTIVATION_FAILED = {"code": "ACTIVATION", "detail": "رابط التفعيل غير صالح أو منتهٍ. اطلب رابطاً جديداً ممن دعاك."}
_PASSKEY_FAILED = {"code": "PASSKEY", "detail": "تعذّر الدخول بمفتاح المرور. حاول مرة أخرى، أو ادخل بكلمة المرور."}
_PASSKEY_NOT_ADDED = {"code": "PASSKEY_ADD", "detail": "لم يُحفظ مفتاح المرور. حاول مرة أخرى."}


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


@router.post("/auth/passkey/options")
async def passkey_login_options(request: Request) -> dict:
    """
    خيارات الدخول بمفتاح المرور. بلا جسم: لا اسم يُسأل عنه، فلا يُعرف من الجواب
    إن كان لأحدٍ حساب. تُطلب حين تُعرض شاشة الدخول لا داخل الضغطة: الجلب داخلها
    قد يستنفد مهلة التفعيل في WebKit (خمس ثوانٍ).
    """
    state = request.app.state
    enforce(state.limiters.passkey_ip, client_ip(request))
    return await run_in_threadpool(passkeys.login_options, state.db, state.settings.public_origin)


@router.post("/auth/passkey", status_code=status.HTTP_204_NO_CONTENT)
async def passkey_login(body: PasskeyLoginBody, request: Request) -> Response:
    state = request.app.state
    enforce(state.limiters.passkey_ip, client_ip(request))
    try:
        token = await run_in_threadpool(
            passkeys.sign_in, state.db, state.settings.login_key, state.settings.public_origin,
            body.model_dump(exclude_none=True))
    except passkeys.PasskeyRejected:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=_PASSKEY_FAILED)
    previous = session_token(request)
    if previous:
        await run_in_threadpool(auth.logout, state.db, previous)
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


def _registration_error(key: str) -> JSONResponse:
    spec = REGISTRATION[key]
    headers = {"Retry-After": str(spec.retry_after)} if spec.retry_after else None
    return JSONResponse(status_code=spec.status, headers=headers,
                        content={"code": spec.code, "field": key, "detail": spec.detail})


@router.post("/auth/signup-code", status_code=status.HTTP_204_NO_CONTENT)
async def signup_code(body: SignupCodeBody, request: Request) -> Response:
    """
    هل يصلح رمز الرابط؟ تسأله الواجهة قبل الخطوة الأولى، فلا يملأ أحدٌ تسع شاشاتٍ
    برمزٍ منتهٍ. لا يكشف شيئاً عن الحسابات، ويُعدّ على حدّ العنوان.
    """
    state = request.app.state
    if not state.settings.registration_open:
        return _registration_error("CLOSED")
    enforce(state.limiters.register_ip, client_ip(request))
    if not await run_in_threadpool(auth.signup_code_usable, state.db, body.code):
        return _registration_error("CODE")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/register", status_code=status.HTTP_204_NO_CONTENT)
async def register(body: RegisterBody, request: Request) -> Response:
    state = request.app.state
    if not state.settings.registration_open:
        return _registration_error("CLOSED")
    try:
        name = auth.check_name(body.name)
        birth_date = auth.check_birth_date(body.birth_date)
        email = auth.check_email(body.email)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    # الحدّ بعد فحص الشكل: خطأٌ في حقلٍ لا يمسّ القاعدة ولا يستهلك محاولة.
    enforce(state.limiters.register_ip, client_ip(request))
    try:
        token = await run_in_threadpool(
            auth.register, state.db, state.settings.login_key, code=body.code, name=name,
            birth_date=birth_date, email=email, password=body.password, profession=body.profession)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    except auth.RegistrationCodeInvalid:
        return _registration_error("CODE")
    except auth.RegistrationTaken:
        return _registration_error("TAKEN")
    previous = session_token(request)
    if previous:
        await run_in_threadpool(auth.logout, state.db, previous)
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


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """
    يحذف صاحب الجلسة حسابه وكل بياناته. التأكيد خطوتان في الواجهة؛ وهنا الحذف
    نفسه، لا يُعاد ولا يُسترجع.
    """
    auth.delete_me(request.app.state.db, user_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return response


@router.post("/me/passkeys/options")
def add_passkey_options(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    """خيارات إضافة مفتاح مرورٍ لصاحب الجلسة. 409 إن بلغ سقف المفاتيح."""
    state = request.app.state
    enforce(state.limiters.passkey_add, str(user_id))
    return passkeys.add_options(state.db, state.settings.login_key, state.settings.public_origin, user_id)


@router.post("/me/passkeys", status_code=status.HTTP_204_NO_CONTENT)
def add_passkey(body: PasskeyAddBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """
    يحفظ مفتاحاً تحقّق منه الخادم. المفتاح لصاحب الجلسة دائماً: الجسم لا يسمّي
    حساباً، والتحدّي صدر له وحده.
    """
    state = request.app.state
    enforce(state.limiters.passkey_add, str(user_id))
    try:
        passkeys.add(state.db, state.settings.public_origin, user_id, body.model_dump(exclude_none=True))
    except passkeys.PasskeyRejected:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_PASSKEY_NOT_ADDED)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    """
    ما تحتاجه الواجهة لتفتح البوابة وتحيّي صاحبها: مهنته، واسمه، وما بقي من
    طلبات اليوم. لا معرّف ولا بريد ولا تاريخ ميلاد.
    """
    db = request.app.state.db
    profession = auth.profession_of(db, user_id)
    return {
        "generations_left": campaigns.remaining_generations(db, user_id),
        "display_name": campaigns.display_name(db, user_id),
        "profession": profession.value if profession else None,
    }


@router.get("/choices")
def choices(request: Request) -> dict:
    """
    كل ما تعرضه الواجهة للاختيار، من الخادم وحده: قيم الميزانية والمدّة
    بكلماتها، وخيارات التعديل وتعارضاتها، والحدود.

    الواجهة تبحث في هذا الجدول ولا تحسب: لا كلمة ولا حدّ ولا خطوة تُشتقّ في
    المتصفّح، فلا تختلف الواجهة عن القاعدة.
    """
    return {
        **money.choices(),
        "registration_open": request.app.state.settings.registration_open,
        "registration": {
            "name_max": auth.NAME_MAX,
            "password_min": auth.PASSWORD_MIN,
            "earliest_year": 1900,
            "terms_version": auth.TERMS_VERSION,
        },
        "professions": [{"code": p.value, "name": NAMES[p], "tagline": TAGLINES[p]} for p in Profession],
        "edit_presets": [preset.value for preset in EditPreset],
        "preset_conflicts": [sorted(p.value for p in pair) for pair in PRESET_CONFLICTS],
        "limits": {
            "note_max": EDIT_NOTE_MAX,
            "presets_max": MAX_PRESETS,
            "versions_max": campaigns.VERSIONS_PER_CAMPAIGN,
            "page_size": campaigns.PAGE_SIZE,
        },
    }
