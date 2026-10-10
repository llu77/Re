"""
تسلسل البدء لحسابٍ قائم
=======================
حسابٌ بلا طريقة استخدامٍ (دعوة) يُسأل «كيف تستخدم الجهاز؟» ثم يقرأ الإشعار ويوافق، ثم
الرئيسية؛ وحسابٌ بطريقةٍ وبلا موافقةٍ يقرأ الإشعار وحده. وقبل الموافقة لا رئيسية.
"""

from __future__ import annotations

from eyework import terms
from eyework.tests.ui.next.conftest import LOGIN, member
from eyework.tests.ui.next.flow import Flow


def _row(owner):
    with owner.cursor() as cursor:
        cursor.execute("SELECT ui_size, terms_version FROM users")
        return cursor.fetchone()


def test_an_invited_account_chooses_its_size_then_agrees_then_works(next_page, server, owner):
    member(owner, size=None, terms_version=None)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#signup-use-next")
    flow.audit("start-size")
    assert page.locator("[aria-label='ابدأ عملاً']").count() == 0
    flow.press("#signup-use-GAZE", lambda: None, "بتتبّع العين")
    flow.press("#signup-use-next", lambda: flow.screen("#notice-next"), "التالي")
    assert page.evaluate("() => document.documentElement.dataset.size") == "gaze"
    assert _row(owner) == ("GAZE", None)
    flow.audit("start-notice-kept")
    flow.press("#notice-next", lambda: flow.screen("#signup-agree"), "التالي")
    flow.audit("start-notice-sent")
    flow.press("#signup-agree", lambda: flow.screen("[aria-label='ابدأ عملاً']"), "أوافق وأتابع")
    flow.audit("home")
    assert _row(owner) == ("GAZE", terms.TERMS_VERSION)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


def test_an_account_with_a_size_but_no_consent_reads_the_notice_only(next_page, server, owner):
    member(owner, size="COMPACT", terms_version=None)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#notice-next")
    assert page.locator("#signup-use-next").count() == 0
    flow.press("#notice-next", lambda: flow.screen("#signup-agree"), "التالي")
    flow.press("#signup-agree", lambda: flow.screen("[aria-label='ابدأ عملاً']"), "أوافق وأتابع")
    assert _row(owner) == ("COMPACT", terms.TERMS_VERSION)
    assert not page.errors, page.errors
