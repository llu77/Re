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

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from eyework import auth
from eyework.professions import Profession
from eyework.rate_limit import RateLimit, RateLimiter, RateLimitExceeded

__all__ = ["COOKIE", "Limiters", "client_ip", "enforce", "require_profession", "require_user", "session_token"]

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
    register_ip: RateLimiter
    upload: RateLimiter
    mutation: RateLimiter
    image: RateLimiter

    @classmethod
    def default(cls) -> "Limiters":
        return cls(
            login_name_ip=RateLimiter(RateLimit(5, 60.0)),
            login_name=RateLimiter(RateLimit(300, 3600.0)),
            login_ip=RateLimiter(RateLimit(20, 60.0)),
            activate_ip=RateLimiter(RateLimit(5, 60.0)),
            # التسجيل برمزٍ يصدره المشغّل، وطلبات فحص الرمز وإنشاء الحساب معاً:
            # عشرون في الساعة من عنوانٍ واحد تكفي دفعةً تتسجّل من شبكة مركزٍ واحد.
            # والقاعدة تسقف المجموع اليومي للجميع (ew_register).
            register_ip=RateLimiter(RateLimit(20, 3600.0)),
            upload=RateLimiter(RateLimit(10, 3600.0)),
            mutation=RateLimiter(RateLimit(120, 60.0)),
            image=RateLimiter(RateLimit(120, 60.0)),
        )


def client_ip(request: Request) -> str:
    """عنوان العميل كما يراه uvicorn — بعد `--proxy-headers` من الوكيل الموثوق وحده."""
    return request.client.host if request.client else "unknown"


def enforce(limiter: RateLimiter, key: str) -> None:
    try:
        limiter.check(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE", "detail": "طلباتٌ كثيرة. حاول بعد قليل."},
            headers={"Retry-After": str(int(exc.retry_after_seconds) + 1)},
        ) from exc


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
