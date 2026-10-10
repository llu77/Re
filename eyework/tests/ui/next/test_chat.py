"""
المحادثة مع سيمبول في المتصفّح
==============================
زرّ سيمبول في كل شاشةٍ من البوابة: دائرةٌ بجانب شريط التبويب العائم في الهاتف، والمحتوى ينتهي فوقهما؛ وفي
الحجم الكبير في صفّ الشريط نفسه، لا فوق المحتوى. الورقة محادثةٌ تبقى بين الشاشات: الأسئلة الجاهزة، والسؤال المكتوب،
وما قرأه سيمبول بأدواته سطوراً تحت جوابه، والشاشة التي يقترحها زرٌّ يفتحها الموظف بنفسه. وفي الحجم الكبير
ثلاث صفحاتٍ بلا تمرير تجتاز عقد النظر على أضيق الإطارات، ولا تقع نظرةٌ بعد ضغطةٍ على ما يُرسل.
"""

from __future__ import annotations

import pytest

from eyework.tests.fakes import FakeGateway, assistant_reply, tool_request
from eyework.tests.ui.next.conftest import HANDHELD, LOGIN, NAME, STRESS, TABLETS, TIGHTEST, frame_ids, member
from eyework.tests.ui.next.flow import Flow

ANSWER = "ابدأ من «حملة جديدة»، ثم راجع «حملاتي»."
LONG = ("ابدأ يومك من «حملاتي»: ما ينتظر اعتمادك أوّلاً، ثم المسودات. اقرأ النصّ المقترح كاملاً قبل أن توافق عليه. "
        "إن لم يناسبك فاطلب نسخةً أخرى واذكر السبب في ملاحظة. ثم اختر الميزانية والمدّة وراجع الملخّص قبل الاعتماد.")


@pytest.fixture
def gateway(server) -> FakeGateway:
    fake = FakeGateway()
    server["app"].state.gateway = fake
    return fake


def _posted(page) -> list[dict]:
    """أجسام طلبات السؤال كما خرجت من الصفحة."""
    return page.evaluate("() => window.__chatBodies || []")


CAPTURE = """
(() => {
    const original = window.fetch;
    window.__chatBodies = [];
    window.fetch = (input, init) => {
        if (String(input).endsWith('/api/ai/assistant') && init && init.body) window.__chatBodies.push(JSON.parse(init.body));
        return original(input, init);
    };
})()
"""


