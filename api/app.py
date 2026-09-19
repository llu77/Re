"""
تجميع التطبيق
==============
بوابتان تحت جذر واحد، بمسارين منفصلين ومصادقة مستقلة لكل منهما.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from psycopg import errors as pg_errors

from api.patient import router as patient_router
from api.practitioner import router as practitioner_router
from core import db

logger = logging.getLogger("symbol.api")

#: رسائل ثابتة لكل قيد. نص الخطأ من قاعدة البيانات قد يحمل قيم الصف — ومنها
#: PHI — فلا يصل العميل ولا السجل أبداً.
_CONSTRAINT_MESSAGES = {
    "illustration_needs_side": "المحتوى المصوَّر يتطلب تحديد الجانب المصاب.",
    "rejection_needs_reason": "الرفض يتطلب سبباً نصياً.",
    "decision_needs_reviewer": "القرار يتطلب مراجِعاً مسمّى.",
    "practitioner_is_licensed": "الممارس يتطلب رقم ترخيص.",
    "queued_before_decision": "تسلسل زمني غير صالح للمقترح.",
}
_FALLBACK_MESSAGE = "الطلب يخالف قيداً في قاعدة البيانات."


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.configure()
    yield
    db.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Symbol Rehab — بوابة الاعتماد",
        description="النظام يقترح، والممارس يقرر. لا محتوى يصل المريض دون اعتماد.",
        lifespan=lifespan,
    )
    app.include_router(practitioner_router)
    app.include_router(patient_router)

    @app.exception_handler(pg_errors.IntegrityError)
    def integrity_error(request: Request, exc: pg_errors.IntegrityError) -> JSONResponse:
        """
        انتهاك قيد ⇒ 422 برسالة ثابتة.

        لا يُسجَّل نص الخطأ الأصلي ولا يُعاد: `diag.message_detail` في
        PostgreSQL يحتوي قيم الصف المخالف، وقد تكون بيانات مريض.
        """
        constraint = getattr(exc.diag, "constraint_name", None) or ""
        logger.warning("انتهاك قيد %s على %s", constraint or "غير مسمّى", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": _CONSTRAINT_MESSAGES.get(constraint, _FALLBACK_MESSAGE)},
        )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
