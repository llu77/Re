"""
التنبيهات والمسارات المنقطعة — في متصفّحٍ حقيقي
================================================
  • «حسناً» فوق وسط الشريط العلوي، وكل زرٍّ في الشريطين معطّلٌ ما دام التنبيه
    ظاهراً، وما يقع تحتها بعد الإقرار ليس زرّ اعتمادٍ ولا عنصر قيمة.
  • وبينها وبين زرّي طرفي الشريط 24 على الأقل، في كل شاشةٍ وكل إطار.
  • فشل الإقلاع لا يترك شاشةً بلا مخرج: «حسناً» تعيد المحاولة.
  • طلبٌ انقطع في الطريق يُقال، ولا يُترك المستخدم أمام شاشةٍ صامتة.
  • «اطلب نسخة جديدة» لا تُرسل بنظرٍ مرّ بها: تبقى معطّلةً حتى يُختار فيها.
"""

from __future__ import annotations

import json

import pytest

from eyework.tests.ui.conftest import VIEWPORTS
from eyework.tests.ui.flow import Flow, sample_photo

BUSY = {"code": "AI_BUSY", "detail": "المساعد مشغولٌ الآن. حاول بعد قليل."}

ACK_STATE = """
() => {
    const screen = document.querySelector('.screen:not([hidden])');
    const ack = screen.querySelector('.alert:not([hidden]) [data-ack]');
    const r = ack.getBoundingClientRect();
    const bar = screen.querySelector('.bar--top').getBoundingClientRect();
    const enabled = [...document.querySelectorAll('button, a[href], label.btn, input, textarea')]
        .filter((e) => e !== ack && !e.disabled && !e.closest('[hidden]'))
        .filter((e) => {
            const o = e.getBoundingClientRect();
            return o.width > 0 && o.height > 0;
        });
    const overlapping = enabled.filter((e) => {
        const o = e.getBoundingClientRect();
        return o.left < r.right + 24 && o.right > r.left - 24 && o.top < r.bottom + 24 && o.bottom > r.top - 24;
    }).map((e) => e.id || e.textContent.trim());
    return {
        screen: screen.dataset.screen,
        centre: r.left + r.width / 2,
        top: r.top,
        inBar: r.top >= bar.top - 1 && r.bottom <= bar.bottom + 1,
        width: r.width,
        height: r.height,
        viewport: innerWidth,
        barEnabled: [...screen.querySelectorAll('.bar .btn')]
            .filter((b) => !b.disabled && b.getAttribute('aria-disabled') !== 'true'
                && getComputedStyle(b).pointerEvents !== 'none')
            .map((b) => b.textContent.trim()),
        overlapping,
    };
}
"""


def _to_photo(flow: Flow) -> None:
    flow.page.goto(flow.base + "/#/")
    flow.screen("home")
    flow.press("#home-new", lambda: flow.screen("photo"), "حملة جديدة")
    flow.page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                      "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")


def _alert_shown(flow: Flow) -> None:
    flow.until("document.querySelector('.screen:not([hidden]) .alert:not([hidden])') !== null")


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=[f"{w}x{h}" for w, h in VIEWPORTS])
def test_the_acknowledgement_sits_alone_at_the_top_centre(page_factory, server, width, height):
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    _to_photo(flow)
    page.route("**/api/campaigns/*/copy", lambda route: route.fulfill(
        status=503, content_type="application/json", body=json.dumps(BUSY)))

    flow.press("#photo-generate", lambda: _alert_shown(flow), "اكتب لي العنوان والوصف")
    state = page.evaluate(ACK_STATE)
    assert state["screen"] == "proposal"
    assert abs(state["centre"] - state["viewport"] / 2) < 1
    assert state["inBar"], state
    assert state["top"] >= 16 and state["width"] >= 71.5 and state["height"] >= 71.5
    assert state["barEnabled"] == [], state
    assert state["overlapping"] == [], state
    audit = flow.audit("alert")
    assert not audit["small"] and not audit["close"] and not audit["edge"], audit
    assert not audit["vertical"] and not audit["horizontal"], audit

    page.unroute("**/api/campaigns/*/copy")
    flow.press(".screen:not([hidden]) .alert [data-ack]", lambda: flow.until(
        "document.querySelector('.screen:not([hidden]) .alert:not([hidden])') === null"), "حسناً")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


