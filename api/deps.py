"""
اعتماديات مشتركة بين البوابتين
================================
استخراج الهوية من ترويسة `Authorization` والتحقق من أنها تخص هذه البوابة.
لا تحتوي هذه الوحدة أي وصول إلى جداول المحتوى.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from core.identity import AuthenticationFailed, Principal, resolve_session
from core.rate_limit import AUTH_LIMIT, EVIDENCE_LIMIT, RateLimiter, RateLimitExceeded
from core.types import Gate

__all__ = [
    "auth_limiter",
    "enforce_auth_rate_limit",
    "enforce_evidence_rate_limit",
    "evidence_limiter",
    "practitioner",
    "patient",
]

auth_limiter = RateLimiter(AUTH_LIMIT)

#: بحث الأدلة نقطة خارجية ومكلفة: نحدّ استهلاك كل ممارس قبل أن يحدّه NCBI
#: بالحظر. الناقل يحدّ المعدل الكلي نحو المصدر؛ هذا يحدّ الفاعل الواحد.
evidence_limiter = RateLimiter(EVIDENCE_LIMIT)


def _enforce(limiter: RateLimiter, key: str, detail: str) -> None:
    try:
        limiter.check(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(int(exc.retry_after_seconds) + 1)},
        ) from exc


def enforce_auth_rate_limit(key: str) -> None:
    _enforce(auth_limiter, key, "محاولات كثيرة. أعد المحاولة لاحقاً.")


def enforce_evidence_rate_limit(key: str) -> None:
    _enforce(evidence_limiter, key, "عمليات بحث كثيرة. أعد المحاولة بعد قليل.")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="مصادقة مطلوبة")
    return authorization.split(" ", 1)[1].strip()


def _principal_for(gate: Gate):
    def dependency(authorization: Annotated[str | None, Header()] = None) -> Principal:
        try:
            return resolve_session(_bearer(authorization), gate)
        except AuthenticationFailed as exc:
            # لا نفصّل السبب: التفصيل يساعد المهاجم ولا يساعد المستخدم.
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="جلسة غير صالحة") from exc

    return dependency


practitioner = Depends(_principal_for("PRACTITIONER"))
patient = Depends(_principal_for("PATIENT"))
