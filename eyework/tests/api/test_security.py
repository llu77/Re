"""
حواجز الويب
===========
ما يحمي المستخدم ولو أخطأت الواجهة أو جاء الطلب من صفحةٍ معادية:

  • **CSRF.** كل طلبٍ يغيّر شيئاً يحمل `X-Eyework: 1` — ترويسةٌ لا ترسلها
    صفحةٌ أجنبية دون إذن CORS — و`Origin` مطابقاً لأصل التطبيق حرفياً. ما
    عداه 403 قبل أن يُقرأ الجسم أو تُمسّ جلسة. والقراءة لا تحتاج شيئاً.
  • **ترويسات كل استجابة.** CSP بلا شيفرةٍ مضمَّنة، وصفحة الاختبار `/probe/`
    بلا اتصالٍ إطلاقاً؛ ومنع التأطير، و`nosniff`، وعدم الإحالة خارج الأصل،
    وعزل الأصل، ولا كاميرا باسم التطبيق؛ وHSTS لأن الأصل https. وما تحت
    `/api/` لا يُخبّأ (`no-store`)، والواجهة تُراجَع عند كل فتح (`no-cache`).
  • **الحجم والنوع قبل القراءة.** JSON فوق 16 KiB، وصورةٌ فوق 12 MiB، ونوعٌ
    غير JPEG/PNG/WebP، تُرفض قبل أن تُخصَّص لها ذاكرة أو تُفكّ.
  • **أخطاء القاعدة لا تخرج.** نصّ خطأ PostgreSQL يحمل قيم الصفّ المخالف — قد
    تكون نصّ إعلانٍ أو معرّفاً — فيُستبدل برسالةٍ عربيةٍ ثابتة، ولا يُسجَّل.
  • **لا إقلاع بدورٍ يتجاوز العزل.** خطأٌ في متغيّرٍ واحد كان سيُبطل كل ضمانةٍ
    في القاعدة بلا أي خطأ ظاهر.
"""

from __future__ import annotations

import io
import logging

import pytest
from PIL import Image

from eyework import campaigns, config
from eyework.copywriter import CopyOutcome
from eyework.db import Database, UnsafeRole
from eyework.tests.api.conftest import (
    COOKIE,
    JPEG,
    LOGIN_KEY,
    ORIGIN,
    PASSWORD,
    SELLER,
    add_user,
    approve,
    attempts,
    current,
    generate,
    path,
    signed_in,
    upload,
    with_cookie,
)
from eyework.tests.fakes import DESCRIPTION, FakeCopywriter
from eyework.web.app import create_app

FORBIDDEN = {"code": "ORIGIN", "detail": "طلبٌ من خارج التطبيق."}
INTERNAL = {"code": "INTERNAL", "detail": "حدث خطأ. حاول مرة أخرى."}
ONE_YEAR = 365 * 24 * 3600

#: (المسار، الحالة المتوقّعة، النوع) لكل سطحٍ يخدمه التطبيق.
SURFACES = [
    pytest.param("/api/choices", 200, "api", id="api"),
    pytest.param("/api/me", 401, "api", id="api-error"),
    pytest.param("/api/campaigns/00000000-0000-4000-8000-000000000000", 401, "api", id="api-campaign"),
    pytest.param("/", 200, "static", id="index"),
    pytest.param("/app.js", 200, "static", id="script"),
    pytest.param("/probe/", 200, "probe", id="probe"),
    pytest.param("/probe/probe.js", 200, "probe", id="probe-script"),
    pytest.param("/no-such-file", 404, "static", id="static-404"),
]


def _csp(response) -> dict[str, list[str]]:
    directives = {}
    for directive in response.headers["content-security-policy"].split(";"):
        name, *sources = directive.split()
        directives[name] = sources
    return directives


def _forged(client, method: str, url: str, *, drop: tuple[str, ...] = (), headers: dict | None = None, **kwargs):
    """طلبٌ كما ترسله صفحةٌ أجنبية: ترويسات الكتابة محذوفةٌ أو مزوّرة."""
    request = client.build_request(method, url, **kwargs)
    for name in drop:
        del request.headers[name]
    for name, value in (headers or {}).items():
        request.headers[name] = value
    return client.send(request)


# ── CSRF ───────────────────────────────────────────────────────────────
FORGERIES = [
    pytest.param({"drop": ("x-eyework",)}, id="no-x-eyework"),
    pytest.param({"headers": {"X-Eyework": "true"}}, id="x-eyework-not-1"),
    pytest.param({"headers": {"Origin": "https://evil.example"}}, id="foreign-origin"),
    pytest.param({"headers": {"Origin": "https://testserver.evil.example"}}, id="origin-prefix"),
    pytest.param({"headers": {"Origin": "http://testserver"}}, id="http-origin"),
    pytest.param({"headers": {"Origin": "null"}}, id="null-origin"),
    pytest.param({"drop": ("origin",)}, id="no-origin"),
]


