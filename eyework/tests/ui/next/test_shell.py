"""
هيكل البوابة: الرئيسية وقائمة الأقسام وزرّ الأدوات
=================================================
أزرار الرئيسية روابط آمنة تفتح عملاً (أداة الحملة تحت #/marketing/…)؛ وزرّ الأدوات في كل
شاشة يفتح «اسأل سيمبول» و«مساعدة» لا غير، والسؤال يصل الخادم ويعود جوابه.
"""

from __future__ import annotations

from eyework.tests.fakes import FakeGateway
from eyework.tests.ui.next.conftest import LOGIN, member
from eyework.tests.ui.next.flow import Flow


def test_the_home_buttons_are_safe_links_that_open_the_campaign_tool(next_page, server, owner):
    member(owner)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.audit("home")
    links = page.eval_on_selector_all("[aria-label='ابدأ عملاً'] a", "(as) => as.map((a) => [a.getAttribute('href'), a.hasAttribute('data-safe')])")
    assert links == [["#/marketing/new", True], ["#/marketing/campaigns", True]]
    flow.press("[aria-label='ابدأ عملاً'] a >> nth=0", lambda: flow.screen("#photo-input"), "حملة جديدة")
    assert page.evaluate("() => location.hash") == "#/marketing/new"
    flow.audit("photo")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_tools_button_offers_symbol_and_help_and_the_question_is_answered(next_page, server, owner):
    member(owner, size="GAZE")
    server["app"].state.gateway = FakeGateway()
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.press("text=الأدوات", lambda: flow.screen("dialog[open]"), "الأدوات")
    flow.audit("tools")
    names = page.eval_on_selector_all("dialog[open] ul button", "(bs) => bs.map((b) => b.textContent.trim())")
    assert len(names) == 2 and names[0].startswith("اسأل سيمبول") and names[1].startswith("مساعدة")
    flow.press("dialog[open] >> text=اسأل سيمبول", lambda: flow.screen("dialog[open] textarea"), "اسأل سيمبول")
    flow.audit("assistant")
    page.fill("dialog[open] textarea", "ماذا أبدأ به اليوم؟")
    flow.press("dialog[open] button[type='submit']", lambda: flow.until(
        "document.querySelector('dialog[open]').textContent.includes('سؤالك')"), "أرسل السؤال")
    flow.audit("assistant-answer")
    assert [url for method, url in page.requests if method == "POST" and url.endswith("/api/ai/assistant")]
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()


def test_the_sections_menu_lists_the_home_entries(next_page, server, owner):
    member(owner)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.press("button[aria-expanded='false']:visible", lambda: flow.screen("[aria-expanded='true']"), "الأقسام")
    flow.audit("menu")
    items = page.eval_on_selector_all("[id$='panel'] a, [role=menu] a, nav a", "(as) => as.map((a) => a.textContent.trim())")
    assert any("حملة جديدة" in item for item in items) and any("حملاتي" in item for item in items)
    assert not flow.failures(), "\n".join(flow.failures())
