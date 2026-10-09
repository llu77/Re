/*
 * رموز الحجم كما في globals.css: اللمس 40/44·8، وتتبّع العين 48·12، والحقول 16px على الأقل،
 * والحدود شعرة. تُقرأ من الملفّ نفسه فلا يصغر هدفٌ عن حدّ Apple بنسخٍ غير مقصود.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const css = readFileSync(join(__dirname, "..", "src", "styles", "globals.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "")

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector)
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start))
  return Object.fromEntries([...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]))
}

const rem = (value: string) => Number.parseFloat(value) * 16

describe("the size tokens", () => {
  const compact = block(':root[data-size="compact"]')
  const gaze = block(':root[data-size="gaze"]')
  const root = block(":root {")

  it("keep the touch targets at 40 and the primary at 44, with 8 between them", () => {
    expect(rem(compact["--ctl"])).toBe(40)
    expect(rem(compact["--ctl-lg"])).toBe(44)
    expect(rem(compact["--row"])).toBe(44)
    expect(rem(compact["--tg"])).toBe(8)
    expect(rem(compact["--edge"])).toBe(16)
  })

  it("keep the gaze targets at 48 (Apple's 44pt and four more) with 12 between them", () => {
    expect(rem(gaze["--ctl"])).toBe(48)
    expect(rem(gaze["--ctl-lg"])).toBe(48)
    expect(rem(gaze["--row"])).toBe(48)
    expect(rem(gaze["--tg"])).toBe(12)
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
    expect(rem(compact["--side"])).toBe(240)
    expect(rem(gaze["--side"])).toBe(192)
  })
})
