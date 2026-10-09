"""
عقد النظر على الواجهة الجديدة، بالحجمين
=======================================
القواعد نفسها (tests/ui/flow.py) بقيم كل حجمٍ من `html[data-size]`:

  • الكبير (gaze): أهدافٌ ≥48 (حدّ Apple 44pt وأربعة احتياطاً) وفجواتٌ ≥12 وحافّةٌ ≥16، اثنا عشر
    هدفاً على الأكثر (أربعةٌ منها شريط التنقّل الثابت)، ولا تمرير ولا قصّ، ولا حركة.
  • العادي (compact): أهدافٌ ≥40 وفجواتٌ ≥8 وحافّةٌ ≥16، والتمرير مسموح؛ وما يقع تحت شريط التبويب
    الثابت قبل التمرير تحت الطيّة لا مجاورٌ له (وإن لم تمرّ الصفحة فالتراكب حقيقيٌّ ويُرفض).

وقاعدتا الهبوط والأقرب إلى النظر كما هما: بعد كل ضغطة لا يقع تحت موضعها ما يعتمد
(`data-commit`) ولا ما يغيّر قيمة (`data-value`، خيارٌ راديوي)، وأقرب عنصرٍ مفعّل إليها
لا يعتمد شيئاً. والشاشة المفحوصة: الورقة المفتوحة إن وُجدت، وإلا المحتوى غير الخامل.
"""

from __future__ import annotations

AUDIT = """
() => {
    const gaze = document.documentElement.dataset.size === 'gaze';
    const MIN = gaze ? 47.5 : 39.5, GAP = gaze ? 11.5 : 7.5, EDGE = 15.5;
    const root = document.querySelector('dialog[open]') || document.querySelector('[role=alert][class*=fixed]')
        || document.querySelector('[data-content]:not([inert])') || document.body;
    const visible = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]')
            && !e.closest('[inert]');
    };
    const SELECTOR = 'button, a[href], input:not([type=hidden]), textarea, select, [role=button], [role=option], [role=tab], [role=combobox], [role=radio]';
    const controls = [...root.querySelectorAll(SELECTOR)].filter(visible).filter((e) => !e.classList.contains('sr-only'));
    const rects = controls.map((e) => [e, e.getBoundingClientRect()]);
    const name = (e) => e.id || e.textContent.trim().slice(0, 20);
    const small = rects.filter(([, r]) => r.width < MIN || r.height < MIN)
        .map(([e, r]) => `${name(e)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    // الحجم العادي: الصفحة تمرّ وشريط التبويب ثابتٌ فوقها، فما يقع تحته قبل التمرير تحت الطيّة لا
    // مجاورٌ له (يظهر فوقه بالتمرير: `.pb-tab`). وإن لم تمرّ الصفحة فالتراكب حقيقي ويُرفض.
    const scroller = document.scrollingElement;
    const bar = document.querySelector('nav[aria-label="أقسام البوابة"]');
    const barRect = bar && getComputedStyle(bar).position === 'fixed' && scroller.scrollHeight > innerHeight + 1
        ? bar.getBoundingClientRect() : null;
    const belowFold = (e, r) => barRect !== null && !bar.contains(e) && r.bottom > barRect.top;
    const close = [];
    for (let i = 0; i < rects.length; i += 1) {
        for (let j = i + 1; j < rects.length; j += 1) {
            const [a, ra] = rects[i];
            const [b, rb] = rects[j];
            if (a.contains(b) || b.contains(a)) continue;
            if (barRect && ((bar.contains(a) && belowFold(b, rb)) || (bar.contains(b) && belowFold(a, ra)))) continue;
            const gap = Math.max(rb.left - ra.right, ra.left - rb.right, rb.top - ra.bottom, ra.top - rb.bottom);
            if (gap < GAP) close.push(`${name(a)} ↔ ${name(b)}: ${Math.round(gap)}`);
        }
    }
    const edge = rects.filter(([, r]) => r.left < EDGE || innerWidth - r.right < EDGE).map(([e]) => name(e));
    const fonts = [...root.querySelectorAll('input, textarea')].filter(visible)
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 16).map((e) => e.id || e.name);
    const clipped = gaze ? [...root.querySelectorAll('h1, p, li, button, a[href], input, textarea, dd')].filter(visible)
        .filter((e) => { const r = e.getBoundingClientRect(); return r.bottom > innerHeight + 1 || r.top < -1; })
        .map((e) => name(e) || e.tagName) : [];
    return {
        gaze, small, close, edge, fonts, clipped,
        enabled: controls.filter((e) => !e.disabled && e.getAttribute('aria-disabled') !== 'true').length,
        vertical: scroller.scrollHeight > innerHeight + 1,
        horizontal: scroller.scrollWidth > innerWidth + 1,
    };
}
"""

