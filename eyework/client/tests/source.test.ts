/*
 * ما لا يدخل شيفرة الواجهة: المؤقّتات، والتخزين في المتصفّح، ومستمعو الحوم والمؤشّر،
 * والعناوين الخارجية. فحصٌ للنصّ نفسه، فلا يعود شيءٌ منها بنسخٍ جديد. ويُستثنى من
 * المؤقّتات ما يُعلَّق بـ«مسموح» مع سببه في السطر نفسه (لا شيء اليوم).
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

function code(file: string): string {
  // بلا التعليقات: ما يُشرح فيها ليس استدعاءً.
  return readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")
}

describe("the client's source", () => {
  it.each([
    ["timers", /\b(setTimeout|setInterval|requestIdleCallback)\s*\(/],
    ["browser storage", /\b(localStorage|sessionStorage|indexedDB)\b/],
    [
      "hover and pointer handlers",
      /\bon(Mouse|Pointer)(Enter|Leave|Over|Out|Move)\b|\bwhile(Hover|Tap)\b|\bonHover(Start|End)\b|\bonTap\b|addEventListener\(\s*["'](pointer|mouse)/,
    ],
    ["external URLs", /https?:\/\/(?!127\.0\.0\.1|localhost)/],
    ["work left for later", /\b(TODO|FIXME|XXX|HACK)\b/],
    // الإطارات tablet/lg/xl وحدها: sm و md و2xl لا تعني شيئاً هنا فلا تُكتب بصمت.
    ["breakpoints outside the three screens", /\b(sm|md|2xl):/],
    // حدّ كل عنصر تحكّم شعرة (var(--line)): لا border-2.
    ["two-pixel borders or rings", /\bborder(-[tbxyse])?-(?:2\b|\[)|\bring-[2-9]\b|\bdivide-[xy]-2\b/],
    // لا مكتبة حركةٍ ولا إيماءاتٍ ولا <style> محقون: الورقة والحوار على <dialog> الأصلي.
    ["motion, gesture or portal libraries", /["'](@radix-ui\/|framer-motion|motion\/react|motion["']|@use-gesture|react-spring|@headlessui|vaul|cmdk)/],
    // `hov:` وحده: لونٌ تحت فأرةٍ في الحجم العادي، لا تحت النظر.
    ["hover variants", /\bhover:|\[&[^\]]*:hover\]|:hover\b/],
  ])("holds no %s", (_, pattern) => {
    const hits = sources.filter((file) => pattern.test(code(file))).map((file) => file.slice(SRC.length + 1))
    expect(hits).toEqual([])
  })

  it("calls fetch in one place only", () => {
    const hits = sources.filter((file) => /\bfetch\s*\(/.test(code(file))).map((file) => file.slice(SRC.length + 1))
    expect(hits).toEqual(["lib/api.ts"])
  })
})
