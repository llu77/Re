"""
تجهيزات اختبارات الواجهة البرمجية
=================================
التطبيق الحقيقي كما يُقلع في الإنتاج — المصنع نفسه، والوسيطات نفسها، وقاعدة
الاختبار بدور الويب `eyework_app` — عبر `TestClient` على أصلٍ https، والكاتب
المصطنع محقونٌ بدل النموذج. لا شيء هنا يتجاوز طبقة الويب: كل حالةٍ تُبنى
بالطلبات نفسها التي ترسلها الواجهة، فما يثبته اختبارٌ يثبته للمستخدم.

**تطبيقٌ جديد لكل اختبار.** حدود المعدّل تعيش في ذاكرة التطبيق؛ تطبيقٌ مشترك
يجعل نتيجة اختبارٍ رهينةً بعدد ما سبقه من طلبات دخولٍ ورفع.

**متصفّحٌ لكل مستخدم.** كل عميلٍ جرّة ملفّات تعريفٍ مستقلّة، ويحمل ترويستي
الكتابة (`X-Eyework` و`Origin`) كما يحملهما `app.js`؛ واختبارات CSRF وحدها
تحذفهما أو تزوّرهما.
"""

from __future__ import annotations

import functools
import io
from contextlib import ExitStack
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import ExifTags, Image

from eyework import auth, config
from eyework.db import Database
from eyework.passwords import hash_password
from eyework.tests.conftest import app_url_for, make_user
from eyework.tests.fakes import FakeCopywriter
from eyework.web.app import create_app

ORIGIN = "https://testserver"
LOGIN_KEY = b"k" * 32
WRITE_HEADERS = {"X-Eyework": "1", "Origin": ORIGIN}
JPEG = {"Content-Type": "image/jpeg"}
COOKIE = "__Host-ew"

PASSWORD = "Strong-Password-2026-x"
SELLER = "seller@example.sa"
INTRUDER = "intruder@example.sa"


# ── التطبيق والمتصفّحات ────────────────────────────────────────────────
@pytest.fixture
def writer() -> FakeCopywriter:
    return FakeCopywriter()


@pytest.fixture
def server(owner, owner_url, writer):
    """تطبيقٌ جديد على قاعدةٍ نظيفة (`owner` يفرّغها أولاً)، يُغلق تجمّعه بعده."""
    settings = config.Settings(
        app_database_url=app_url_for(owner_url),
        login_key=LOGIN_KEY,
        anthropic_api_key=None,
        public_origin=ORIGIN,
    )
    database = Database(settings.app_database_url)
    try:
        yield create_app(settings, copywriter=writer, database=database)
    finally:
        database.close()


@pytest.fixture
def browser(server):
    """
    مصنع متصفّحات على التطبيق نفسه. `write_headers=False` ⇒ بلا ترويستي
    الكتابة (لاختبارات CSRF وإعادة ملفٍّ قديم يدوياً).
    """
    with ExitStack() as stack:
        def open_browser(*, write_headers: bool = True, raise_server_exceptions: bool = True) -> TestClient:
            client = TestClient(
                server,
                base_url=ORIGIN,
                headers=dict(WRITE_HEADERS) if write_headers else None,
                raise_server_exceptions=raise_server_exceptions,
            )
            return stack.enter_context(client)

        yield open_browser


@functools.lru_cache(maxsize=None)
def _password_hash(password: str) -> str:
    # scrypt بمعاملات الإنتاج يكلّف عُشر ثانية؛ تجزئةٌ واحدة لكل كلمة تكفي.
    return hash_password(password)


def add_user(owner, username: str, *, password: str = PASSWORD, active: bool = True,
             profession: str = "MARKETING") -> UUID:
    """حسابٌ مفعَّل كما يتركه التفعيل: HMAC الاسم، وتجزئة الكلمة، و`activated_at`."""
    return make_user(owner, login=auth.login_hmac(LOGIN_KEY, username),
                     password_hash=_password_hash(password), active=active, profession=profession)


def log_in(client: TestClient, username: str = SELLER, password: str = PASSWORD) -> httpx.Response:
    return client.post("/api/auth/login", json={"username": username, "password": password})