#: كل شاشةٍ تُعرض بتنبيهها، ويُقاس بُعد كل زرٍّ في شريطها العلوي عن «حسناً» —
#: والمحجوز منها أيضاً، فقد يظهر والتنبيه ظاهر: أسوأ الحال.
ACK_CLEARANCE = """
() => {
    const screens = [...document.querySelectorAll('.screen')];
    const close = [];
    for (const screen of screens) {
        screens.forEach((s) => { s.hidden = s !== screen; });
        const alert = screen.querySelector('.alert');
        alert.hidden = false;
        const a = alert.querySelector('[data-ack]').getBoundingClientRect();
        for (const button of screen.querySelectorAll('.bar--top .btn')) {
            const r = button.getBoundingClientRect();
            const gap = Math.max(r.left - a.right, a.left - r.right, r.top - a.bottom, a.top - r.bottom);
            if (gap < 23.5) close.push(`${screen.dataset.screen} ${button.textContent.trim()}: ${Math.round(gap)}`);
        }
        alert.hidden = true;
    }
    return close;
}
"""


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=[f"{w}x{h}" for w, h in VIEWPORTS])
def test_the_acknowledgement_keeps_its_distance_on_every_screen(page_factory, server, width, height):
    """
    زرّا طرفي الشريط العلوي لا يقتربان من «حسناً» أقلّ من 24: في 320px كان كلٌّ
    منهما على 4 منها، و«احفظ الملاحظة» — أطول الأسماء — يركبها؛ وفي 375 و390 كان
    على 15 و22.
    """
    page = page_factory(width, height)
    page.goto(server["base"] + "/#/")
    Flow(page, server["base"]).screen("home")
    # عرض الاسم بخطّ Amiri لا بالخطّ البديل قبل وصوله.
    page.evaluate("() => document.fonts.ready.then(() => true)")
    assert page.evaluate(ACK_CLEARANCE) == []
    assert not page.errors, page.errors


def test_every_screen_has_an_alert_and_text_at_the_top_centre(page_factory, server):
    # ما تحت «حسناً» بعد الإقرار هو وسط الشريط العلوي للشاشة التالية، أيّاً كانت.
    page = page_factory()
    page.goto(server["base"] + "/#/")
    Flow(page, server["base"]).screen("home")
    screens = page.evaluate("""
        () => [...document.querySelectorAll('.screen')].map((s) => ({
            name: s.dataset.screen,
            alert: s.querySelector('.alert [data-ack]') !== null,
            middle: s.querySelector('.bar--top').children[1].matches('p.step'),
        }))
    """)
    assert [s["name"] for s in screens if not (s["alert"] and s["middle"])] == []


