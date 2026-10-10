"""
أداة الحملة على الواجهة الجديدة، بالحجمين
=========================================
المسار الكامل كما في tests/ui/flow.py — نقرةً نقرة من الرئيسية إلى حملةٍ جاهزة ثم سحبها —
وفحص كل شاشةٍ فيه بعقد النظر لكل حجم (flow.py هنا)، وقاعدتا الهبوط والأقرب إلى النظر في
الحجم الكبير على إطارات الهاتف؛ ثم ما نُقل من اختبارات الواجهة القائمة: قفل الشاشة أثناء
الكتابة، والردود التي تصل بعد المغادرة، والتنبيهات والمسارات المنقطعة، وأطول نصٍّ مقبول،
وكلمة سيمبول، و«حملاتي» بصفحاتها، واللمس، و«زيادة التباين».

في الحجم الكبير لا تزيد الشاشة على اثني عشر هدفاً (أربعةٌ منها شريط التنقّل)، فالخيارات الستّ
(التعديلات، والمبالغ، والمُدَد) ثلاثةٌ وزرٌّ يقلّب إلى الثلاثة الأخرى؛ والاختبارات تصل الخيار بمفتاحه
أينما كان. المسار الكامل يمشي على إطارات الآيفون والآيباد والحاسوب (conftest.FRAMES).
"""

from __future__ import annotations

import time
import json

import pytest

from eyework import campaigns
from eyework.copy_rules import DESCRIPTION_MAX, NOTE_TO_USER_MAX, TITLE_MAX, check_copy, check_note_to_user
from eyework.tests.conftest import add_version, create_campaign
from eyework.tests.fakes import NOTE, ok
from eyework.tests.ui.flow import sample_photo
from eyework.tests.ui.next.conftest import DESKTOP, FRAMES, LOGIN, PHONES, STRESS, TIGHTEST, frame_ids, member
from eyework.tests.ui.next.flow import PRESS_GAP, Flow

SIZES = ["compact", "gaze"]
PHOTO = {"name": "p.jpg", "mimeType": "image/jpeg", "buffer": sample_photo()}
BASE = "#/marketing"
STATE = "window.__eyework_state()"


def _page(next_page, owner, server, size: str = "compact", width: int = 390, height: int = 664):
    """حسابٌ تسويقيٌّ بالحجم المطلوب، وصفحةٌ داخلةٌ به؛ والكاتب المصطنع بلا نتائج مجدولة."""
    member(owner, size="GAZE" if size == "gaze" else "COMPACT")
    server["writer"].outcomes.clear()
    server["writer"].requests.clear()
    return next_page(width, height, login=LOGIN, size=size)


def _press_choice(flow: Flow, group: str, key: str, settle, label: str) -> None:
    """خيارٌ بمفتاحه: في الحجم الكبير قد يكون في الصفحة الأخرى من المجموعة."""
    if flow.page.locator(f"#{group} [data-key='{key}']").count() == 0:
        flow.press(f"#{group}-more", lambda: flow.screen(f"#{group} [data-key='{key}']"), "خياراتٌ أخرى")
    flow.press(f"#{group} [data-key='{key}']", settle, label)


def _status(word: str) -> str:
    return f"document.querySelector('#proposal-status') && document.querySelector('#proposal-status').textContent.includes('{word}')"


def _end(word: str) -> str:
    return f"document.querySelector('#proposal-end').textContent.includes('{word}')"


def _to_proposal(flow: Flow) -> None:
    """من الرئيسية إلى أوّل نصٍّ مقترح."""
    page = flow.page
    page.goto(page.next + "#/")
    flow.screen("#home-new")
    flow.audit("home")
    flow.press("#home-new", lambda: flow.screen("#photo-input"), "حملة جديدة")
    flow.audit("photo-empty")
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until("!document.querySelector('#photo-generate').disabled")
    flow.audit("photo-draft")
    flow.press("#photo-generate", lambda: flow.screen("#proposal-copy"), "اكتب النص")
    flow.audit("proposal")