def signed_in(owner, browser, username: str, *, profession: str = "MARKETING", **options) -> TestClient:
    add_user(owner, username, profession=profession)
    client = browser(**options)
    response = log_in(client, username)
    assert response.status_code == 204, response.text
    return client


@pytest.fixture
def seller(owner, browser) -> TestClient:
    return signed_in(owner, browser, SELLER)


@pytest.fixture
def intruder(owner, browser) -> TestClient:
    return signed_in(owner, browser, INTRUDER)


def with_cookie(token: str) -> dict[str, str]:
    """ملفّ الجلسة يدوياً — لإعادة رمزٍ قديم من متصفّحٍ بلا جرّة."""
    return {"Cookie": f"{COOKIE}={token}"}


# ── الصور ──────────────────────────────────────────────────────────────
def noise_jpeg(size: tuple[int, int] = (640, 480), *, gps: bool = False) -> bytes:
    """صورة ضجيجٍ (لا تُضغط إلى لا شيء)، وبموقع التقاطٍ في EXIF إن طُلب."""
    image = Image.effect_noise(size, 60).convert("RGB")
    buffer = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif[ExifTags.Base.Make] = "Apple"
        location = exif.get_ifd(ExifTags.IFD.GPSInfo)
        location[ExifTags.GPS.GPSLatitudeRef] = "N"
        location[ExifTags.GPS.GPSLatitude] = (24.0, 42.0, 51.5)
        location[ExifTags.GPS.GPSLongitudeRef] = "E"
        location[ExifTags.GPS.GPSLongitude] = (46.0, 40.0, 3.2)
        image.save(buffer, "JPEG", exif=exif)
    else:
        image.save(buffer, "JPEG")
    return buffer.getvalue()


# ── خطوات الحملة ───────────────────────────────────────────────────────
def expect(response: httpx.Response, status: int = 200) -> dict:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


def path(view: dict, suffix: str = "") -> str:
    return f"/api/campaigns/{view['id']}{suffix}"


def upload(client: TestClient, jpeg: bytes | None = None) -> dict:
    return expect(client.post("/api/campaigns", content=jpeg or noise_jpeg(), headers=JPEG), 201)


def generate(client: TestClient, view: dict) -> dict:
    body = expect(client.post(path(view, "/copy"), json={"expected_row_version": view["row_version"]}))
    assert body["result"] == "OK", body
    return body["campaign"]


def edit(client: TestClient, view: dict, presets: tuple[str, ...] = ("SHORTER",),
         note: str | None = None) -> dict:
    payload = {"expected_row_version": view["row_version"], "expected_version_id": view["copy"]["version_id"],
               "presets": list(presets)}
    if note is not None:
        payload["note"] = note
    body = expect(client.post(path(view, "/copy/edit"), json=payload))
    assert body["result"] == "OK", body
    return body["campaign"]


def approve(client: TestClient, view: dict) -> dict:
    return expect(client.post(path(view, "/copy/approve"), json={
        "expected_row_version": view["row_version"], "version_id": view["copy"]["version_id"]}))


def set_budget(client: TestClient, view: dict, sar: int) -> dict:
    return expect(client.put(path(view, "/budget"), json={
        "expected_row_version": view["row_version"], "budget_sar": sar}))


def set_days(client: TestClient, view: dict, days: int) -> dict:
    return expect(client.put(path(view, "/days"), json={
        "expected_row_version": view["row_version"], "days": days}))


def current(client: TestClient, view: dict) -> dict:
    return expect(client.get(path(view)))


# ── ما في القاعدة ──────────────────────────────────────────────────────
def attempts(owner) -> list[tuple[str | None, bool]]:
    """(النتيجة، أُغلقت؟) لكل محاولة، بترتيب بدئها."""
    with owner.cursor() as cursor:
        cursor.execute("SELECT outcome, finished_at IS NOT NULL FROM generation_attempts ORDER BY started_at")
        return [tuple(row) for row in cursor.fetchall()]


def open_attempts(owner) -> int:
    with owner.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM generation_attempts WHERE finished_at IS NULL")
        return cursor.fetchone()[0]