@pytest.mark.parametrize(("width", "height"), HANDHELD, ids=frame_ids(HANDHELD))
def test_the_floating_button_sits_beside_the_tab_bar_and_the_content_ends_above_them(next_page, server, owner, width, height):
    member(owner)
    page = next_page(width, height, login=LOGIN)
    flow = Flow(page)
    page.goto(page.next + "#/marketing/campaigns")
    flow.screen("#nav-chat")
    flow.audit("campaigns")
    launcher = page.eval_on_selector("#nav-chat", "(e) => { const r = e.getBoundingClientRect(); return [r.top, r.bottom, r.left, r.right] }")
    bar = page.eval_on_selector("nav[aria-label='أقسام البوابة']", "(e) => { const r = e.getBoundingClientRect(); return [r.top, r.bottom, r.left, r.right] }")
    # في صفّ الشريط نفسه، ومركزاهما على خطٍّ واحد، وبينهما فجوة.
    assert abs((launcher[0] + launcher[1]) / 2 - (bar[0] + bar[1]) / 2) <= 1, (launcher, bar)
    assert launcher[3] <= bar[2] - 7.5, (launcher, bar)
    # طرف النهاية: يسار الصفحة العربية، بحافّتها.
    assert abs(launcher[2] - 16) <= 0.5, launcher
    # آخر المحتوى بعد التمرير كلّه فوق الشريط والزرّ بالفجوة.
    page.evaluate("() => window.scrollTo(0, document.scrollingElement.scrollHeight)")
    last = page.evaluate("""() => Math.max(...[...document.querySelectorAll('main button, main a[href], main p, main h1')]
        .map((e) => e.getBoundingClientRect().bottom))""")
    top = min(launcher[0], bar[0])
    assert last <= top - 7.5, (last, top)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_conversation_carries_on_with_tools_and_opens_the_suggested_screen(next_page, server, owner, gateway):
    member(owner)
    page = next_page(login=LOGIN)
    page.add_init_script(CAPTURE)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] [role=log]"), "اسأل سيمبول")
    flow.audit("chat-empty")
    assert f"أهلاً {NAME}، كيف أساعدك" in page.inner_text("dialog[open] [role=log]")
    ready = page.eval_on_selector_all("dialog[open] ul[aria-label='أسئلةٌ جاهزة'] button", "(bs) => bs.map((b) => b.textContent.trim())")
    assert ready == ["من أين أبدأ عملي اليوم؟"]

    gateway.queue(assistant_reply(answer=ANSWER))
    flow.press("dialog[open] ul[aria-label='أسئلةٌ جاهزة'] button >> nth=0",
               lambda: flow.until("document.querySelector('dialog[open] [role=log]').textContent.includes('راجع «حملاتي»')"),
               "سؤالٌ جاهز")
    assert page.locator("dialog[open] ul[aria-label='أسئلةٌ جاهزة']").count() == 0

    gateway.queue(tool_request("CAMPAIGNS"), assistant_reply(answer="لا حملات بعد؛ ابدأ واحدة.", used=("TOOL",), open="new"))
    page.fill("dialog[open] textarea", "هل عندي حملات؟ رقمي 0551234567")
    flow.press("dialog[open] button[type=submit]", lambda: flow.screen("dialog[open] >> text=افتح «حملة جديدة»"), "أرسل")
    flow.audit("chat-answer")
    log = page.inner_text("dialog[open] [role=log]")
    assert "هل عندي حملات؟ رقمي [رقم]" in log and "0551234567" not in log
    assert "حملاتك" in log and "لا حملات بعد؛ ابدأ واحدة." in log
    bodies = _posted(page)
    assert bodies[0] == {"screen": {"kind": "HOME"}, "ready_question": 0, "history": []}
    assert bodies[1]["history"] == [{"question": "من أين أبدأ عملي اليوم؟", "answer": ANSWER}]
    assert "<conversation>" in gateway.calls[-1].user and '<tool_result name="CAMPAIGNS">' in gateway.calls[-1].user

    flow.press("dialog[open] >> text=افتح «حملة جديدة»", lambda: flow.screen("#photo-input"), "افتح")
    assert page.evaluate("() => location.hash") == "#/marketing/new"
    assert page.locator("dialog[open]").count() == 0
    # المحادثة باقيةٌ في الشاشة التالية، وسؤالها يحمل شاشته.
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] [role=log]"), "اسأل سيمبول")
    assert page.inner_text("dialog[open] [role=log]").count("سيمبول:") == 2
    flow.press("dialog[open] >> text=محادثة جديدة", lambda: flow.screen("dialog[open] ul[aria-label='أسئلةٌ جاهزة']"), "محادثة جديدة")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors
    flow.gaze_safe()