def _to_review(flow: Flow) -> None:
    """من الرئيسية إلى شاشة المراجعة، عبر كل شاشةٍ قبلها (المسار نفسه في tests/ui/flow.py)."""
    page = flow.page
    _to_proposal(flow)
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    flow.audit("edit")
    _press_choice(flow, "edit-chips", "SHORTER", lambda: None, "خيار تعديل")
    _press_choice(flow, "edit-chips", "MORE_FORMAL", lambda: None, "خيار تعديل")
    flow.audit("edit-chosen")
    flow.press("#edit-note", lambda: flow.screen("#note-text"), "ملاحظة نصية")
    flow.audit("note")
    page.fill("#note-text", "اذكر أنه مصنوعٌ من الجلد الطبيعي")
    flow.press("#note-save", lambda: flow.screen("#edit-chips"), "احفظ الملاحظة")
    flow.press("#edit-submit", lambda: flow.until(_status("2 من")), "اطلب نسخة جديدة")
    flow.audit("proposal-v2")

    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    flow.audit("edit-v2")
    flow.press("#edit-restore", lambda: flow.until(_status("1 من")), "النسخة السابقة")
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    flow.until("document.querySelector('#edit-restore').textContent.includes('الأحدث')")
    flow.press("#edit-restore", lambda: flow.until(_status("2 من")), "النسخة الأحدث")

    flow.press("#proposal-end", lambda: flow.until(_end("الميزانية")), "أوافق على النص")
    flow.audit("approved")
    flow.press("#proposal-start", lambda: flow.until(_end("أوافق")), "تراجع عن الموافقة")
    flow.press("#proposal-end", lambda: flow.until(_end("الميزانية")), "أوافق على النص")

    flow.press("#proposal-end", lambda: flow.screen("#budget-presets"), "تابع إلى الميزانية")
    flow.audit("budget-empty")
    _press_choice(flow, "budget-presets", "2500", lambda: flow.until("!document.querySelector('#budget-next').disabled"), "مبلغ جاهز")
    flow.press("#budget-up", lambda: flow.until("document.querySelector('#budget-value').textContent.includes('2,750')"), "أكثر")
    flow.audit("budget")
    flow.press("#budget-next", lambda: flow.screen("#days-presets"), "التالي: عدد الأيام")
    flow.audit("days-empty")
    _press_choice(flow, "days-presets", "14", lambda: flow.until("!document.querySelector('#days-next').disabled"), "مدّة جاهزة")
    flow.audit("days")
    flow.press("#days-next", lambda: flow.screen("#review-continue"), "التالي: المراجعة")
    flow.audit("review")


def _finish(flow: Flow) -> None:
    """من المراجعة إلى حملةٍ جاهزة، ثم السحب والرجوع والرئيسية و«حملاتي»."""
    flow.press("#review-continue", lambda: flow.screen("#confirm-yes"), "متابعة للتأكيد")
    flow.audit("confirm")
    flow.press("#confirm-back", lambda: flow.screen("#review-continue"), "رجوع دون اعتماد")
    flow.press("#review-continue", lambda: flow.screen("#confirm-yes"), "متابعة للتأكيد")
    flow.press("#confirm-yes", lambda: flow.screen("#ready-share"), "نعم، اعتمد الحملة")
    flow.audit("ready")
    flow.press("#ready-withdraw", lambda: flow.screen("#cancel-yes"), "اسحب الحملة")
    flow.audit("withdraw")
    flow.press("#cancel-back", lambda: flow.screen("#ready-share"), "رجوع دون إلغاء")
    flow.press("#ready-home", lambda: flow.screen("#home-new"), "الرئيسية")
    flow.press("#home-campaigns", lambda: flow.until("document.querySelectorAll('#campaigns-list li').length === 1"), "حملاتي")
    flow.audit("campaigns-one")


def _to_ready(flow: Flow) -> None:
    _to_review(flow)
    flow.press("#review-continue", lambda: flow.screen("#confirm-yes"), "متابعة للتأكيد")
    flow.press("#confirm-yes", lambda: flow.screen("#ready-share"), "نعم، اعتمد الحملة")


def _proposal_text(page) -> str:
    """نصّ المقترح كلّه: في الحجم الكبير صفحةً صفحة حتى تتعطّل «التالي»."""
    if page.evaluate("() => document.documentElement.dataset.size") != "gaze":
        return page.inner_text("#proposal-copy")
    parts = []
    while True:
        parts.append(page.inner_text("#proposal-copy p"))
        forward = page.locator("#proposal-copy nav button >> nth=1")
        if forward.count() == 0 or forward.is_disabled():
            break
        # ضغطتان بالنظر في الموضع نفسه بينهما مكوثٌ كامل: أقرب منه تُعدّ «نقرتين» فلا تُحسب الثانية.
        page.wait_for_timeout(PRESS_GAP * 1000)
        forward.click()
        page.wait_for_function("(before) => document.querySelector('#proposal-copy p').innerText !== before", arg=parts[-1])
    return "\n".join(parts)


def _notice(page) -> str:
    page.wait_for_selector("#notice-ack")
    return page.inner_text("[role=alert]")


# ── المسار الكامل بعقد النظر ──────────────────────────────────────────────
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), FRAMES, ids=frame_ids(FRAMES))
def test_every_screen_honours_the_gaze_contract(next_page, server, owner, size, width, height):
    page = _page(next_page, owner, server, size, width, height)
    flow = Flow(page)
    _to_review(flow)
    _finish(flow)
    assert not flow.failures(), "\n".join(flow.failures())
    if size == "gaze" and (width, height) != DESKTOP:
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors
    flow.gaze_safe()
    foreign = [url for _, url in page.requests if not url.startswith(server["base"])]
    assert not foreign, foreign


