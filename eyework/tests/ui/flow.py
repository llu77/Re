"""
مسار المستخدم الكامل، وفحوص كل حالةٍ فيه
=========================================
يقود الواجهة كما يقودها المستخدم — نقرةً نقرة — من الرئيسية إلى حملةٍ
جاهزة، ويفحص كل شاشةٍ يمرّ بها، ويفحص بعد كل نقرةٍ ما يقع تحت موضعها في
الحالة التالية.

**قاعدة الهبوط.** النظر الباقي على موضعٍ بعد تغيّر الشاشة قد يضغط ما صار
تحته. فبعد كل نقرة: ما تحت مركز الهدف وأركانه الأربعة (بإزاحة 8px) في
الحالة التالية يجب ألّا يكون زرّاً يعتمد شيئاً (`data-commit`) ولا عنصر قيمة
(خيار أو خطوة) — إلا العنصر نفسه في مكانه، لأن أثره ظاهرٌ ويُعكس.

**والأقرب إلى النظر.** «الانتقال إلى العنصر» (Snap to Item، مفعّلٌ افتراضاً في
تتبّع العين) ينقل المؤشر إلى أقرب عنصرٍ إلى موضع النظر، ولا تنشر Apple مسافته.
فأقرب عنصرٍ مفعّل إلى مركز الهدف في الحالة التالية — أيّاً كان بُعده — لا يعتمد
شيئاً.
"""

from __future__ import annotations

import io

from PIL import Image

STEPPERS = ("budget-up", "budget-down", "days-up", "days-down",
            *(f"signup-{unit}-{way}" for unit in ("year", "month", "day") for way in ("up", "down")))

AUDIT = """
() => {
    const screen = document.querySelector('.screen:not([hidden])');
    const visible = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[hidden]');
    };
    const controls = [...screen.querySelectorAll('button, a[href], label.btn, input:not(.visually-hidden), textarea')]
        .filter(visible);
    const rects = controls.map((e) => [e, e.getBoundingClientRect()]);
    const small = rects.filter(([, r]) => r.width < 71.5 || r.height < 71.5)
        .map(([e, r]) => `${e.id || e.textContent.trim().slice(0, 20)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    const close = [];
    for (let i = 0; i < rects.length; i += 1) {
        for (let j = i + 1; j < rects.length; j += 1) {
            const [a, ra] = rects[i];
            const [b, rb] = rects[j];
            const gap = Math.max(rb.left - ra.right, ra.left - rb.right, rb.top - ra.bottom, ra.top - rb.bottom);
            if (gap < 23.5) {
                close.push(`${a.id || a.textContent.trim().slice(0, 15)} ↔ ${b.id || b.textContent.trim().slice(0, 15)}: ${Math.round(gap)}`);
            }
        }
    }
    const edge = rects.filter(([, r]) => r.left < 15.5 || innerWidth - r.right < 15.5)
        .map(([e]) => e.id || e.textContent.trim().slice(0, 20));
    const content = screen.querySelector('.content');
    // ما يقصّه حدّ المحتوى (overflow: hidden) لا يُرى ولا يُمرَّر إليه: قصٌّ لا تمرير.
    const box = content.getBoundingClientRect();
    const clipped = [...content.querySelectorAll('*')].filter(visible)
        .filter((e) => !e.closest('.alert') && !e.classList.contains('visually-hidden'))
        .filter((e) => { const r = e.getBoundingClientRect(); return r.bottom > box.bottom + 1 || r.top < box.top - 1; })
        .map((e) => e.id || e.className || e.tagName);
    const fonts = [...screen.querySelectorAll('input, textarea')].filter(visible)
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 16).map((e) => e.id);
    return {
        screen: screen.dataset.screen,
        small, close, edge, fonts, clipped,
        enabled: controls.filter((e) => !e.disabled).length,
        vertical: content.scrollHeight > content.clientHeight + 1 || document.scrollingElement.scrollHeight > innerHeight + 1,
        horizontal: document.scrollingElement.scrollWidth > innerWidth + 1,
    };
}
"""

