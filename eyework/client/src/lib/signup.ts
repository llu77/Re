/*
 * التسجيل: الحالة والفحص خطوةً خطوة
 * =================================
 * منقولٌ من static/portal.js: البيانات في الذاكرة حتى الخطوة الأخيرة، ولا تُرسل إلا
 * معها. الفحص هنا هو فحص الخادم نفسه (auth.check_name وcheck_email) كي لا تختلف
 * الواجهة عن القاعدة؛ وما يرفضه الخادم بعد ذلك يعود برمز حقله فتُفتح خطوته.
 *
 * الخطوات بعد شاشتي الإشعار (registration_spec §8.5): «كيف تستخدم الجهاز؟» أولاها،
 * ثم الاسم، ثم تاريخ الميلاد بثلاث خطوات (سنواتٌ وأشهرٌ وأيامٌ جاهزة وخطوة «أقدم/أحدث»
 * بدل الكتابة)، ثم المهنة، ثم البريد، ثم المراجعة، ثم كلمة المرور.
 */

import type { SizeMode } from "./size"

export const MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

export const SIGNUP_STEPS = ["use", "name", "year", "month", "day", "profession", "email", "review", "password"] as const
export type SignupStep = (typeof SIGNUP_STEPS)[number]
/** الإشعار قبل الخطوات: شاشتان، ما يُحفظ وما يُرسَل. */
export type SignupScreen = "kept" | "sent" | SignupStep

export const STEP_LABELS: Record<SignupStep, string> = {
  use: "طريقة الاستخدام",
  name: "الاسم",
  year: "سنة الميلاد",
  month: "الشهر",
  day: "اليوم",
  profession: "المهنة",
  email: "البريد",
  review: "المراجعة",
  password: "كلمة المرور",
}

export const YEAR_PRESETS = [1960, 1970, 1980, 1990, 2000, 2010]
export const MONTH_PRESETS = [1, 3, 5, 7, 9, 11]
export const DAY_PRESETS = [1, 5, 10, 15, 20, 25]

/** رمز الخطأ من الخادم ← الشاشة التي يُصلَح فيها. */
export const FIELD_SCREENS: Record<string, SignupScreen> = {
  NAME: "name", BIRTH: "year", EMAIL: "email", TAKEN: "email", PASSWORD: "password", CONSENT: "kept", UI_SIZE: "use",
}

export interface SignupState {
  /** رمز الرابط، أو null في التسجيل بلا رابط. */
  code: string | null
  /** سُئل الخادم عن الرمز (أو عن فتح التسجيل) قبل الخطوة الأولى. */
  checked: boolean
  agreed: boolean
  use: SizeMode | null
  name: string
  year: number | null
  month: number | null
  day: number | null
  profession: string | null
  email: string
  /** رسالة خطأٍ من الخادم تُعرض على الخطوة التي يُصلَح فيها بعد رسمها. */
  alert: string | null
}

export function newSignup(code: string | null): SignupState {
  return { code, checked: false, agreed: false, use: null, name: "", year: null, month: null, day: null,
           profession: null, email: "", alert: null }
}

export function daysIn(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

/** الاسم كما يفحصه الخادم (auth.check_name): مسافاتٌ مفردة، و«ی/ک» عربية. */
export function normalizeName(raw: string): string {
  return raw.replace(/ی/g, "ي").replace(/ک/g, "ك").replace(/\s+/g, " ").trim()
}

export function nameIsValid(name: string, max: number): boolean {
  return name.length > 0 && name.length <= max && /^[ء-غف-يa-zA-Z]+( [ء-غف-يa-zA-Z]+)*$/.test(name)
}

/** البريد كما يوحّده الخادم (auth.normalize_login) ويفحصه (auth.check_email). */
export function normalizeEmail(raw: string): string {
  return raw.normalize("NFKC").toLowerCase().replace(/ß/g, "ss").trim()
}

export function emailIsValid(email: string): boolean {
  return email.length <= 254 && /^[a-z0-9._+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(email)
}

export function birthDate(s: SignupState): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${s.year}-${pad(s.month ?? 0)}-${pad(s.day ?? 0)}`
}

export function birthWords(s: SignupState): string {
  return `${s.day} ${MONTHS[(s.month ?? 1) - 1]} ${s.year}`
}

export function birthInFuture(s: SignupState, today: Date = new Date()): boolean {
  if (s.year === null || s.month === null || s.day === null) return false
  return new Date(s.year, s.month - 1, s.day) > today
}

/** أوّل شاشةٍ ناقصة: لا تُفتح شاشةٌ قبل ما يسبقها (رابطٌ محفوظ، أو «رجوع» المتصفّح). */
export function firstMissing(s: SignupState, nameMax: number): SignupScreen | null {
  // الإشعار شاشتان والموافقة في ثانيتهما: كلتاهما تُفتحان قبل الموافقة، وما بعدهما لا.
  if (!s.agreed) return "sent"
  if (s.use === null) return "use"
  if (!nameIsValid(s.name, nameMax)) return "name"
  if (s.year === null) return "year"
  if (s.month === null) return "month"
  if (s.day === null || birthInFuture(s)) return "day"
  if (s.profession === null) return "profession"
  if (!emailIsValid(s.email)) return "email"
  return null
}

export const SCREEN_ORDER: SignupScreen[] = ["kept", "sent", ...SIGNUP_STEPS]

export function screenRoute(screen: SignupScreen): string {
  return screen === "kept" ? "#/signup" : `#/signup/${screen}`
}

export function screenFromRoute(route: string): SignupScreen {
  const tail = route.replace(/^#\/signup\/?/, "")
  return (SCREEN_ORDER as string[]).includes(tail) ? (tail as SignupScreen) : "kept"
}

/** «رجوع»: الأب المنطقي للشاشة، وشاشة الدخول قبل الإشعار. */
export function parentRoute(screen: SignupScreen): string {
  const index = SCREEN_ORDER.indexOf(screen)
  return index <= 0 ? "#/login" : screenRoute(SCREEN_ORDER[index - 1])
}

/** ترقيم الخطوة في المؤشّر (بعد الإشعار): من 1. */
export function stepNumber(screen: SignupScreen): number {
  const index = (SIGNUP_STEPS as readonly string[]).indexOf(screen)
  return index < 0 ? 0 : index + 1
}

/** يوم الميلاد المختار لم يعد في الشهر (31 ثم فبراير): يُسقَط ليُختار من جديد. */
export function dropImpossibleDay(s: SignupState): SignupState {
  if (s.year === null || s.month === null || s.day === null) return s
  return s.day > daysIn(s.year, s.month) ? { ...s, day: null } : s
}