def test_the_confirming_control_is_far_from_the_one_that_opened_it(next_page, server, owner):
    """
    «نعم، اعتمد الحملة» على نصف ارتفاع الشاشة على الأقل من «متابعة للتأكيد»، وموضع «متابعة
    للتأكيد» في شاشة التأكيد لا يُضغط فيه شيء — ونظرةٌ باقية هناك، تتكرّر ست مرات، لا ترسل طلباً.
    """
    page = _page(next_page, owner, server, "gaze")
    flow = Flow(page)
    _to_review(flow)
    initiator = page.locator("#review-continue").bounding_box()
    centre = (initiator["x"] + initiator["width"] / 2, initiator["y"] + initiator["height"] / 2)
    # نقرةٌ قبل 400ms من سابقتها لا تُحسب في الحجم الكبير (lib/repeat-press.ts): الاختبار يمهل كما يمهل النظر.
    flow.pace()
    page.locator("#review-continue").click()
    flow.clicked()
    flow.screen("#confirm-yes")
    commit = page.locator("#confirm-yes").bounding_box()
    distance = abs((commit["y"] + commit["height"] / 2) - centre[1])
    assert distance >= 0.5 * 664, distance

    under = page.evaluate(
        "([x, y]) => { const e = document.elementFromPoint(x, y);"
        " return e && e.closest('button, a, label, input') ? (e.closest('button, a, label, input').id || 'control') : null; }",
        list(centre))
    assert under is None, under

    before = len([r for r in page.requests if r[0] != "GET"])
    for _ in range(6):
        # كل مكوثٍ بعد الذي قبله بمهلةٍ كاملة: يُختبر ما تحت الموضع، لا حارس «النقرتين».
        page.wait_for_timeout(PRESS_GAP * 1000)
        page.mouse.click(*centre)
    assert len([r for r in page.requests if r[0] != "GET"]) == before
    assert page.locator("#confirm-yes").is_visible()


def test_amount_words_follow_a_label_and_colon(next_page, server, owner):
    """الكلمات في موضع الرفع وحده: بعد العنوان والنقطتين مباشرةً، لا في وسط جملة."""
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_review(flow)
    assert page.locator("#review-budget").inner_text().startswith("الميزانية الإجمالية: ألفان وسبعمئة وخمسون ريالاً")
    assert page.locator("#review-days").inner_text().startswith("المدة: أربعة عشر يوماً")
    page.locator("#review-continue").click()
    flow.screen("#confirm-yes")
    restate = page.locator("#confirm-restate").inner_text()
    assert "الميزانية الإجمالية: ألفان وسبعمئة وخمسون ريالاً." in restate
    assert "المدة: أربعة عشر يوماً." in restate
    assert "لن يُنشر شيءٌ ولن يُدفع أيّ مبلغٍ تلقائياً" in restate


# ── الشاشة مضاءة أثناء الكتابة ───────────────────────────────────────────
#: `navigator.wakeLock` هنا بديلٌ للاختبار وحده: Chromium بلا شاشةٍ لا يمنحه.
WAKE_STUB = """
(() => {
    // hold: الطلب يبقى معلّقاً حتى grant()، كما يتأخّر WebKit بسؤال الإذن.
    const log = { requests: 0, released: 0, live: null, refuse: false, hold: false, pending: [], locks: [] };
    log.grant = () => log.pending.shift()();
    Object.defineProperty(window, '__wake', { value: log });
    Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
        request: async () => {
            if (log.refuse) throw new DOMException('refused', 'NotAllowedError');
            log.requests += 1;
            const lock = new EventTarget();
            lock.released = false;
            lock.release = async () => {
                if (lock.released) return;
                lock.released = true;
                log.released += 1;
                lock.dispatchEvent(new Event('release'));
            };
            log.locks.push(lock);
            if (log.hold) {
                return new Promise((resolve) => log.pending.push(() => { log.live = lock; resolve(lock); }));
            }
            log.live = lock;
            return lock;
        },
    } });
    let visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
    window.__setVisibility = (value) => { visibility = value; document.dispatchEvent(new Event('visibilitychange')); };
})();
"""


def _waiting(next_page, server, owner, *, refuse: bool = False):
    page = _page(next_page, owner, server)
    page.add_init_script(WAKE_STUB)
    held = []
    page.route("**/api/campaigns/*/copy", lambda route: held.append(route))
    flow = Flow(page)
    page.goto(page.next + BASE + "/new")
    flow.screen("#photo-input")
    if refuse:
        page.evaluate("() => { window.__wake.refuse = true; }")
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until("!document.querySelector('#photo-generate').disabled")
    page.click("#photo-generate")
    flow.screen("#proposal-waiting")
    page.wait_for_function(f"() => {STATE}.waitingFor !== null")
    return page, flow, held


