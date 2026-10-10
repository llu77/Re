"""
عقد النظر على الواجهة الجديدة، بالحجمين
=======================================
القواعد نفسها (tests/ui/flow.py) بقيم كل حجمٍ من `html[data-size]`:

  • الكبير (gaze): الهدف شكلٌ ≥48 عرضاً ومساحة إصابةٍ ≥72 طولاً (`HIT`: الشكل و12px خفيّة فوقه وتحته)، والحقل
    ≥56، وبين مساحتي إصابةٍ ≥24، وحافّةٌ ≥16 من الشكل، ولا يقلّ البُعد بين مركزي هدفين عن 96 (`CENTRE`، درجتان
    من 45 سم)؛ اثنا عشر هدفاً على الأكثر (ثلاثةٌ منها شريط التنقّل الثابت)، ولا تمرير ولا قصّ (ولا ما يقصّه
    وعاؤه)، ولا هدفٌ تُغطّى مساحة إصابته، ولا نصٌّ يخرج من زرّه، ولا حركة؛ وكل هدفٍ زرٌّ أو رابطٌ أو حقل
    (`roles`): «الانتقال إلى العنصر» في تتبّع العين والرأس يقصد ما له سمة الزرّ. ونقاط الهبوط الخمس في مساحة
    الإصابة كلّها.
  • العادي (compact): أهدافٌ ≥40 وفجواتٌ ≥8 وحافّةٌ ≥16، والتمرير مسموح؛ وما يقع تحت شريط التبويب
    الثابت أو في فجوته قبل التمرير تحت الطيّة لا مجاورٌ له إن كان التمرير المتبقّي يرفعه فوق الشريط
    بالفجوة كاملة (وإلا فالتراكب حقيقيٌّ ويُرفض).

وقاعدتا الهبوط والأقرب إلى النظر كما هما: بعد كل ضغطة لا يقع تحت موضعها ما يعتمد
(`data-commit`) ولا ما يغيّر قيمة (`data-value`، خيارٌ راديوي)، وأقرب عنصرٍ مفعّل إليها
لا يعتمد شيئاً. والشاشة المفحوصة: الورقة المفتوحة إن وُجدت، وإلا المحتوى غير الخامل.
"""

from __future__ import annotations

import os
import time

#: مساحة إصابة الهدف: إطاره المرسوم ومعه `::after` الخفيّ (الحجم الكبير: 12px فوقه وتحته، globals.css)، مقصوصةً
#: بما يقصّها (العنصر نفسه إن أخفى ما يفيض منه، وأوعيته). باللمس لا مساحة خفيّة: الإطار نفسه.
HIT = """
(e) => {
    const r = e.getBoundingClientRect();
    let top = r.top, bottom = r.bottom, left = r.left, right = r.right;
    const after = getComputedStyle(e, '::after');
    if (after.content && after.content !== 'none' && after.position === 'absolute') {
        const n = (v) => (v === 'auto' ? 0 : parseFloat(v) || 0);
        top = Math.min(top, r.top + n(after.top));
        bottom = Math.max(bottom, r.bottom - n(after.bottom));
        left = Math.min(left, r.left + n(after.left));
        right = Math.max(right, r.right - n(after.right));
        for (let a = e; a && a !== document.body; a = a.parentElement) {
            const s = getComputedStyle(a);
            if (s.overflowX !== 'visible' || s.overflowY !== 'visible') {
                const b = a.getBoundingClientRect();
                top = Math.max(top, b.top); bottom = Math.min(bottom, b.bottom);
                left = Math.max(left, b.left); right = Math.min(right, b.right);
            }
            if (a.tagName === 'DIALOG') break;
        }
    }
    return { top, bottom, left, right, width: right - left, height: bottom - top };
}
"""

MOTION = """
() => document.documentElement.dataset.size !== 'gaze' ? [] : document.getAnimations()
    .filter((a) => a.playState === 'running')
    .map((a) => a.animationName || a.transitionProperty
         || (a.effect && a.effect.target ? a.effect.target.tagName.toLowerCase() : 'animation'))
"""