LANDING = """
(points) => points.map(([x, y]) => {
    const element = document.elementFromPoint(x, y);
    const control = element && element.closest('button, a[href], label.btn, input, textarea');
    if (!control) return null;
    const key = (e) => e.id || (e.dataset && e.dataset.key) || '';
    // العنصر نفسه في مكانه — أو خيارٌ أُعيد بناؤه بالمفتاح نفسه — أثره ظاهرٌ ويُعكس.
    if (control === window.__activated || (key(control) && key(control) === window.__activatedKey)) return null;
    if (control.disabled || getComputedStyle(control).visibility === 'hidden') return null;
    const valueControl = control.classList.contains('chip') || %s.includes(control.id);
    if (control.hasAttribute('data-commit') || valueControl) {
        return control.id || control.textContent.trim();
    }
    return null;
}).filter(Boolean)
""" % list(STEPPERS)


#: أقرب عنصرٍ مفعّلٍ إلى نقطة الضغط في الحالة التالية: إليه ينقل «الانتقال إلى
#: العنصر» (Snap to Item) مؤشرَ نظرٍ باقٍ. Apple لا تنشر مسافة الانتقال، فلا عتبة:
#: الأقرب أيّاً كان بُعده لا يعتمد شيئاً.
NEAREST = """
([x, y]) => {
    const screen = document.querySelector('.screen:not([hidden])');
    const usable = (e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !e.closest('[hidden]') && !e.disabled
            && e.getAttribute('aria-disabled') !== 'true' && getComputedStyle(e).visibility !== 'hidden';
    };
    const distance = (r) => Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom));
    const controls = [...screen.querySelectorAll('button, a[href], label.btn, input, textarea')].filter(usable);
    if (!controls.length) return null;
    const nearest = controls.reduce((a, b) => distance(a.getBoundingClientRect()) <= distance(b.getBoundingClientRect()) ? a : b);
    const key = (e) => e.id || (e.dataset && e.dataset.key) || '';
    if (nearest === window.__activated || (key(nearest) && key(nearest) === window.__activatedKey)) return null;
    return nearest.hasAttribute('data-commit')
        ? `${nearest.id || nearest.textContent.trim()} على بعد ${Math.round(distance(nearest.getBoundingClientRect()))}px`
        : null;
}
"""


def sample_photo() -> bytes:
    buffer = io.BytesIO()
    Image.effect_noise((1200, 900), 40).convert("RGB").save(buffer, "JPEG")
    return buffer.getvalue()


