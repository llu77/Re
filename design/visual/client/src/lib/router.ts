/*
 * التنقّل بالوسم (#/…) كما في app.js: «رجوع» يذهب إلى الأب المنطقي لا إلى تاريخ
 * المتصفّح، و`replace` لا يترك أثراً في التاريخ. مستمعٌ واحد لـhashchange.
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
