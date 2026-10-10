import { afterEach, describe, expect, it } from "vitest"

import { REPEAT_MS, classify, guardRepeatPresses } from "@/lib/repeat-press"

describe("a repeated press on the large size", () => {
  const click = (timeStamp: number, target: EventTarget | null = null, isTrusted = true) => ({ isTrusted, timeStamp, target })

  it("counts the first press and one that comes after the pause", () => {
    expect(classify(null, click(1000))).toBe("count")
    expect(classify({ at: 1000, target: null }, click(1000 + REPEAT_MS))).toBe("count")
  })

  it("does not count the second tap of a double tap or a burst from a facial expression", () => {
    expect(classify({ at: 1000, target: null }, click(1120))).toBe("repeat")
    expect(classify({ at: 1000, target: null }, click(1000 + REPEAT_MS - 1))).toBe("repeat")
  })

  it("lets through what the page sends itself", () => {
    expect(classify({ at: 1000, target: null }, click(1001, null, false))).toBe("pass")
  })

  it("lets a label pass its press to its field (the photo picker)", () => {
    document.body.innerHTML = '<label for="photo-input" id="photo-pick"><span>اختر صورة المنتج</span></label><input id="photo-input" type="file">'
    const span = document.querySelector("#photo-pick span")!
    const input = document.querySelector("#photo-input")!
    expect(classify({ at: 1000, target: span }, click(1003, input))).toBe("pass")
    expect(classify({ at: 1000, target: document.body }, click(1003, input))).toBe("repeat")
  })
})

describe("the guard on the window", () => {
  let remove: (() => void) | null = null
  afterEach(() => {
    remove?.()
    remove = null
    document.body.innerHTML = ""
  })

  it("stops a repeated press before the page's own listeners", () => {
    document.body.innerHTML = '<button id="next">التالي</button>'
    const button = document.querySelector("#next")!
    let presses = 0
    button.addEventListener("click", () => {
      presses += 1
    })
    remove = guardRepeatPresses()
    // jsdom لا يصنع نقرةً موثوقة؛ والحارس لا يعدّ إلا الموثوقة، فتمرّ كلّها هنا.
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    expect(presses).toBe(2)
  })
})
