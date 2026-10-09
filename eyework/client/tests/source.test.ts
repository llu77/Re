/*
 * ما لا يدخل المكوّنات المكيَّفة من الأصل: محاكاة الطلبات بمؤقّت، والتخزين في المتصفّح،
 * والفتح بالحوم، والصور من خارج الأصل. فحصٌ للنصّ نفسه، فلا يعود شيءٌ منها بنسخٍ جديد.
 */
import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const SRC = join(__dirname, "..", "src")

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? files(join(dir, entry.name)) : [join(dir, entry.name)],
  )
}

const sources = files(SRC).filter((file) => /\.(ts|tsx|css)$/.test(file))

describe("the adapted components", () => {
  it.each([
    ["timers", /\b(setTimeout|setInterval|requestIdleCallback)\s*\(/],
    ["browser storage", /\b(localStorage|sessionStorage|indexedDB)\b/],
    [
      "hover and pointer handlers",
      /\bon(Mouse|Pointer)(Enter|Leave|Over|Out|Move)\b|\bwhile(Hover|Tap)\b|\bonHover(Start|End)\b|\bonTap\b|addEventListener\(\s*["'](pointer|mouse)/,
    ],
    ["external URLs", /https?:\/\//],
  ])("hold no %s", (_, pattern) => {
    const hits = sources.filter((file) => pattern.test(readFileSync(file, "utf8").replace(/^\s*(\/\/|\*).*$/gm, "")))
    expect(hits).toEqual([])
  })
})
