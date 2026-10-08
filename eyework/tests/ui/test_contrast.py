"""
«زيادة التباين» وأزرار الجزأين
==============================
مع «زيادة التباين» في iOS تغمق الحدود والنصّ الثانوي وتعرض حدود الأزرار، ولا
يتغيّر حجم هدفٍ ولا تمرّر شاشة. والزرّ المؤلَّف من جزأين يُصاب كلّه: ما تحت المؤشر
هو الزرّ لا جزؤه.
"""

from __future__ import annotations

import pytest

from eyework.tests.conftest import create_campaign
from eyework.tests.ui.conftest import PHONES, STRESS
from eyework.tests.ui.flow import Flow
from eyework.tests.ui.test_portals import _user_id

#: أصغر إطارين للهاتف، وإطار الإجهاد: الحدّ الأعرض يُضيّق ما داخل الزرّ.
SMALLEST = [*PHONES[:2], STRESS]


def _luminance(rgb: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(part) for part in rgb.removeprefix("rgb(").removesuffix(")").split(",")[:3])
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(foreground: str, background: str = "rgb(255, 255, 255)") -> float:
    a, b = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@pytest.mark.parametrize(("width", "height"), SMALLEST, ids=[f"{w}x{h}" for w, h in SMALLEST])
def test_increase_contrast_darkens_lines_and_text_and_keeps_every_target(page_factory, server, width, height):
    page = page_factory(width, height)
    page.emulate_media(contrast="more")
    flow = Flow(page, server["base"])
    flow.run()
    failures = [f"{a['label']}: {k}" for a in flow.audits for k in ("small", "close", "edge", "clipped") if a[k]]
    failures += [f"{a['label']}: تمرير" for a in flow.audits if a["vertical"] or a["horizontal"]]
    assert not failures, failures
    style = page.evaluate("""() => {
        const button = document.querySelector('.screen:not([hidden]) .btn');
        const css = getComputedStyle(document.documentElement);
        const probe = document.createElement('p');
        probe.style.color = 'var(--ink-soft)';
        document.body.append(probe);
        const soft = getComputedStyle(probe).color;
        probe.style.color = 'var(--line)';
        const line = getComputedStyle(probe).color;
        probe.remove();
        return { border: getComputedStyle(button).borderTopWidth, soft, line,
                 box: [button.getBoundingClientRect().width, button.getBoundingClientRect().height] };
    }""")
    assert style["border"] == "3px"
    assert min(style["box"]) >= 71.5
    assert _contrast(style["soft"]) >= 7
    assert _contrast(style["line"]) >= 3


def test_without_increase_contrast_nothing_changes(page_factory, server):
    page = page_factory()
    page.emulate_media(contrast="no-preference")
    page.goto(server["base"] + "/#/")
    Flow(page, server["base"]).screen("home")
    assert page.evaluate("() => getComputedStyle(document.querySelector('#home-account')).borderTopWidth") == "2px"


def test_a_two_part_row_button_is_hit_as_one(page_factory, server, owner, app):
    create_campaign(app, _user_id(owner))
    page = page_factory()
    page.goto(server["base"] + "/#/")
    flow = Flow(page, server["base"])
    flow.until("document.querySelectorAll('#home-list li').length === 1")
    hit = page.evaluate("""() => {
        const status = document.querySelector('#home-list .row-status');
        const r = status.getBoundingClientRect();
        const element = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return [element.tagName, element === status.closest('button')];
    }""")
    assert hit == ["BUTTON", True]
