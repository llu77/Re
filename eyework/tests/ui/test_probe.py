"""
صفحة فحص الإدخال
================
الصفحة التي يقوم عليها قرار البناء كلّه. تُثبت هنا ثلاثة أشياء: لا ترسل شيئاً
ولا تخزّن شيئاً، وتسجّل ما تقيسه، وتحكم بنجاحٍ أو فشلٍ صحيحين.
"""

from __future__ import annotations

import io
import re

import pytest
from PIL import Image


@pytest.fixture
def probe(page_factory, server):
    page = page_factory(390, 664, session=False)
    page.goto(server["base"] + "/probe/")
    page.wait_for_selector(".sec[data-section='env']:not([hidden])")
    page.wait_for_load_state("networkidle")
    return page


def _section(page, name):
    for _ in range(20):
        if page.locator(f".sec[data-section='{name}']").is_visible():
            return
        page.locator("#next").click()
    raise AssertionError(f"لم يُبلغ القسم {name}")


def test_nothing_leaves_the_device(probe, server):
    """بعد التحميل لا طلب واحد، مهما ضُغط؛ والصفحة تحمل CSP تمنع الاتصال أصلاً."""
    loaded = len(probe.requests)
    _section(probe, "activation")
    for target in ("t44", "t56", "t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    # واجهات المنصّة الحقيقية في المتصفّح، بلا بدائل: الملفّان من بايتاتٍ في الصفحة.
    _section(probe, "apis")
    for button in ("#api-copy", "#api-wake", "#api-share"):
        probe.locator(button).click()
    _section(probe, "pages")
    probe.locator("#api-text").click()
    _section(probe, "wait")
    probe.locator("#wait-start").click()
    probe.locator("#wait-done").click()
    _section(probe, "verdict")
    probe.locator("#copy").click()
    assert probe.requests[loaded:] == []
    assert all(url.startswith(server["base"]) for _, url in probe.requests)
    csp = probe.request.get(server["base"] + "/probe/").headers["content-security-policy"]
    assert "connect-src 'none'" in csp and "form-action 'none'" in csp


def test_nothing_is_stored_and_no_timer_runs(probe):
    _section(probe, "rearm")
    probe.locator("#rearm-a").click()
    probe.locator("#rearm-b").click()
    _section(probe, "verdict")
    storage = probe.evaluate("() => [localStorage.length, sessionStorage.length]")
    assert storage == [0, 0]
    assert probe.evaluate("() => window.__eyework.timers") == []


def _rearm_row(page) -> str:
    _section(page, "verdict")
    return next(row for row in _rows(page, "checks-core") if "دون تحريك النظر" in row)


def test_a_re_press_in_place_reads_as_a_re_press(probe):
    """الضغط على الثاني في موضع الأول بلا حركة: الإخفاء والإظهار وحدهما ليسا حركة."""
    _section(probe, "rearm")
    box = probe.locator("#rearm-a").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    probe.mouse.move(x, y)
    probe.mouse.click(x, y)
    probe.mouse.click(x, y)
    assert "دون أن يتحرّك النظر" in probe.inner_text("#rearm-result")
    assert "نعم" in _rearm_row(probe)


def test_leaving_the_cell_between_presses_reads_as_movement(probe):
    _section(probe, "rearm")
    box = probe.locator("#rearm-a").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    probe.mouse.move(x, y)
    probe.mouse.click(x, y)
    probe.mouse.move(x, box["y"] + box["height"] + 40)
    probe.mouse.move(x, y)
    probe.mouse.click(x, y)
    assert "بعد أن تحرّك النظر" in probe.inner_text("#rearm-result")
    assert "لا" in _rearm_row(probe).split("دون تحريك النظر", 1)[1]


def _rows(page, table):
    return page.locator(f"#{table} tr").all_inner_texts()


def _summary(page) -> dict[str, str]:
    """
    نصّ «انسخ النتيجة» كما يلصقه المختبِر في جدول البوابة: كل فحصٍ بمفتاحه،
    وسطور الرأس بأسمائها، والمحاولات تحت «attempts»، والأحداث تحت «events».
    """
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    _section(page, "verdict")
    page.locator("#copy").click()
    page.wait_for_function("() => document.getElementById('copy').textContent === 'نُسخت النتيجة'")
    text = page.evaluate("() => navigator.clipboard.readText()")
    head, events = text.split("آخر الأحداث:", 1)
    head, _, attempts = head.partition("المحاولات:")
    found = {"events": events, "attempts": attempts}
    for line in head.splitlines():
        if " · " in line:
            key, rest = line.split(" · ", 1)
            found[key] = rest
        elif ": " in line:
            name, value = line.split(": ", 1)
            found[name] = value
    return found


def _number(text: str) -> int:
    """أول عددٍ في النصّ، بالأرقام العربية أو اللاتينية."""
    digits = re.search(r"[0-9٠-٩]+", text).group()
    return int(digits.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))