@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=frame_ids(TIGHTEST))
def test_the_gaze_size_pages_the_chat_without_scrolling_and_no_look_lands_on_a_send(next_page, server, owner, gateway, width, height):
    member(owner, size="GAZE")
    page = next_page(width, height, login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    assert page.eval_on_selector("#nav-chat", "(e) => getComputedStyle(e).position") != "fixed"
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] >> text=اكتب سؤالك"), "سيمبول")
    flow.audit("chat-start")
    names = page.eval_on_selector_all("dialog[open] button", "(bs) => bs.map((b) => b.textContent.trim())")
    assert names == ["من أين أبدأ عملي اليوم؟", "اكتب سؤالك", "الأدوات", "إغلاق"]

    gateway.queue(tool_request("CAMPAIGNS"), assistant_reply(answer=LONG, used=("TOOL",), open="campaigns"))
    flow.press("dialog[open] >> text=من أين أبدأ عملي اليوم؟", lambda: flow.screen("dialog[open] >> text=سؤالٌ جديد"), "سؤالٌ جاهز")
    flow.audit("chat-answer")
    assert "حملاتك" in page.inner_text("dialog[open]")
    pages = page.locator("dialog[open] nav[aria-label='صفحات جواب سيمبول']")
    assert pages.count() == 1, "الجواب الطويل صفحاتٌ في الحجم الكبير"
    flow.press("dialog[open] nav[aria-label='صفحات جواب سيمبول'] >> text=التالي",
               lambda: flow.until("document.querySelector('dialog[open] nav[aria-label=\"صفحات جواب سيمبول\"] span').textContent.startsWith('2')"),
               "التالي")
    flow.audit("chat-answer-2")

    flow.press("dialog[open] >> text=سؤالٌ جديد", lambda: flow.screen("dialog[open] >> text=اكتب سؤالك"), "سؤالٌ جديد")
    flow.press("dialog[open] >> text=اكتب سؤالك", lambda: flow.screen("dialog[open] textarea"), "اكتب سؤالك")
    flow.audit("chat-write")
    page.fill("dialog[open] textarea", "ماذا بعد الصورة؟")
    gateway.queue(assistant_reply(answer=ANSWER, open="new"))
    flow.press("dialog[open] button[type=submit]", lambda: flow.screen("dialog[open] #chat-answer-open"), "أرسل")
    flow.audit("chat-answer-open")
    # «افتح» وحده في نصف الشريط، واسم الشاشة في سطرٍ فوقه وفي اسم الزرّ لقارئ الشاشة.
    assert "الشاشة المقترحة: حملة جديدة" in page.inner_text("dialog[open] section[aria-label='جواب سيمبول']")
    assert page.get_attribute("dialog[open] #chat-answer-open", "aria-label") == "افتح «حملة جديدة»"
    flow.press("dialog[open] #chat-answer-open", lambda: flow.screen("#photo-input"), "افتح")
    assert page.evaluate("() => location.hash") == "#/marketing/new"
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()


def test_a_refused_question_shows_the_servers_reason_and_keeps_the_draft(next_page, server, owner, gateway):
    member(owner, size="GAZE")
    page = next_page(*STRESS, login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("[aria-label='ابدأ عملاً']")
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] >> text=اكتب سؤالك"), "سيمبول")
    flow.press("dialog[open] >> text=اكتب سؤالك", lambda: flow.screen("dialog[open] textarea"), "اكتب سؤالك")
    page.fill("dialog[open] textarea", "سؤالٌ يرفضه النموذج")
    from eyework.tests.fakes import model_reply
    gateway.queue(model_reply("UPSTREAM_BUSY", retry_after=45))
    flow.press("dialog[open] button[type=submit]", lambda: flow.screen("dialog[open] [role=alert]"), "أرسل")
    flow.audit("chat-refused")
    assert page.input_value("dialog[open] textarea") == "سؤالٌ يرفضه النموذج"
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", ["compact", "gaze"])
def test_the_tablet_has_symbol_in_the_corner_or_the_rail(next_page, server, owner, gateway, size):
    member(owner, size="GAZE" if size == "gaze" else "COMPACT")
    page = next_page(*TABLETS[0], login=LOGIN)
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#sidebar")
    inside = page.evaluate("() => document.querySelector('#sidebar').contains(document.querySelector('#nav-chat'))")
    assert inside is (size == "gaze")
    flow.audit("home-tablet")
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] button"), "سيمبول")
    flow.audit("chat-tablet")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_the_storekeepers_question_reads_the_items_and_suggests_a_screen(next_page, server, owner, gateway):
    member(owner, "keeper@example.sa", profession="STOREKEEPER")
    page = next_page(login="keeper@example.sa")
    flow = Flow(page)
    page.goto(page.next)
    flow.screen("#nav-chat")
    gateway.queue(tool_request("ITEMS", "ماء"), assistant_reply(answer="لا منتج بهذا الاسم بعد.", used=("TOOL",), open="item"))
    flow.press("#nav-chat", lambda: flow.screen("dialog[open] textarea"), "اسأل سيمبول")
    page.fill("dialog[open] textarea", "كم رصيد الماء؟")
    flow.press("dialog[open] button[type=submit]", lambda: flow.screen("dialog[open] >> text=افتح «منتج جديد»"), "أرسل")
    assert "بحث في المنتجات: «ماء»" in page.inner_text("dialog[open] [role=log]")
    assert "لا منتج يطابق «ماء»." in gateway.calls[-1].user
    flow.press("dialog[open] >> text=افتح «منتج جديد»", lambda: flow.until("location.hash === '#/inventory/items/new'"), "افتح")
    assert not page.errors, page.errors
