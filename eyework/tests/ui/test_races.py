"""
ردودٌ تصل بعد أن غادر المستخدم
==============================
النظر بطيءٌ والشبكة أبطأ أحياناً: ما يصل بعد انتقالٍ أحدث لا يرسم الشاشة التي
تركها المستخدم، ولا يغيّر الحملة التي يعمل عليها الآن.
"""

from __future__ import annotations

from eyework.tests.ui.flow import Flow, sample_photo

PHOTO = {"name": "p.jpg", "mimeType": "image/jpeg", "buffer": sample_photo()}


def _hold(page, pattern: str, method: str | None = None) -> list:
    """يحبس الطلبات المطابقة حتى يُطلقها الاختبار؛ وما سواها يمرّ."""
    held: list = []

    def handler(route):
        if method and route.request.method != method:
            route.continue_()
            return
        held.append(route)
    page.route(pattern, handler)
    return held


def _draft(flow: Flow) -> str:
    page = flow.page
    page.goto(flow.base + "/#/new")
    flow.screen("photo")
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until("location.hash.startsWith('#/c/')")
    return page.evaluate("() => location.hash.slice(4)")


def test_a_slow_read_of_one_draft_does_not_take_over_a_new_campaign(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    draft = _draft(flow)
    page.goto(server["base"] + "/#/")
    flow.until("document.querySelectorAll('#home-list li').length === 1")
    # الحملة تُقرأ من جديد حين تُفتح من القائمة؛ تُحبس قراءتها.
    page.evaluate("() => { state.campaign = null; }")
    held = _hold(page, f"**/api/campaigns/{draft}", "GET")
    page.click("#home-list li button")
    page.wait_for_function("() => location.hash.startsWith('#/c/')")
    page.click("#home-new")
    flow.screen("photo")
    held[0].continue_()
    page.wait_for_load_state("networkidle")

    assert page.evaluate("() => location.hash") == "#/new"
    assert page.evaluate("() => state.campaign") is None
    flow.screen("photo")
    page.unroute(f"**/api/campaigns/{draft}")
    writes = []
    page.on("request", lambda r: writes.append((r.method, r.url)) if r.method in ("POST", "PUT") else None)
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until("location.hash.startsWith('#/c/')")
    assert [m for m, url in writes if "/api/campaigns" in url] == ["POST"], writes
    assert not page.errors, page.errors


def test_leaving_during_an_approval_does_not_redraw_the_screen_left(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    _draft(flow)
    page.click("#photo-generate")
    flow.until("!document.querySelector('#proposal-copy').hidden")
    held = _hold(page, "**/api/campaigns/*/copy/approve")
    page.click("#proposal-end")
    page.wait_for_function("() => state.busy === true")
    page.click(".screen[data-screen='proposal'] [data-back]")
    flow.screen("home")
    held[0].continue_()
    page.wait_for_load_state("networkidle")

    assert page.evaluate("() => location.hash") == "#/"
    flow.screen("home")
    assert page.evaluate("() => state.campaign") is None
    assert not page.errors, page.errors


def test_check_now_twice_while_offline_keeps_the_waiting_screen(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    _draft(flow)
    # الطلب ينقطع في الطريق، وقراءة الحملة تنقطع أيضاً: مآل الكتابة غير معروف.
    page.route("**/api/campaigns/*/copy", lambda route: route.abort())
    page.route("**/api/campaigns/*", lambda route: route.abort()
               if route.request.method == "GET" else route.continue_())
    page.click("#photo-generate")
    flow.until("!document.querySelector('.screen[data-screen=proposal] .alert').hidden")
    page.click(".screen[data-screen='proposal'] [data-ack]")
    # «حسناً» لا تغادر الانتظار: «تحقّق الآن» هو المخرج.
    assert page.is_visible("#proposal-check")
    page.click("#proposal-check")
    page.click("#proposal-check", force=True, no_wait_after=True)
    flow.until("!document.querySelector('.screen[data-screen=proposal] .alert').hidden")
    flow.screen("proposal")
    assert page.is_visible("#proposal-waiting")
    assert not page.errors, page.errors