def _centre(page, selector):
    box = page.locator(selector).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _choose(page, attribute, value):
    """الطريقة وحالة «الانتقال إلى العنصر» تُختاران في القسم الأول."""
    while not page.locator(".sec[data-section='env']").is_visible():
        page.locator("#prev").click()
    page.locator(f"[data-{attribute}='{value}']").click()


def test_gaze_clicks_on_the_app_sizes_pass_the_gate(probe):
    """القرار على الأحجام التي يستعملها التطبيق (72 فأكبر)؛ 44 و56 قياسٌ للدقّة لا شرط."""
    _section(probe, "activation")
    for target in ("t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == "pass"
    assert any("نجح" in row and "٢ من ٢" in row for row in _rows(probe, "checks-core")), _rows(probe, "checks-core")
    _section(probe, "details")
    assert any("٧٢، ٩٦" in row for row in _rows(probe, "checks-detail")), _rows(probe, "checks-detail")


def test_a_missed_app_size_fails_the_gate(probe):
    _section(probe, "activation")
    for target in ("t44", "t56", "t72"):
        probe.locator(f"[data-probe='{target}']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == "fail"


def test_touch_taps_never_pass_the_gaze_gate(probe):
    """أساس المقارنة باللمس ثم العودة إلى «بالنظر»: لا نقرة لمسٍ تُحسب نظراً."""
    probe.locator("[data-mode='touch']").click()
    _section(probe, "activation")
    for target in ("t44", "t56", "t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    # الطريقة تُختار في القسم الأول: يعود إليه المشغّل ليبدّلها.
    while not probe.locator(".sec[data-section='env']").is_visible():
        probe.locator("#prev").click()
    probe.locator("[data-mode='gaze']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == ""
    _section(probe, "details")
    assert any("للمقارنة" in row and "٤" in row for row in _rows(probe, "checks-detail"))


def test_untested_is_not_a_pass(probe):
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == ""


def test_stepper_counts_exactly(probe):
    _section(probe, "stepper")
    for _ in range(4):
        probe.locator("#stepper-plus").click()
    probe.locator("#stepper-done").click()
    assert "٤" in probe.locator("#stepper-result").inner_text()
    _section(probe, "verdict")
    assert any("لم ينجح" in row for row in probe.locator("#checks-core tr").all_inner_texts()
               if "ثلاث" in row)


_OVERFLOWS = (
    "() => { const s = document.querySelector('.sec:not([hidden])');"
    " return [...s.children].some(e => e.getBoundingClientRect().bottom > s.getBoundingClientRect().bottom + 1)"
    " || document.scrollingElement.scrollHeight > innerHeight + 1; }")


@pytest.mark.parametrize(("width", "height"), [(375, 635), (390, 664)])
def test_every_section_fits_without_scrolling(page_factory, server, width, height):
    page = page_factory(width, height, session=False)
    page.goto(server["base"] + "/probe/")
    page.wait_for_selector(".sec[data-section='env']:not([hidden])")
    count = page.locator(".sec").count()
    for index in range(count):
        overflow = page.evaluate(_OVERFLOWS)
        assert not overflow, page.locator(".sec:not([hidden])").get_attribute("data-section")
        if index < count - 1:
            page.locator("#next").click()


def test_the_probe_uses_the_apps_geometry(probe):
    """أزرار الفحص بهندسة التطبيق نفسها (72 و24)، وإلا قيس غيرُ ما يُستعمل."""
    sizes = probe.evaluate("""() => {
        const style = (selector) => getComputedStyle(document.querySelector(selector));
        return [style('.btn').minHeight, style('.btn').minWidth, style('.row').columnGap,
                style('.nav').columnGap, style('.sec').rowGap];
    }""")
    assert sizes == ["72px", "72px", "24px", "24px", "24px"]
    for button in ("#prev", "#next", "[data-mode='gaze']"):
        box = probe.locator(button).bounding_box()
        assert box["width"] >= 72 and box["height"] >= 72, button


def test_a_touch_like_press_is_not_hover(probe):
    """
    جهازٌ لا يمرّ يُطلق pointerover قبل pointerdown مباشرة (Pointer Events 3):
    المرور وحده ليس «نعم»، والفاصل قرابة الصفر لا «زمن مكوث».
    """
    _section(probe, "activation")
    for target in ("t72", "t96"):
        probe.touchscreen.tap(*_centre(probe, f"[data-probe='{target}']"))
    found = _summary(probe)
    assert "(لا (pointermove: ٠))" in found["hover"], found["hover"]
    assert "touch" in found["pointer"], found["pointer"]
    assert _number(found["gap"].split("(", 1)[1]) < 50, found["gap"]


def test_a_hovering_pointer_is_hover(probe):
    """حركاتٌ على الهدف قبل pointerdown: مؤشرٌ يمرّ، ويُطبع عددها."""
    _section(probe, "activation")
    for target in ("t72", "t96"):
        x, y = _centre(probe, f"[data-probe='{target}']")
        probe.mouse.move(x - 30, y - 30)
        probe.mouse.move(x, y, steps=5)
        probe.mouse.down()
        probe.mouse.up()
    found = _summary(probe)
    assert "(نعم (pointermove:" in found["hover"], found["hover"]
    assert _number(found["hover"].split("pointermove:", 1)[1]) >= 2, found["hover"]


def test_pointer_type_comes_from_pointerdown_not_click(probe):
    """في iOS قد يحمل click الناتج عن لمسٍ النوع mouse (علّة WebKit 282988)."""
    _section(probe, "activation")
    probe.locator("[data-probe='t72']").evaluate("""(element) => {
        const at = { bubbles: true, cancelable: true, isPrimary: true, clientX: 10, clientY: 10 };
        element.dispatchEvent(new PointerEvent('pointerover', { ...at, pointerType: 'touch' }));
        element.dispatchEvent(new PointerEvent('pointerdown', { ...at, pointerType: 'touch' }));
        element.dispatchEvent(new PointerEvent('pointerup', { ...at, pointerType: 'touch' }));
        element.dispatchEvent(new PointerEvent('click', { ...at, pointerType: 'mouse' }));
    }""")
    found = _summary(probe)
    assert "touch" in found["pointer"] and "mouse" not in found["pointer"], found["pointer"]


@pytest.mark.parametrize("how", ["keyboard", "touch"])
def test_without_pointer_moves_the_re_press_is_unknown(probe, how):
    """
    بلا حركة pointermove على الخانة لا يُعرف هل تحرّك النظر: لا أحداث حدودٍ أصلاً
    (لوحة المفاتيح)، أو أحداثٌ ترافق الضغطة نفسها (اللمس). لا يُقرأ ذلك «إعادة ضغط»
    ولا «حركة».
    """
    _section(probe, "rearm")
    for button in ("#rearm-a", "#rearm-b"):
        if how == "keyboard":
            probe.locator(button).focus()
            probe.keyboard.press("Enter")
        else:
            probe.touchscreen.tap(*_centre(probe, button))
    assert "الحركة غير معروفة" in probe.inner_text("#rearm-result")
    assert "الحركة غير معروفة" in _rearm_row(probe)


@pytest.mark.parametrize(("snap", "printed"), [(None, False), ("on", False), ("off", True)])
def test_the_size_recommendation_needs_snap_to_item_off(probe, snap, printed):
    """
    أين يضغط المكوث حين يُفعَّل «الانتقال إلى العنصر» غير موثّق؛ فالتوصية من
    نقراتٍ أُعلن معها مُعطَّلاً وحدها، والحالة في النتيجة المنسوخة وفي كل حدث.
    """
    if snap:
        _choose(probe, "snap", snap)
        assert probe.locator(f"[data-snap='{snap}']").get_attribute("aria-pressed") == "true"
    _section(probe, "activation")
    for target in ("t44", "t56", "t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    found = _summary(probe)
    assert ("بكسل" in found["accuracy"]) is printed, found["accuracy"]
    if not printed:
        assert found["accuracy"].startswith("حجم الهدف الموصى به: NOT_RUN"), found["accuracy"]
    state = {None: "لم يُحدَّد", "on": "مُفعَّل", "off": "مُعطَّل"}[snap]
    assert found["الانتقال إلى العنصر (Snap to Item)"] == state
    assert f"gaze/snap-{snap or '?'} activation t72 click" in found["events"]


def test_head_tracking_presses_are_counted_apart(probe):
    """نقرات «بالرأس» تُعدّ وحدها: لا تنجح بوابة النظر بها ولا تُحسب أحجاماً بالنظر."""
    _choose(probe, "mode", "head")
    assert probe.locator("[data-mode='gaze']").get_attribute("aria-pressed") == "false"
    _section(probe, "activation")
    for target in ("t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == ""
    found = _summary(probe)
    assert found["head"].endswith("INFO (٧٢، ٩٦)"), found["head"]
    assert "NOT_RUN" in found["sizes"] and "NOT_RUN" in found["activation"]


@pytest.mark.parametrize(("typed", "recorded"), [
    ("27.0.1", "27.0.1"),
    ("٢٦٫٧٫١", "26.7.1"),
    ("18.7.8 ", "18.7.8"),
    ("iPhone", "لم يُكتب"),
    ("27.0.1; x", "لم يُكتب"),
])
def test_the_ios_version_is_typed_and_checked(probe, typed, recorded):
    """وكيل المستخدم لا يذكر إصدار iOS منذ Safari 26: يكتبه المختبِر، ولا يُقبل إلا شكلُ إصدار."""
    _section(probe, "device")
    field = probe.locator("#probe-ios")
    field.fill(typed)
    field.press("Tab")
    status = probe.inner_text("#ios-result")
    assert (recorded in status) if recorded[0].isdigit() else ("لم يُفهم" in status), status
    assert _summary(probe)["إصدار iOS (كتبه المختبِر)"] == recorded


def test_a_full_run_still_fits_the_smallest_window(page_factory, server):
    """كل الملاحظات ممتلئة — بالطرق الثلاث — والنتيجة والتفاصيل بلا تمرير عند 375×635."""
    page = page_factory(375, 635, session=False)
    page.goto(server["base"] + "/probe/")
    page.wait_for_selector(".sec[data-section='env']:not([hidden])")
    _choose(page, "snap", "off")
    for mode in ("touch", "head", "gaze"):
        _choose(page, "mode", mode)
        _section(page, "activation")
        for target in ("t44", "t56", "t72", "t96"):
            page.locator(f"[data-probe='{target}']").click()
    _section(page, "rearm")
    page.locator("#rearm-a").click()
    page.locator("#rearm-b").click()
    # أطول ما تكتبه أقسام المنصّة: خطأٌ باسمه، وانتظارٌ خُفيت فيه الصفحة.
    _stub(page, share="NotAllowedError")
    _section(page, "apis")
    for button in ("#api-copy", "#api-wake", "#api-share"):
        page.locator(button).click()
    page.wait_for_function("() => document.getElementById('api-results').textContent.includes('NotAllowedError')")
    assert not page.evaluate(_OVERFLOWS), "apis"
    _section(page, "pages")
    page.locator("#api-text").click()
    page.locator("[data-pages='no']").click()
    assert not page.evaluate(_OVERFLOWS), "pages"
    _section(page, "wait")
    page.locator("#wait-start").click()
    page.wait_for_function("() => window.__sentinel")
    page.evaluate("() => window.__sentinel.dispatchEvent(new Event('release'))")
    page.locator("#wait-done").click()
    page.locator("[data-wait='dimmed']").click()
    assert not page.evaluate(_OVERFLOWS), "wait"
    for section in ("verdict", "platform", "details"):
        _section(page, section)
        assert not page.evaluate(_OVERFLOWS), section


# ── التفعيل وواجهات المنصّة ─────────────────────────────────────────────

#: بدائل الاختبار لواجهات المنصّة: كلٌّ يسجّل عند استدعائه هل كان التفعيل قائماً،
#: ويفشل مرةً واحدة باسم الخطأ إن طُلب. الحافظة تبقى صالحةً لـ«انسخ النتيجة».
_STUBS = """(failures) => {
    const calls = [];
    window.__calls = calls;
    const active = () => navigator.userActivation.isActive;
    const once = (api) => {
        const name = failures[api];
        failures[api] = null;
        return name ? Promise.reject(new DOMException('stub', name)) : null;
    };
    let clipboard = '';
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        writeText: (text) => {
            calls.push({ api: 'copy', active: active(), text });
            return once('copy') || Promise.resolve().then(() => { clipboard = text; });
        },
        readText: () => Promise.resolve(clipboard),
    } });
    Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
        request: (type) => {
            calls.push({ api: 'wake', active: active(), type });
            const sentinel = new EventTarget();
            sentinel.released = false;
            sentinel.release = () => {
                sentinel.released = true;
                calls.push({ api: 'release' });
                sentinel.dispatchEvent(new Event('release'));
                return Promise.resolve();
            };
            window.__sentinel = sentinel;
            return once('wake') || Promise.resolve(sentinel);
        },
    } });
    Object.defineProperty(navigator, 'canShare', { configurable: true,
        value: (data) => Boolean(data.files && data.files.length) });
    Object.defineProperty(navigator, 'share', { configurable: true, value: (data) => {
        const file = data.files[0];
        const call = { api: 'share', active: active(), name: file.name, type: file.type };
        calls.push(call);
        return file.arrayBuffer().then((buffer) => {
            call.bytes = Array.from(new Uint8Array(buffer));
            return once('share');
        });
    } });
}"""

#: يقدّم زمن ضغطة «انتهى الانتظار» ثوانيَ: لا يُنتظر 210 ثوانٍ في اختبار، والصفحة
#: لا تقرأ الزمن إلا من `event.timeStamp`.
_LATER = """(seconds) => window.addEventListener('click', (event) => {
    if (event.target.id === 'wait-done') {
        Object.defineProperty(event, 'timeStamp', { value: event.timeStamp + seconds * 1000 });
    }
}, { capture: true })"""


def _stub(page, **failures):
    page.evaluate(_STUBS, failures)


def _calls(page) -> list[dict]:
    return page.evaluate("() => window.__calls")


def test_each_platform_api_runs_inside_its_own_press(probe):
    """
    زرٌّ لكل واجهة، والاستدعاء داخل الضغطة والتفعيل قائم: هذا ما تشترطه WebKit
    للنسخ والمشاركة وأول طلبٍ لإبقاء الشاشة مضاءة. ولا مؤقّت في أيٍّ منها.
    """
    _stub(probe)
    _section(probe, "apis")
    for button in ("#api-copy", "#api-wake", "#api-share"):
        probe.locator(button).click()
    probe.wait_for_function("() => window.__calls.some((call) => call.bytes)")
    calls = {call["api"]: call for call in _calls(probe)}
    assert calls["copy"]["active"] and calls["wake"]["active"] and calls["share"]["active"], calls
    assert calls["wake"]["type"] == "screen" and "release" in calls, calls
    shared = calls["share"]
    assert (shared["name"], shared["type"]) == ("probe.jpg", "image/jpeg")
    assert Image.open(io.BytesIO(bytes(shared["bytes"]))).format == "JPEG"
    shown = probe.inner_text("#api-results")
    assert shown.count("ok، موثوقة: نعم، التفعيل قائم: نعم") == 3, shown
    found = _summary(probe)
    for key in ("copy", "wake", "share"):
        assert found[key].split(": ", 1)[1].startswith("PASS"), found[key]
    assert "share gaze/snap-? ok isTrusted=true userActivation=true" in found["attempts"]
    assert probe.evaluate("() => window.__eyework.timers") == []


def test_a_synthetic_press_is_not_a_users_press(probe):
    """
    نقرةٌ من شيفرة (`element.click()`) ليست ضغطة مستخدم فلا تنجح، وإن نجح النسخ.
    والتفعيل يُقرأ كما هو: قد يبقى قائماً من ضغطةٍ حقيقيةٍ قبلها بثوانٍ.
    """
    _stub(probe)
    _section(probe, "apis")
    probe.locator("#api-copy").evaluate("(button) => button.click()")
    probe.wait_for_function("() => window.__calls.length === 1")
    assert "ok، موثوقة: لا" in probe.inner_text("#api-results")
    assert _summary(probe)["copy"].split(": ", 1)[1].startswith("FAIL (ok، موثوقة: لا")


@pytest.mark.parametrize(("api", "error", "status"), [
    ("share", "NotAllowedError", "FAIL"),
    ("share", "AbortError", "INFO"),
    ("wake", "NotAllowedError", "FAIL"),
    ("copy", "NotAllowedError", "FAIL"),
])
def test_a_refused_api_is_recorded_by_its_error(probe, api, error, status):
    _stub(probe, **{api: error})
    _section(probe, "apis")
    probe.locator(f"#api-{api}").click()
    probe.wait_for_function("(name) => document.getElementById('api-results').textContent.includes(name)", arg=error)
    row = _summary(probe)[api]
    assert row.split(": ", 1)[1].startswith(f"{status} ({error}"), row


def test_touch_presses_never_pass_the_platform_checks(probe):
    """كما في الضغط: الحكم من ضغطات «بالنظر» وحدها، والباقي في قائمة المحاولات."""
    _stub(probe)
    _choose(probe, "mode", "touch")
    _section(probe, "apis")
    probe.locator("#api-copy").click()
    probe.wait_for_function("() => window.__calls.length === 1")
    found = _summary(probe)
    assert found["copy"].split(": ", 1)[1].startswith("NOT_RUN"), found["copy"]
    assert "copy touch/snap-? ok isTrusted=true" in found["attempts"]


def test_the_pages_answer_belongs_to_a_text_share(probe):
    """لا جواب قبل مشاركة؛ والملفّ نصٌّ عربي بترميز UTF-8 وعلامته، مبنيٌّ في الصفحة."""
    _stub(probe)
    _section(probe, "pages")
    assert probe.locator("[data-pages='yes']").is_disabled()
    probe.locator("#api-text").click()
    probe.wait_for_function("() => window.__calls.some((call) => call.bytes)")
    shared = next(call for call in _calls(probe) if call["api"] == "share")
    assert (shared["name"], shared["type"]) == ("probe.txt", "text/plain")
    text = bytes(shared["bytes"])
    assert text.startswith(b"\xef\xbb\xbf") and "فحص الإدخال" in text.decode("utf-8")
    probe.locator("[data-pages='yes']").click()
    assert probe.locator("[data-pages='yes']").get_attribute("aria-pressed") == "true"
    found = _summary(probe)
    assert found["pages"].split(": ", 1)[1].startswith("INFO (ظهر"), found["pages"]
    assert "pages=yes" in found["attempts"]


@pytest.mark.parametrize(("seconds", "answer", "status"), [
    (210, "on", "PASS"),
    (0, "on", "INFO"),
    (210, "dimmed", "INFO"),
    (0, "locked", "FAIL"),
])
def test_the_long_wait(probe, seconds, answer, status):
    """
    القفل يُطلب داخل الضغطة ويُفلت عند «انتهى»؛ المدّة من `event.timeStamp`؛ ولا
    ينجح إلا ما بقي مضاءً 200 ثانية فأكثر، ولا يُغتفر قفلُ الشاشة مهما قصر الانتظار.
    """
    _stub(probe)
    probe.evaluate(_LATER, seconds)
    _section(probe, "wait")
    probe.locator("#wait-start").click()
    probe.wait_for_function("() => document.getElementById('wait-result').textContent.includes('ok')")
    assert probe.locator("#wait-start").is_hidden() and probe.locator("#wait-answers").is_hidden()
    probe.locator("#wait-done").click()
    assert [call["api"] for call in _calls(probe)] == ["wake", "release"]
    assert _calls(probe)[0]["active"]
    assert probe.locator("#wait-again").is_hidden()
    probe.locator(f"[data-wait='{answer}']").click()
    assert probe.locator("#wait-again").is_visible()
    result = probe.inner_text("#wait-result")
    assert _number(result) == seconds, result
    row = _summary(probe)["wait"]
    assert row.split(": ", 1)[1].startswith(status), row
    assert probe.evaluate("() => window.__eyework.timers") == []


def test_a_wait_that_hid_the_page_says_so(probe):
    """ما تراه الصفحة بنفسها: خُفيت (قُفلت الشاشة أو تُرك التطبيق)، وأُفلت القفل قبل النهاية."""
    _stub(probe)
    _section(probe, "wait")
    probe.locator("#wait-start").click()
    probe.wait_for_function("() => window.__sentinel")
    probe.evaluate("""() => {
        Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
        document.dispatchEvent(new Event('visibilitychange'));
        window.__sentinel.dispatchEvent(new Event('release'));
        delete document.visibilityState;
    }""")
    probe.locator("#wait-done").click()
    probe.locator("[data-wait='on']").click()
    found = _summary(probe)
    assert "خُفيت الصفحة" in found["wait"] and "أُفلت القفل قبل النهاية" in found["wait"], found["wait"]
    assert "hidden=true releasedEarly=true answer=on" in found["attempts"]
