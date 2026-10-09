"""
الدخول على الواجهة الجديدة
==========================
بكلمة المرور: الخطأ يُقال في سطره ولا ينتقل شيء، والصواب يفتح الرئيسية بحجم الحساب من
الخادم لا من العنوان. و«حجمٌ أكبر» قبل الدخول يحمل الحجم في العنوان.
"""

from __future__ import annotations

import pytest

from eyework.tests.ui.conftest import PASSWORD
from eyework.tests.ui.next.conftest import DESKTOP, LANDSCAPE, LOGIN, PHONES, STRESS, frame_ids, member
from eyework.tests.ui.next.flow import Flow

#: أضيق هاتف، وإطار الإجهاد، والآيباد أفقياً.
SIGN_IN_FRAMES = [PHONES[0], STRESS, LANDSCAPE]


@pytest.mark.parametrize(("width", "height"), SIGN_IN_FRAMES, ids=frame_ids(SIGN_IN_FRAMES))
@pytest.mark.parametrize("size", ["compact", "gaze"])
def test_the_password_signs_in_and_the_servers_size_wins(next_page, server, owner, width, height, size):
    member(owner, size="GAZE" if size == "gaze" else "COMPACT")
    page = next_page(width, height, size=size)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#welcome-login")
    flow.audit("welcome")
    flow.press("#welcome-login", lambda: flow.screen("input[name='username']"), "ادخل")
    flow.audit("login")
    page.fill("input[name='username']", LOGIN)
    page.fill("input[name='password']", "wrong-password-2026")
    flow.press("button[type='submit']", lambda: flow.until(
        "document.querySelector('form [role=alert]').textContent.trim().length > 0"), "ادخل (خطأ)")
    flow.audit("login-error")
    assert page.url.endswith("#/login")
    page.fill("input[name='password']", PASSWORD)
    flow.press("button[type='submit']", lambda: flow.screen("[aria-label='ابدأ عملاً']"), "ادخل")
    flow.audit("home")
    assert page.evaluate("() => document.documentElement.dataset.size") == size
    assert not flow.failures(), "\n".join(flow.failures())
    if size == "gaze" and (width, height) != DESKTOP:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()


def test_the_size_toggle_before_sign_in_lives_in_the_address(next_page, server, owner):
    page = next_page()
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#welcome-login")
    assert page.evaluate("() => document.documentElement.dataset.size") == "compact"
    flow.press("button[aria-pressed='false']", lambda: flow.until(
        "document.documentElement.dataset.size === 'gaze'"), "حجمٌ أكبر")
    assert "size=large" in page.url and "gaze" not in page.url
    flow.audit("welcome-gaze")
    page.reload()
    flow.screen("#welcome-login")
    assert page.evaluate("() => document.documentElement.dataset.size") == "gaze"
    assert not flow.failures(), "\n".join(flow.failures())


def test_a_signed_in_account_with_the_servers_size_opens_the_home_directly(next_page, server, owner):
    member(owner, size="GAZE")
    page = next_page(login=LOGIN)
    page.goto(page.next)
    page.wait_for_selector("[aria-label='ابدأ عملاً']")
    assert page.evaluate("() => document.documentElement.dataset.size") == "gaze"
    assert not page.errors, page.errors
