"""
صفحة فحص الإدخال
================
الصفحة التي يقوم عليها قرار البناء كلّه. تُثبت هنا ثلاثة أشياء: لا ترسل شيئاً
ولا تخزّن شيئاً، وتسجّل ما تقيسه، وتحكم بنجاحٍ أو فشلٍ صحيحين.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def probe(page_factory, server):
    page = page_factory(390, 664, session=False)
    page.goto(server["base"] + "/probe/")
    page.wait_for_selector(".sec[data-section='env']:not([hidden])")
    page.wait_for_load_state("networkidle")
    return page


def _section(page, name):
    for _ in range(12):
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


@pytest.mark.parametrize(("width", "height"), [(375, 635), (390, 664)])
def test_every_section_fits_without_scrolling(page_factory, server, width, height):
    page = page_factory(width, height, session=False)
    page.goto(server["base"] + "/probe/")
    page.wait_for_selector(".sec[data-section='env']:not([hidden])")
    count = page.locator(".sec").count()
    for index in range(count):
        overflow = page.evaluate(
            "() => { const s = document.querySelector('.sec:not([hidden])');"
            " return [...s.children].some(e => e.getBoundingClientRect().bottom > s.getBoundingClientRect().bottom + 1)"
            " || document.scrollingElement.scrollHeight > innerHeight + 1; }")
        assert not overflow, page.locator(".sec:not([hidden])").get_attribute("data-section")
        if index < count - 1:
            page.locator("#next").click()
