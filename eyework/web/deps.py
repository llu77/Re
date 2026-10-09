"""
اعتماديات الطلب
===============
الجلسة من ملفّ تعريف الارتباط `__Host-ew` وحده: `HttpOnly` فلا تقرؤه شيفرة
الصفحة، و`Secure` و`SameSite=Strict` و`Path=/` بلا `Domain` — وهي شروط
البادئة `__Host-` نفسها، فلا يضعه نطاقٌ فرعي ولا اتصالٌ غير مشفّر.

وكل طلبٍ يغيّر شيئاً يحمل `X-Eyework: 1` و`Origin` مطابقاً لأصل التطبيق:
صفحةٌ من موقعٍ آخر لا تستطيع إرسال الترويسة الأولى دون إذن CORS، ولا تزوير
الثانية.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from eyework import auth, terms
from eyework.professions import Profession
from eyework.rate_limit import RateLimit, RateLimiter, RateLimitExceeded
from eyework.web.errors import TERMS_REQUIRED

__all__ = ["COOKIE", "Limiters", "client_ip", "client_network", "enforce", "refuse_if_full",
           "require_current_terms", "require_profession", "require_user", "session_token"]

COOKIE = "__Host-ew"
COOKIE_MAX_AGE = 30 * 24 * 3600
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True, slots=True)
class Limiters:
    """حدود المعدّل في الذاكرة. ما كلفته مال (التوليد) محدودٌ في القاعدة."""

    #: الحدّ الصارم لكل (اسم، عنوان): من يخمّن من عنوانه لا يحبس صاحب الحساب في عنوانه.
    login_name_ip: RateLimiter
    #: سقفٌ عالٍ لكل اسم من كل العناوين: حاجزٌ أمام التخمين الموزّع وحده.
    login_name: RateLimiter
    login_ip: RateLimiter
    activate_ip: RateLimiter
    signup_code_ip: RateLimiter
    register_ip: RateLimiter
    #: خيارات الدخول بمفتاح المرور والتحقّق منه، لكل شبكة (`client_network`): كل طلب
    #: خياراتٍ صفٌّ في القاعدة، وللقاعدة سقفها فوقه (passkey_login_ceiling).
    passkey_ip: RateLimiter
    #: خيارات إنشاء المفتاح بعد الدخول بكلمة المرور وحفظه، لكل حساب.
    passkey_add: RateLimiter
    upload: RateLimiter
    mutation: RateLimiter
    image: RateLimiter
    #: التسجيل بلا رابط لكل شبكة (عنوان IPv4، أو /64 من IPv6): خمسٌ في الساعة، وعشرٌ في اليوم.
    register_open_net: RateLimiter
    register_open_net_day: RateLimiter
    #: أجوبة «البريد مأخوذ» بلا رابط لكل شبكة: ثلاثٌ في اليوم ثم لا جواب — نظير قفل الرمز بعد ثلاث.
    taken_open_net: RateLimiter
    #: «هل يُنشأ حسابٌ بلا رابطٍ الآن؟» قبل الخطوة الأولى.
    registration_check_net: RateLimiter
    #: تغيير طريقة الاستخدام، والموافقة على نسخةٍ جديدة: لكل حساب.
    ui_size_user: RateLimiter
    terms_user: RateLimiter

    @classmethod
    def default(cls) -> "Limiters":
        return cls(
            login_name_ip=RateLimiter(RateLimit(5, 60.0)),
            login_name=RateLimiter(RateLimit(300, 3600.0)),
            login_ip=RateLimiter(RateLimit(20, 60.0)),
            activate_ip=RateLimiter(RateLimit(5, 60.0)),
            # التسجيل برمزٍ يصدره المشغّل: عشرون في الساعة من عنوانٍ واحد تكفي دفعةً
            # تتسجّل من شبكة مركزٍ واحد. والواجهة تفحص الرمز ثم تُنشئ الحساب، فلكلٍّ
            # منهما حدّه، وإلا صار العشرون عشرة. والقاعدة تسقف المجموع اليومي (ew_register).
            signup_code_ip=RateLimiter(RateLimit(20, 3600.0)),
            register_ip=RateLimiter(RateLimit(20, 3600.0)),
            # خيارات الدخول تُطلب كلما عُرضت شاشته، ثم التحقّق مرةً لكل ضغطة.
            passkey_ip=RateLimiter(RateLimit(20, 60.0)),
            passkey_add=RateLimiter(RateLimit(20, 3600.0)),
            upload=RateLimiter(RateLimit(10, 3600.0)),
            mutation=RateLimiter(RateLimit(120, 60.0)),
            image=RateLimiter(RateLimit(120, 60.0)),
            # بلا رابط لا يعرف المشغّل من يسجّل، فالحدّ على الشبكة أضيق من حدّ الرابط، وسؤال
            # «هل البريد مأخوذ؟» بلا رابط يُنشئ حساباً حقيقياً أو يُحسب على الشبكة: ثلاث
            # أجوبة في اليوم ثم لا جواب (المواصفة §4.3)، والقاعدة توقف التسجيل المفتوح كلّه
            # بعد ستّين.
            register_open_net=RateLimiter(RateLimit(5, 3600.0)),
            register_open_net_day=RateLimiter(RateLimit(10, 86400.0)),
            taken_open_net=RateLimiter(RateLimit(3, 86400.0)),
            registration_check_net=RateLimiter(RateLimit(30, 3600.0)),
            ui_size_user=RateLimiter(RateLimit(30, 3600.0)),
            terms_user=RateLimiter(RateLimit(10, 3600.0)),
        )


def client_ip(request: Request) -> str:
    """عنوان العميل كما يراه uvicorn — بعد `--proxy-headers` من الوكيل الموثوق وحده."""
    return request.client.host if request.client else "unknown"


def client_network(request: Request) -> str:
    """
    مفتاح حدٍّ لكل مشترك: عنوان IPv4 كما هو، وIPv6 بشبكته /64 — يُعطى المشترك
    الواحد عادةً /64 كاملة، فعنوانٌ جديد منها لكل طلبٍ يتجاوز حدّاً على العنوان.
    وعنوان IPv4 بصيغة IPv6 (`::ffff:a.b.c.d`) عنوانُ IPv4.
    """
    host = client_ip(request)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return host


_RATE = {"code": "RATE", "detail": "طلباتٌ كثيرة. حاول بعد قليل."}


def enforce(limiter: RateLimiter, key: str) -> None:
    try:
        limiter.check(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=dict(_RATE),
            headers={"Retry-After": str(int(exc.retry_after_seconds) + 1)},
        ) from exc


def refuse_if_full(limiter: RateLimiter, key: str) -> None:
    """429 كـ`enforce` إن لم يبقَ مكان، ولا يسجّل شيئاً: لما يُعدّ بعد وقوعه (`record`)."""
    wait = limiter.blocked(key)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=dict(_RATE),
            headers={"Retry-After": str(int(wait) + 1)},
        )


def session_token(request: Request) -> str | None:
    token = request.cookies.get(COOKIE)
    # رمزٌ بشكلٍ غير شكل رموزنا لا يُرسل إلى القاعدة أصلاً.
    if token and _TOKEN.fullmatch(token):
        return token
    return None


def require_user(request: Request) -> UUID:
    token = session_token(request)
    user_id = auth.resolve(request.app.state.db, token) if token else None
    if user_id is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION", "detail": "سجّل الدخول للمتابعة."},
        )
    return user_id


def require_current_terms(request: Request, user_id: UUID = Depends(require_user)) -> UUID:
    """
    لا يُرسَل شيءٌ لصاحب الجلسة إلى مزوّد النموذج قبل أن يوافق على النسخة الحالية من
    «قبل أن تبدأ». من وافق على أقدم — أو لم يوافق قطّ، كحساب الدعوة — يُردّ إلى
    الموافقة بـ403 TERMS. أحدث من الحالية يكفي (`terms.is_current`). اعتماديةٌ لكل
    مسارٍ يصل النموذج، واختبارٌ معماري يفرض ذلك.
    """
    if not terms.is_current(auth.terms_version_of(request.app.state.db, user_id)):
        raise HTTPException(TERMS_REQUIRED.status,
                            detail={"code": TERMS_REQUIRED.code, "detail": TERMS_REQUIRED.detail})
    return user_id


def require_profession(profession: Profession):
    """
    بوابة مهنةٍ واحدة: الأداة لأصحاب مهنتها وحدهم، 403 لغيرهم.

    `require_user` داخلها هو نفسه في المسار، وFastAPI يحسبه مرةً للطلب.
    والقاعدة تفرض الشرط نفسه عند الإنشاء؛ هذا الحاجز الأول لا الوحيد.
    """

    def dependency(request: Request, user_id: UUID = Depends(require_user)) -> UUID:
        if auth.profession_of(request.app.state.db, user_id) is not profession:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "PROFESSION", "detail": "هذه الأداة لبوابة مهنةٍ أخرى."},
            )
        return user_id

    return dependency
