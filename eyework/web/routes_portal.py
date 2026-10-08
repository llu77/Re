"""
مسار البوابة
============
بوابة مهنة صاحب الجلسة وحدها: لا مسار يعرض بوابة مهنةٍ أخرى، ولا يُختار
بالطلب أيّ بوابةٍ تُعرض — المهنة من القاعدة.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from eyework import auth, professions
from eyework.web.deps import require_user

__all__ = ["router"]

router = APIRouter(prefix="/api")


@router.get("/portal")
def portal(request: Request, user_id: UUID = Depends(require_user)) -> dict:
    profession = auth.profession_of(request.app.state.db, user_id)
    if profession is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            detail={"code": "SESSION", "detail": "سجّل الدخول للمتابعة."})
    return professions.view(profession)