@pytest.mark.parametrize("forgery", FORGERIES)
def test_a_write_without_the_header_and_exact_origin_is_forbidden(owner, seller, browser, forgery):
    """صفحةٌ معادية تُرسل نماذج بملفّ الجلسة؛ بلا هذين الشرطين تكتب باسم المستخدم."""
    token = seller.cookies.get(COOKIE)

    created = _forged(seller, "POST", "/api/campaigns", content=b"\xff\xd8\xff", **forgery)
    assert created.status_code == 403
    assert created.json() == FORBIDDEN

    logout = _forged(seller, "POST", "/api/auth/logout", **forgery)
    assert logout.status_code == 403
    assert logout.json() == FORBIDDEN
    assert "set-cookie" not in logout.headers

    stranger = browser()
    login = _forged(stranger, "POST", "/api/auth/login", json={"username": SELLER, "password": PASSWORD},
                    **forgery)
    assert login.status_code == 403
    assert "set-cookie" not in login.headers

    # لم يتغيّر شيء: الجلسة قائمة، ولا حملة.
    reader = browser(write_headers=False)
    assert reader.get("/api/me", headers=with_cookie(token)).status_code == 200
    assert reader.get("/api/campaigns", headers=with_cookie(token)).json()["items"] == []


def test_reading_needs_no_write_headers(seller, browser):
    """قراءةٌ تُرفض بلا الترويسة تكسر الروابط العادية والصور في الصفحة."""
    view = upload(seller)
    reader = browser(write_headers=False)
    cookie = with_cookie(seller.cookies.get(COOKIE))
    assert reader.get("/api/me", headers=cookie).status_code == 200
    assert reader.get(path(view), headers=cookie).status_code == 200
    assert reader.get(path(view, "/image"), headers=cookie).status_code == 200


# ── الترويسات ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(("route", "status", "kind"), SURFACES)
def test_every_surface_carries_the_security_headers(browser, route, status, kind):
    """استجابةٌ واحدة بلا هذه الترويسات تُؤطَّر، أو تُشمّ نوعاً آخر، أو تُخبّأ."""
    response = browser().get(route)
    assert response.status_code == status
    headers = response.headers

    csp = _csp(response)
    assert csp["default-src"] == ["'self'"]
    assert csp["script-src"] == ["'self'"]
    assert csp["style-src"] == ["'self'"]
    assert csp["object-src"] == ["'none'"]
    assert csp["base-uri"] == ["'none'"]
    assert csp["frame-ancestors"] == ["'none'"]
    if kind == "probe":
        assert csp["connect-src"] == ["'none'"]
        assert csp["form-action"] == ["'none'"]
    else:
        assert csp["connect-src"] == ["'self'"]
        assert csp["form-action"] == ["'self'"]

    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "same-origin"
    assert headers["x-content-type-options"] == "nosniff"
    assert "camera=()" in [policy.strip() for policy in headers["permissions-policy"].split(",")]
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert headers["cross-origin-resource-policy"] == "same-origin"

    hsts = dict(part.strip().partition("=")[::2] for part in headers["strict-transport-security"].split(";"))
    assert int(hsts["max-age"]) >= ONE_YEAR
    assert headers["cache-control"] == ("no-store" if kind == "api" else "no-cache")


def test_an_unexpected_error_still_carries_the_security_headers(browser, owner, monkeypatch):
    """
    «ما يُطبَّق على كل استجابة» يشمل استجابة الخطأ غير المتوقَّع: بلا
    `no-store` ولا `nosniff` ولا CSP تُخبّأ وتُشمّ كما تشاء الوسائط.
    """
    def broken(*args, **kwargs):
        raise RuntimeError("row (00000000-..., secret copy) failed")

    monkeypatch.setattr(campaigns, "remaining_generations", broken)
    client = signed_in(owner, browser, SELLER, raise_server_exceptions=False)
    response = client.get("/api/me")
    assert response.status_code == 500
    assert response.json() == INTERNAL
    assert "secret copy" not in response.text
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "content-security-policy" in response.headers


# ── الحجم والنوع ───────────────────────────────────────────────────────
def test_a_json_body_over_16_kib_is_refused_before_it_is_read(browser, owner):
    """جسمٌ بلا حدٍّ يُقرأ كلّه في الذاكرة قبل أن يرفضه التحقّق."""
    add_user(owner, SELLER)
    response = browser().post("/api/auth/login", json={"username": SELLER, "password": "x" * (16 * 1024)})
    assert response.status_code == 413
    assert response.json()["code"] == "BODY"
    assert "set-cookie" not in response.headers


