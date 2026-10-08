"""
تجميع التطبيق
==============
بوابتان تحت جذر واحد، بمسارين منفصلين ومصادقة مستقلة لكل منهما.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
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

    # بوابة المريض: ملفات ساكنة تستهلك `/patient/*`. تُخدم من الأصل نفسه
    # فلا حاجة إلى CORS ولا إلى نطاق ثانٍ.
    #
    # بلا شرط عمداً: نشرٌ بلا مجلد البوابة يجب أن يفشل عند الإقلاع لا أن يعمل
    # بلا واجهة — `StaticFiles` ترفع الخطأ هنا.
    portal = Path(__file__).resolve().parent.parent / "portal"
    app.mount("/app", StaticFiles(directory=portal, html=True), name="portal")

    _mount_console(app)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


#: لوحة الممارس تعرض بيانات مرضى: لا شيفرة إلا من الأصل، ولا إطار يحتويها،
#: ولا إحالة تحمل مسارها إلى موقعٍ خارجي (روابط الأدلّة تفتح PubMed).
#: `style-src 'unsafe-inline'` لأن مكتبة Radix تحقن عنصر <style> لقفل
#: التمرير خلف النوافذ؛ الأنماط لا تنفّذ شيفرة، والسكربتات تبقى من الأصل وحده.
CONSOLE_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
_CONSOLE_HEADERS = {
    "Content-Security-Policy": CONSOLE_CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _mount_console(app: FastAPI) -> None:
    """
    لوحة الممارس تحت `/console`: واجهة مبنيّة من `console/` تستهلك
    `/practitioner/*` من الأصل نفسه.

    البناء ناتجٌ لا مصدر فلا يُحفظ في المستودع. بلا بناءٍ يردّ المسار 503
    برسالة صريحة: لا تعمل المنصّة كأن اللوحة موجودة، ولا يتوقّف إقلاع بوابة
    المريض بسبب واجهةٍ أخرى.
    """
    dist = Path(__file__).resolve().parent.parent / "console" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/console", StaticFiles(directory=dist, html=True), name="console")
    else:
        @app.get("/console/{path:path}", include_in_schema=False)
        def console_not_built(path: str) -> JSONResponse:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "لوحة الممارس لم تُبنَ: npm ci && npm run build في console/"},
            )

    @app.middleware("http")
    async def console_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/console" or path.startswith("/console/"):
            for name, value in _CONSOLE_HEADERS.items():
                response.headers.setdefault(name, value)
            # الملفّات المجزّأة لا تتغيّر أبداً؛ الصفحة نفسها تُراجَع عند كل فتح.
            # والخطأ لا يُحفظ: في نشرٍ متدرّج قد تطلب الصفحة الجديدة ملفّاً من
            # نسخةٍ لم يصلها بعد، و404 «immutable» يبقى سنةً بعد أن يصل.
            code = response.status_code
            if code >= 400:
                cache = "no-store"
            elif path.startswith("/console/assets/") and (200 <= code < 300 or code == 304):
                cache = "public, max-age=31536000, immutable"
            else:
                cache = "no-cache"
            response.headers.setdefault("Cache-Control", cache)
        return response


app = create_app()
