/*
 * ما تشترك فيه القوائم المنسدلة (Select وCombobox وDropdownNavigation)
 * =================================================================
 * تُغلق بالضغط خارجها: مستمع `click` على المستند وهي مفتوحة وحدها، لا pointerdown ولا
 * mousedown — النظر والإصبع يرسلان click وحده (اختبار المصدر يرفض مستمعي المؤشّر).
 */

import * as React from "react"

export function useOutsideClick(open: boolean, ref: React.RefObject<HTMLElement>, onOutside: () => void) {
  const callback = React.useRef(onOutside)
  callback.current = onOutside
  React.useEffect(() => {
    if (!open) return
    function onClick(event: MouseEvent) {
      const root = ref.current
      if (root && event.target instanceof Node && !root.contains(event.target)) callback.current()
    }
    document.addEventListener("click", onClick)
    return () => document.removeEventListener("click", onClick)
  }, [open, ref])
}

/** المفتاح التالي في قائمة، دائرياً. */
export function step(index: number, delta: number, length: number): number {
  if (length === 0) return -1
  if (index < 0) return delta > 0 ? 0 : length - 1
  return (index + delta + length) % length
}
