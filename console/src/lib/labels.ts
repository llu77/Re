import type { AffectedSide, ProposalKind, ProposalStatus } from "@/lib/types"

/** أسماء عربية لقيم العقد. قيمةٌ جديدة في الخادم تظهر باسمها الخام لا تختفي. */
const KINDS: Record<ProposalKind, string> = {
  PLAN: "خطة علاج",
  PLAN_UPDATE: "تحديث خطة",
  ILLUSTRATION_SET: "رسوم توضيحية للتمارين",
  READINESS: "تقييم الجاهزية",
  DOCUMENTATION: "توثيق",
}

const STATUSES: Record<ProposalStatus, string> = {
  DRAFT: "مسودة",
  PENDING: "بانتظار المراجعة",
  APPROVED: "معتمد",
  EDITED_APPROVED: "معتمد بعد تعديل",
  REJECTED: "مرفوض",
  EXPIRED: "انتهت مهلته",
}

const SIDES: Record<AffectedSide, string> = {
  LEFT: "الجانب الأيسر",
  RIGHT: "الجانب الأيمن",
  BILATERAL: "الجانبان",
}

/** عناوين التمارين المصوَّرة كما يكتبها مولّدها (`tools/visual_exercises.py`). */
const EXERCISES: Record<string, string> = {
  scanning_grid: "تمرين مسح الشبكة البصرية",
  fixation_cross: "تمرين الإبصار اللامركزي (PRL)",
  contrast_chart: "تدريب حساسية التباين",
  reading_ruler: "تمرين القراءة بالمسطرة",
  tracking_exercise: "تمرين تتبع المسار البصري",
}

export const kindLabel = (kind: string) => KINDS[kind as ProposalKind] ?? kind
export const statusLabel = (status: string) => STATUSES[status as ProposalStatus] ?? status
export const sideLabel = (side: string) => SIDES[side as AffectedSide] ?? side
export const exerciseLabel = (type: string) =>
  Object.prototype.hasOwnProperty.call(EXERCISES, type) ? EXERCISES[type] : type

// التوقيت توقيت الرياض والصيغة صيغة البوابة نفسها، فيقرأ الممارس والمريض
// التاريخ نفسه بالكتابة نفسها.
const DATE_TIME = new Intl.DateTimeFormat("ar", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Riyadh",
})
const RELATIVE = new Intl.RelativeTimeFormat("ar", { numeric: "auto" })

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—"
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME.format(date)
}

/** «منذ ساعتين»، «بعد ٣ أيام» — يُحسب عند العرض، بلا مؤقّت يعيد الرسم. */
export function formatRelative(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "—"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "—"
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return RELATIVE.format(Math.trunc(seconds / size), unit)
  }
  return RELATIVE.format(0, "minute")
}

/** أول ثمانية من المعرّف تكفي للتمييز بالعين؛ المعرّف كاملاً في `title`. */
export const shortId = (id: string) => id.slice(0, 8)
