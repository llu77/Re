"""
عقد التفاعل بالنظر — في متصفّحٍ حقيقي
======================================
كل شاشةٍ يمرّ بها المسار الكامل، عند كل إطار — مقاسات iPhone المؤقّتة، وإطار
الإجهاد، والحاسوب (conftest.py):

  • كل هدفٍ ≥ 72×72، وبين أيّ هدفين ≥ 24، وعن حافّتي الشاشة ≥ 16.
  • عشرة أهدافٍ مفعّلة على الأكثر.
  • لا تمرير في أيّ خطوة — عموديّاً ولا أفقياً.
  • خطّ الحقول ≥ 16px، فلا يكبّر iOS الصفحة عند التركيز.
  • لا مؤقّت، ولا طلب كاميرا، ولا مستمع مرورٍ أو ضغطٍ أو سحب.
  • كل طلبٍ إلى الأصل نفسه.
  • قاعدة الهبوط بعد كل نقرة، وأقرب عنصرٍ إلى النظر بعدها لا يعتمد شيئاً
    (انظر flow.py).
"""

from __future__ import annotations

import re

import pytest

from eyework.tests.ui.conftest import HANDHELD, VIEWPORTS
from eyework.tests.ui.flow import Flow

HOVER_OR_GESTURE = re.compile(r"^(pointer|mouse|touch|drag|wheel|contextmenu)")


@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=[f"{w}x{h}" for w, h in VIEWPORTS])
def test_every_screen_honours_the_gaze_contract(page_factory, server, width, height):
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    flow.run()

    failures = []
    for audit in flow.audits:
        for key in ("small", "close", "edge", "fonts", "clipped"):
            if audit[key]:
                failures.append(f"{audit['label']} {key}: {audit[key]}")
        if audit["enabled"] > 10:
            failures.append(f"{audit['label']}: {audit['enabled']} أهداف مفعّلة")
        if audit["vertical"] or audit["horizontal"]:
            failures.append(f"{audit['label']}: تمرير")
    assert not failures, "\n".join(failures)
    assert not page.errors, page.errors


@pytest.mark.parametrize(("width", "height"), HANDHELD, ids=[f"{w}x{h}" for w, h in HANDHELD])
def test_nothing_that_commits_lands_under_a_resting_gaze(page_factory, server, width, height):
    flow = Flow(page_factory(width, height), server["base"])
    flow.run()
    assert not flow.landings, "\n".join(flow.landings)


def test_no_timers_no_camera_no_hover_listeners_and_only_same_origin(page_factory, server):
    page = page_factory()
    Flow(page, server["base"]).run()
    log = page.evaluate("() => ({ timers: window.__eyework.timers, camera: window.__eyework.camera,"
                        " listeners: window.__eyework.listeners })")
    assert log["timers"] == []
    assert log["camera"] == 0
    assert not [t for t in log["listeners"] if HOVER_OR_GESTURE.match(t)]
    foreign = [url for _, url in page.requests if not url.startswith(server["base"])]
    assert not foreign, foreign


def test_the_confirming_control_is_far_from_the_one_that_opened_it(page_factory, server):
    """
    «نعم، اعتمد الحملة» على نصف ارتفاع الشاشة على الأقل من «متابعة للتأكيد»،
    وموضع «متابعة للتأكيد» في شاشة التأكيد لا يُضغط فيه شيء — ونظرةٌ باقية
    هناك، تتكرّر ست مرات، لا ترسل طلباً.
    """
    page = page_factory(390, 664)
    flow = Flow(page, server["base"])
    flow.to_review()
    initiator = page.locator("#review-continue").bounding_box()
    centre = (initiator["x"] + initiator["width"] / 2, initiator["y"] + initiator["height"] / 2)
    page.locator("#review-continue").click()
    flow.screen("confirm")
    commit = page.locator("#confirm-yes").bounding_box()
    distance = abs((commit["y"] + commit["height"] / 2) - centre[1])
    assert distance >= 0.5 * 664, distance

    under = page.evaluate(
        "([x, y]) => { const e = document.elementFromPoint(x, y);"
        " return e && e.closest('button, a, label, input') ? e.closest('button, a, label, input').id : null; }",
        list(centre))
    assert under is None, under

    before = len([r for r in page.requests if r[0] != "GET"])
    for _ in range(6):
        page.mouse.click(*centre)
    assert len([r for r in page.requests if r[0] != "GET"]) == before
    assert page.locator(".screen[data-screen='confirm']").is_visible()


def test_amount_words_follow_a_label_and_colon(page_factory, server):
    """الكلمات في موضع الرفع وحده: بعد العنوان والنقطتين مباشرةً، لا في وسط جملة."""
    page = page_factory()
    flow = Flow(page, server["base"])
    flow.to_review()
    assert page.locator("#review-budget").inner_text().startswith("الميزانية الإجمالية: ألفان وسبعمئة وخمسون ريالاً")
    assert page.locator("#review-days").inner_text().startswith("المدة: أربعة عشر يوماً")
    page.locator("#review-continue").click()
    flow.screen("confirm")
    restate = page.locator("#confirm-restate").inner_text()
    assert "الميزانية الإجمالية: ألفان وسبعمئة وخمسون ريالاً." in restate
    assert "المدة: أربعة عشر يوماً." in restate
    assert "لن يُنشر شيءٌ ولن يُدفع أيّ مبلغٍ تلقائياً" in restate


@pytest.mark.parametrize("path", ["/#/", "/probe/"])
def test_hidden_means_hidden(page_factory, server, path):
    """
    عنصرٌ بالسمة hidden لا يُعرض أبداً — ولا يعترض النظر.

    `.btn { display: inline-flex }` كان يغلب السمة، فيظهر زرٌّ «مخفيّ» فوق
    غيره ويأخذ الضغطة بدله.
    """
    page = page_factory(session=path != "/probe/")
    page.goto(server["base"] + path)
    page.wait_for_load_state("networkidle")
    shown = page.evaluate(
        "() => [...document.querySelectorAll('[hidden]')]"
        ".filter(e => getComputedStyle(e).display !== 'none').map(e => e.id || e.className)")
    assert shown == []


def test_a_phone_in_landscape_is_asked_to_rotate(page_factory, server):
    """في الوضع الأفقي لا يُضغط شيء: الشاشات مخفيّة وطلب التدوير ظاهر."""
    page = page_factory(844, 390)
    page.goto(server["base"] + "/#/")
    page.wait_for_selector(".screen[data-screen='home']:not([hidden])", state="attached")
    assert page.is_visible(".rotate")
    reachable = page.evaluate("""
        () => [...document.querySelectorAll('.screen:not([hidden]) button, .screen:not([hidden]) a[href]')]
            .filter((e) => {
                const r = e.getBoundingClientRect();
                const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                return hit && e.contains(hit);
            }).map((e) => e.id || e.textContent.trim())
    """)
    assert reachable == []

    page.set_viewport_size({"width": 390, "height": 664})
    assert not page.is_visible(".rotate")
    assert page.is_visible("#home-new")
