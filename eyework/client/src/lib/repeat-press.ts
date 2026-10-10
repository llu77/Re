/*
 * الضغطة المكرّرة في الحجم الكبير
 * ================================
 * تتبّع الرأس في iOS 26 يربط حركات الوجه (الابتسام، الرمش، تجعيد الأنف…) بـ«نقرة» أو «نقرتين»
 * (Apple: «Control iPhone with the movement of your head»)، وقائمة AssistiveTouch في تتبّع العين
 * والرأس فيها «النقر المزدوج». والنقرتان تصلان الصفحة ضغطتين في الموضع نفسه: الأولى تفتح ما بعدها،
 * والثانية تقع على ما صار تحتها («التالي» مرةً ثانية فتُطوى صفحةٌ لم تُقرأ، أو خيارٌ يُعكس). قاعدتا
 * الهبوط تمنعان أن يكون ما تحتها اعتماداً أو قيمة، وهذا يمنع الباقي: في الحجم الكبير لا تُحسب ضغطةٌ
 * تأتي قبل مضيّ `REPEAT_MS` من الضغطة التي قبلها. ولا يُضغط هدفان مقصودان بالنظر أو بالرأس في أقلّ من
 * ذلك: بينهما انتقالٌ ومكوثٌ أو حركة وجه.
 *
 * بالزمن الذي يحمله الحدث (`event.timeStamp`) لا بمؤقّت، وعلى `click` وحده كبقية الواجهة. وما يرسله
 * المتصفّح نفسه ليس ضغطةً ثانية: النقرة التي ينقلها <label> إلى حقله (اختيار الصورة)، وما تستدعيه
 * الشيفرة (`isTrusted` كاذب).
 */

/** أقصر ما بين ضغطتين تُحسبان. «النقرتان» من النظام أقرب من ذلك بكثير. */
export const REPEAT_MS = 400

export interface Press {
  at: number
  target: EventTarget | null
}

interface ClickLike {
  isTrusted: boolean
  timeStamp: number
  target: EventTarget | null
}

/** النقرة التي ينقلها المتصفّح من <label> إلى حقله بعد ضغطةٍ عليه. */
function forwarded(target: EventTarget | null, previous: EventTarget | null): boolean {
  if (!target || !previous || typeof Node === "undefined" || !(previous instanceof Node)) return false
  const labels = (target as { labels?: NodeListOf<HTMLLabelElement> | null }).labels
  return Boolean(labels && Array.from(labels).some((label) => label.contains(previous)))
}

/**
 * ما تفعله النقرة: «count» ضغطةٌ تُحسب، و«repeat» ضغطةٌ لا تُحسب، و«pass» ما ليس ضغطةً من المستخدم.
 * والضغطة التي لا تُحسب تمدّ المهلة أيضاً: سلسلة نقراتٍ متقاربة ضغطةٌ واحدة.
 */
export function classify(previous: Press | null, event: ClickLike): "count" | "repeat" | "pass" {
  if (!event.isTrusted) return "pass"
  if (previous && forwarded(event.target, previous.target)) return "pass"
  if (previous && event.timeStamp >= previous.at && event.timeStamp - previous.at < REPEAT_MS) return "repeat"
  return "count"
}

/** يركّب الحارس على النافذة (في مرحلة الالتقاط، قبل React) ويعيد ما يزيله. */
export function guardRepeatPresses(): () => void {
  let previous: Press | null = null
  function onClick(event: MouseEvent) {
    const kind = classify(previous, event)
    if (kind === "pass") return
    previous = { at: event.timeStamp, target: event.target }
    if (kind === "repeat") {
      event.preventDefault()
      event.stopImmediatePropagation()
    }
  }
  window.addEventListener("click", onClick, { capture: true })
  return () => window.removeEventListener("click", onClick, { capture: true })
}