def test_a_failed_start_offers_a_retry(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    page.route("**/api/choices", lambda route: route.fulfill(
        status=503, content_type="application/json", body=json.dumps({"detail": "الخدمة متوقّفة مؤقّتاً."})))
    page.goto(server["base"] + "/#/")
    flow.screen("login")
    _alert_shown(flow)
    assert "«حسناً» تعيد المحاولة" in page.inner_text(".screen[data-screen='login'] .alert__text")

    page.unroute("**/api/choices")
    page.click(".screen[data-screen='login'] .alert [data-ack]")
    flow.screen("home")
    assert not page.errors, page.errors


def test_signing_in_after_a_failed_start_loads_the_choices_first(page_factory, server):
    # التنبيه يغطّي زرّ الدخول، لكن «اذهب» في لوحة المفاتيح ترسل النموذج: الدخول
    # يمرّ، والخيارات تُقرأ قبل أوّل شاشة.
    from eyework.tests.ui.conftest import LOGIN, PASSWORD

    page = page_factory(session=False)
    flow = Flow(page, server["base"])
    page.route("**/api/choices", lambda route: route.fulfill(
        status=503, content_type="application/json", body=json.dumps({"detail": "الخدمة متوقّفة مؤقّتاً."})))
    page.goto(server["base"] + "/#/")
    flow.screen("login")
    _alert_shown(flow)

    page.unroute("**/api/choices")
    page.fill("#login-username", LOGIN)
    page.fill("#login-password", PASSWORD)
    page.press("#login-password", "Enter")
    flow.screen("home")
    # أوّل شاشةٍ تحتاج الخيارات: سطر الحالة في الاقتراح يذكر حدّ النسخ منها.
    page.click("#home-new")
    flow.screen("photo")
    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    page.click("#photo-generate")
    flow.until("!document.querySelector('#proposal-copy').hidden")
    assert "النسخة 1 من 10" in page.inner_text("#proposal-status")
    assert not page.errors, page.errors


def test_a_dropped_request_says_what_happened(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    _to_photo(flow)
    page.route("**/api/campaigns/*/copy", lambda route: route.abort("connectionreset"))

    page.click("#photo-generate")
    _alert_shown(flow)
    # الطلب لم يبلغ الخادم: الحملة بلا نصّ، فتُعرض كما حُفظت — شاشة الصورة.
    assert page.is_visible(".screen[data-screen='photo']")
    assert "انقطع الاتصال" in page.inner_text(".screen[data-screen='photo'] .alert__text")
    assert not page.errors, page.errors


def test_a_new_version_is_requested_only_by_a_choice_made_on_the_edit_screen(page_factory, server):
    page = page_factory()
    flow = Flow(page, server["base"])
    _to_photo(flow)
    flow.press("#photo-generate", lambda: flow.until("!document.querySelector('#proposal-copy').hidden"),
               "اكتب لي العنوان والوصف")

    flow.press("#proposal-start", lambda: flow.screen("edit"), "اطلب تعديلاً")
    assert page.is_disabled("#edit-submit")
    page.click("#edit-chips .chip >> nth=0")
    assert page.is_enabled("#edit-submit")

    # يعود إلى الاقتراح ثم إلى التعديل: الخيار باقٍ، والإرسال معطّلٌ حتى يُختار من جديد.
    page.click(".screen[data-screen='edit'] [data-back]")
    flow.screen("proposal")
    flow.press("#proposal-start", lambda: flow.screen("edit"), "اطلب تعديلاً")
    assert page.get_attribute("#edit-chips .chip >> nth=0", "aria-pressed") == "true"
    assert page.is_disabled("#edit-submit")
    page.click("#edit-chips .chip >> nth=2")
    assert page.is_enabled("#edit-submit")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


def test_an_alert_also_locks_the_download_link_on_the_ready_screen(page_factory, server):
    """الرابط لا يعرف disabled؛ نظرةٌ باقية عليه أثناء التنبيه لا تنزّل شيئاً."""
    page = page_factory()
    flow = Flow(page, server["base"])
    flow.to_review()
    flow.press("#review-continue", lambda: flow.screen("confirm"), "متابعة للتأكيد")
    flow.press("#confirm-yes", lambda: flow.screen("ready"), "نعم، اعتمد الحملة")
    page.evaluate("() => UI.showAlert(UI.screen('ready'), 'تعذّر النسخ.')")
    state = page.evaluate(ACK_STATE)
    assert state["barEnabled"] == [], state
    assert page.get_attribute("#ready-download", "aria-disabled") == "true"
    page.click(".screen[data-screen='ready'] [data-ack]")
    assert page.get_attribute("#ready-download", "aria-disabled") is None
    assert page.evaluate("() => getComputedStyle(document.querySelector('#ready-download')).pointerEvents") != "none"
    assert not page.errors, page.errors


@pytest.mark.parametrize("installed", [False, True], ids=["safari", "home-screen"])
def test_the_download_link_is_not_offered_in_the_installed_app(page_factory, server, installed):
    """
    WebKit 290847 (مفتوح): في التطبيق المضاف إلى الشاشة الرئيسية قد يُفضي التنزيل إلى
    شاشةٍ لا يُخرج منها إلا بإغلاق التطبيق قسراً — طريقٌ مسدود لمن يعمل بالنظر.
    """
    page = page_factory()
    if installed:
        page.add_init_script("Object.defineProperty(navigator, 'standalone', { value: true });")
    flow = Flow(page, server["base"])
    flow.to_review()
    flow.press("#review-continue", lambda: flow.screen("confirm"), "متابعة للتأكيد")
    flow.press("#confirm-yes", lambda: flow.screen("ready"), "نعم، اعتمد الحملة")
    link = page.locator("#ready-download")
    if installed:
        assert page.evaluate("() => getComputedStyle(document.querySelector('#ready-download')).visibility") == "hidden"
        assert link.get_attribute("href") is None
    else:
        assert link.is_visible() and link.get_attribute("href").startswith("/api/campaigns/")
    # المشاركة تفشل: الرسالة لا تدلّ على رابطٍ غير معروض.
    page.evaluate("() => { navigator.share = () => Promise.reject(new DOMException('x', 'NotAllowedError')); }")
    page.click("#ready-share")
    page.wait_for_selector(".screen[data-screen='ready'] .alert:not([hidden])")
    message = page.inner_text(".screen[data-screen='ready'] .alert__text")
    assert ("نزّل الصورة" in message) is not installed
    assert not page.errors, page.errors