AUDIT = """
(hitSource) => {
    const hit = eval(hitSource);
    const gaze = document.documentElement.dataset.size === 'gaze';
    // الحجم الكبير: مساحة الإصابة 72 طولاً (شكلٌ 48 ومساحةٌ خفيّة)، والعرض 48 على الأقل، والحقل 56 (لا مساحة خفيّة له).
    const MIN = gaze ? 47.5 : 39.5, MIN_HIT = gaze ? 71.5 : 39.5, MIN_FIELD = gaze ? 55.5 : 39.5;
    const GAP = gaze ? 23.5 : 7.5, EDGE = 15.5;
    const root = document.querySelector('dialog[open]') || document.querySelector('[role=alert][class*=fixed]')
        || document.querySelector('[data-content]:not([inert])') || document.body;
    const visible = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]')
            && !e.closest('[inert]');
    };
    const SELECTOR = 'button, a[href], input:not([type=hidden]), textarea, select, [role=button], [role=option], [role=tab], [role=combobox], [role=radio]';
    const controls = [...root.querySelectorAll(SELECTOR)].filter(visible).filter((e) => !e.classList.contains('sr-only'));
    const drawn = controls.map((e) => [e, e.getBoundingClientRect()]);
    const rects = controls.map((e) => [e, hit(e)]);
    const name = (e) => e.id || e.textContent.trim().slice(0, 20);
    const field = (e) => e.matches('input, textarea, select');
    const small = rects.filter(([e, r]) => r.width < MIN || r.height < (field(e) ? MIN_FIELD : MIN_HIT))
        .map(([e, r]) => `${name(e)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    // الحجم العادي: الصفحة تمرّ، وشريط التبويب وزرّ «اسأل سيمبول» العائم ثابتان فوقها. ما يقع تحت أحدهما أو في
    // فجوته قبل التمرير ليس مجاوراً له إن كان التمرير المتبقّي يرفعه فوقه بالفجوة كاملة (يظهر فوقه بالتمرير:
    // `.pb-tab-launcher`)؛ وإلا فالتراكب حقيقيٌّ ويُرفض: صفحةٌ لا تمرّ، أو عنصرٌ لا يرتفع عنه مهما مُرّرت.
    const scroller = document.scrollingElement;
    const room = scroller.scrollHeight - innerHeight - scroller.scrollTop;
    const fixed = [document.querySelector('nav[aria-label="أقسام البوابة"]'), document.getElementById('nav-chat')]
        .filter((c) => c && getComputedStyle(c).position === 'fixed' && visible(c));
    const belowFold = (c, e, r) => {
        const top = c.getBoundingClientRect().top;
        return !c.contains(e) && r.bottom > top - GAP && r.bottom - room <= top - GAP;
    };
    const close = [];
    for (let i = 0; i < rects.length; i += 1) {
        for (let j = i + 1; j < rects.length; j += 1) {
            const [a, ra] = rects[i];
            const [b, rb] = rects[j];
            if (a.contains(b) || b.contains(a)) continue;
            if (fixed.some((c) => (c.contains(a) && belowFold(c, b, rb)) || (c.contains(b) && belowFold(c, a, ra)))) continue;
            const gap = Math.max(rb.left - ra.right, ra.left - rb.right, rb.top - ra.bottom, ra.top - rb.bottom);
            if (gap < GAP) close.push(`${name(a)} ↔ ${name(b)}: ${Math.round(gap)}`);
        }
    }
    const edge = drawn.filter(([, r]) => r.left < EDGE || innerWidth - r.right < EDGE).map(([e]) => name(e));
    const fonts = [...root.querySelectorAll('input, textarea')].filter(visible)
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 16).map((e) => e.id || e.name);
    const clipped = gaze ? [...root.querySelectorAll('h1, h2, h3, p, li, button, a[href], input, textarea, label, legend, dt, dd')].filter(visible)
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

#: الحجم الكبير وحده: ما لا تقيسه الأحجام والفجوات. النظر والرأس يختاران بأقرب عنصرٍ إلى موضع المؤشّر (والنظام
#: يقفز إليه بـ«الانتقال إلى العنصر»)، فالبُعد بين مراكز الأهداف هو ما يفصل بينها لا الفجوة بين حوافّها: 96px
#: درجتان من 45 سم على هاتفٍ بعرض 390؛ وما يغطّي جزءاً من هدفٍ يُضغط بدله؛ ونصٌّ يخرج من زرّه أو يُقصّ تحت شريطٍ
#: يُقرأ لغيره. والقفز في عناصر التحكّم المخصّصة يقصد ما له سمة الزرّ (مهندس Apple في منتدى المطوّرين، 2024)،
#: وWebKit لا يعطيها `role=radio|option|tab`: فهدف الحجم الكبير زرٌّ بلا دورٍ آخر، أو رابطٌ، أو حقل (`roles`).
CENTRE = 95.5

LAYOUT = r"""
([centre, hitSource]) => {
    const hit = eval(hitSource);
    if (document.documentElement.dataset.size !== 'gaze') return { occluded: [], spill: [], cut: [], centres: [], roles: [] };
    const root = document.querySelector('dialog[open]') || document.querySelector('[data-content]:not([inert])') || document.body;
    const SELECTOR = 'button, a[href], input:not([type=hidden]), textarea, select, [role=button], [role=option], [role=tab], [role=combobox], [role=radio]';
    const visible = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]')
            && !e.closest('[inert]') && !e.classList.contains('sr-only');
    };
    const name = (e) => e.id || e.getAttribute('aria-label') || e.textContent.trim().replace(/\s+/g, ' ').slice(0, 24);
    const all = [...root.querySelectorAll(SELECTOR)].filter(visible);
    const controls = all.filter((e) => !all.some((o) => o !== e && o.contains(e)));
    const enabled = controls.filter((e) => !e.disabled && e.getAttribute('aria-disabled') !== 'true');
    // ما فوق الهدف: نقاطٌ داخلية (لا زوايا مدوّرة) يجب أن يكون أعلى ما عندها الهدفَ نفسه أو ما فيه.
    const occluded = [];
    for (const e of enabled) {
        const r = hit(e);
        const covers = new Set();
        for (const [fx, fy] of [[0.5, 0.5], [0.25, 0.3], [0.75, 0.3], [0.25, 0.7], [0.75, 0.7]]) {
            const x = r.left + r.width * fx, y = r.top + r.height * fy;
            if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) continue;
            const top = document.elementFromPoint(x, y);
            if (top && top !== e && !e.contains(top) && !top.contains(e)) covers.add(name(top.closest(SELECTOR) || top) || top.tagName);
        }
        if (covers.size) occluded.push(`${name(e)} تحت ${[...covers].join('، ')}`);
    }
    // نصٌّ خارج زرّه (لا ما يُختصر بنقاطٍ عمداً).
    const spill = [];
    for (const e of controls) {
        if (e.matches('input, textarea, select')) continue;
        const r = e.getBoundingClientRect();
        const walker = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
        let node, worst = 0;
        while ((node = walker.nextNode())) {
            if (!node.textContent.trim() || getComputedStyle(node.parentElement).textOverflow === 'ellipsis') continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            for (const t of range.getClientRects()) worst = Math.max(worst, r.left - t.left, t.right - r.right, r.top - t.top, t.bottom - r.bottom);
        }
        if (worst > 1) spill.push(`${name(e)}: ${Math.round(worst)}px`);
    }
    // ما يقصّه وعاؤه (الشاشة لا تمرّ، فالمحتوى يُقصّ في حدوده) ولو بقي داخل الشاشة.
    const cut = [];
    const texts = [...root.querySelectorAll('h1, h2, h3, p, li, dt, dd, label, legend, button, a[href], input, textarea, select')]
        .filter(visible);
    for (const e of texts) {
        const r = e.getBoundingClientRect();
        for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
            const style = getComputedStyle(a);
            // الحوار المفتوح في الطبقة العليا: لا يقصّه ما وراءه، وحدّه هو.
            if (a.tagName !== 'DIALOG' && style.overflowY === 'visible' && style.overflowX === 'visible') continue;
            const b = a.getBoundingClientRect();
            if (r.bottom > b.bottom + 1 || r.top < b.top - 1 || r.left < b.left - 1 || r.right > b.right + 1) {
                cut.push(name(e) || e.tagName);
            }
            break;
        }
    }
    // البُعد بين مراكز الأهداف المفعّلة.
    const centres = [];
    for (let i = 0; i < enabled.length; i += 1) {
        for (let j = i + 1; j < enabled.length; j += 1) {
            const a = enabled[i].getBoundingClientRect(), b = enabled[j].getBoundingClientRect();
            const d = Math.hypot((a.left + a.right - b.left - b.right) / 2, (a.top + a.bottom - b.top - b.bottom) / 2);
            if (d < centre) centres.push(`${name(enabled[i])} ↔ ${name(enabled[j])}: ${Math.round(d)}`);
        }
    }
    // سمة الزرّ في WebKit: <button> بلا دورٍ يغلبه (وaria-pressed يبقيها)، أو role=button؛ والرابط والحقل كما
    // هما. وaria-haspopup يجعل الزرّ «زرّاً منبثقاً» بلا سمة الزرّ (buttonRoleType في WebKit).
    const roles = enabled.flatMap((e) => {
        const role = e.getAttribute('role');
        const popup = e.getAttribute('aria-haspopup');
        const found = [];
        if (role && role !== 'button' && !(e.matches('input, textarea, select') && role === 'combobox')) found.push(`role=${role}`);
        if (popup && popup !== 'false' && !e.matches('input, textarea, select')) found.push(`aria-haspopup=${popup}`);
        return found.map((what) => `${name(e)}: ${what}`);
    });
    return { occluded, spill, cut: [...new Set(cut)], centres, roles };
}
"""

LANDING = """
(points) => points.map(([x, y]) => {
    const element = document.elementFromPoint(x, y);
    const control = element && element.closest('button, a[href], input, textarea, select, [role=radio], [role=option]');
    if (!control) return null;
    const key = (e) => e.id || (e.dataset && e.dataset.key) || '';
    // الزرّ نفسه بعد الضغطة آمن — إلا أن يصير زرّ اعتمادٍ لم يكنه (React يعيد العقدة نفسها حين
    // يبدّل «التالي» بـ«احفظ» في الخانة نفسها، فيعتمد ثبات النظر ما لم يُقصد).
    // ...وكذلك اعتمادٌ صار اعتماداً آخر في العقدة نفسها («حُلّت» ثم «أغلقها رغم ذلك»): اسمه أو نصّه تغيّر.
    const became = control.hasAttribute('data-commit')
        && (!window.__activatedCommit || key(control) !== window.__activatedKey || control.textContent.trim() !== window.__activatedText);
    if (!became && (control === window.__activated || (key(control) && key(control) === window.__activatedKey))) return null;
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
        const became = nearest.hasAttribute('data-commit')
            && (!window.__activatedCommit || key(nearest) !== window.__activatedKey || nearest.textContent.trim() !== window.__activatedText);
        const same = !became && (nearest === window.__activated || (key(nearest) && key(nearest) === window.__activatedKey));
        return { name: name(nearest), distance: Math.round(distance(nearest)),
                 commit: !same && nearest.hasAttribute('data-commit') };
    });
}
"""


#: الحجم الكبير لا يحسب ضغطةً تأتي قبل 400ms من التي قبلها (client/src/lib/repeat-press.ts): «النقرتان» من
#: حركة وجه. والمستخدم بالنظر أو بالرأس لا يضغط أسرع من ذلك، فلا يضغط الاختبار أسرع منه (بهامش).
PRESS_GAP = 0.45


class Flow:
    def __init__(self, page) -> None:
        self.page = page
        self.audits: list[dict] = []
        self.landings: list[str] = []
        self.pressed = float("-inf")

    def pace(self) -> None:
        """
        في الحجم الكبير: ما بقي من مهلة الضغطة السابقة، كما يمضي بين ضغطتين بالنظر أو بالرأس. والمهلة من وصول الضغطة
        السابقة (`clicked`) لا من طلبها: Playwright ينتظر قبل النقر أن يثبت العنصر، فلو حُسبت من الطلب لجاءت الضغطة التالية
        أحياناً قبل 400ms من السابقة فأسقطها التطبيق («النقرتان»).
        """
        if self.page.evaluate("() => document.documentElement.dataset.size") == "gaze":
            wait = PRESS_GAP - (time.monotonic() - self.pressed)
            if wait > 0:
                self.page.wait_for_timeout(wait * 1000)

    def clicked(self) -> None:
        """وصلت الضغطة: منها تُحسب مهلة التالية."""
        self.pressed = time.monotonic()

    def screen(self, selector: str) -> None:
        self.page.wait_for_selector(selector)

    def until(self, predicate: str) -> None:
        self.page.wait_for_function(f"() => {predicate}")

    def fonts(self) -> None:
        self.page.evaluate("() => document.fonts.ready.then(() => true)")
        # وتنتهي حركات الظهور قبل القياس: حوارٌ يُكبَّر من 0.98 تقيس أزراره أصغر ممّا هي. المنتهية وحدها:
        # دوّارة «جارٍ…» بلا نهاية تنتظر طلبها لا الزمن، وانتظارها بلا حدّ يعلّق الاختبار بلا رسالة.
        self.page.evaluate("""() => Promise.all(document.getAnimations()
            .filter((a) => a.effect && a.effect.getComputedTiming().iterations !== Infinity)
            .map((a) => a.finished.catch(() => null))).then(() => true)""")

    def audit(self, label: str) -> dict:
        # «لا حركة» في الحجم الكبير: ما يتحرّك لحظة القياس يُعدّ قبل انتظار الحركات.
        motion = self.page.evaluate(MOTION)
        self.fonts()
        # للتطوير: لقطةٌ لكل تدقيقٍ في المجلّد الذي يسمّيه المتغيّر، بإطار الصفحة وحجمها.
        shots = os.environ.get("EYEWORK_AUDIT_SHOTS")
        if shots:
            frame = self.page.viewport_size or {"width": 0, "height": 0}
            size = self.page.evaluate("() => document.documentElement.dataset.size")
            os.makedirs(shots, exist_ok=True)
            self.page.screenshot(path=os.path.join(shots, f"{size}-{frame['width']}x{frame['height']}-{len(self.audits):02d}-{label}.png"))
        result = self.page.evaluate(AUDIT, HIT)
        result.update(self.page.evaluate(LAYOUT, [CENTRE, HIT]))
        result["label"] = label
        result["motion"] = motion
        self.audits.append(result)
        return result

    def press(self, selector: str, settle, label: str) -> None:
        """نقرةٌ ثم فحصُ ما تحت موضعها حين تستقرّ الحالة التالية."""
        locator = self.page.locator(selector).first
        locator.evaluate("(e) => { window.__activated = e; window.__activatedKey = e.id || e.dataset.key || '';"
                         " window.__activatedCommit = e.hasAttribute('data-commit');"
                         " window.__activatedText = e.textContent.trim(); }")
        # النقاط الخمس في مساحة الإصابة كلّها، والخفيّةُ منها (الحجم الكبير): النظر يضغط في أيّ موضعٍ منها.
        box = locator.evaluate(f"(e) => ({HIT})(e)")
        inset = 8
        points = [
            [(box["left"] + box["right"]) / 2, (box["top"] + box["bottom"]) / 2],
            [box["left"] + inset, box["top"] + inset],
            [box["right"] - inset, box["top"] + inset],
            [box["left"] + inset, box["bottom"] - inset],
            [box["right"] - inset, box["bottom"] - inset],
        ]
        self.pace()
        locator.click()
        self.clicked()
        settle()
        self.fonts()
        hazards = self.page.evaluate(LANDING, points)
        if hazards:
            self.landings.append(f"{label}: {sorted(set(hazards))}")
        nearest = self.page.evaluate(NEAREST, points)
        commits = sorted({f"{n['name']} على بعد {n['distance']}px" for n in nearest if n["commit"]})
        if commits:
            self.landings.append(f"{label}: أقرب عنصرٍ إلى النظر يعتمد — {commits}")

    def open_tools(self) -> None:
        """ورقة الأدوات: من «الأدوات» في الشريط أو السكّة، وفي الحجم الكبير على الهاتف من ورقة سيمبول (مكانها في
        الشريط لزرّه)."""
        if self.page.locator("#nav-tools").count():
            self.press("#nav-tools", lambda: self.screen("dialog[open] ul button"), "الأدوات")
            return
        self.press("#nav-chat", lambda: self.screen("dialog[open] >> text=الأدوات"), "سيمبول")
        self.press("dialog[open] >> text=الأدوات", lambda: self.screen("dialog[open] ul button"), "الأدوات")

    def ask_symbol(self, question: str, answered: str) -> None:
        """سؤالٌ مكتوب إلى سيمبول من زرّه، حتى يظهر في الورقة ما ينتظره الاختبار من جوابه."""
        gaze = self.page.evaluate("() => document.documentElement.dataset.size") == "gaze"
        if gaze:
            self.press("#nav-chat", lambda: self.screen("dialog[open] button"), "سيمبول")
            if self.page.locator("dialog[open] >> text=سؤالٌ جديد").count():
                self.press("dialog[open] >> text=سؤالٌ جديد", lambda: self.screen("dialog[open] >> text=اكتب سؤالك"), "سؤالٌ جديد")
            self.press("dialog[open] >> text=اكتب سؤالك", lambda: self.screen("dialog[open] textarea"), "اكتب سؤالك")
        else:
            self.press("#nav-chat", lambda: self.screen("dialog[open] textarea"), "اسأل سيمبول")
        self.page.fill("dialog[open] textarea", question)
        self.press("dialog[open] button[type='submit']",
                   lambda: self.until(f"document.querySelector('dialog[open]').textContent.includes({answered!r})"), "أرسل")

    def failures(self) -> list[str]:
        failures = []
        for audit in self.audits:
            for key in ("small", "close", "edge", "fonts", "clipped", "occluded", "spill", "cut", "centres", "roles"):
                if audit[key]:
                    failures.append(f"{audit['label']} {key}: {audit[key]}")
            if audit["gaze"] and audit["enabled"] > 12:
                failures.append(f"{audit['label']}: {audit['enabled']} أهداف مفعّلة")
            if audit["gaze"] and audit["vertical"]:
                failures.append(f"{audit['label']}: تمرير")
            if audit["gaze"] and audit["motion"]:
                failures.append(f"{audit['label']} motion: {audit['motion']}")
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
