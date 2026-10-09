/*
 * إبقاء الشاشة مضاءة أثناء الكتابة
 * ================================
 * منقولٌ من static/app.js: الكتابة قد تستغرق حتى 200 ثانية. الطلب الأول داخل الضغطة (يحتاج
 * تفعيلاً من المستخدم)، وWebKit يُسقط القفل حين تُخفى الصفحة، فيُطلب من جديد حين تعود ما
 * دام الانتظار قائماً. لا مؤقّت هنا. أثر قفل الشاشة على طلبٍ جارٍ في Safari لم يُقَس بعد
 * (بوابة الإصدار 0).
 */

import { getState, setState } from "./store"

export async function keepAwake(): Promise<WakeLockSentinel | null> {
  if (!navigator.wakeLock) return null
  try {
    const lock = await navigator.wakeLock.request("screen")
    // انتهى الانتظار والطلب في الطريق (WebKit يمنحه بعد سؤال الإذن): يُترك فوراً.
    if (!getState().waitingFor) {
      lock.release().catch(() => {})
      return null
    }
    // عودتان سريعتان تطلبان مرتين: يبقى قفلٌ واحد.
    const previous = getState().wakeLock
    if (previous) previous.release().catch(() => {})
    lock.addEventListener("release", () => {
      if (getState().wakeLock === lock) setState({ wakeLock: null })
    })
    setState({ wakeLock: lock })
    return lock
  } catch {
    return null
  }
}

export function letSleep() {
  const lock = getState().wakeLock
  setState({ wakeLock: null })
  if (lock) lock.release().catch(() => {})
}
