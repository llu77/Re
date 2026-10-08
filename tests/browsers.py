"""
Chromium لاختبارات المتصفّح
============================
المتصفّح الذي ثبّته Playwright نفسه (`python -m playwright install chromium`)
أولاً، كما في CI. ثم المثبَّت في بيئة التطوير تحت `/opt/pw-browsers` حين لا
يطابق إصدار Playwright متصفّحه.

**الغياب فشلٌ في CI لا تجاوز.** `SYMBOL_REQUIRE_BROWSER=1` يجعل غياب Playwright
أو Chromium أو بناء لوحة الممارس فشلاً: فحصٌ يُتجاوز بصمت يبدو أخضر وهو لم
يفحص شيئاً. وبلا الضبط يُتجاوز بسببٍ صريح، كما في أيّ بيئة تطوير ناقصة.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import NoReturn

import pytest

REQUIRE_BROWSER = os.environ.get("SYMBOL_REQUIRE_BROWSER") == "1"

#: المتصفّح المثبَّت في بيئة التطوير، حين لا يطابق إصدار Playwright متصفّحه.
LOCAL_CHROMIUM = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


def unavailable(reason: str) -> NoReturn:
    """يتجاوز الوحدة أو الاختبار بالسبب، أو يُفشله حين يُطلب المتصفّح."""
    if REQUIRE_BROWSER:
        pytest.fail(f"{reason} (SYMBOL_REQUIRE_BROWSER=1)", pytrace=False)
    pytest.skip(reason, allow_module_level=True)


@functools.cache
def _installed() -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as pw:
        own = Path(pw.chromium.executable_path)
    for candidate in (own, LOCAL_CHROMIUM):
        if candidate.is_file():
            return str(candidate)
    return ""


def chromium_executable() -> str:
    """مسار Chromium يُشغَّل به، أو تجاوزٌ/فشلٌ بالسبب."""
    found = _installed()
    if found is None:
        unavailable("playwright غير مثبّت")
    if not found:
        unavailable("متصفح Chromium غير متاح")
    return found
