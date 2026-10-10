/*
 * تقسيم النصّ الطويل في الحجم الكبير: عند الجمل، وما طال من جملةٍ (رسالةٌ ملصوقة بلا علامات) عند الكلمات،
 * فلا تبقى صفحةٌ أطول من حدّها فتُقصّ تحت الشاشة.
 */
import { describe, expect, it } from "vitest"

import { paginate } from "@/components/ui/paged-text"

describe("paginate", () => {
  it("keeps sentences together while they fit", () => {
    expect(paginate("الطابعة لا تعمل. جرّبوا إعادة التشغيل. ثم أخبرونا.", 40)).toEqual(["الطابعة لا تعمل. جرّبوا إعادة التشغيل.", "ثم أخبرونا."])
  })

  it("cuts a long unpunctuated message at words, never beyond the page", () => {
    const text = Array.from({ length: 120 }, (_, i) => `كلمة${i}`).join(" ")
    const pages = paginate(text, 100)
    expect(pages.length).toBeGreaterThan(5)
    for (const page of pages) expect([...page].length).toBeLessThanOrEqual(100)
    expect(pages.join(" ").split(/\s+/)).toEqual(text.split(/\s+/))
  })

  it("cuts a single word longer than the page by characters", () => {
    const pages = paginate("x".repeat(250), 100)
    expect(pages.map((p) => p.length)).toEqual([100, 100, 50])
  })
})
