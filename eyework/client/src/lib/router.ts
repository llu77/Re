/*
 * التنقّل بالوسم (#/…)
 * ===================
 * كما في static/app.js: مستمعٌ واحد لـhashchange، و«رجوع» إلى الأب المنطقي لا إلى تاريخ
 * المتصفّح، و`replace` لا يترك أثراً في التاريخ. وبعد الدخول والتسجيل والخروج والحذف
 * انتقالٌ كامل (`reload`): لا يبقى في الذاكرة شيءٌ ممّا قبلها، وهكذا يعرض Safari حفظ
 * كلمة المرور.
 */

import * as React from "react"

const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((listener) => listener())
}

window.addEventListener("hashchange", emit)

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function currentHash(): string {
  return location.hash || "#/"
}

export function useHash(): string {
  return React.useSyncExternalStore(subscribe, currentHash)
}

export function go(hash: string, { replace = false }: { replace?: boolean } = {}) {
  if (replace) {
    history.replaceState(null, "", hash)
    emit()
  } else if (location.hash === hash) {
    emit()
  } else {
    location.hash = hash
  }
}

/** الوسم بلا استعلامه: `#/signup/name`. */
export function route(hash: string): string {
  return hash.split("?")[0]
}

/** انتقالٌ كامل إلى الجذر (أو وسمٍ فيه): وثيقةٌ جديدة بلا ذاكرة. */
export function reload(hash = "") {
  location.replace(`${import.meta.env.BASE_URL}${hash}`)
}
