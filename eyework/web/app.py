"""
تجميع التطبيق
=============
`create_app()` مصنعٌ لا وحدةٌ تبني تطبيقاً عند استيرادها: الإعداد والأسرار
تُقرأ حين يُبنى التطبيق فعلاً، والاختبارات تحقن ما تشاء.

    uvicorn --factory eyework.web.app:create_app --no-access-log \
            --proxy-headers --forwarded-allow-ips <عنوان الوكيل>

`--no-access-log` مقصود: سطر الوصول يحمل عنوان IP ومساراً وتوقيتاً، وهذا
وحده يكفي لاستنتاج من يستخدم التطبيق — ومستخدموه معلومةٌ صحّية.

ما يُطبَّق على كل استجابة:
  • CSP بلا شيفرةٍ مضمَّنة ولا طرفٍ ثالث؛ وصفحة الاختبار `/probe/` بلا اتصالٍ
    إطلاقاً (`connect-src 'none'`).
  • `Permissions-Policy: camera=()` — لا كاميرا في هذا التطبيق، ولا يستطيع
    أحدٌ أن يطلبها باسمه.
  • منع التأطير، وعدم الإحالة، و`nosniff`، وعزل الأصل.
  • `Cache-Control: no-store` لكل ما تحت `/api/`.

وما يُطبَّق على كل طلبٍ يغيّر شيئاً: `X-Eyework: 1` و`Origin` مطابق، وحدٌّ
لحجم الجسم قبل قراءته.
"""

from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg import errors as pg_errors

from eyework import campaigns, config, images
from eyework.copywriter import AnthropicCopywriter, Copywriter
from eyework.db import Database
from eyework.web import routes_auth, routes_campaigns
from eyework.web.deps import Limiters
from eyework.web.errors import AI_OUTCOMES, CONSTRAINTS, EDIT_REQUEST, GENERIC, IMAGE, ErrorSpec

__all__ = ["create_app"]

logger = logging.getLogger("eyework.web")

STATIC = Path(__file__).resolve().parent.parent / "static"
JSON_BODY_LIMIT = 16 * 1024

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("font/woff2", ".woff2")

_BASE_CSP = (
    "default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; "
    "font-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'"
)
APP_CSP = f"{_BASE_CSP}; connect-src 'self'; form-action 'self'"
PROBE_CSP = f"{_BASE_CSP}; connect-src 'none'; form-action 'none'"

_SECURITY_HEADERS = {
    # same-origin لا no-referrer: مع no-referrer يرسل المتصفّح `Origin: null` في
    # طلبات POST من الأصل نفسه، فيرفض فحصُ الأصل كلَّ طلبٍ مشروع.
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), display-capture=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}

_FORBIDDEN = {"code": "ORIGIN", "detail": "طلبٌ من خارج التطبيق."}


def _internal(request: Request, exc: Exception) -> JSONResponse:
    # الصنف والمسار فقط: نصّ الاستثناء قد يحمل قيم صفّ أو نصّ إعلان.
    logger.error("خطأ غير متوقَّع %s على %s", type(exc).__name__, request.url.path)
    return JSONResponse(status_code=500, content={"code": "INTERNAL", "detail": "حدث خطأ. حاول مرة أخرى."})


def _error(spec: ErrorSpec) -> JSONResponse:
    headers = {"Retry-After": str(spec.retry_after)} if spec.retry_after else None
    return JSONResponse(status_code=spec.status, content={"code": spec.code, "detail": spec.detail},
                        headers=headers)


