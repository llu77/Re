"""
هيكل البوابة: شريط التبويب السفلي، والشريط الجانبي، والأدوات
============================================================
الهاتف: أربعة بنودٍ ثابتة في أسفل الشاشة (الرئيسية، والأقسام، والأدوات، وحسابي) روابط وأزرارٌ
آمنة لا تعتمد شيئاً؛ الآيباد والحاسوب: شريطٌ جانبي ببنود البوابة والأدوات وحسابي؛ وفي الحجم الكبير
سكّةٌ بالبنود الأربعة نفسها (اثنا عشر هدفاً على الأكثر). زرّ الأدوات في كل شاشة يفتح «اسأل
سيمبول» و«مساعدة» لا غير، والسؤال يصل الخادم ويعود جوابه. والشريط السفلي يختفي ما دام حقلٌ
مركَّزاً فلا يركب لوحة المفاتيح؛ وفي العريض بحجم اللمس تُعرض «حملاتي» بجانب الحملة.
"""

from __future__ import annotations

import pytest

from eyework.tests.conftest import add_version, create_campaign
from eyework.tests.fakes import FakeGateway
from eyework.tests.ui.next.conftest import DESKTOP, LOGIN, PHONES, TABLETS, WIDE, frame_ids, member
from eyework.tests.ui.next.flow import Flow

NAV = ["nav-home", "nav-sections", "nav-tools", "nav-account"]


def _ids(page, selector: str) -> list[str]:
    return page.eval_on_selector_all(selector, "(es) => es.map((e) => e.id)")


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


def test_the_tab_bar_opens_the_sections_the_tools_and_the_account(next_page, server, owner):
    member(owner)
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#nav-home")
    assert _ids(page, "nav[aria-label='أقسام البوابة'] a, nav[aria-label='أقسام البوابة'] button") == NAV
    assert page.get_attribute("#nav-home", "href") == "#/marketing"
    assert page.get_attribute("#nav-account", "href") == "#/account"
    assert page.get_attribute("#nav-home", "aria-current") == "page"
    assert page.locator("#sidebar").count() == 0
    flow.audit("home")

    flow.press("#nav-sections", lambda: flow.screen("dialog[open]"), "الأقسام")
    flow.audit("sections")
    assert page.eval_on_selector_all("dialog[open] a", "(as) => as.map((a) => a.getAttribute('href'))") == ["#/marketing/new", "#/marketing/campaigns"]
    flow.press("dialog[open] a >> nth=1", lambda: flow.screen("#campaigns-newer"), "حملاتي")
    assert page.locator("dialog[open]").count() == 0
    assert page.evaluate("() => location.hash") == "#/marketing/campaigns"

    flow.press("#nav-tools", lambda: flow.screen("dialog[open]"), "الأدوات")
    names = page.eval_on_selector_all("dialog[open] ul button", "(bs) => bs.map((b) => b.textContent.trim())")
    assert len(names) == 2 and names[0].startswith("اسأل سيمبول") and names[1].startswith("مساعدة")
    flow.press("dialog[open] >> text=إغلاق", lambda: page.wait_for_selector("dialog[open]", state="detached"), "إغلاق")

    flow.press("#nav-account", lambda: flow.screen("#account-ui-size-apply"), "حسابي")
    assert page.get_attribute("#nav-account", "aria-current") == "page"
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_tools_button_offers_symbol_and_help_and_the_question_is_answered(next_page, server, owner):
    member(owner, size="GAZE")
    server["app"].state.gateway = FakeGateway()
    page = next_page(login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.press("#nav-tools", lambda: flow.screen("dialog[open]"), "الأدوات")
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


@pytest.mark.parametrize(("width", "height"), WIDE, ids=frame_ids(WIDE))
def test_the_sidebar_lists_the_entries_and_the_tools_on_wide_frames(next_page, server, owner, width, height):
    member(owner)
    page = next_page(width, height, login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#sidebar")
    flow.audit("home-wide")
    assert _ids(page, "#sidebar a, #sidebar button") == ["nav-home", "nav-entry-new", "nav-entry-campaigns", "nav-assistant", "nav-help", "nav-account"]
    assert page.locator("#nav-sections").count() == 0 and page.locator("#nav-tools").count() == 0
    assert page.get_attribute("#nav-home", "aria-current") == "page"
    flow.press("#nav-entry-new", lambda: flow.screen("#photo-input"), "حملة جديدة")
    assert page.get_attribute("#nav-entry-new", "aria-current") == "page"
    flow.audit("photo-wide")
    flow.press("#nav-assistant", lambda: flow.screen("dialog[open] textarea"), "اسأل سيمبول")
    flow.audit("assistant-wide")
    flow.press("dialog[open] >> text=إغلاق", lambda: page.wait_for_selector("dialog[open]", state="detached"), "إغلاق")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_gaze_rail_has_the_four_entries_only(next_page, server, owner):
    member(owner, size="GAZE")
    page = next_page(*TABLETS[2], login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#sidebar")
    flow.audit("home-rail")
    assert _ids(page, "#sidebar a, #sidebar button") == NAV
    flow.press("#nav-sections", lambda: flow.screen("dialog[open]"), "الأقسام")
    flow.audit("sections-rail")
    assert page.eval_on_selector_all("dialog[open] a", "(as) => as.map((a) => a.getAttribute('href'))") == ["#/marketing/new", "#/marketing/campaigns"]
    flow.press("dialog[open] a >> nth=0", lambda: flow.screen("#photo-input"), "حملة جديدة")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()


@pytest.mark.parametrize("size", ["compact", "gaze"])
def test_the_list_and_the_campaign_share_the_wide_screen_by_touch_only(next_page, server, owner, app, size):
    user = member(owner, size="GAZE" if size == "gaze" else "COMPACT")
    campaign = create_campaign(app, user)
    add_version(app, user, campaign)
    page = next_page(*DESKTOP, login=LOGIN, size=size)
    flow = Flow(page)
    page.goto(page.next + f"#/marketing/c/{campaign}")
    flow.screen("#proposal-copy")
    flow.audit("campaign-wide")
    if size == "compact":
        assert page.is_visible("#campaigns-list")
        assert page.eval_on_selector_all("#campaigns-list li button", "(bs) => bs.length") == 1
    else:
        assert page.locator("#campaigns-list").count() == 0
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_tab_bar_hides_while_a_field_has_focus(next_page, server, owner, app):
    user = member(owner)
    campaign = create_campaign(app, user)
    add_version(app, user, campaign)
    page = next_page(*PHONES[1], login=LOGIN)
    flow = Flow(page)
    page.goto(page.next + f"#/marketing/c/{campaign}/note")
    flow.screen("#note-text")
    assert page.is_visible("#nav-home")
    page.focus("#note-text")
    flow.until("document.documentElement.dataset.keyboard === 'open'")
    assert page.is_hidden("#nav-home")
    page.evaluate("() => document.activeElement.blur()")
    flow.until("document.documentElement.dataset.keyboard === undefined")
    assert page.is_visible("#nav-home")
    assert not page.errors, page.errors
