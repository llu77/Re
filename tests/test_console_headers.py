"""
ترويسات لوحة الممارس
=====================
تُقرأ من التطبيق نفسه بلا متصفّح ولا قاعدة، فتعمل حيث لا يعمل
`test_console.py`: غياب Chromium لا يُسقط معه فحص سياسة المحتوى.

ما يحتاج البناء (ملفٌّ مجزّأ حقيقي من `console/dist`) يُتجاوز بلا بناء، ويفشل
في CI (`SYMBOL_REQUIRE_BROWSER=1`، انظر `tests/browsers.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import browsers

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from api.app import create_app  # noqa: E402

DIST = Path(__file__).resolve().parent.parent / "console" / "dist" / "index.html"


@pytest.fixture(scope="module")
def client():
    # بلا `with`: لا يُشغَّل طور الإقلاع، فلا تُفتح اتصالات قاعدة لا يحتاجها هذا.
    return TestClient(create_app())


def test_the_console_is_served_with_its_security_headers(client):
    if not DIST.exists():  # pragma: no cover - يعتمد على البناء
        browsers.unavailable("لوحة الممارس لم تُبنَ: npm ci && npm run build في console/")
    response = client.get("/console/")
    assert response.status_code == 200
    headers = response.headers
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Cache-Control"] == "no-cache"

    asset = response.text.split('src="', 1)[1].split('"', 1)[0]
    response = client.get(asset)
    assert response.status_code == 200
    assert "immutable" in response.headers["Cache-Control"]
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    # إعادة التحقّق (304) تُبقي الملفّ المحفوظ ثابتاً لا تُسقط عنه «immutable».
    revalidated = client.get(asset, headers={"If-None-Match": response.headers["ETag"]})
    assert revalidated.status_code == 304
    assert "immutable" in revalidated.headers["Cache-Control"]


def test_illustrations_may_be_data_images_but_scripts_stay_on_the_origin(client):
    """
    رسوم المقترحات تُراجَع صوراً بعنوان `data:`، فتسمح بها `img-src`. وما
    عداها لا يتّسع: السكربت والخط والاتصال من الأصل وحده.
    """
    policy = client.get("/console/").headers["Content-Security-Policy"]
    directives = {
        name: values
        for name, *values in (part.split() for part in policy.split(";") if part.strip())
    }
    assert directives["img-src"] == ["'self'", "data:"]
    assert directives["script-src"] == ["'self'"]
    assert directives["font-src"] == ["'self'"]
    assert directives["connect-src"] == ["'self'"]
    assert directives["default-src"] == ["'none'"]


@pytest.mark.parametrize("path", ["/console/assets/index-DOESNOTEXIST.js", "/console/assets/"])
def test_a_missing_asset_is_never_cached(client, path):
    """
    نشرٌ متدرّج: الصفحة الجديدة تطلب ملفّاً مجزّأً من نسخةٍ لم يصلها بعد.
    خطؤها (404، أو 503 بلا بناء) كان يُرسَل «immutable» لسنة، فيبقى في
    المتصفّح وأيّ ذاكرةٍ وسيطة بعد أن يصل الملفّ.
    """
    response = client.get(path)
    assert response.status_code in (404, 503)
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_the_patient_portal_keeps_its_own_headers(client):
    """الترويسات للوحة وحدها: البوابة لا تتغيّر بسببها."""
    response = client.get("/app/")
    assert "Content-Security-Policy" not in response.headers
