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


def test_the_patient_portal_keeps_its_own_headers(client):
    """الترويسات للوحة وحدها: البوابة لا تتغيّر بسببها."""
    response = client.get("/app/")
    assert "Content-Security-Policy" not in response.headers
