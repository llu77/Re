// قياس الأهداف والمسافات في الحالة الظاهرة — نظير AUDIT في eyework/tests/ui/flow.py
// للواجهة الجديدة: الحجم من <html data-size>، والهدف كل ما يُضغط أو يُكتب فيه، وما خارج
// <dialog> المفتوح خاملٌ فلا يُعدّ.
(rules) => {
  const modal = document.querySelector("dialog[open]")
  const scope = modal || document.body
  const SELECTOR = 'button, a[href], input:not([type="hidden"]), textarea, select, [role="option"], [role="tab"], [role="radio"]'
  const visible = (e) => {
    const r = e.getBoundingClientRect()
    // ‎sr-only (رابط «تخطَّ إلى المحتوى» قبل أن يُركَّز) مربّعٌ 1×1 لا يُرى ولا يُصاب.
    if (r.width <= 1 || r.height <= 1) return false
    const style = getComputedStyle(e)
    if (style.visibility === "hidden" || style.display === "none") return false
    if (e.closest("[hidden], [inert]")) return false
    return true
  }
  const name = (e) =>
    (e.getAttribute("aria-label") || e.innerText || e.value || e.id || e.getAttribute("role") || e.tagName).trim().replace(/\s+/g, " ").slice(0, 40)
  const kind = (e) => (e.hasAttribute("data-commit") ? "commit" : e.hasAttribute("data-value") ? "value" : "safe")
  // ما يغطّيه غيره (حقلٌ تحت قائمةٍ منسدلة مفتوحة) لا يُصاب، فلا يُعدّ جاراً لما فوقه.
  // وما خارج الشاشة لا يُفحص هكذا: في الحجم العادي تمرّ إليه الصفحة.
  const covered = (e) => {
    const r = e.getBoundingClientRect()
    const x = r.left + r.width / 2
    const y = r.top + r.height / 2
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false
    const hit = document.elementFromPoint(x, y)
    return !!hit && !e.contains(hit) && !hit.contains(e)
  }
  // زرّ الأدوات في الحجم العادي يطفو فوق الصفحة وهي تمرّ: لا يُقاس جاراً لما تحته.
  const floating = (e) => rules.floatingFab && e.matches("button[aria-haspopup=dialog]")
  // الرأس لاصقٌ في الحجم العادي: صفحةٌ مُرِّرت تمرّ تحته، فما دخل تحته من المحتوى ليس جاراً له.
  const header = !modal && scrollY > 0 ? document.querySelector("body > #root header") : null
  const headerBottom = header ? header.getBoundingClientRect().bottom : -Infinity
  const underHeader = (e) => !header.contains(e) && e.getBoundingClientRect().top < headerBottom
  const controls = [...scope.querySelectorAll(SELECTOR)].filter(visible)
    .filter((e) => !covered(e) && !floating(e) && !(header && underHeader(e)))
  const fab = [...document.querySelectorAll("button[aria-haspopup=dialog]")].find(visible)
  const targets = controls.map((e) => {
    const r = e.getBoundingClientRect()
    return { e, name: name(e), kind: kind(e), disabled: !!(e.disabled || e.getAttribute("aria-disabled") === "true"),
             x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10, r }
  })
  const small = targets.filter((t) => t.r.width < rules.min - 0.5 || t.r.height < rules.min - 0.5)
    .map((t) => `${t.name} ${Math.round(t.r.width)}x${Math.round(t.r.height)}`)
  const close = []
  let minGap = Infinity
  for (let i = 0; i < targets.length; i += 1) {
    for (let j = i + 1; j < targets.length; j += 1) {
      const a = targets[i].r
      const b = targets[j].r
      // عنصرٌ داخل آخر (حقلٌ وزرّه) ليس جارين.
      if (targets[i].e.contains(targets[j].e) || targets[j].e.contains(targets[i].e)) continue
      const gap = Math.max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom)
      if (gap < minGap) minGap = gap
      if (gap < rules.gap - 0.5) close.push(`${targets[i].name} ↔ ${targets[j].name}: ${Math.round(gap * 10) / 10}`)
    }
  }
  const edge = targets.filter((t) => t.r.left < rules.edge - 0.5 || innerWidth - t.r.right < rules.edge - 0.5)
    .map((t) => `${t.name} (${Math.round(t.r.left)}, ${Math.round(innerWidth - t.r.right)})`)
  const fonts = targets.filter((t) => ["INPUT", "TEXTAREA", "SELECT"].includes(t.e.tagName))
    .filter((t) => parseFloat(getComputedStyle(t.e).fontSize) < 16).map((t) => t.name)
  const offscreen = targets.filter((t) => t.r.bottom > innerHeight + 0.5 || t.r.top < -0.5).map((t) => t.name)
  // ما يقصّه حدٌّ مخفي (overflow) داخل المحتوى: نصٌّ أو هدفٌ لا يُرى كلّه ولا يُمرَّر إليه.
  const clipped = []
  for (const e of scope.querySelectorAll("main *, dialog[open] *")) {
    if (!visible(e) || e.children.length > 0 && !e.matches(SELECTOR)) continue
    const r = e.getBoundingClientRect()
    let p = e.parentElement
    while (p && p !== document.body) {
      const s = getComputedStyle(p)
      if (s.overflowY === "hidden" || s.overflowX === "hidden") {
        const box = p.getBoundingClientRect()
        if (r.bottom > box.bottom + 1 || r.top < box.top - 1) { clipped.push((e.innerText || e.tagName).trim().slice(0, 30)); break }
      }
      p = p.parentElement
    }
  }
  const underFab = fab && !modal
    ? targets.filter((t) => t.e !== fab).filter((t) => {
        const f = fab.getBoundingClientRect()
        return !(t.r.right <= f.left || t.r.left >= f.right || t.r.bottom <= f.top || t.r.top >= f.bottom)
      }).map((t) => t.name)
    : []
  return {
    size: document.documentElement.dataset.size,
    viewport: [innerWidth, innerHeight],
    count: targets.length,
    enabled: targets.filter((t) => !t.disabled).length,
    minTarget: targets.length ? Math.min(...targets.map((t) => Math.min(t.r.width, t.r.height))) : null,
    minGap: Number.isFinite(minGap) ? Math.round(minGap * 10) / 10 : null,
    small, close, edge, fonts, offscreen, clipped: [...new Set(clipped)], underFab,
    vertical: document.scrollingElement.scrollHeight > innerHeight + 1,
    horizontal: document.scrollingElement.scrollWidth > innerWidth + 1,
    targets: targets.map(({ name, kind, disabled, x, y, w, h }) => ({ name, kind, disabled, x, y, w, h })),
  }
}
