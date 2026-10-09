/*
 * الجلسة: الإقلاع وروابط التطبيق
 * ==============================
 * لا شاشة تفاعلية قبل خيارات الخادم (/api/choices)، ثم صاحب الجلسة (/api/me) إلا في
 * التسجيل والتفعيل حيث لا جلسة بعد. ورابط تسجيلٍ أو تفعيلٍ فُتح يُقرأ إلى الذاكرة ويُمحى
 * من شريط العنوان قبل أيّ شيء.
 */

import { api, detail } from "@/lib/api"
import { route as routeOf } from "@/lib/router"
import { newSignup } from "@/lib/signup"
import { setState, type Choices, type Me } from "@/lib/store"

/** رابط تسجيلٍ أو تفعيلٍ فُتح: يُقرأ إلى الذاكرة ويُمحى من شريط العنوان قبل أيّ شيء. */
export function captureLinks() {
  const hash = location.hash
  if (hash.startsWith("#signup=")) {
    const params = new URLSearchParams(hash.slice(1))
    setState({ signup: newSignup(params.get("signup") || "") })
    history.replaceState(null, "", `${location.pathname}${location.search}#/signup`)
  } else if (hash.startsWith("#activate=")) {
    const params = new URLSearchParams(hash.slice(1))
    setState({ activation: { token: params.get("activate") || "", username: params.get("u") || "" } })
    history.replaceState(null, "", `${location.pathname}${location.search}#/activate`)
  }
}

export async function boot() {
  setState({ startupError: null })
  const choices = await api<Choices>("GET", "/api/choices")
  if (choices.status !== 200 || !choices.data) {
    setState({ startupError: detail(choices) })
    return
  }
  setState({ choices: choices.data })
  const path = routeOf(location.hash || "#/")
  // التسجيل والتفعيل قبل الجلسة: لا يُسأل عن صاحبٍ لم يُنشأ حسابه بعد.
  if (path.startsWith("#/signup") || path.startsWith("#/activate")) {
    setState({ me: null, booted: true })
    return
  }
  const me = await api<Me>("GET", "/api/me", { quiet: true })
  if (me.status === 200 && me.data) {
    setState({ me: me.data, booted: true })
  } else if (me.status === 401) {
    setState({ me: null, booted: true })
  } else {
    setState({ startupError: detail(me) })
  }
}

/** يعيد قراءة صاحب الجلسة بعد تغييرٍ في حسابه (الحجم، الموافقة). */
export async function refreshMe(): Promise<Me | null> {
  const me = await api<Me>("GET", "/api/me")
  if (me.status === 200 && me.data) setState({ me: me.data })
  return me.status === 200 ? me.data : null
}