def create_app(
    settings: config.Settings | None = None,
    *,
    copywriter: Copywriter | None = None,
    database: Database | None = None,
) -> FastAPI:
    settings = settings or config.load()
    owns_database = database is None
    if copywriter is None and not settings.anthropic_api_key:
        raise config.ConfigError("EYEWORK_ANTHROPIC_API_KEY غير مضبوط")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if owns_database:
            app.state.db.close()

    app = FastAPI(
        title="صياغة — حملات المنتجات",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = database or Database(settings.app_database_url)
    # يرفض الإقلاع بدورٍ يتجاوز العزل: كل ضمانةٍ في القاعدة تسقط معه بصمت.
    try:
        app.state.db.verify_role()
    except BaseException:
        if owns_database:
            app.state.db.close()
        raise
    app.state.copywriter = copywriter or AnthropicCopywriter(settings.anthropic_api_key)
    app.state.limiters = Limiters.default()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            # CSRF: ترويسةٌ لا تُرسلها صفحةٌ أجنبية دون CORS، وأصلٌ لا يُزوَّر.
            if (request.headers.get("x-eyework") != "1"
                    or request.headers.get("origin") != settings.public_origin):
                return JSONResponse(status_code=403, content=_FORBIDDEN)
            content_type = request.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                length = request.headers.get("content-length")
                if length is None or not length.isdigit():
                    return JSONResponse(status_code=411, content={"code": "LENGTH", "detail": "حجم الطلب مطلوب."})
                if int(length) > JSON_BODY_LIMIT:
                    return JSONResponse(status_code=413, content={"code": "BODY", "detail": "الطلب أكبر من المسموح."})

        try:
            response = await call_next(request)
        except Exception as exc:
            # معالج Exception في Starlette يعمل خارج هذا الغلاف، فلا تلحق
            # ردَّه الترويسات أدناه. يُبنى هنا ليمرّ بها كغيره.
            response = _internal(request, exc)

        path = request.url.path
        response.headers["Content-Security-Policy"] = PROBE_CSP if path.startswith("/probe") else APP_CSP
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.public_origin.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        else:
            # الواجهة تُراجَع عند كل فتح: لا نسخة قديمة من app.js بعد إصلاح.
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    # ── ترجمة الأخطاء ───────────────────────────────────────────────────
    @app.exception_handler(pg_errors.IntegrityError)
    def integrity_error(request: Request, exc: pg_errors.IntegrityError) -> JSONResponse:
        constraint = getattr(exc.diag, "constraint_name", None) or ""
        logger.warning("قيد %s على %s", constraint or "غير مسمّى", request.url.path)
        return _error(CONSTRAINTS.get(constraint, GENERIC))

    @app.exception_handler(pg_errors.NoDataFound)
    def no_data(request: Request, exc: pg_errors.NoDataFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "detail": "الحملة غير موجودة."})

    @app.exception_handler(campaigns.NotFound)
    def not_found(request: Request, exc: campaigns.NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "detail": "الحملة غير موجودة."})

    @app.exception_handler(campaigns.Conflict)
    def conflict(request: Request, exc: campaigns.Conflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": exc.code, "detail": CONSTRAINTS["stale_row_version"].detail})

    @app.exception_handler(campaigns.Invalid)
    def invalid(request: Request, exc: campaigns.Invalid) -> JSONResponse:
        return _error(EDIT_REQUEST.get(exc.code, GENERIC))

    @app.exception_handler(campaigns.AiFailure)
    def ai_failure(request: Request, exc: campaigns.AiFailure) -> JSONResponse:
        spec = AI_OUTCOMES.get(exc.outcome, AI_OUTCOMES["UPSTREAM_ERROR"])
        if exc.retry_after_seconds:
            spec = ErrorSpec(spec.status, spec.code, spec.detail, exc.retry_after_seconds)
        return _error(spec)

    @app.exception_handler(images.ImageRejected)
    def image_rejected(request: Request, exc: images.ImageRejected) -> JSONResponse:
        return _error(IMAGE.get(exc.code, IMAGE["CORRUPT"]))

    @app.exception_handler(RequestValidationError)
    def validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # لا تُعاد القيم المرسلة: قد تكون كلمة مرور.
        return JSONResponse(status_code=422, content={"code": "INVALID", "detail": "قيمةٌ غير صالحة في الطلب."})

    @app.exception_handler(HTTPException)
    def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        content = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP", "detail": "طلبٌ غير صالح."}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    # ما يفلت من الغلاف نفسه.
    app.add_exception_handler(Exception, _internal)

    # ── المسارات ────────────────────────────────────────────────────────
    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(routes_auth.router)
    app.include_router(routes_campaigns.router)
    # أخيراً: كل ما لم يطابق مساراً أعلاه ملفٌّ ساكن. بلا شرط: نشرٌ بلا مجلد
    # الواجهة يفشل عند الإقلاع لا أن يعمل بلا واجهة.
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
