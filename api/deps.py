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
from core.rate_limit import AUTH_LIMIT, RateLimiter, RateLimitExceeded
from core.types import Gate

__all__ = ["auth_limiter", "enforce_auth_rate_limit", "practitioner", "patient"]

auth_limiter = RateLimiter(AUTH_LIMIT)


def enforce_auth_rate_limit(key: str) -> None:
    try:
        auth_limiter.check(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="محاولات كثيرة. أعد المحاولة لاحقاً.",
            headers={"Retry-After": str(int(exc.retry_after_seconds) + 1)},
        ) from exc


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