def test_the_lock_is_taken_in_the_press_retaken_after_hiding_and_released_at_the_end(next_page, server, owner):
    page, flow, held = _waiting(next_page, server, owner)
    page.wait_for_function("() => window.__wake.requests === 1")
    assert page.is_hidden("#proposal-awake")

    # النظام يُسقط القفل حين تُخفى الصفحة، ثم تعود والكتابة جارية.
    page.evaluate("() => { window.__setVisibility('hidden'); window.__wake.live.release(); }")
    page.evaluate("() => window.__setVisibility('visible')")
    page.wait_for_function("() => window.__wake.requests === 2")
    assert page.is_hidden("#proposal-awake")

    held[0].continue_()
    flow.screen("#proposal-copy")
    page.wait_for_function(f"() => window.__wake.live.released && {STATE}.wakeLock === null")
    # بعد الردّ لا يُطلب القفل حين تعود الصفحة.
    page.evaluate("() => { window.__setVisibility('hidden'); window.__setVisibility('visible'); }")
    assert page.evaluate("() => window.__wake.requests") == 2
    assert not page.errors, page.errors


def test_a_refused_lock_is_said_on_the_waiting_screen(next_page, server, owner):
    page, flow, held = _waiting(next_page, server, owner, refuse=True)
    page.wait_for_selector("#proposal-awake")
    audit = flow.audit("waiting-unlocked")
    assert not audit["vertical"] and not audit["clipped"], audit
    held[0].continue_()
    flow.screen("#proposal-copy")
    assert not page.errors, page.errors


def test_a_lock_granted_after_the_wait_ended_is_let_go(next_page, server, owner):
    """طلبٌ من عودة الصفحة لم يُمنح بعد حين وصل الردّ: يُترك فور منحه، فلا تبقى الشاشة مضاءة بلا انتظار."""
    page, flow, held = _waiting(next_page, server, owner)
    page.wait_for_function("() => window.__wake.requests === 1")
    page.evaluate("""() => {
        window.__wake.hold = true;
        window.__setVisibility('hidden');
        window.__wake.live.release();
        window.__setVisibility('visible');
    }""")
    page.wait_for_function("() => window.__wake.pending.length === 1")
    held[0].continue_()
    flow.screen("#proposal-copy")
    page.wait_for_function(f"() => {STATE}.waitingFor === null")
    page.evaluate("() => window.__wake.grant()")
    page.wait_for_function("() => window.__wake.locks.every((lock) => lock.released)", timeout=3000)
    assert page.evaluate(f"() => {STATE}.wakeLock === null")
    assert not page.errors, page.errors


def test_two_returns_while_waiting_keep_one_lock(next_page, server, owner):
    """الصفحة تُخفى وتعود مرتين والطلبان معلّقان: يبقى قفلٌ واحد، ويُترك عند الردّ."""
    page, flow, held = _waiting(next_page, server, owner)
    page.wait_for_function("() => window.__wake.requests === 1")
    page.evaluate("""() => {
        window.__wake.hold = true;
        window.__setVisibility('hidden');
        window.__wake.live.release();
        window.__setVisibility('visible');
        window.__setVisibility('hidden');
        window.__setVisibility('visible');
    }""")
    page.wait_for_function("() => window.__wake.pending.length === 2")
    page.evaluate("() => { window.__wake.grant(); window.__wake.grant(); }")
    page.wait_for_function("() => window.__wake.locks.filter((lock) => !lock.released).length === 1", timeout=3000)
    assert page.evaluate(f"() => window.__wake.locks.find((lock) => !lock.released) === {STATE}.wakeLock")
    held[0].continue_()
    flow.screen("#proposal-copy")
    page.wait_for_function("() => window.__wake.locks.every((lock) => lock.released)", timeout=3000)
    assert not page.errors, page.errors


@pytest.mark.parametrize("refuse", [True, False], ids=["refused", "held"])
def test_returning_to_a_running_wait_says_whether_the_screen_may_lock(next_page, server, owner, refuse):
    """«رجوع» إلى الرئيسية ثم الحملة نفسها من «حملاتي» والكتابة جارية: السطر يقول ما هو قائم."""
    page, flow, held = _waiting(next_page, server, owner, refuse=refuse)
    if refuse:
        page.wait_for_selector("#proposal-awake")
    else:
        page.wait_for_function(f"() => window.__wake.requests === 1 && {STATE}.wakeLock !== null")
        assert page.is_hidden("#proposal-awake")
    page.click("#proposal-back")
    flow.screen("#home-new")
    page.click("#home-campaigns")
    flow.until("document.querySelectorAll('#campaigns-list li').length === 1")
    page.click("#campaigns-list li button")
    flow.screen("#proposal-waiting")
    assert page.evaluate(f"() => {STATE}.waitingFor") is not None
    assert page.locator("#proposal-check").count() == 0
    assert page.is_hidden("#proposal-awake") is (not refuse)
    held[0].continue_()
    flow.screen("#proposal-copy")
    assert not page.errors, page.errors


# ── ردودٌ تصل بعد أن غادر المستخدم ───────────────────────────────────────
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


