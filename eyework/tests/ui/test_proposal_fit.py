"""
أطول نصٍّ مقبول يُقرأ كاملاً قبل الموافقة
=========================================
النصّ المقترح يُوافَق عليه كما يُرى، فلا يُقصّ منه حرف في أيّ إطار. أطول ما
تقبله قواعد النصّ — بتنبيهٍ وملاحظة، وبفقراتٍ تُهدر أسطرها — يتّسع للشاشة؛
وإن لم يتّسع معه شيءٌ فالملاحظة تُعرض وحدها أولاً ثم النصّ كاملاً.
"""

from __future__ import annotations

import pytest

from eyework.copy_rules import DESCRIPTION_MAX, NOTE_TO_USER_MAX, TITLE_MAX, check_copy, check_note_to_user
from eyework.tests.fakes import ok
from eyework.tests.ui.conftest import VIEWPORTS
from eyework.tests.ui.flow import Flow, sample_photo

WORDS = "حقيبة يد من الجلد الطبيعي بسعر مناسب وتصميم أنيق وصحية للظهر وتتسع لكل الأغراض اليومية "
TITLE = (WORDS * 2)[:TITLE_MAX].strip()
# أربع فقرات: ثلاثٌ أطول من سطرٍ بقليل تُهدر كلٌّ منها سطراً، والرابعة تأخذ الباقي.
SHORT = (WORDS * 2)[:34].strip()
WASTEFUL = "\n".join([SHORT, SHORT, SHORT, (WORDS * 4)[:DESCRIPTION_MAX - 3 * (len(SHORT) + 1)].strip()])
EVEN = "\n".join([(WORDS * 2)[:59].strip()] * 4)
NOTE = ("أبرزتُ الخامة واللون والحزام، ولم أذكر المقاس ولا السعة لأنهما لا يظهران في الصورة بوضوح. " * 2)
NOTE = NOTE[:NOTE_TO_USER_MAX].strip()


@pytest.mark.parametrize("description", [EVEN, WASTEFUL], ids=["even", "wasteful"])
@pytest.mark.parametrize(("width", "height"), VIEWPORTS, ids=[f"{w}x{h}" for w, h in VIEWPORTS])
def test_the_longest_valid_copy_is_never_clipped(page_factory, server, description, width, height):
    check = check_copy(TITLE, description)
    assert check.ok and check.warnings and check_note_to_user(NOTE)[0] == NOTE, (check.errors, len(description))
    server["writer"].queue(ok(TITLE, description, NOTE))
    page = page_factory(width, height)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/new")
    flow.screen("photo")
    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    flow.press("#photo-generate", lambda: flow.until("!document.querySelector('#proposal-copy').hidden"),
               "اكتب لي العنوان والوصف")

    alert = page.locator(".screen[data-screen='proposal'] .alert")
    if alert.is_visible():
        # لم يتّسع للملاحظة: تُقرأ وحدها أولاً، كاملةً.
        assert NOTE in alert.inner_text()
        flow.audit("note-first")
        flow.press(".screen[data-screen='proposal'] [data-ack]", lambda: flow.until(
            "document.querySelector('.screen[data-screen=proposal] .alert').hidden"), "حسناً")
        assert alert.is_hidden()
    else:
        assert NOTE in page.inner_text("#proposal-note")
    audit = flow.audit("proposal")
    assert not audit["clipped"] and not audit["vertical"], audit
    assert page.inner_text("#proposal-description").replace("\n", "") == description.replace("\n", "")
    assert "تحقّق من هذه العبارة" in page.inner_text("#proposal-warnings")
    assert not flow.landings, flow.landings
    assert not page.errors, page.errors


def _candidates() -> list[str]:
    """أوصافٌ مقبولة بثلاث فقراتٍ قصيرة متساوية وفقرةٍ رابعة بالباقي، بكل طولٍ للقصيرة."""
    found = []
    for size in range(12, 70):
        short = (WORDS * 2)[:size].strip()
        rest = DESCRIPTION_MAX - 3 * (len(short) + 1)
        description = "\n".join([short, short, short, (WORDS * 4)[:rest].strip()])
        if check_copy(TITLE, description).ok:
            found.append(description)
    return found


SEARCH = """
(candidates) => {
    const box = document.querySelector('#proposal-description');
    let worst = null, height = -1;
    for (const text of candidates) {
        box.textContent = text;
        const h = box.getBoundingClientRect().height;
        if (h > height) { height = h; worst = text; }
    }
    return worst;
}
"""


RENDER = """([text, zoom]) => {
    document.documentElement.style.fontSize = zoom + '%';
    state.campaign.copy.description = text;
    state.noteShownFor = null;
    renderProposal();
}"""


@pytest.mark.parametrize("zoom", [100, 115])
def test_the_worst_wrapping_copy_is_never_clipped(page_factory, server, zoom):
    """
    في أصغر إطار، بالفقرات التي تُهدر أكثر الأسطر (يُبحث عنها في الصفحة نفسها).
    عند 115% — تكبير نصّ Safari — لا تتّسع الملاحظة معه: تُعرض وحدها أولاً، ثم
    النصّ كاملاً. وما فوق ذلك في أصغر إطارٍ لا تتّسع له أيّ شاشة (الأهداف تكبر
    مع النصّ)، وهو حدٌّ معلن لا يختبره هذا الملف.
    """
    server["writer"].queue(ok(TITLE, EVEN, NOTE))
    page = page_factory(375, 635)
    flow = Flow(page, server["base"])
    page.goto(server["base"] + "/#/new")
    flow.screen("photo")
    page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                 "buffer": sample_photo()}])
    flow.until("!document.querySelector('#photo-generate').disabled")
    page.click("#photo-generate")
    flow.until("!document.querySelector('#proposal-copy').hidden")
    if page.locator(".screen[data-screen='proposal'] .alert").is_visible():
        page.click(".screen[data-screen='proposal'] [data-ack]")

    worst = page.evaluate(SEARCH, _candidates())
    page.evaluate(RENDER, [worst, zoom])
    alert = page.locator(".screen[data-screen='proposal'] .alert")
    if zoom > 100:
        assert alert.is_visible() and NOTE in alert.inner_text()
        page.click(".screen[data-screen='proposal'] [data-ack]")
        page.evaluate("() => renderProposal()")
        assert alert.is_hidden()
    audit = flow.audit(f"proposal-worst-{zoom}")
    assert not audit["clipped"] and not audit["vertical"], audit
    assert page.inner_text("#proposal-description").replace("\n", "") == worst.replace("\n", "")
    assert not page.errors, page.errors
