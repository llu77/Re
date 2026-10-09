"""
مسارات الدخول
=============
الحساب بالتسجيل المفتوح، أو برابط المشغّل، أو بالدعوة — والخادم وحده يقرّر الوضع
(`EYEWORK_REGISTRATION`) — ولا «نسيت كلمة المرور»: رابط تفعيلٍ جديد من المشغّل
هو الاسترداد، ومن سجّل بلا رابط يطلبه كتابةً إلى بريد المشغّل (`support_contact`).
وكل فشلٍ في الدخول برسالةٍ واحدة لا تقول أيّ الحقلين أخطأ؛ أما التسجيل فيقول
أيّ حقلٍ يُصلَح، لأن صاحبه هو من كتبه.

ومفتاح المرور طريقٌ ثانٍ إلى الجلسة نفسها: بلا اسمٍ ولا كلمة، وكل فشلٍ فيه
برسالةٍ واحدة كذلك. يُنشئه المتصفّح بعد الدخول بكلمة المرور مباشرةً، لا من زرّ،
ولا يحلّ محلّ كلمة المرور.

**التسجيل بلا رابط يجيب «البريد مأخوذ» بصدق** (409): من يحاول التسجيل ببريدٍ
مسجَّل يعرف أن لصاحبه حساباً هنا، والإشعار يقول ذلك. ما يحدّ السؤال: لا مسار
يسأل عن بريدٍ إلا طلبُ تسجيلٍ كامل بكل حقوله وتجزئة كلمة مروره؛ وسؤالٌ عن بريدٍ
حرّ يُنشئ حساباً حقيقياً؛ وثلاثة أجوبة «مأخوذ» في اليوم للشبكة الواحدة ثم لا
تسجيل منها؛ وستّون للتطبيق كلّه توقف التسجيل المفتوح يومه (في القاعدة)؛ وعند
الامتلاء يصل الجواب نفسه لكل بريد.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from eyework import assistant, auth, campaigns, inventory_rules, money, passkeys, reviewer, terms, ui_size
from eyework.copy_rules import EDIT_NOTE_MAX, MAX_PRESETS, PRESET_CONFLICTS, EditPreset
from eyework.professions import NAMES, TAGLINES, Profession
from eyework.web.deps import (
    COOKIE,
    COOKIE_MAX_AGE,
    client_ip,
    client_network,
    enforce,
    refuse_if_full,
    require_user,
    session_token,
)
from eyework.web.errors import CONSTRAINTS, REGISTRATION
from eyework.web.schemas import (
    ActivateBody,
    LoginBody,
    PasskeyAddBody,
    PasskeyAddOptionsBody,
    PasskeyLoginBody,
    RegisterBody,
    SignupCodeBody,
    TermsBody,
    UiSizeBody,
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
    enforce(state.limiters.passkey_ip, client_network(request))
    return await run_in_threadpool(passkeys.login_options, state.db, state.settings.public_origin)


@router.post("/auth/passkey", status_code=status.HTTP_204_NO_CONTENT)
async def passkey_login(body: PasskeyLoginBody, request: Request) -> Response:
    state = request.app.state
    enforce(state.limiters.passkey_ip, client_network(request))
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


def _constraint_error(name: str) -> JSONResponse:
    """قيدٌ من القاعدة باسمه، بالجواب نفسه الذي يعطيه معالج القيود في `web/app.py`."""
    spec = CONSTRAINTS[name]
    headers = {"Retry-After": str(spec.retry_after)} if spec.retry_after else None
    return JSONResponse(status_code=spec.status, headers=headers, content={"code": spec.code, "detail": spec.detail})


@router.get("/auth/registration", status_code=status.HTTP_204_NO_CONTENT)
async def registration(request: Request) -> Response:
    """
    هل يُنشأ حسابٌ بلا رابطٍ الآن؟ تسأله الواجهة قبل الخطوة الأولى، فلا يكتب أحدٌ
    إحدى عشرة شاشةً بالنظر ليسمع في آخرها أن اليوم اكتمل. حال التطبيق كلّه: لا بريد
    فيه ولا يقول شيئاً عن أحد، ولا يسجّل شيئاً.
    """
    state = request.app.state
    if state.settings.registration == "closed":
        return _registration_error("CLOSED")
    if state.settings.registration == "code":
        return _registration_error("LINK_REQUIRED")
    enforce(state.limiters.registration_check_net, client_network(request))
    blocker = await run_in_threadpool(auth.open_registration_blocker, state.db)
    return _constraint_error(blocker) if blocker else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/signup-code", status_code=status.HTTP_204_NO_CONTENT)
async def signup_code(body: SignupCodeBody, request: Request) -> Response:
    """
    هل يصلح رمز الرابط؟ تسأله الواجهة قبل الخطوة الأولى، فلا يملأ أحدٌ تسع شاشاتٍ
    برمزٍ منتهٍ. لا يكشف شيئاً عن الحسابات، وله حدٌّ لكل عنوان غير حدّ إنشاء الحساب.
    """
    state = request.app.state
    if state.settings.registration == "closed":
        return _registration_error("CLOSED")
    enforce(state.limiters.signup_code_ip, client_ip(request))
    if not await run_in_threadpool(auth.signup_code_usable, state.db, body.code):
        return _registration_error("CODE")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/register", status_code=status.HTTP_204_NO_CONTENT)
async def register(body: RegisterBody, request: Request) -> Response:
    """
    ترتيب الفحوص هو ضمانة التعداد (المواصفة §4.3): الوضع، فالنسخة، فالحقول — خطأٌ
    فيها لا يستهلك محاولة — فحدود الشبكة، ثم القاعدة: الحقول من جديد، فالسقوف
    والإيقاف قبل الإدراج (الجواب نفسه لكل بريد)، ثم الإدراج: مأخوذ، أو حساب.
    """
    state = request.app.state
    mode = state.settings.registration
    if mode == "closed":
        return _registration_error("CLOSED")
    if body.code is None and mode != "open":
        return _registration_error("LINK_REQUIRED")
    # ما وافق عليه هو ما عُرض عليه: نسخةٌ تغيّرت منذ عرضها لا تُنشئ حساباً.
    if body.terms_version != terms.TERMS_VERSION:
        return _registration_error("TERMS")
    try:
        name = auth.check_name(body.name)
        birth_date = auth.check_birth_date(body.birth_date)
        email = auth.check_email(body.email)
        password = auth.check_password(body.password)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    # الحدّ بعد فحص الشكل: خطأٌ في حقلٍ لا يمسّ القاعدة ولا يستهلك محاولة.
    limiters = state.limiters
    net = client_network(request) if body.code is None else None
    if net is None:
        enforce(limiters.register_ip, client_ip(request))
    else:
        # الثلاثة تُفحص قبل أن يُسجَّل شيء: شبكةٌ أغلقتها أجوبة «مأخوذ» لا تسجّل حتى بريداً حرّاً،
        # فلا يُعرف من جوابها شيء.
        for limiter in (limiters.register_open_net, limiters.register_open_net_day, limiters.taken_open_net):
            refuse_if_full(limiter, net)
        limiters.register_open_net.record(net)
        limiters.register_open_net_day.record(net)
    try:
        token = await run_in_threadpool(
            auth.register, state.db, state.settings.login_key, code=body.code, name=name,
            birth_date=birth_date, email=email, password=password, profession=body.profession,
            ui_size=body.ui_size)
    except auth.RegistrationInvalid as exc:
        return _registration_error(exc.field)
    except auth.RegistrationCodeInvalid:
        return _registration_error("CODE")
    except auth.RegistrationTaken:
        if net is not None:
            limiters.taken_open_net.record(net)
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
def add_passkey_options(body: PasskeyAddOptionsBody, request: Request,
                        user_id: UUID = Depends(require_user)) -> dict:
    """
    خيارات الإنشاء المشروط بعد الدخول بكلمة المرور: لجلسة هذا الطلب وحدها، ما دامت
    فُتحت بكلمة المرور قبل خمس دقائق على الأكثر (403 بعدها)، وباسم الدخول نفسه.
    409 إن بلغ الحساب سقف المفاتيح.
    """
    state = request.app.state
    enforce(state.limiters.passkey_add, str(user_id))
    return passkeys.add_options(state.db, state.settings.login_key, state.settings.public_origin, user_id,
                                auth.hash_token(session_token(request)), body.username)


@router.post("/me/passkeys", status_code=status.HTTP_204_NO_CONTENT)
def add_passkey(body: PasskeyAddBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """
    يحفظ مفتاحاً تحقّق منه الخادم. المفتاح لصاحب الجلسة دائماً: الجسم لا يسمّي
    حساباً، والتحدّي صدر له وحده؛ والقاعدة تفحص جلسة الطلب ثانيةً في معاملة الحفظ.
    """
    state = request.app.state
    enforce(state.limiters.passkey_add, str(user_id))
    try:
        passkeys.add(state.db, state.settings.public_origin, user_id, auth.hash_token(session_token(request)),
                     body.model_dump(exclude_none=True))
    except passkeys.PasskeyRejected:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=_PASSKEY_NOT_ADDED)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/me/ui-size", status_code=status.HTTP_204_NO_CONTENT)
def set_ui_size(body: UiSizeBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """طريقة الاستخدام لصاحب الجلسة وحده. لا تحتاج موافقةً حالية: لا تُرسَل إلى أحد."""
    state = request.app.state
    enforce(state.limiters.ui_size_user, str(user_id))
    auth.set_ui_size(state.db, user_id, body.ui_size)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/terms", status_code=status.HTTP_204_NO_CONTENT)
def accept_terms(body: TermsBody, request: Request, user_id: UUID = Depends(require_user)) -> Response:
    """الموافقة على النسخة الحالية من «قبل أن تبدأ»، لمن وافق على أقدم أو لم يوافق قطّ."""
    state = request.app.state
    enforce(state.limiters.terms_user, str(user_id))
    if body.terms_version != terms.TERMS_VERSION:
        return _registration_error("TERMS")
    auth.accept_terms(state.db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    """
    ما تحتاجه الواجهة لتفتح البوابة وتحيّي صاحبها: مهنته، واسمه، وحدّ اليوم وما
    بقي منه، وطريقة استخدامه (فارغةٌ حتى يختار)، وهل موافقته حالية (قاعدة البوّابة
    نفسها). لا معرّف ولا بريد ولا تاريخ ميلاد.
    """
    db = request.app.state.db
    profession = auth.profession_of(db, user_id)
    limit, left = campaigns.generation_allowance(db, user_id)
    size = auth.ui_size_of(db, user_id)
    return {
        "generations_left": left,
        "generation_limit": limit,
        "display_name": campaigns.display_name(db, user_id),
        "profession": profession.value if profession else None,
        "ui_size": size.value if size else None,
        "terms_current": terms.is_current(auth.terms_version_of(db, user_id)),
        # عدّاد «اسأل سيمبول» لليوم: ما تعرضه الواجهة في الزرّ العائم (ai_spec §8.2).
        "ai": {"assistant": reviewer.usage_of(db, user_id, "ASSISTANT")},
    }


@router.get("/choices")
def choices(request: Request) -> dict:
    """
    كل ما تعرضه الواجهة للاختيار، من الخادم وحده: قيم الميزانية والمدّة
    بكلماتها، وخيارات التعديل وتعارضاتها، والحدود، ووضع التسجيل وبريد المشغّل،
    وطريقتا الاستخدام، ونصّ «قبل أن تبدأ» بنسخته.

    الواجهة تبحث في هذا الجدول ولا تحسب: لا كلمة ولا حدّ ولا خطوة تُشتقّ في
    المتصفّح، فلا تختلف الواجهة عن القاعدة — ولا يختلف الإشعار المعروض عمّا يُحفظ.
    """
    settings = request.app.state.settings
    return {
        **money.choices(),
        # يبقى كما في المواصفة §7.11 ويعني «ليس مغلقاً»: التفصيل في registration.mode.
        "registration_open": settings.registration != "closed",
        "registration": {
            "mode": settings.registration,
            "name_max": auth.NAME_MAX,
            "password_min": auth.PASSWORD_MIN,
            "earliest_year": 1900,
            "terms_version": terms.TERMS_VERSION,
        },
        "support_contact": settings.support_contact,
        "ui_sizes": [{"code": size.value, "name": name, "detail": detail}
                     for size, (name, detail) in ui_size.CHOICES.items()],
        "notice": terms.notice(),
        # حدّ سؤال المساعد والأسئلة الجاهزة لكل شاشة: ثابتةٌ في الخادم لا في الواجهة.
        "assistant": assistant.choices(),
        "inventory": inventory_rules.choices(),
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
