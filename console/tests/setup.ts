import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

/**
 * jsdom بلا `matchMedia` ولا `ResizeObserver`، والشريط يحتاج الأول (هاتف أم
 * سطح مكتب) وRadix يحتاج الثاني. `setViewportWidth` يحدّد أيّهما يُختبر.
 */
let width = 1280
const listeners = new Set<() => void>()

export function setViewportWidth(next: number) {
  width = next
  listeners.forEach((listener) => listener())
}

function matches(query: string): boolean {
  const max = query.match(/max-width:\s*(\d+)px/)
  return max ? width <= Number(max[1]) : false
}

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: (query: string) => ({
    get matches() {
      return matches(query)
    },
    media: query,
    onchange: null,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
    addListener: (listener: () => void) => listeners.add(listener),
    removeListener: (listener: () => void) => listeners.delete(listener),
    dispatchEvent: () => false,
  }),
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, "ResizeObserver", { configurable: true, value: ResizeObserverStub })

afterEach(() => {
  cleanup()
  setViewportWidth(1280)
  document.cookie = "sidebar_state=; max-age=0; path=/"
  window.sessionStorage.clear()
  window.location.hash = ""
})
