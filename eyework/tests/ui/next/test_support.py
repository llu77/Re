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

import os
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


def _new_ticket(flow: Flow, text: str = CUSTOMER, label: str = "سارة") -> None:
    """القناة، ثم الرسالة، ثم ما سيُحفظ (البريد والرقم محذوفان)، ثم الاسم للتحية، ثم الحفظ."""
    page = flow.page
    gaze = _gaze(page)
    flow.press("#home-new", lambda: flow.screen("#ticket-text, #ticket-channel"), "تذكرة جديدة")
    _audit(flow, "ticket-new")
    if gaze:
        _pick(flow, "ticket-channel", "MESSAGING", "واتساب أو رسائل")
        flow.press("#ticket-next", lambda: flow.screen("#ticket-text"), "الرسالة")
    else:
        flow.press("#ticket-channel-MESSAGING", lambda: None, "واتساب")
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
    page.locator("#ticket-label").blur()
    _audit(flow, "ticket-details")
    if gaze:
        flow.press("#ticket-next", lambda: flow.screen("#ticket-save"), "الحفظ")
        _audit(flow, "ticket-save")
    flow.press("#ticket-save", lambda: flow.until("location.hash.includes('/t/')"), "احفظ التذكرة")


def _to_decisions(flow: Flow) -> None:
    """التذكرة حتى «قرارك»: صفحاتٌ بـ«التالي» في الحجم الكبير، وصفحةٌ تمرّ في العادي."""
    if _gaze(flow.page):
        _press_until(flow, "#ticket-next", "#decide-send, #decide-write, #decide-more", "التالي")
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
    _new_ticket(flow)
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
    status, category, label = _status(owner, "SELECT status, category, customer_label FROM support_tickets")
    assert (status, category, label) == ("RESOLVED", "PRINTING", "سارة")
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
        _press_until(flow, "#ticket-next", "#decide-more", "التالي")
        flow.press("#decide-more", lambda: flow.screen("#decide-write"), "المزيد")
        _audit(flow, "ticket-more")
    flow.press("#decide-write", lambda: flow.screen("#compose-prev, #compose-back"), "اكتب الردّ بنفسك")
    _audit(flow, "compose")
    text = "سنصلح الشاشة خلال 2 ساعات. أعيدوا تشغيل جهاز الاستقبال من زرّ الطاقة."
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
    flow.press("[data-flag-status='open'] button[data-commit]", lambda: flow.screen("[data-flag-status='acknowledged']"), "تابع رغم ذلك")
    if gaze:
        flow.press("#reply-next", lambda: flow.screen("#reply-copy"), "التالي")
    assert page.locator("#reply-copy").is_enabled()
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
    flow.press("#decide-reject", lambda: flow.screen("#reject-reason"), "ارفض المسودة")
    _audit(flow, "reject")
    _pick(flow, "reject-reason", "TOO_LONG", "أطول من اللازم")
    flow.press("#reject-submit", lambda: flow.until("!location.hash.includes('/reject')"), "ارفض المسودة")
    assert _status(owner, "SELECT reject_reason FROM support_drafts") == ("TOO_LONG",)
    _to_decisions(flow)
    flow.press("#decide-escalate", lambda: flow.screen("#escalate-target, #escalate-target-TIER2"), "صعّد")
    _audit(flow, "escalate")
    if gaze:
        _pick(flow, "escalate-target", "VENDOR", "المورّد أو الشركة المصنّعة")
        flow.press("#escalate-next", lambda: flow.screen("#escalate-note"), "الملاحظة")
        _audit(flow, "escalate-note")
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
        _press_until(flow, "#ticket-next", "#decide-more", "التالي")
        flow.press("#decide-more", lambda: flow.screen("#decide-resolve"), "المزيد")
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
    flow.press("#nav-home", lambda: flow.screen("#home-settings-phone"), "الرئيسية")
    flow.press("#home-settings-phone", lambda: flow.screen("#settings-signature"), "إعدادات الدعم")
    page.fill("#settings-signature", "فريق الدعم الفني")
    page.locator("#settings-signature").blur()
    _audit(flow, "settings")
    flow.press("#settings-save-signature", lambda: flow.screen("text=حُفظت الإعدادات"), "احفظ التوقيع")
    assert _status(owner, "SELECT signature FROM support_settings") == ("فريق الدعم الفني",)
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
