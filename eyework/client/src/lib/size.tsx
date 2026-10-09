/*
 * حجم الواجهة
 * ===========
 * قيمتان: `compact` (الافتراضي) و`gaze`. تُكتب على <html data-size>، فتبدّل متغيّرات
 * CSS كلّها (styles/globals.css)؛ وReact يعرفها لما يختلف بناءً لا قياساً: خطوةٌ في
 * كل شاشة بدل نموذجٍ طويل، وصفحاتٌ بدل التمرير، ولا حركة.
 *
 * مصدرها بعد الدخول الخادم وحده (`ui_size` في GET /api/me: COMPACT أو GAZE أو null)، ويغيّرها
 * المستخدم من «حسابي» (PUT /api/me/ui-size). وقبل الدخول — الترحيب والدخول والإشعار وخطوة
 * «كيف تستخدم الجهاز؟» — يختارها زرّ «حجمٌ أكبر» في الرأس، وتُحمل في عنوان الصفحة لا في
 * المتصفّح: التطبيق لا يخزّن في الجهاز شيئاً. والقيمة في العنوان `?size=large` لا تذكر النظر:
 * عنوانٌ في سجلّ Safari على جهازٍ مشترك لا يقول إن صاحبه يستعمل تتبّع العين
 * (registration_spec §8.2). و`null` من الخادم ليس «عادياً»: هو «اسأل» (§8.7).
 */

import * as React from "react"

export type SizeMode = "compact" | "gaze"
export const SIZE_MODES: readonly SizeMode[] = ["compact", "gaze"]

/** قيمة الخادم ↔ قيمة الواجهة. */
export type ServerSize = "COMPACT" | "GAZE"
export const toServer = (mode: SizeMode): ServerSize => (mode === "gaze" ? "GAZE" : "COMPACT")
/** قيمة الخادم، أو null حين لم يُختر بعد: يُسأل صاحب الحساب ولا يُصغَّر شيءٌ بصمت. */
export const fromServer = (value: unknown): SizeMode | null => (value === "GAZE" ? "gaze" : value === "COMPACT" ? "compact" : null)

/** القيمة المحايدة في العنوان للحجم الكبير قبل الدخول. */
export const URL_LARGE = "large"

export function applySize(mode: SizeMode) {
  document.documentElement.dataset.size = mode
}

/** `?size=large` في العنوان ← الكبير؛ وغيره لا شيء. */
export function sizeFromUrl(search: string = window.location.search): SizeMode | null {
  return new URLSearchParams(search).get("size") === URL_LARGE ? "gaze" : null
}

/** يكتب الحجم في العنوان دون تنقّلٍ ولا سجلٍّ جديد، ليبقى بعد إعادة التحميل. */
export function writeSizeToUrl(mode: SizeMode) {
  const url = new URL(window.location.href)
  if (mode === "gaze") url.searchParams.set("size", URL_LARGE)
  else url.searchParams.delete("size")
  window.history.replaceState(window.history.state, "", url)
}

interface SizeContextValue {
  size: SizeMode
  setSize: (mode: SizeMode) => void
}

const SizeContext = React.createContext<SizeContextValue | null>(null)

export function SizeProvider({ initial, children }: { initial: SizeMode; children: React.ReactNode }) {
  const [size, setSize] = React.useState<SizeMode>(initial)
  // قبل الرسم: لا إطار واحدٌ بالحجم الخطأ.
  React.useLayoutEffect(() => applySize(size), [size])
  const value = React.useMemo(() => ({ size, setSize }), [size])
  return <SizeContext.Provider value={value}>{children}</SizeContext.Provider>
}

/** استعلامُ وسائطٍ كحالة React: يتغيّر بفعل المستخدم (تدوير، شريط Safari، لوحة المفاتيح) لا من تلقاء الواجهة. */
export function useMatch(query: string): boolean {
  const subscribe = React.useCallback(
    (listener: () => void) => {
      const list = window.matchMedia(query)
      list.addEventListener("change", listener)
      return () => list.removeEventListener("change", listener)
    },
    [query],
  )
  return React.useSyncExternalStore(subscribe, () => window.matchMedia(query).matches)
}

/** شاشةٌ قصيرة (480px أو أقل: الهاتف أفقياً، أو لوحة المفاتيح): الحجم الكبير يعرض فيها أقلّ في الصفحة. */
export const SHORT_QUERY = "(max-height: 30rem)"
/** الآيباد فأوسع (744px: iPad mini عمودياً): شريطٌ جانبي بدل شريط التبويب. */
export const TABLET_QUERY = "(min-width: 46.5rem)"
/** عريضٌ (1024px): القائمة والتفصيل معاً في الحجم العادي. */
export const WIDE_QUERY = "(min-width: 64rem)"

export function useShortScreen(): boolean {
  return useMatch(SHORT_QUERY)
}

/** عدد الصفوف في صفحةٍ بحسب الحجم وطول الشاشة. */
export function usePageSize(sizes: { compact: number; gaze: number; gazeShort?: number }): number {
  const { size } = useSize()
  const short = useShortScreen()
  if (size === "compact") return sizes.compact
  return short ? (sizes.gazeShort ?? Math.max(1, sizes.gaze - 1)) : sizes.gaze
}

export function useSize(): SizeContextValue {
  const value = React.useContext(SizeContext)
  if (!value) throw new Error("useSize خارج SizeProvider")
  return value
}
