"""
متغيّرات مكتبة Anthropic في البيئة
==================================
المكتبة تقرأ بصمت وجهةً وترويساتٍ وإعداد تسجيل من البيئة. أيٌّ منها هنا يرسل
الصورة إلى غير Anthropic أو يكتبها في سجلّ، فيرفض التطبيق الإقلاع.
"""

from __future__ import annotations

import base64

import pytest

from eyework import config


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("EYEWORK_APP_DATABASE_URL", "postgresql://x@localhost/eyework_test")
    monkeypatch.setenv("EYEWORK_LOGIN_KEY", base64.b64encode(b"k" * 32).decode())
    monkeypatch.setenv("EYEWORK_PUBLIC_ORIGIN", "http://localhost:8000")
    for name in config.SDK_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("name", config.SDK_ENVIRONMENT)
def test_the_app_refuses_to_start_with_an_sdk_override(base_env, monkeypatch, name):
    monkeypatch.setenv(name, "anything")
    with pytest.raises(config.ConfigError, match=name):
        config.load()


def test_the_app_starts_without_them(base_env):
    assert config.load().public_origin == "http://localhost:8000"
