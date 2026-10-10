/*
 * التواريخ والأعداد في النصّ
 * ==========================
 * التقويم الميلادي بأسماء الأشهر العربية (يناير… كما في السعودية في الفواتير)،
 * والأرقام لاتينية كما في المبالغ.
 */

const day = new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", { day: "numeric", month: "long" })
const dayYear = new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", { day: "numeric", month: "long", year: "numeric" })
const time = new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", { hour: "numeric", minute: "2-digit" })

export function formatDay(iso: string, withYear = false): string {
  const date = new Date(iso)
  return (withYear ? dayYear : day).format(date)
}

export function formatTime(iso: string): string {
  return time.format(new Date(iso))
}

/** «منذ 3 ساعات» بالنسبة إلى `now` المعطى، لا إلى ساعة الجهاز وهي تمضي: لا يتغيّر النصّ وحده. */
export function formatAgo(iso: string, now: string): string {
  const minutes = Math.max(0, Math.round((Date.parse(now) - Date.parse(iso)) / 60000))
  if (minutes < 1) return "الآن"
  if (minutes < 60) return minutes === 1 ? "منذ دقيقة" : minutes === 2 ? "منذ دقيقتين" : `منذ ${minutes} ${minutes <= 10 ? "دقائق" : "دقيقة"}`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return hours === 1 ? "منذ ساعة" : hours === 2 ? "منذ ساعتين" : `منذ ${hours} ${hours <= 10 ? "ساعات" : "ساعة"}`
  const days = Math.round(hours / 24)
  return days === 1 ? "منذ يوم" : days === 2 ? "منذ يومين" : `منذ ${days} ${days <= 10 ? "أيام" : "يوماً"}`
}

/** العدّ بالعربية: «3 أصناف»، «صنفٌ واحد»، «صنفان». */
export function countLabel(n: number, one: string, two: string, few: string, many: string): string {
  if (n === 1) return one
  if (n === 2) return two
  if (n >= 3 && n <= 10) return `${n} ${few}`
  return `${n} ${many}`
}
