// قاعدة الهبوط والأقرب إلى النظر — نظيرا LANDING وNEAREST في eyework/tests/ui/flow.py:
// بعد الضغط واستقرار الحالة التالية، ما تحت مركز الهدف وأركانه الأربعة (بإزاحة 8px) لا
// يعتمد شيئاً (data-commit) ولا يغيّر قيمة (data-value) — إلا الهدف نفسه في مكانه؛ وأقرب
// هدفٍ مفعّلٍ إلى كل نقطةٍ لا يعتمد شيئاً (Snap to Item في تتبّع العين).
(points) => {
  const SELECTOR = 'button, a[href], input:not([type="hidden"]), textarea, select, [role="option"], [role="tab"], [role="radio"]'
  const modal = document.querySelector("dialog[open]")
  const scope = modal || document.body
  const same = (e) => e === window.__activated || (window.__activatedKey && (e.id || e.textContent.trim()) === window.__activatedKey)
  const usable = (e) => {
    const r = e.getBoundingClientRect()
    const s = getComputedStyle(e)
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && !e.closest("[hidden], [inert]") && !e.disabled
      && e.getAttribute("aria-disabled") !== "true"
  }
  const name = (e) => (e.getAttribute("aria-label") || e.innerText || e.id || e.tagName).trim().replace(/\s+/g, " ").slice(0, 40)
  const under = points.map(([x, y]) => {
    const hit = document.elementFromPoint(x, y)
    const control = hit && hit.closest(SELECTOR)
    if (!control || !usable(control) || same(control)) return null
    if (control.hasAttribute("data-commit") || control.hasAttribute("data-value")) return name(control)
    return null
  }).filter(Boolean)
  const controls = [...scope.querySelectorAll(SELECTOR)].filter(usable)
  const nearest = points.map(([x, y]) => {
    if (!controls.length) return null
    const distance = (e) => {
      const r = e.getBoundingClientRect()
      return Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom))
    }
    const n = controls.reduce((a, b) => (distance(a) <= distance(b) ? a : b))
    return { name: name(n), distance: Math.round(distance(n)), commit: !same(n) && n.hasAttribute("data-commit"), same: same(n) }
  }).filter(Boolean)
  return { under: [...new Set(under)], nearest }
}
