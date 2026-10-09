/*
 * لوحة المفاتيح وشريط التبويب
 * ===========================
 * شريط التبويب السفلي ثابتٌ في أسفل الشاشة، ولوحة مفاتيح iOS تصعد فوقه حين يُركَّز حقل: يُكتب
 * `data-keyboard="open"` على <html> ما دام حقلٌ قابلٌ للكتابة مركَّزاً، فيختفي الشريط (`kb:hidden`)
 * ولا يركب لوحة المفاتيح. بالتركيز لا بمؤقّتٍ ولا بقياس الشاشة: `focusin`/`focusout` على المحتوى.
 */

import * as React from "react"

/* ما يفتح لوحة المفاتيح وحده: لا ملفّ ولا اختيار ولا زرّ (iOS يفتح لها منتقياً أو لا شيء). */
const EDITABLE = [
  "input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=reset]):not([type=range]):not([type=color])",
  "textarea",
  "[contenteditable]:not([contenteditable=false])",
].join(", ")

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
    // حقلٌ يُزال وهو مركَّز (انتقالٌ بعد ردّ خادم) لا يرسل focusout في WebKit: الانتقال يغلق العلم.
    window.addEventListener("hashchange", close)
    return () => {
      element.removeEventListener("focusin", onFocusIn)
      element.removeEventListener("focusout", onFocusOut)
      window.removeEventListener("hashchange", close)
      close()
    }
  }, [main])
}
