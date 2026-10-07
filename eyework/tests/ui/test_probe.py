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


def test_trusted_clicks_on_every_target_pass_the_gate(probe):
    _section(probe, "activation")
    for target in ("t44", "t56", "t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == "pass"
    rows = probe.locator("#checks-core tr").all_inner_texts()
    assert any("نجح" in row and "٤ من ٤" in row for row in rows), rows


def test_a_missed_target_fails_the_gate(probe):
    _section(probe, "activation")
    for target in ("t72", "t96"):
        probe.locator(f"[data-probe='{target}']").click()
    _section(probe, "verdict")
    assert probe.locator("#verdict").get_attribute("data-state") == "fail"


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