def _until_held(page, held: list, seconds: float = 10.0) -> None:
    """حتى يصل الطلب المحبوس: معالج الحبس يعمل حين يعالج Playwright أحداثه، فالانتظار بأحداثٍ لا بنوم."""
    deadline = time.monotonic() + seconds
    while not held:
        assert time.monotonic() < deadline, "لم يصل الطلب المحبوس"
        page.wait_for_timeout(20)


def _draft(flow: Flow) -> str:
    page = flow.page
    page.goto(page.next + BASE + "/new")
    flow.screen("#photo-input")
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until(f"location.hash.startsWith('{BASE}/c/')")
    return page.evaluate(f"() => location.hash.slice('{BASE}/c/'.length)")


def test_a_slow_read_of_one_draft_does_not_take_over_a_new_campaign(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    draft = _draft(flow)
    page.goto(page.next + BASE + "/campaigns")
    flow.until("document.querySelectorAll('#campaigns-list li').length === 1")
    # الحملة تُقرأ من جديد حين تُفتح من القائمة؛ تُحبس قراءتها، ويبدأ المستخدم حملةً جديدة قبل وصولها.
    held = _hold(page, f"**/api/campaigns/{draft}", "GET")
    page.click("#campaigns-list li button")
    page.wait_for_function(f"() => location.hash.startsWith('{BASE}/c/')")
    # القراءة في الطريق قبل المغادرة: الحملة تُطلب بعد رسم شاشتها، لا مع تغيّر العنوان.
    _until_held(page, held)
    page.evaluate(f"() => {{ location.hash = '{BASE}/new'; }}")
    flow.screen("#photo-input")
    held[0].continue_()
    page.wait_for_load_state("networkidle")

    assert page.evaluate("() => location.hash") == BASE + "/new"
    assert page.evaluate(f"() => {STATE}.campaign") is None
    flow.screen("#photo-input")
    page.unroute(f"**/api/campaigns/{draft}")
    writes = []
    page.on("request", lambda r: writes.append((r.method, r.url)) if r.method in ("POST", "PUT") else None)
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until(f"location.hash.startsWith('{BASE}/c/')")
    assert [m for m, url in writes if "/api/campaigns" in url] == ["POST"], writes
    assert not page.errors, page.errors


def test_leaving_during_an_approval_does_not_redraw_the_screen_left(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _draft(flow)
    page.click("#photo-generate")
    flow.screen("#proposal-copy")
    held = _hold(page, "**/api/campaigns/*/copy/approve")
    page.click("#proposal-end")
    page.wait_for_function(f"() => {STATE}.busy === true")
    page.click("#proposal-back")
    flow.screen("#home-new")
    held[0].continue_()
    page.wait_for_load_state("networkidle")

    assert page.evaluate("() => location.hash") == BASE
    flow.screen("#home-new")
    assert page.evaluate(f"() => {STATE}.campaign") is None
    assert not page.errors, page.errors


def test_check_now_twice_while_offline_keeps_the_waiting_screen(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _draft(flow)
    # الطلب ينقطع في الطريق، وقراءة الحملة تنقطع أيضاً: مآل الكتابة غير معروف.
    page.route("**/api/campaigns/*/copy", lambda route: route.abort())
    page.route("**/api/campaigns/*", lambda route: route.abort()
               if route.request.method == "GET" else route.continue_())
    page.click("#photo-generate")
    assert "تحقّق الآن" in _notice(page)
    page.click("#notice-ack")
    # «حسناً» لا تغادر الانتظار: «تحقّق الآن» هو المخرج.
    assert page.is_visible("#proposal-check")
    page.click("#proposal-check")
    page.click("#proposal-check", force=True, no_wait_after=True)
    assert "«تحقّق الآن» تعيد المحاولة" in _notice(page)
    # التنبيه يغطّي الشاشة ولا يبدّلها: الانتظار باقٍ تحته، ويظهر بعد «حسناً» كما كان.
    assert page.locator("#proposal-waiting").count() == 1
    page.click("#notice-ack")
    assert page.is_visible("#proposal-waiting") and page.is_visible("#proposal-check")
    assert not page.errors, page.errors


# ── التنبيهات والمسارات المنقطعة ─────────────────────────────────────────
def test_a_dropped_request_says_what_happened(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _draft(flow)
    page.route("**/api/campaigns/*/copy", lambda route: route.abort("connectionreset"))
    page.click("#photo-generate")
    message = _notice(page)
    # الطلب لم يبلغ الخادم: الحملة بلا نصّ، فتُعرض كما حُفظت — شاشة الصورة.
    assert "انقطع الاتصال" in message
    page.click("#notice-ack")
    assert page.is_visible("#photo-pick")
    assert not page.errors, page.errors


def test_a_failed_request_is_acknowledged_before_anything_else(next_page, server, owner):
    """ما حول التنبيه خاملٌ حتى «حسناً»: نظرةٌ باقية على الزرّ الذي فشل لا تعيد الطلب."""
    page = _page(next_page, owner, server, "gaze")
    flow = Flow(page)
    _draft(flow)
    page.route("**/api/campaigns/*/copy", lambda route: route.fulfill(
        status=503, content_type="application/json", body=json.dumps({"code": "AI_BUSY", "detail": "المساعد مشغولٌ الآن. حاول بعد قليل."})))
    flow.press("#photo-generate", lambda: page.wait_for_selector("#notice-ack"), "اكتب النص")
    assert "المساعد مشغولٌ الآن" in page.inner_text("[role=alert]")
    assert page.evaluate("() => document.querySelector('#photo-generate').closest('[inert]') !== null")
    audit = flow.audit("alert")
    assert audit["enabled"] == 1 and not audit["small"] and not audit["edge"], audit
    page.unroute("**/api/campaigns/*/copy")
    flow.press("#notice-ack", lambda: page.wait_for_selector("#notice-ack", state="detached"), "حسناً")
    assert page.is_visible("#photo-generate") and page.is_enabled("#photo-generate")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


def test_a_new_version_is_requested_only_by_a_choice_made_on_the_edit_screen(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_proposal(flow)
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    assert page.is_disabled("#edit-submit")
    page.click("#edit-chips [data-key='SHORTER']")
    assert page.is_enabled("#edit-submit")

    # يعود إلى الاقتراح ثم إلى التعديل: الخيار باقٍ، والإرسال معطّلٌ حتى يُختار من جديد.
    page.click("#edit-back")
    flow.screen("#proposal-copy")
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    assert page.get_attribute("#edit-chips [data-key='SHORTER']", "aria-pressed") == "true"
    assert page.is_disabled("#edit-submit")
    page.click("#edit-chips [data-key='MORE_FORMAL']")
    assert page.is_enabled("#edit-submit")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


def test_a_note_left_by_back_stays_a_draft_until_saved(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_proposal(flow)
    flow.press("#proposal-start", lambda: flow.screen("#edit-chips"), "اطلب تعديلاً")
    page.click("#edit-note")
    flow.screen("#note-text")
    page.fill("#note-text", "الجلد  طبيعي\nواللون بنيّ")
    page.click("#note-back")
    flow.screen("#edit-chips")
    assert page.is_disabled("#edit-submit") and page.inner_text("#edit-note") == "ملاحظة نصية"
    page.click("#edit-note")
    flow.screen("#note-text")
    assert page.input_value("#note-text") == "الجلد  طبيعي\nواللون بنيّ"
    page.click("#note-save")
    flow.screen("#edit-chips")
    assert page.is_enabled("#edit-submit") and "مكتوبة" in page.inner_text("#edit-note")
    page.click("#edit-submit")
    flow.until(_status("2 من"))
    # ما يُرسل هو ما يُحسب: المسافات المتكرّرة وفواصل الأسطر مسافةٌ واحدة.
    assert server["writer"].requests[-1].edit_note == "الجلد طبيعي واللون بنيّ"


@pytest.mark.parametrize("installed", [False, True], ids=["safari", "home-screen"])
def test_the_download_link_is_not_offered_in_the_installed_app(next_page, server, owner, installed):
    """
    WebKit 290847 (مفتوح): في التطبيق المضاف إلى الشاشة الرئيسية قد يُفضي التنزيل إلى شاشةٍ لا
    يُخرج منها إلا بإغلاق التطبيق قسراً — طريقٌ مسدود لمن يعمل بالنظر.
    """
    page = _page(next_page, owner, server)
    if installed:
        page.add_init_script("Object.defineProperty(navigator, 'standalone', { value: true });")
    flow = Flow(page)
    _to_ready(flow)
    link = page.locator("#ready-download")
    if installed:
        assert link.count() == 0
    else:
        assert link.is_visible() and link.get_attribute("href").startswith("/api/campaigns/")
    # المشاركة تفشل: الرسالة لا تدلّ على رابطٍ غير معروض.
    page.evaluate("() => { navigator.share = () => Promise.reject(new DOMException('x', 'NotAllowedError')); }")
    flow.until("!document.querySelector('#ready-share').disabled")
    page.click("#ready-share")
    message = _notice(page)
    assert ("نزّل الصورة" in message) is not installed
    assert not page.errors, page.errors


@pytest.mark.parametrize("image", ["arrives", "fails"])
def test_sharing_waits_for_the_image_and_says_when_it_could_not_load(next_page, server, owner, image):
    """قبل وصول الصورة لا مشاركة؛ وإن لم تُحمَّل الصورة قيل ذلك، والمشاركة بالنصّ."""
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_review(flow)
    flow.press("#review-continue", lambda: flow.screen("#confirm-yes"), "متابعة للتأكيد")
    gate = {"open": False, "held": []}

    def hold(route):
        if image == "fails":
            route.fulfill(status=500, content_type="application/json", body='{"detail": "عطل"}')
        elif gate["open"]:
            route.continue_()
        else:
            gate["held"].append(route)

    page.route("**/api/campaigns/*/image*", hold)
    page.click("#confirm-yes")
    flow.screen("#ready-share")
    page.evaluate("""() => {
        window.__shared = null;
        navigator.canShare = () => true;
        navigator.share = (data) => { window.__shared = data; return Promise.resolve(); };
    }""")
    if image == "arrives":
        for _ in range(200):
            if gate["held"]:
                break
            page.wait_for_timeout(25)
        assert gate["held"] and page.is_disabled("#ready-share")
        gate["open"] = True
        for route in gate["held"]:
            route.continue_()
    flow.until("!document.querySelector('#ready-share').disabled")
    page.click("#ready-share")
    flow.until("window.__shared !== null")
    files = page.evaluate("() => (window.__shared.files || []).length")
    status = page.text_content("#ready-status")
    if image == "arrives":
        assert files == 1 and status == ""
    else:
        assert files == 0 and "النصّ وحده" in status
    assert not page.errors, page.errors


def test_a_notice_on_the_ready_screen_locks_every_control_until_the_ack(next_page, server, owner):
    """النسخ يفشل: التنبيه يُقرّ أولاً، وما حوله — الرابط أيضاً، وهو لا يعرف disabled — خاملٌ حتى «حسناً»."""
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_ready(flow)
    flow.until("!document.querySelector('#ready-share').disabled")
    page.evaluate("() => { navigator.clipboard.writeText = () => Promise.reject(new DOMException('x', 'NotAllowedError')); }")
    page.click("#ready-copy-title")
    assert "تعذّر النسخ" in _notice(page)
    inert = "(id) => document.querySelector(id).closest('[inert]') !== null"
    assert page.evaluate(inert, "#ready-download") and page.evaluate(inert, "#ready-share")
    page.click("#notice-ack")
    assert not page.evaluate(inert, "#ready-download") and page.is_enabled("#ready-share")
    assert not page.errors, page.errors


# ── أطول نصٍّ مقبول، وكلمة سيمبول ─────────────────────────────────────────
WORDS = "حقيبة يد من الجلد الطبيعي بسعر مناسب وتصميم أنيق وصحية للظهر وتتسع لكل الأغراض اليومية "
TITLE = (WORDS * 2)[:TITLE_MAX].strip()
SHORT = (WORDS * 2)[:34].strip()
WASTEFUL = "\n".join([SHORT, SHORT, SHORT, (WORDS * 4)[:DESCRIPTION_MAX - 3 * (len(SHORT) + 1)].strip()])
EVEN = "\n".join([(WORDS * 2)[:59].strip()] * 4)
LONG_NOTE = ("أبرزتُ الخامة واللون والحزام، ولم أذكر المقاس ولا السعة لأنهما لا يظهران في الصورة بوضوح. " * 2)
LONG_NOTE = LONG_NOTE[:NOTE_TO_USER_MAX].strip()


def _squash(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("description", [EVEN, WASTEFUL], ids=["even", "wasteful"])
@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=[f"{w}x{h}" for w, h in TIGHTEST])
def test_the_longest_valid_copy_is_read_whole_before_approval(next_page, server, owner, size, description, width, height):
    """
    النصّ المقترح يُوافَق عليه كما يُرى، فلا يُقصّ منه حرف: في الحجم الكبير صفحاتٌ تُقرأ كلّها
    بلا تمريرٍ ولا قصّ، وفي العادي كلّه في الصفحة. أطول ما تقبله قواعد النصّ، بتنبيهٍ وملاحظة.
    """
    check = check_copy(TITLE, description)
    assert check.ok and check.warnings and check_note_to_user(LONG_NOTE)[0] == LONG_NOTE, (check.errors, len(description))
    page = _page(next_page, owner, server, size, width, height)
    server["writer"].queue(ok(TITLE, description, LONG_NOTE))
    flow = Flow(page)
    _to_proposal(flow)
    audit = flow.audits[-1]
    assert not audit["clipped"], audit
    if size == "gaze":
        assert not audit["vertical"], audit
    text = _proposal_text(page)
    assert _squash(TITLE) in _squash(text)
    assert _squash(description) in _squash(text)
    assert "تحقّق من هذه العبارة" in text and _squash(LONG_NOTE) in _squash(text)
    assert not flow.failures(), "\n".join(flow.failures())
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
def test_the_assistants_note_is_shown_beside_the_proposed_copy(next_page, server, owner, size):
    page = _page(next_page, owner, server, size)
    flow = Flow(page)
    _to_proposal(flow)
    if size == "gaze":
        assert f"سيمبول: {NOTE}" in _proposal_text(page)
    else:
        note = page.inner_text("#proposal-note")
        assert note.startswith("سيمبول") and NOTE in note


# ── «حملاتي» بصفحاتها ─────────────────────────────────────────────────────
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize(("width", "height"), TIGHTEST, ids=[f"{w}x{h}" for w, h in TIGHTEST])
def test_a_full_page_of_campaigns_fits_and_pages(next_page, server, owner, app, size, width, height):
    user = member(owner, size="GAZE" if size == "gaze" else "COMPACT")
    for _ in range(campaigns.PAGE_SIZE + 1):
        campaign = create_campaign(app, user)
        add_version(app, user, campaign, title="حقيبة يد جلدية بلون بنيّ داكن بتصميمٍ عملي")
    page = next_page(width, height, login=LOGIN, size=size)
    flow = Flow(page)
    page.goto(page.next + BASE + "/campaigns")
    flow.until(f"document.querySelectorAll('#campaigns-list li').length === {campaigns.PAGE_SIZE}"
               " && !document.querySelector('#campaigns-older').disabled")
    flow.audit("campaigns-full")
    # عنوانٌ يتكرّر في الصفحة يُرقَّم بموضعه: لكل صفٍّ اسمٌ لا يشاركه فيه غيره.
    names = page.eval_on_selector_all("#campaigns-list li button", "(bs) => bs.map((b) => b.textContent.trim())")
    assert len(set(names)) == campaigns.PAGE_SIZE and all(name.startswith("حقيبة يد") for name in names)
    assert page.is_disabled("#campaigns-newer")
    flow.press("#campaigns-older", lambda: flow.until("document.querySelectorAll('#campaigns-list li').length === 1"), "الأقدم")
    assert page.is_disabled("#campaigns-older") and page.is_enabled("#campaigns-newer")
    flow.press("#campaigns-newer", lambda: flow.until(
        f"document.querySelectorAll('#campaigns-list li').length === {campaigns.PAGE_SIZE}"), "الأحدث")
    assert not flow.failures(), "\n".join(flow.failures())
    assert not page.errors, page.errors


def test_an_empty_list_offers_a_new_campaign(next_page, server, owner):
    page = _page(next_page, owner, server)
    flow = Flow(page)
    page.goto(page.next + BASE + "/campaigns")
    flow.screen("#campaigns-new")
    assert "لا حملات بعد" in page.inner_text("main")
    flow.press("#campaigns-new", lambda: flow.screen("#photo-input"), "حملة جديدة")
    assert not page.errors, page.errors


# ── اللمس كالنظر، و«زيادة التباين» ───────────────────────────────────────
def test_a_campaign_by_touch_to_the_approved_copy(next_page, server, owner):
    """الواجهة تستمع إلى click وحده، وiOS يرسله من الإقامة بالنظر ومن النقر باللمس."""
    page = _page(next_page, owner, server, "compact", *PHONES[0])
    flow = Flow(page)
    page.goto(page.next + "#/")
    flow.screen("#home-new")
    page.tap("#home-new")
    flow.screen("#photo-input")
    page.set_input_files("#photo-input", files=[PHOTO])
    flow.until("!document.querySelector('#photo-generate').disabled")
    page.tap("#photo-generate")
    flow.screen("#proposal-copy")
    page.tap("#proposal-end")
    flow.until(_end("الميزانية"))
    page.tap("#proposal-end")
    flow.screen("#budget-presets")
    page.tap("#budget-presets [data-key='500']")
    flow.until("!document.querySelector('#budget-next').disabled")
    page.tap("#proposal-back, #budget-back")
    flow.screen("#proposal-copy")
    assert not page.errors, page.errors


@pytest.mark.parametrize("size", SIZES)
def test_increase_contrast_keeps_every_target_in_place(next_page, server, owner, size):
    page = _page(next_page, owner, server, size, *STRESS)
    page.emulate_media(contrast="more")
    flow = Flow(page)
    _to_review(flow)
    _finish(flow)
    assert not flow.failures(), "\n".join(flow.failures())
    if size == "gaze":
        assert not flow.landings, "\n".join(flow.landings)
    assert not page.errors, page.errors


def test_the_help_quotes_no_label_that_a_device_has_not_confirmed(next_page, server, owner):
    """تسميات قوائم iOS بالعربية لم تُتحقَّق على جهازٍ بعد: ما بين «» في كل نصٍّ تسميةُ زرٍّ في التطبيق."""
    page = _page(next_page, owner, server)
    flow = Flow(page)
    _to_ready(flow)
    quoted = page.evaluate("""() => {
        const own = new Set([...document.querySelectorAll('button, a, h1, h2')].map((e) => e.textContent.trim()));
        return [...document.querySelectorAll('main p')]
            .flatMap((e) => [...e.textContent.matchAll(/«([^»]+)»/g)].map((m) => m[1]))
            .filter((label) => !own.has(label));
    }""")
    assert quoted == [], quoted
    # لا تلميح شرحٍ في «حملاتي».
    page.click("#ready-home")
    flow.screen("#home-new")
    page.click("#home-campaigns")
    flow.screen("h1 >> text=حملاتي")
    assert page.locator("#campaigns-install").count() == 0
