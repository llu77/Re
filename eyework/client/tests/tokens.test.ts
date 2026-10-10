/*
 * رموز الحجم كما في globals.css: اللمس 40/44·8، وتتبّع العين 48·12، والحقول 16px على الأقل،
 * والحدود شعرة. تُقرأ من الملفّ نفسه فلا يصغر هدفٌ عن حدّ Apple بنسخٍ غير مقصود.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const css = readFileSync(join(__dirname, "..", "src", "styles", "globals.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "")

/** كتل الملفّ كلّها بترتيبها، وهل كلٌّ منها داخل @media. */
function blocks(): { selectors: string[]; body: string; inMedia: boolean }[] {
  const out: { selectors: string[]; body: string; inMedia: boolean }[] = []
  const stack: ("media" | "group")[] = []
  let i = 0
  for (;;) {
    const open = css.indexOf("{", i)
    const close = css.indexOf("}", i)
    if (open === -1 && close === -1) break
    if (open !== -1 && (close === -1 || open < close)) {
      const head = (css.slice(i, open).split(";").pop() ?? "").trim()
      if (head.startsWith("@")) {
        stack.push(head.startsWith("@media") ? "media" : "group")
        i = open + 1
        continue
      }
      const end = css.indexOf("}", open)
      out.push({ selectors: head.split(",").map((part) => part.trim()), body: css.slice(open + 1, end), inMedia: stack.includes("media") })
      i = end + 1
    } else {
      stack.pop()
      i = close + 1
    }
  }
  return out
}

const SIZE_TOKEN = /^--(ctl|ctl-lg|row|tg|tg-min|edge|sec|pad|icon|tab|bar|side|fs-[\w-]+|lh-[\w-]+)$/

/** كل كتل المحدّد بترتيبها (الأخيرة تغلب). ما وُضع منها داخل @media لا يُدمج، ويُرفض إن غيّر حجماً:
 *  الألوان قد تتغيّر بالتباين (prefers-contrast)، أمّا الأحجام فلا تتغيّر بالإطار. */
function block(selector: string): Record<string, string> {
  const merged: Record<string, string> = {}
  const own = blocks().filter((b) => b.selectors.includes(selector))
  if (!own.length) throw new Error(`لا كتلة لـ${selector}`)
  for (const b of own) {
    const tokens = [...b.body.matchAll(/(--[\w-]+):\s*([^;]+);/g)]
    if (b.inMedia) {
      const sized = tokens.filter((token) => SIZE_TOKEN.test(token[1])).map((token) => token[1])
      if (sized.length) throw new Error(`${selector} داخل @media يغيّر ${sized.join(", ")}: الأحجام لا تتغيّر بالإطار`)
      continue
    }
    for (const token of tokens) merged[token[1]] = token[2].trim()
  }
  return merged
}

const rem = (value: string) => Number.parseFloat(value) * 16

describe("the size tokens", () => {
  const compact = block(':root[data-size="compact"]')
  const gaze = block(':root[data-size="gaze"]')
  const root = block(":root")

  it("keep the touch targets at 40 and the primary at 44, with 8 between them", () => {
    expect(rem(compact["--ctl"])).toBe(40)
    expect(rem(compact["--ctl-lg"])).toBe(44)
    expect(rem(compact["--row"])).toBe(44)
    expect(rem(compact["--tg"])).toBe(8)
    expect(rem(compact["--edge"])).toBe(16)
  })

  it("keep the gaze targets at 56 with 40 between them, so two centres are at least 96 apart (2° at 45 cm)", () => {
    expect(rem(gaze["--ctl"])).toBe(56)
    expect(rem(gaze["--ctl-lg"])).toBe(56)
    expect(rem(gaze["--row"])).toBe(56)
    expect(rem(gaze["--tg"])).toBe(40)
    expect(rem(gaze["--ctl"]) + rem(gaze["--tg"])).toBeGreaterThanOrEqual(96)
    // آخر صفٍّ فوق شريط التبويب: نصف الهدف والفاصل ونصف البند.
    expect(rem(gaze["--ctl"]) / 2 + rem(gaze["--sec"]) + rem(gaze["--bar"]) / 2).toBeGreaterThanOrEqual(96)
    expect(rem(gaze["--tg-min"])).toBe(12)
    expect(rem(gaze["--edge"])).toBe(16)
  })

  it("never let a field's text drop under 16px (iOS zooms otherwise), nor the body under 15", () => {
    expect(rem(compact["--fs-input"])).toBeGreaterThanOrEqual(16)
    expect(rem(gaze["--fs-input"])).toBeGreaterThanOrEqual(16)
    expect(rem(compact["--fs-body"])).toBeGreaterThanOrEqual(15)
    expect(rem(gaze["--fs-body"])).toBeGreaterThanOrEqual(17)
  })

  it("draw every control with a hairline and the focus ring in the primary colour", () => {
    expect(root["--line"]).toBe("1px")
    expect(root["--ring"]).toBe(root["--primary"])
  })

  it("size the bars for the bottom tab bar and the sidebar", () => {
    expect(rem(compact["--tab"])).toBe(60)
    expect(rem(gaze["--tab"])).toBe(64)
    expect(rem(compact["--bar"])).toBe(44)
    expect(rem(gaze["--bar"])).toBe(56)
    expect(rem(compact["--side"])).toBe(240)
    expect(rem(gaze["--side"])).toBe(192)
  })

  it("keep the icons, the section gaps and the card padding at the planned sizes", () => {
    expect(rem(compact["--icon"])).toBe(18)
    expect(rem(gaze["--icon"])).toBe(20)
    expect(rem(compact["--sec"])).toBe(20)
    expect(rem(gaze["--sec"])).toBe(40)
    expect(rem(compact["--pad"])).toBe(14)
    expect(rem(compact["--fs-small"])).toBe(13)
    expect(rem(gaze["--fs-small"])).toBe(15)
  })
})
