"""
مكتب الدعم الفني على الواجهة الجديدة، بالحجمين
==============================================
المسار الكامل نقرةً نقرة: مقالةٌ في قاعدة المعرفة تُكتب وتُعتمد (مراجعة سيمبول بالبوّابة المصطنعة)، ثم
إشعار المكتب («قرأتُه» ثم «أوافق وأتابع»)، ثم تذكرةٌ يُلصق فيها كلام العميل فيُحذف بريده ورقمه قبل الحفظ،
فمسودة سيمبول المؤسَّسة على المقالة باقتباسها، فاعتماد اقتراح التصنيف، فـ«أرسل كما هي»، فـ«انسخ الردّ»
و«نعم، أرسلته» فتُحلّ التذكرة. ثم ردٌّ يكتبه الموظف فيه وعدٌ (تنبيه القاعدة) وملاحظة سيمبول، وقرار كلٍّ منهما
قبل النسخ؛ والتصعيد والحلّ دون ردٍّ والرفض؛ و«تحسين المسودات» والإعدادات. وفي كل شاشةٍ عقد النظر لكل حجم
(flow.py)، وقاعدتا الهبوط والأقرب إلى النظر في الحجم الكبير.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from eyework.tests.fakes import FakeGateway, draft_reply, flag, review_reply
from eyework.tests.ui.next.conftest import FRAMES, LOGIN, PHONES, STRESS, frame_ids, member
from eyework.tests.ui.next.flow import Flow

SIZES = ["compact", "gaze"]
BASE = "#/support"
SHOTS = os.environ.get("EYEWORK_SHOTS")
TITLE = "الطابعة تطبع صفحاتٍ فارغة"
ISSUE = "الطابعة تطبع صفحاتٍ فارغة بعد تغيير الحبر."
RESOLUTION = "1. افتح غطاء الطابعة وأخرج خرطوشة الحبر.\n2. انزع الشريط اللاصق الواقي إن كان موجوداً.\n3. اطبع صفحة اختبار."
CUSTOMER = "السلام عليكم، الطابعة في المكتب تطبع صفحاتٍ فارغة منذ الصباح. بريدي sara@example.com وجوالي 0551234567."
ANSWER = "نأسف لتعطّل الطباعة. جرّبوا ما يلي:\n1. انزعوا الشريط اللاصق الواقي إن كان موجوداً.\n2. اطبعوا صفحة اختبار.\nإن بقيت الصفحات فارغة فأخبرونا."


def _page(next_page, owner, server, size: str = "compact", width: int = 390, height: int = 664):
    """موظف دعمٍ بالحجم المطلوب، وصفحةٌ داخلةٌ به تقرأ الحافظة وتكتبها، والبوّابة المصطنعة بلا أجوبة مجدولة."""
    member(owner, profession="SUPPORT", size="GAZE" if size == "gaze" else "COMPACT")
    gateway = FakeGateway()
    server["app"].state.gateway = gateway
    server["app"].state.review_runner.gateway = gateway
    page = next_page(width, height, login=LOGIN, size=size)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=server["base"])
    page.gateway = gateway
    return page


def _gaze(page) -> bool:
    return page.evaluate("() => document.documentElement.dataset.size") == "gaze"


def _shot(page, label: str) -> None:
    if SHOTS:
        size = page.evaluate("() => document.documentElement.dataset.size")
        width = page.viewport_size["width"]
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=f"{SHOTS}/support-{label}-{size}-{width}.png", full_page=size != "gaze")


def _audit(flow: Flow, label: str) -> None:
    if not _gaze(flow.page):
        flow.page.evaluate("() => window.scrollTo(0, 0)")
    flow.audit(label)
    _shot(flow.page, label)


def _pick(flow: Flow, picker: str, key: str, text: str) -> None:
    """خيارٌ من منتقٍ: قائمة Select في الحجم العادي (بنصّ الخيار)، وخياراتٌ مكان الخطوة في الكبير (بمفتاحه)."""
    page = flow.page
    flow.press(f"#{picker}", lambda: flow.screen("[role=listbox]"), text)
    if _gaze(page):
        # المنتقي مفتوحاً: خياراته مكان الحقول المخفية، بلا قصٍّ ولا تراكبٍ على حقلٍ ظاهر.
        _audit(flow, f"{picker}-open")
        while page.locator(f"[role=listbox] [data-key='{key}']").count() == 0:
            flow.press("[data-gaze-host] [role=group] button:has-text('التالية')", lambda: None, "التالية")
        flow.press(f"[role=listbox] [data-key='{key}']", lambda: page.wait_for_selector("[role=listbox]", state="detached"), text)
    else:
        flow.press(f"[role=listbox] [role=option]:has-text('{text}')", lambda: page.wait_for_selector("[role=listbox]", state="detached"), text)


def _press_until(flow: Flow, button: str, target: str, label: str, limit: int = 8) -> None:
    """«التالي» حتى يظهر ما يُطلب (صفحات الحجم الكبير)."""
    page = flow.page
    for _ in range(limit):
        if page.locator(target).count():
            return
        flow.press(button, lambda: page.wait_for_load_state(), label)
    flow.screen(target)


def _status(owner, sql: str, params: tuple = ()):
    with owner.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


# ── قاعدة المعرفة ───────────────────────────────────────────────────────
def _article(flow: Flow) -> None:
    """مقالةٌ جديدة بحقولها، ثم «اعتمد» بمراجعة سيمبول (بلا ملاحظات) ثم «اعتمد المقالة»."""
    page = flow.page
    gaze = _gaze(page)
    flow.press("#home-knowledge", lambda: flow.screen("#kb-new"), "قاعدة المعرفة")
    _audit(flow, "kb-empty")
    flow.press("#kb-new", lambda: flow.screen("#article-title"), "مقالة جديدة")
    page.fill("#article-title", TITLE)
    page.fill("#article-issue", ISSUE)
    _audit(flow, "article-new")
    if gaze:
        flow.press("#article-next", lambda: flow.screen("#article-resolution"), "الحلّ")
    page.fill("#article-resolution", RESOLUTION)
    if gaze:
        _audit(flow, "article-resolution")
        flow.press("#article-next", lambda: flow.screen("#article-environment"), "البيئة")
        flow.press("#article-next", lambda: flow.screen("#article-save"), "الحفظ")
        _audit(flow, "article-save")
    flow.press("#article-save", lambda: flow.screen("#article-publish"), "احفظ المقالة")
    _audit(flow, "article")
    flow.press("#article-publish", lambda: flow.screen("#publish-prev, #publish-back"), "اعتمد")
    flow.until("document.querySelector('#publish-review') && !document.querySelector('#publish-review').textContent.includes('يراجع')")
    _audit(flow, "publish")
    if gaze:
        flow.press("#publish-next", lambda: flow.screen("#publish-submit"), "التالي")
        _audit(flow, "publish-submit")
    flow.press("#publish-submit", lambda: flow.screen("#article-needs-review"), "اعتمد المقالة")
    _audit(flow, "article-published")


# ── الإشعار والتذكرة ────────────────────────────────────────────────────
def _notice(flow: Flow) -> None:
    page = flow.page
    flow.press("#nav-home", lambda: flow.screen("#home-notice"), "الرئيسية")
    _audit(flow, "home-before-notice")
    flow.press("#home-notice", lambda: flow.screen("#notice-read"), "اقرأ الإشعار")
    _audit(flow, "notice")
    flow.press("#notice-read", lambda: flow.screen("#notice-agree"), "قرأتُه")
    _audit(flow, "notice-agree")
    flow.press("#notice-agree", lambda: flow.screen("#home-new"), "أوافق وأتابع")
    assert page.locator("#home-notice").count() == 0
    _audit(flow, "home")


CHANNELS = {"MESSAGING": "واتساب أو رسائل", "PHONE": "مكالمة"}


def _new_ticket(flow: Flow, text: str = CUSTOMER, label: str = "سارة", channel: str = "MESSAGING", subject: str | None = None) -> None:
    """القناة، ثم الرسالة، ثم ما سيُحفظ (البريد والرقم محذوفان)، ثم الاسم للتحية والموضوع، ثم الحفظ."""
    page = flow.page
    gaze = _gaze(page)
    flow.press("#home-new", lambda: flow.screen("#ticket-text, #ticket-channel"), "تذكرة جديدة")
    _audit(flow, "ticket-new")
    if gaze:
        _pick(flow, "ticket-channel", channel, CHANNELS[channel])
        flow.press("#ticket-next", lambda: flow.screen("#ticket-text"), "الرسالة")
    else:
        flow.press(f"#ticket-channel-{channel}", lambda: None, CHANNELS[channel])
    page.fill("#ticket-text", text)
    page.locator("#ticket-text").blur()
    _audit(flow, "ticket-message")
    flow.press("#ticket-next" if gaze else "#ticket-review", lambda: flow.screen("#ticket-masked"), "راجع ما سيُحفظ")
    _audit(flow, "ticket-preview")
    if "@" in text:
        assert page.text_content("#ticket-masked") == "حُذف: بريدٌ واحد، ورقمٌ واحد."
    if gaze:
        flow.press("#ticket-next", lambda: flow.screen("#ticket-label"), "التفاصيل")
    page.fill("#ticket-label", label)
    if subject:
        page.fill("#ticket-subject", subject)
    page.locator("#ticket-label").blur()
    _audit(flow, "ticket-details")
    if gaze:
        flow.press("#ticket-next", lambda: flow.screen("#ticket-save"), "الحفظ")
        _audit(flow, "ticket-save")
    flow.press("#ticket-save", lambda: flow.until("location.hash.includes('/t/')"), "احفظ التذكرة")


def _to_decisions(flow: Flow) -> None:
    """التذكرة حتى «قرارك»: صفحاتٌ بـ«التالي» في الحجم الكبير، وصفحةٌ تمرّ في العادي."""
    if _gaze(flow.page):
        _press_until(flow, "#ticket-next", "#decide-send, #decide-write, #decide-ask", "التالي")
        _audit(flow, "ticket-decide")


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), FRAMES, ids=frame_ids(FRAMES))
def test_the_agent_walks_from_an_article_to_a_confirmed_reply(next_page, server, owner, size, width, height):
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    gaze = size == "gaze"
    page.goto(page.next + "#/")
    flow.screen("#home-new")
    assert page.evaluate("() => location.hash") == BASE
    _audit(flow, "home-first")
    _notice(flow)
    _article(flow)
    flow.press("#nav-home", lambda: flow.screen("#home-new"), "الرئيسية")
    page.gateway.queue(draft_reply("DRAFT", "ANSWER", ANSWER, ({"article": "A1", "quote": "انزع الشريط اللاصق الواقي إن كان موجوداً"},),
                                   subject="الطابعة تطبع صفحاتٍ فارغة", impact="WIDESPREAD", urgency="STOPPED", note="استندتُ إلى مقالة الطابعة."))
    _new_ticket(flow, subject="طابعة المكتب")
    flow.until("!document.querySelector('#ticket-drafting')")
    flow.screen("#ticket-accept-suggestion")
    _audit(flow, "ticket-suggestion")
    flow.press("#ticket-accept-suggestion", lambda: flow.until("!document.querySelector('#ticket-accept-suggestion')"), "اعتمد المقترح")
    if not gaze:
        flow.screen("#ticket-draft")
        assert "KB-1 · " + TITLE in page.text_content("#ticket-draft")
        _audit(flow, "ticket")
    else:
        _press_until(flow, "#ticket-next", "#ticket-draft", "التالي")
        _audit(flow, "ticket-draft")
        assert "KB-1 · " + TITLE in page.text_content("#ticket-draft")
    _to_decisions(flow)
    flow.press("#decide-send", lambda: flow.screen("#reply-prev, #reply-back"), "أرسل كما هي")
    _audit(flow, "reply")
    assert page.locator("#reply-review").count() == 0
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-copy"), "التالي")
        _audit(flow, "reply-send")
    flow.press("#reply-copy", lambda: flow.screen("#reply-sent"), "انسخ الردّ")
    assert page.evaluate("() => navigator.clipboard.readText()").startswith("مرحباً سارة،\n\nنأسف لتعطّل الطباعة.")
    _audit(flow, "reply-confirm")
    flow.press("#reply-sent", lambda: flow.until("!location.hash.includes('/reply')"), "نعم، أرسلته")
    flow.screen("[data-screen-root]")
    _audit(flow, "ticket-resolved")
    assert not flow.failures(), "\n".join(flow.failures())
    if gaze:
        assert not flow.landings, "\n".join(flow.landings)
        flow.gaze_safe()
    assert not page.errors, page.errors
    status, category, label, subject = _status(owner, "SELECT status, category, customer_label, subject FROM support_tickets")
    assert (status, category, label, subject) == ("RESOLVED", "PRINTING", "سارة", "طابعة المكتب")
    assert _status(owner, "SELECT origin, state, release_via FROM support_replies") == ("AS_IS", "SENT", "COPY")
    body = _status(owner, "SELECT body FROM support_messages WHERE author = 'CUSTOMER'")[0]
    assert "sara@example.com" not in body and "0551234567" not in body and "[بريد محذوف]" in body
    sent = [call.user for call in page.gateway.calls if call.feature == "SUPPORT_DRAFT"]
    assert sent and all("سارة" not in user for user in sent)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), [PHONES[0], STRESS], ids=frame_ids([PHONES[0], STRESS]))
def test_a_reply_the_agent_writes_waits_for_a_decision_on_each_flag(next_page, server, owner, size, width, height):
    """ردٌّ بقلم الموظف فيه وعد: تنبيه القاعدة يُتجاوز بسببه، وملاحظة سيمبول «تابع رغم ذلك»، ثم النسخ."""
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    gaze = size == "gaze"
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    _new_ticket(flow, "الشاشة سوداء في جهاز الاستقبال منذ أمس ولا تستجيب.", "خالد")
    flow.until("!document.querySelector('#ticket-drafting')")
    _audit(flow, "ticket-cannot-answer")
    if gaze:
        _press_until(flow, "#ticket-next", "#decide-write", "التالي")
        _audit(flow, "ticket-more")
    flow.press("#decide-write", lambda: flow.screen("#compose-prev, #compose-back"), "اكتب الردّ بنفسك")
    _audit(flow, "compose")
    text = ("سنصلح الشاشة خلال 2 ساعات. أعيدوا تشغيل جهاز الاستقبال من زرّ الطاقة."
            if width > 320 else "أرسلوا لنا كلمة المرور الحالية لحسابكم في بوابة الموظفين لنعيد ضبطها. أعيدوا تشغيل الجهاز.")
    if gaze:
        flow.press("#compose-next", lambda: flow.screen("#compose-tool-write"), "التالي")
        flow.press("#compose-tool-write", lambda: None, "اكتب بنفسك")
        _audit(flow, "compose-how")
        flow.press("#compose-next", lambda: flow.screen("#compose-text"), "التالي")
        page.fill("#compose-text", text)
        page.locator("#compose-text").blur()
        _audit(flow, "compose-text")
        flow.press("#compose-next", lambda: flow.screen("#compose-prepare"), "جهّز")
        _audit(flow, "compose-prepare")
    else:
        page.fill("#compose-text", text)
        page.locator("#compose-text").blur()
    page.gateway.queue(review_reply(flag("UNAUTHORIZED_PROMISE", "HIGH", "reply", 1, "الردّ يعد بموعدٍ لا تذكره مقالة.", "احذف الموعد أو اذكر أنكم ستتابعون.")))
    flow.press("#compose-prepare", lambda: flow.screen("#reply-prev, #reply-back"), "جهّز الردّ")
    flow.until("document.querySelector('#reply-review') && !document.querySelector('#reply-review').textContent.includes('يراجع')")
    _audit(flow, "reply-review")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("[id^='flag-reason-']"), "التنبيه")
        _audit(flow, "reply-rule-flag")
    flag_id = page.get_attribute("[id^='flag-reason-']", "id").removeprefix("flag-reason-")
    _pick(flow, f"flag-reason-{flag_id}", "EMPLOYER_APPROVED", "جهة العمل موافقة")
    flow.press(f"#flag-dismiss-{flag_id}", lambda: flow.until("!document.querySelector('[id^=\"flag-dismiss-\"]')"), "تابع رغم ذلك")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("[data-flag-status='open']"), "التالي")
        _audit(flow, "reply-ai-flag")
    flow.press("[data-flag-status='open'] button[data-commit]", lambda: flow.until("!document.querySelector(\"[data-flag-status='open']\")"), "تابع رغم ذلك")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-copy"), "التالي")
    flow.until("!document.querySelector('#reply-copy').disabled")
    _audit(flow, "reply-decided")
    flow.press("#reply-copy", lambda: flow.screen("#reply-sent"), "انسخ الردّ")
    flow.press("#reply-sent", lambda: flow.until("!location.hash.includes('/reply')"), "نعم، أرسلته")
    assert not flow.failures(), "\n".join(flow.failures())
    if gaze:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    assert _status(owner, "SELECT origin, state FROM support_replies") == ("MANUAL", "SENT")
    assert _status(owner, "SELECT state, dismiss_reason FROM support_flags") == ("DISMISSED", "EMPLOYER_APPROVED")
    assert _status(owner, "SELECT choice FROM ai_flag_decisions ORDER BY id DESC LIMIT 1") == ("PROCEED",)


@pytest.mark.parametrize("size", SIZES)
def test_escalating_rejecting_and_resolving_without_a_written_reply(next_page, server, owner, size):
    """«ارفض المسودة» بسببه، ثم «صعّد» إلى جهةٍ بملاحظة، ثم «عاد الجواب»، ثم «حُلّت» وتذكيرٌ بآخر رسالةٍ بلا ردّ."""
    page = _page(next_page, owner, server, size, *PHONES[0])
    flow = Flow(page)
    gaze = size == "gaze"
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    page.gateway.queue(draft_reply("DRAFT", "ASK_INFO", "لنساعدكم بسرعة، ما نصّ رسالة الخطأ كما تظهر على الشاشة؟", (),
                                   impact="SINGLE", urgency="DEGRADED"))
    _new_ticket(flow, "البريد لا يصلني في الجوال منذ تحديث النظام.", "منى")
    flow.until("!document.querySelector('#ticket-drafting')")
    _to_decisions(flow)
    if gaze:
        _press_until(flow, "#ticket-next", "#decide-reject", "المزيد")
    flow.press("#decide-reject", lambda: flow.screen("#reject-reason"), "ارفض المسودة")
    _audit(flow, "reject")
    _pick(flow, "reject-reason", "TOO_LONG", "أطول من اللازم")
    flow.press("#reject-submit", lambda: flow.until("!location.hash.includes('/reject')"), "ارفض المسودة")
    assert _status(owner, "SELECT reject_reason FROM support_drafts") == ("TOO_LONG",)
    # ملاحظةٌ داخلية تُقرأ في الحجم الكبير أيضاً: صفحة «المحادثة» بعد آخر رسالة.
    ticket_id = page.evaluate("() => location.hash").split("/t/")[1].split("/")[0].split("?")[0]
    api, headers = f"{server['base']}/api/support/tickets/{ticket_id}", {"X-Eyework": "1", "Origin": server["base"]}
    version = page.request.get(api).json()["row_version"]
    noted = page.request.post(api + "/messages", headers=headers, data={
        "client_token": str(uuid.uuid4()), "expected_row_version": version, "author": "NOTE", "text": "اتصلتُ بها وطلبتُ صورة الخطأ."})
    assert noted.status == 201, noted.text()
    page.reload()
    flow.screen("#ticket-prev, #ticket-back")
    if gaze:
        _press_until(flow, "#ticket-next", "text=اتصلتُ بها وطلبتُ صورة الخطأ.", "التالي")
        _audit(flow, "ticket-thread")
    else:
        flow.press("#ticket-earlier", lambda: flow.screen("text=اتصلتُ بها وطلبتُ صورة الخطأ."), "رسائل سابقة")
    _to_decisions(flow)
    flow.press("#decide-escalate", lambda: flow.screen("#escalate-target, #escalate-target-TIER2"), "صعّد")
    _audit(flow, "escalate")
    if gaze:
        _pick(flow, "escalate-target", "VENDOR", "المورّد أو الشركة المصنّعة")
        flow.press("#escalate-next", lambda: flow.screen("#escalate-note"), "الملاحظة")
        _audit(flow, "escalate-note")
    # الملخّص يُنسخ ليُلصق في قناة الجهة.
    flow.press("#escalate-copy", lambda: flow.screen("text=نُسخ الملخّص"), "انسخ ملخّص التصعيد")
    assert page.evaluate("() => navigator.clipboard.readText()").startswith("التذكرة #1")
    if gaze:
        flow.press("#escalate-next", lambda: flow.screen("#escalate-notify-no"), "العميل")
        _audit(flow, "escalate-notify")
        flow.press("#escalate-next", lambda: flow.screen("#escalate-submit"), "التصعيد")
        _audit(flow, "escalate-submit")
    else:
        flow.press("#escalate-target-VENDOR", lambda: None, "المورّد")
    if not gaze:
        assert page.input_value("#escalate-note").startswith("التذكرة #1")
    flow.press("#escalate-submit", lambda: flow.until("!location.hash.includes('/escalate')"), "صعّد التذكرة")
    assert _status(owner, "SELECT status, escalation_target FROM support_tickets") == ("ESCALATED", "VENDOR")
    _to_decisions(flow)
    if gaze:
        _press_until(flow, "#ticket-next", "#decide-returned", "التالي")
    flow.press("#decide-returned", lambda: flow.until("!document.querySelector('#decide-returned')"), "عاد الجواب من التصعيد")
    assert _status(owner, "SELECT status FROM support_tickets") == ("OPEN",)
    if gaze:
        _audit(flow, "ticket-returned")
        _press_until(flow, "#ticket-next", "#decide-resolve", "التالي")
    flow.press("#decide-resolve", lambda: flow.screen("#resolve-submit"), "حُلّت دون ردٍّ مكتوب")
    flow.screen("#resolve-submit")
    _audit(flow, "resolve")
    if gaze:
        _pick(flow, "resolve-resolution", "DUPLICATE", "مكرّرة")
    else:
        flow.press("#resolve-DUPLICATE", lambda: None, "مكرّرة")
    flow.press("#resolve-submit", lambda: flow.screen("#resolve-confirm"), "حُلّت")
    _audit(flow, "resolve-unanswered")
    flow.press("#resolve-confirm", lambda: flow.until("!location.hash.includes('/resolve')"), "أغلقها رغم ذلك")
    assert _status(owner, "SELECT status, resolution FROM support_tickets") == ("RESOLVED", "DUPLICATE")
    assert not flow.failures(), "\n".join(flow.failures())
    if gaze:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), [PHONES[0], STRESS], ids=frame_ids([PHONES[0], STRESS]))
def test_the_lists_the_settings_and_the_tools(next_page, server, owner, size, width, height):
    """القوائم الأربع فارغةً بعباراتها، والإعدادات (التوقيع)، و«تحسين المسودات»، وأداة «عبارات وأسئلة جاهزة»."""
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    for entry, text in (("decide", "لا شيء ينتظر قرارك الآن."), ("open", "لا تذاكر مفتوحة."), ("pending", "لا أحد بانتظار ردّه."),
                        ("escalated", "لا تذاكر عند جهةٍ أخرى.")):
        flow.press("#nav-home", lambda: flow.screen(f"#home-{entry}"), "الرئيسية")
        flow.press(f"#home-{entry}", lambda: flow.screen(f"text={text}"), entry)
        _audit(flow, f"list-{entry}")
    # في الحجم الكبير يظهر رابط الإعدادات بعد الإشعار: الأزرار الستة وزرّ الإشعار تملأ الهاتف الأضيق.
    if size == "gaze":
        assert not page.locator("#home-settings-phone").is_visible()
        _notice(flow)
    flow.press("#nav-home", lambda: flow.screen("#home-settings-phone"), "الرئيسية")
    flow.press("#home-settings-phone", lambda: flow.screen("#settings-signature"), "إعدادات الدعم")
    page.fill("#settings-signature", "فريق الدعم الفني")
    page.locator("#settings-signature").blur()
    _audit(flow, "settings")
    flow.press("#settings-save-signature", lambda: flow.screen("#settings-saved"), "احفظ التوقيع")
    assert _status(owner, "SELECT signature FROM support_settings") == ("فريق الدعم الفني",)
    # هدف زمن الخدمة بمنتقيه (مفتوحاً في الحجم الكبير بلا حقلٍ تحته)، وحفظه لا يمسح التوقيع.
    if size == "gaze":
        flow.press("button[aria-expanded]:has-text('التوقيع')", lambda: flow.screen("[role=radio]:has-text('زمن الخدمة')"), "الإعدادات")
        flow.press("[role=radio]:has-text('زمن الخدمة')", lambda: flow.screen("#settings-first-URGENT"), "زمن الخدمة")
    _pick(flow, "settings-first-URGENT", "120", "ساعتان")
    with page.expect_response(lambda r: r.url.endswith("/api/support/settings") and r.request.method == "PUT"):
        flow.press("#settings-save-sla", lambda: None, "احفظ الأهداف")
    with owner.cursor() as cursor:
        cursor.execute("SELECT (SELECT signature FROM support_settings),"
                       " (SELECT first_reply_minutes FROM support_sla_targets WHERE priority = 'URGENT')")
        assert cursor.fetchone() == ("فريق الدعم الفني", 120)
    page.goto(page.next + BASE + "/kb/improve")
    flow.screen("text=لا ثغرات في آخر ثلاثين يوماً")
    _audit(flow, "improve")
    flow.press("#nav-tools", lambda: flow.screen("text=عبارات وأسئلة جاهزة"), "الأدوات")
    flow.press("text=عبارات وأسئلة جاهزة", lambda: flow.screen("#phrase-copy-THANKS_SORRY"), "عبارات وأسئلة جاهزة")
    _audit(flow, "tool-phrases")
    flow.press("#phrase-copy-THANKS_SORRY", lambda: flow.screen("text=نُسخت. الصقها في الردّ."), "انسخ")
    assert page.evaluate("() => navigator.clipboard.readText()") == "شكراً على تواصلكم، ونأسف لما حدث."
    assert not flow.failures(), "\n".join(flow.failures())
    if size == "gaze":
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), [PHONES[0], STRESS], ids=frame_ids([PHONES[0], STRESS]))
def test_a_reply_read_aloud_shared_or_confirmed_later_never_lands_on_a_commit(next_page, server, owner, size, width, height):
    """
    ردّ مكالمةٍ يُقرأ للعميل («انتهيت»)، ثم يُؤكَّد لاحقاً من التذكرة («أكّد الإرسال»)؛ وردّ رسالةٍ يُشارَك (ورقة
    المشاركة مصطنعة كما في Safari). في كل انتقالٍ تقع الضغطة على زرٍّ آمن، ولا يكون الاعتماد أقرب ما إليها.
    """
    page = _page(next_page, owner, server, size, width, height)
    page.add_init_script("navigator.share = async () => {}")
    flow = Flow(page)
    gaze = size == "gaze"
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    ask = "لنساعدكم بسرعة، ما نصّ رسالة الخطأ كما تظهر على الشاشة؟"
    page.gateway.queue(draft_reply("DRAFT", "ASK_INFO", ask, (), impact="SINGLE", urgency="DEGRADED"))
    _new_ticket(flow, "اتصل العميل: البريد لا يصلني في الجوال منذ تحديث النظام.", "منى", channel="PHONE")
    flow.until("!document.querySelector('#ticket-drafting')")
    _to_decisions(flow)
    flow.press("#decide-send", lambda: flow.screen("#reply-prev, #reply-back"), "أرسل كما هي")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-script"), "التالي")
        _audit(flow, "reply-send-phone")
    assert page.locator("#reply-share").count() == 1
    flow.press("#reply-script", lambda: flow.screen("#reply-script-done"), "اقرأه للعميل")
    _audit(flow, "reply-script")
    flow.press("#reply-script-done", lambda: flow.screen("#reply-sent"), "انتهيت")
    _audit(flow, "reply-confirm-phone")
    flow.press("#reply-back" if gaze else "#reply-back", lambda: flow.screen("#ticket-open-reply"), "التذكرة")
    _audit(flow, "ticket-released")
    flow.press("#ticket-open-reply", lambda: flow.screen("#reply-sent"), "أكّد الإرسال")
    _audit(flow, "reply-confirm-later")
    flow.press("#reply-sent", lambda: flow.until("!location.hash.includes('/reply')"), "نعم، أرسلته")
    assert _status(owner, "SELECT state, release_via FROM support_replies") == ("SENT", "SCRIPT")

    page.gateway.queue(draft_reply("DRAFT", "ASK_INFO", ask, (), impact="SINGLE", urgency="DEGRADED"))
    flow.press("#nav-home", lambda: flow.screen("#home-new"), "الرئيسية")
    _new_ticket(flow, "البريد لا يصلني في الجوال منذ تحديث النظام.", "سارة")
    flow.until("!document.querySelector('#ticket-drafting')")
    _to_decisions(flow)
    flow.press("#decide-send", lambda: flow.screen("#reply-prev, #reply-back"), "أرسل كما هي")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-share"), "التالي")
    flow.press("#reply-share", lambda: flow.screen("#reply-sent"), "شارك الردّ")
    _audit(flow, "reply-confirm-share")
    flow.press("#reply-sent", lambda: flow.until("!location.hash.includes('/reply')"), "نعم، أرسلته")
    with owner.cursor() as cursor:
        cursor.execute("SELECT release_via FROM support_replies ORDER BY created_at")
        assert [row[0] for row in cursor.fetchall()] == ["SCRIPT", "SHARE"]
    assert not flow.failures(), "\n".join(flow.failures())
    if gaze:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
def test_a_list_longer_than_a_page_pages_by_what_the_table_shows(next_page, server, owner, size):
    """أربع تذاكر مفتوحة: ثلاثٌ في صفحة الحجم الكبير ثم الرابعة في الثانية، وكلّها معاً في العادي."""
    page = _page(next_page, owner, server, size, *PHONES[0])
    flow = Flow(page)
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    api, headers = f"{server['base']}/api/support", {"X-Eyework": "1", "Origin": server["base"]}
    for n in range(4):
        created = page.request.post(api + "/tickets", headers=headers, data={
            "client_token": str(uuid.uuid4()), "channel": "MESSAGING", "text": f"الطابعة رقم {n + 1} في المكتب لا تطبع شيئاً منذ الصباح."})
        assert created.status == 201, created.text()
    page.goto(page.next + BASE + "/open")
    rows = "[aria-label='التذاكر المفتوحة'] li"
    flow.until(f"document.querySelectorAll(\"{rows}\").length > 0")
    _audit(flow, "list-open-long")
    if size == "gaze":
        assert page.locator(rows).count() == 3
        pager = "[aria-label='صفحات التذاكر المفتوحة'] button:has-text('التالي')"
        flow.press(pager, lambda: flow.until(f"document.querySelectorAll(\"{rows}\").length === 1"), "التالي")
        _audit(flow, "list-open-long-2")
    else:
        assert page.locator(rows).count() == 4
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
def test_symbols_notes_arriving_after_the_copy_press_wait_for_a_decision_without_moving_under_the_gaze(next_page, server, owner, size):
    """
    المراجعة لم تنتهِ حين فُتح الردّ (PENDING)، ثم انتهت بملاحظة: «انسخ الردّ» يُرفض 409 بالملاحظة، فتبقى صفحة النسخ
    مكانها وأزرارها معطّلة (لا تحلّ بطاقة الملاحظة تحت النظر)، ثم «تابع رغم ذلك» ثم النسخ.
    """
    page = _page(next_page, owner, server, size, *PHONES[0])
    flow = Flow(page)
    gaze = size == "gaze"

    def pending(route):
        response = route.fetch()
        body = response.json()
        body["review"].update({"status": "PENDING", "reason": None, "message": None})
        body["flags"] = []
        route.fulfill(response=response, json=body)

    page.route("**/api/ai/review", pending)
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    _new_ticket(flow, "الشاشة سوداء في جهاز الاستقبال منذ أمس ولا تستجيب.", "خالد")
    flow.until("!document.querySelector('#ticket-drafting')")
    if gaze:
        _press_until(flow, "#ticket-next", "#decide-write", "التالي")
    flow.press("#decide-write", lambda: flow.screen("#compose-prev, #compose-back"), "اكتب الردّ بنفسك")
    text = "أعيدوا تشغيل جهاز الاستقبال من زرّ الطاقة، ثم أخبرونا بالنتيجة."
    if gaze:
        flow.press("#compose-next", lambda: flow.screen("#compose-tool-write"), "التالي")
        flow.press("#compose-tool-write", lambda: None, "اكتب بنفسك")
        flow.press("#compose-next", lambda: flow.screen("#compose-text"), "التالي")
        page.fill("#compose-text", text)
        page.locator("#compose-text").blur()
        flow.press("#compose-next", lambda: flow.screen("#compose-prepare"), "جهّز")
    else:
        page.fill("#compose-text", text)
        page.locator("#compose-text").blur()
    page.gateway.queue(review_reply(flag("UNSUPPORTED_CLAIM", "MEDIUM", "reply", 1, "الردّ يذكر خطوةً لا تذكرها مقالة.", "تأكّد من الخطوة.")))
    flow.press("#compose-prepare", lambda: flow.screen("#reply-prev, #reply-back"), "جهّز الردّ")
    flow.until("document.querySelector('#reply-review') && !document.querySelector('#reply-review').textContent.includes('يراجع')")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-copy"), "التالي")
    assert page.locator("#reply-copy").is_enabled()
    flow.press("#reply-copy", lambda: flow.until("document.querySelector('#reply-copy').disabled"), "انسخ الردّ")
    _audit(flow, "reply-late-flags")
    assert page.locator("#reply-sent").count() == 0
    assert _status(owner, "SELECT state FROM support_replies") == ("READY",)
    if gaze:
        flow.press("#reply-prev", lambda: flow.screen("[data-flag-status='open']"), "السابق")
    flow.press("[data-flag-status='open'] button[data-commit]", lambda: flow.screen("[data-flag-status='acknowledged']"), "تابع رغم ذلك")
    if gaze:
        flow.press("#reply-next", lambda: flow.until("!document.querySelector('#reply-copy').disabled"), "التالي")
    flow.press("#reply-copy", lambda: flow.screen("#reply-sent"), "انسخ الردّ")
    flow.press("#reply-sent", lambda: flow.until("!location.hash.includes('/reply')"), "نعم، أرسلته")
    assert _status(owner, "SELECT state FROM support_replies") == ("SENT",)
    assert not flow.failures(), "\n".join(flow.failures())
    if gaze:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), [PHONES[0], STRESS], ids=frame_ids([PHONES[0], STRESS]))
def test_a_long_unpunctuated_message_reads_in_pages_without_losing_a_word_on_gaze(next_page, server, owner, width, height):
    """رسالةٌ ملصوقة بنحو أربعة آلاف حرفٍ بلا علامات، وفيها كلمةٌ أطول من الصفحة: صفحاتٌ لا تمرّ ولا تُقصّ، ونصّها كلّه."""
    page = _page(next_page, owner, server, "gaze", width, height)
    flow = Flow(page)
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    text = " ".join(["الطابعة في المكتب لا تطبع الصفحات الملوّنة منذ تحديث البرنامج"] * 58 + ["x" * 300, "والسلام"])
    assert 3900 <= len(text) <= 4000
    api, headers = f"{server['base']}/api/support", {"X-Eyework": "1", "Origin": server["base"]}
    # بترميز UTF-8 كما يرسله المتصفّح (JSON.stringify)، لا بهروب \uXXXX الذي يضاعف الحجم ستّ مرات.
    body = json.dumps({"client_token": str(uuid.uuid4()), "channel": "MESSAGING", "text": text}, ensure_ascii=False)
    created = page.request.post(api + "/tickets", headers={**headers, "Content-Type": "application/json"}, data=body)
    assert created.status == 201, created.text()
    page.goto(page.next + BASE + "/t/" + created.json()["id"])
    flow.screen("#ticket-prev")
    pager = "nav[aria-label='صفحات رسالة العميل']"
    _press_until(flow, "#ticket-next", pager, "التالي")
    shown = []
    while True:
        shown.append(page.locator("article[aria-label='رسالة العميل'] p.text-flow").inner_text())
        _audit(flow, f"long-message-{len(shown)}")
        following = page.locator(f"{pager} button:has-text('التالي')")
        if not following.is_enabled():
            break
        flow.press(f"{pager} button:has-text('التالي')", lambda: flow.until(
            f"document.querySelector(\"article[aria-label='رسالة العميل'] p.text-flow\").innerText !== {shown[-1]!r}"), "التالي")
    assert len(shown) > 10 and all(len(piece) <= 260 for piece in shown)
    assert "".join(shown).replace(" ", "") == text.replace(" ", "")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
def test_a_ticket_changed_since_it_was_shown_says_so_and_reloads(next_page, server, owner, size):
    """
    ملاحظةٌ أُضيفت من مكانٍ آخر بعد عرض التذكرة: «اعتمد المقترح» يُرفض 409 فيُقال ذلك في صفحة الاقتراح نفسها،
    وتُقرأ التذكرة من جديد، والضغطة الثانية تعتمده.
    """
    page = _page(next_page, owner, server, size, *PHONES[0])
    flow = Flow(page)
    page.goto(page.next + BASE)
    flow.screen("#home-new")
    _notice(flow)
    _new_ticket(flow, "الشاشة سوداء في جهاز الاستقبال منذ أمس ولا تستجيب.", "خالد")
    flow.until("!document.querySelector('#ticket-drafting')")
    flow.screen("#ticket-accept-suggestion")
    ticket_id = page.evaluate("() => location.hash.split('/t/')[1].split('?')[0]")
    api, headers = f"{server['base']}/api/support", {"X-Eyework": "1", "Origin": server["base"]}
    version = page.request.get(f"{api}/tickets/{ticket_id}", headers=headers).json()["row_version"]
    note = page.request.post(f"{api}/tickets/{ticket_id}/messages", headers=headers, data={
        "client_token": str(uuid.uuid4()), "expected_row_version": version, "author": "NOTE",
        "text": "اتصل العميل وقال إن الجهاز يعمل بعد إعادة توصيل الكهرباء."})
    assert note.status == 201, note.text()
    flow.press("#ticket-accept-suggestion", lambda: flow.screen("text=تغيّرت التذكرة منذ عرضها"), "اعتمد المقترح")
    _audit(flow, "ticket-stale")
    assert _status(owner, "SELECT category FROM support_tickets") == (None,)
    flow.press("#ticket-accept-suggestion", lambda: flow.until("!document.querySelector('#ticket-accept-suggestion')"), "اعتمد المقترح")
    assert _status(owner, "SELECT category IS NOT NULL FROM support_tickets") == (True,)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors
