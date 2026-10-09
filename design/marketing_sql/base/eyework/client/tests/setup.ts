import { afterEach, vi } from "vitest"
import { cleanup } from "@testing-library/react"

/*
 * jsdom بلا `matchMedia`، وframer-motion يسأله عن «تقليل الحركة». `setReducedMotion`
 * يحدّد الجواب.
 */
let reduced = false

export function setReducedMotion(next: boolean) {
  reduced = next
}

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: (query: string) => ({
    get matches() {
      return query.includes("prefers-reduced-motion") ? reduced : false
    },
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
})

afterEach(() => {
  cleanup()
  reduced = false
  vi.restoreAllMocks()
})