def test_an_image_over_12_mib_is_refused(seller):
    """ملفٌّ بلا حدٍّ يملأ ذاكرة الخادم قبل أن يُفكّ."""
    response = seller.post("/api/campaigns", content=bytes(13 * 1024 * 1024), headers=JPEG)
    assert response.status_code == 413
    assert response.json()["code"] == "IMAGE_TOO_LARGE"
    assert seller.get("/api/campaigns").json()["items"] == []


def _gif() -> bytes:
    buffer = io.BytesIO()
    Image.effect_noise((400, 400), 60).convert("P").save(buffer, "GIF")
    return buffer.getvalue()


@pytest.mark.parametrize("declared", ["image/gif", "image/jpeg"])
def test_a_gif_is_refused_whatever_it_claims_to_be(seller, declared):
    """GIF قد يكون متحرّكاً، والنوع المعلَن لا يُصدَّق: البايتات هي الحكم."""
    response = seller.post("/api/campaigns", content=_gif(), headers={"Content-Type": declared})
    assert response.status_code == 415
    assert response.json()["code"] == "IMAGE_TYPE"
    assert seller.get("/api/campaigns").json()["items"] == []


# ── أخطاء القاعدة ──────────────────────────────────────────────────────
def test_a_named_constraint_answers_with_its_fixed_message(seller, monkeypatch, caplog):
    """نصّ خطأ PostgreSQL يحمل الصفّ المخالف كاملاً؛ يصل العميل أو السجلّ فيُسرَّب."""
    view = approve(seller, generate(seller, upload(seller)))
    # الفحص في بايثون معطَّل، فلا يبقى إلا قيد القاعدة.
    monkeypatch.setattr(campaigns, "is_valid_budget", lambda value: True)
    caplog.set_level(logging.DEBUG)

    response = seller.put(path(view, "/budget"), json={"expected_row_version": view["row_version"], "budget_sar": 75})
    assert response.status_code == 422
    assert response.json() == {"code": "BUDGET_RANGE", "detail": "اختر مبلغاً من القيم المعروضة."}
    for leak in ("budget_in_domain", "violates", "Failing row", "campaigns", view["id"]):
        assert leak not in response.text
    # السجلّ يسمّي القيد والمسار وحدهما، لا نصّ القاعدة ولا الصفّ المخالف.
    for record in caplog.records:
        assert "violates" not in record.getMessage()
        assert "Failing row" not in record.getMessage()
    assert current(seller, view)["budget"] is None


def test_an_unnamed_constraint_answers_with_the_generic_message(seller, writer, owner, caplog):
    """قيدٌ لا رسالة له يجب ألّا يعيد نصّ القاعدة بدلاً منها."""
    view = upload(seller)
    marker = "MARKER-7781"
    # عنوانٌ أقصر من حدّ القاعدة من كاتبٍ لا يفحص — يصل قيد CHECK في copy_versions.
    writer.queue(CopyOutcome("OK", title="XQZ", description=f"{DESCRIPTION} {marker}",
                             served_model="claude-opus-5-5", input_tokens=1, output_tokens=1))
    caplog.set_level(logging.DEBUG)

    response = seller.post(path(view, "/copy"), json={"expected_row_version": view["row_version"]})
    assert response.status_code == 422
    assert response.json() == {"code": "CONSTRAINT", "detail": "الطلب يخالف قيداً. راجع القيم وحاول مرة أخرى."}
    for leak in ("XQZ", marker, "copy_versions", "violates", "Failing row"):
        assert leak not in response.text
    for record in caplog.records:
        assert marker not in record.getMessage()
        assert "Failing row" not in record.getMessage()
    assert attempts(owner) == [("DISCARDED", True)]
    assert current(seller, view) == view


# ── الدور ──────────────────────────────────────────────────────────────
def test_the_app_refuses_to_start_with_the_owner_role(owner_url):
    """دور المالك يتجاوز العزل: كل سياسة RLS تصير زينةً بلا أي خطأ ظاهر."""
    settings = config.Settings(app_database_url=owner_url, login_key=LOGIN_KEY,
                               anthropic_api_key=None, public_origin=ORIGIN)
    database = Database(owner_url)
    try:
        with pytest.raises(UnsafeRole):
            create_app(settings, copywriter=FakeCopywriter(), database=database)
    finally:
        database.close()


def test_the_app_refuses_to_start_from_an_owner_url_alone(owner_url, monkeypatch):
    """بلا قاعدةٍ محقونة يبني التطبيق تجمّعه من الإعداد — والفحص نفسه يسري."""
    opened: list[Database] = []
    original = Database.__init__

    def tracking(self, *args, **kwargs):
        original(self, *args, **kwargs)
        opened.append(self)

    monkeypatch.setattr(Database, "__init__", tracking)
    settings = config.Settings(app_database_url=owner_url, login_key=LOGIN_KEY,
                               anthropic_api_key=None, public_origin=ORIGIN)
    try:
        with pytest.raises(UnsafeRole):
            create_app(settings, copywriter=FakeCopywriter())
    finally:
        for database in opened:
            database.close()
