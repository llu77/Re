/*
 * لوحة المفاتيح وشريط التبويب
 * ===========================
 * شريط التبويب السفلي ثابتٌ في أسفل الشاشة، ولوحة مفاتيح iOS تصعد فوقه حين يُركَّز حقل: يُكتب
 * `data-keyboard="open"` على <html> ما دام حقلٌ قابلٌ للكتابة مركَّزاً، فيختفي الشريط (`kb:hidden`)
 * ولا يركب لوحة المفاتيح. بالتركيز لا بمؤقّتٍ ولا بقياس الشاشة: `focusin`/`focusout` على المحتوى.
 */

import * as React from "react"

const EDITABLE = "input, textarea, select, [contenteditable]"

function editable(target: EventTarget | null): boolean {
  return target instanceof Element && target.matches(EDITABLE) && !(target as HTMLInputElement).readOnly
}

export function useKeyboardFlag(main: React.RefObject<HTMLElement>) {
  React.useEffect(() => {
    const element = main.current
    if (!element) return undefined
    const open = () => {
      document.documentElement.dataset.keyboard = "open"
    }
    const close = () => {
      delete document.documentElement.dataset.keyboard
    }
    const onFocusIn = (event: FocusEvent) => {
      if (editable(event.target)) open()
    }
    const onFocusOut = (event: FocusEvent) => {
      if (editable(event.target) && !editable(event.relatedTarget)) close()
    }
    element.addEventListener("focusin", onFocusIn)
    element.addEventListener("focusout", onFocusOut)
    return () => {
      element.removeEventListener("focusin", onFocusIn)
      element.removeEventListener("focusout", onFocusOut)
      close()
    }
  }, [main])
}