class Flow:
    def __init__(self, page, base: str) -> None:
        self.page = page
        self.base = base
        self.audits: list[dict] = []
        self.landings: list[str] = []

    # ── الانتظار ────────────────────────────────────────────────────────
    def screen(self, name: str) -> None:
        self.page.wait_for_selector(f".screen[data-screen='{name}']:not([hidden])")

    def until(self, predicate: str) -> None:
        # دالّةٌ لا نصّ: CSP تمنع eval، وهذا ما يجب.
        self.page.wait_for_function(f"() => {predicate}")

    # ── الفحوص ──────────────────────────────────────────────────────────
    def audit(self, label: str) -> dict:
        result = self.page.evaluate(AUDIT)
        result["label"] = label
        self.audits.append(result)
        return result

    def press(self, selector: str, settle, label: str) -> None:
        """نقرةٌ ثم فحصُ ما تحت موضعها حين تستقرّ الحالة التالية."""
        locator = self.page.locator(selector)
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
        hazards = self.page.evaluate(LANDING, points)
        if hazards:
            self.landings.append(f"{label}: {sorted(set(hazards))}")
        nearest = self.page.evaluate(NEAREST, points[0])
        if nearest:
            self.landings.append(f"{label}: أقرب عنصرٍ إلى النظر يعتمد — {nearest}")

    # ── المسار ──────────────────────────────────────────────────────────
    def run(self) -> None:
        self.to_review()
        self.finish()

    def to_review(self) -> None:
        """من الرئيسية إلى شاشة المراجعة، عبر كل شاشةٍ قبلها."""
        page = self.page
        page.goto(self.base + "/#/")
        self.screen("home")
        self.until("document.querySelector('#home-new') !== null")
        self.audit("home")

        self.press("#home-new", lambda: self.screen("photo"), "حملة جديدة")
        self.audit("photo-empty")
        page.set_input_files("#photo-input", files=[{"name": "p.jpg", "mimeType": "image/jpeg",
                                                     "buffer": sample_photo()}])
        self.until("!document.querySelector('#photo-generate').disabled")
        self.audit("photo-draft")

        self.press("#photo-generate", lambda: self.until(
            "!document.querySelector('#proposal-copy').hidden"), "اكتب لي العنوان والوصف")
        self.audit("proposal")

        self.press("#proposal-start", lambda: self.screen("edit"), "اطلب تعديلاً")
        self.audit("edit")
        self.press("#edit-chips .chip >> nth=0", lambda: None, "خيار تعديل")
        self.press("#edit-chips .chip >> nth=2", lambda: None, "خيار تعديل")
        self.press("#edit-note", lambda: self.screen("note"), "ملاحظة نصية")
        self.audit("note")
        page.fill("#note-text", "اذكر أنه مصنوعٌ من الجلد الطبيعي")
        self.press("#note-save", lambda: self.screen("edit"), "احفظ الملاحظة")
        self.press("#edit-submit", lambda: self.until(
            "!document.querySelector('#proposal-copy').hidden"
            " && document.querySelector('#proposal-status').textContent.includes('2 من')"), "اطلب نسخة جديدة")
        self.audit("proposal-v2")

        self.press("#proposal-start", lambda: self.screen("edit"), "اطلب تعديلاً")
        self.press("#edit-restore", lambda: self.until(
            "!document.querySelector('#proposal-copy').hidden"
            " && document.querySelector('#proposal-status').textContent.includes('1 من')"), "النسخة السابقة")
        self.press("#proposal-start", lambda: self.screen("edit"), "اطلب تعديلاً")
        self.until("document.querySelector('#edit-restore').textContent.includes('الأحدث')")
        self.press("#edit-restore", lambda: self.until(
            "!document.querySelector('#proposal-copy').hidden"
            " && document.querySelector('#proposal-status').textContent.includes('2 من')"), "النسخة الأحدث")

        self.press("#proposal-end", lambda: self.until(
            "document.querySelector('#proposal-end').textContent.includes('الميزانية')"), "أوافق على النص")
        self.audit("approved")
        self.press("#proposal-start", lambda: self.until(
            "document.querySelector('#proposal-end').textContent.includes('أوافق')"), "تراجع عن الموافقة")
        self.press("#proposal-end", lambda: self.until(
            "document.querySelector('#proposal-end').textContent.includes('الميزانية')"), "أوافق على النص")

        self.press("#proposal-end", lambda: self.screen("budget"), "تابع إلى الميزانية")
        self.audit("budget-empty")
        self.press("#budget-presets .chip >> nth=4", lambda: self.until(
            "!document.querySelector('#budget-next').disabled"), "مبلغ جاهز")
        self.press("#budget-up", lambda: self.until(
            "document.querySelector('#budget-value').textContent.includes('2,750')"), "أكثر")
        self.audit("budget")
        self.press("#budget-next", lambda: self.screen("days"), "التالي: عدد الأيام")
        self.audit("days-empty")
        self.press("#days-presets .chip >> nth=3", lambda: self.until(
            "!document.querySelector('#days-next').disabled"), "مدّة جاهزة")
        self.audit("days")
        self.press("#days-next", lambda: self.screen("review"), "التالي: المراجعة")
        self.audit("review")

    def finish(self) -> None:
        """من المراجعة إلى حملةٍ جاهزة، ثم السحب والرجوع والرئيسية."""
        self.press("#review-continue", lambda: self.screen("confirm"), "متابعة للتأكيد")
        self.audit("confirm")
        self.press("#confirm-back", lambda: self.screen("review"), "رجوع دون اعتماد")
        self.press("#review-continue", lambda: self.screen("confirm"), "متابعة للتأكيد")
        self.press("#confirm-yes", lambda: self.screen("ready"), "نعم، اعتمد الحملة")
        self.audit("ready")

        self.press(".screen[data-screen='ready'] [data-cancel]", lambda: self.screen("cancel"), "اسحب الحملة")
        self.audit("withdraw")
        self.press("#cancel-back", lambda: self.screen("ready"), "رجوع دون إلغاء")
        self.press(".screen[data-screen='ready'] [data-home]", lambda: self.screen("home"), "الرئيسية")
        self.until("document.querySelectorAll('#home-list li').length === 1")
        self.audit("home-one")