LANDING = """
(points) => points.map(([x, y]) => {
    const element = document.elementFromPoint(x, y);
    const control = element && element.closest('button, a[href], input, textarea, select, [role=radio], [role=option]');
    if (!control) return null;
    const key = (e) => e.id || (e.dataset && e.dataset.key) || '';
    if (control === window.__activated || (key(control) && key(control) === window.__activatedKey)) return null;
    if (control.disabled || getComputedStyle(control).visibility === 'hidden') return null;
    const value = control.hasAttribute('data-value') || control.getAttribute('role') === 'radio' || control.classList.contains('chip');
    if (control.hasAttribute('data-commit') || value) return control.id || control.textContent.trim();
    return null;
}).filter(Boolean)
"""

NEAREST = """
(points) => {
    const root = document.querySelector('dialog[open]') || document.querySelector('[data-content]:not([inert])') || document.body;
    const usable = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !e.closest('[hidden]') && !e.closest('[inert]') && !e.disabled
            && e.getAttribute('aria-disabled') !== 'true' && getComputedStyle(e).visibility !== 'hidden'
            && !e.classList.contains('sr-only');
    };
    const controls = [...document.querySelectorAll('button, a[href], input, textarea, select, [role=radio]')]
        .filter(usable).filter((e) => root.contains(e) || e.closest('[role=alert]'));
    if (!controls.length) return [];
    const key = (e) => e.id || (e.dataset && e.dataset.key) || '';
    const name = (e) => e.id || e.textContent.trim();
    return points.map(([x, y]) => {
        const distance = (e) => {
            const r = e.getBoundingClientRect();
            return Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom));
        };
        const nearest = controls.reduce((a, b) => distance(a) <= distance(b) ? a : b);
        const same = nearest === window.__activated || (key(nearest) && key(nearest) === window.__activatedKey);
        return { name: name(nearest), distance: Math.round(distance(nearest)),
                 commit: !same && nearest.hasAttribute('data-commit') };
    });
}
"""


class Flow:
    def __init__(self, page) -> None:
        self.page = page
        self.audits: list[dict] = []
        self.landings: list[str] = []

    def screen(self, selector: str) -> None:
        self.page.wait_for_selector(selector)

    def until(self, predicate: str) -> None:
        self.page.wait_for_function(f"() => {predicate}")

    def fonts(self) -> None:
        self.page.evaluate("() => document.fonts.ready.then(() => true)")

    def audit(self, label: str) -> dict:
        self.fonts()
        result = self.page.evaluate(AUDIT)
        result["label"] = label
        self.audits.append(result)
        return result

    def press(self, selector: str, settle, label: str) -> None:
        """نقرةٌ ثم فحصُ ما تحت موضعها حين تستقرّ الحالة التالية."""
        locator = self.page.locator(selector).first
        box = locator.bounding_box()
        locator.evaluate("(e) => { window.__activated = e; window.__activatedKey = e.id || e.dataset.key || ''; }")
        inset = 8
        points = [
            [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
            [box["x"] + inset, box["y"] + inset],
            [box["x"] + box["width"] - inset, box["y"] + inset],
            [box["x"] + inset, box["y"] + box["height"] - inset],
            [box["x"] + box["width"] - inset, box["y"] + box["height"] - inset],
        ]
        locator.click()
        settle()
        self.fonts()
        hazards = self.page.evaluate(LANDING, points)
        if hazards:
            self.landings.append(f"{label}: {sorted(set(hazards))}")
        nearest = self.page.evaluate(NEAREST, points)
        commits = sorted({f"{n['name']} على بعد {n['distance']}px" for n in nearest if n["commit"]})
        if commits:
            self.landings.append(f"{label}: أقرب عنصرٍ إلى النظر يعتمد — {commits}")

    def failures(self) -> list[str]:
        failures = []
        for audit in self.audits:
            for key in ("small", "close", "edge", "fonts", "clipped"):
                if audit[key]:
                    failures.append(f"{audit['label']} {key}: {audit[key]}")
            if audit["gaze"] and audit["enabled"] > 12:
                failures.append(f"{audit['label']}: {audit['enabled']} أهداف مفعّلة")
            if audit["gaze"] and audit["vertical"]:
                failures.append(f"{audit['label']}: تمرير")
            if audit["horizontal"]:
                failures.append(f"{audit['label']}: تمرير أفقي")
        return failures

    def gaze_safe(self) -> None:
        """لا مؤقّت من شيفرة التطبيق، ولا مستمع حومٍ أو إيماءة، ولا مخالفة لسياسة المحتوى."""
        log = self.page.evaluate("() => window.__eyework")
        assert log["timers"] == [], log["timers"]
        hover = [t for t in log["listeners"] if t in ("mouseover", "mouseenter", "mousemove", "pointerover", "pointerenter",
                                                     "pointermove", "touchstart", "touchmove", "wheel", "dragstart")]
        assert not hover, hover
        assert log["csp"] == [], log["csp"]
