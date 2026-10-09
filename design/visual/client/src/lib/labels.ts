/* نصوص الواجهة الثابتة. ما يأتي من الخادم (المهن، الحدود، المصادر) لا يُكرَّر هنا. */
import { Building2, MapPin, Phone, Smartphone, type LucideIcon } from "lucide-react"

export const PERSONA = "سيمبول"

export const MODE: Record<string, { label: string; icon: LucideIcon; tone: "success" | "neutral" }> = {
  IN_APP: { label: "جزءٌ منها في هذه البوابة، تسمّيه الملاحظة", icon: Smartphone, tone: "success" },
  EMPLOYER_SYSTEM: { label: "عملٌ مكتبي يحتاج أنظمة صاحب العمل", icon: Building2, tone: "neutral" },
  ON_SITE: { label: "عملٌ ميداني لا يُؤدّى بالنظر", icon: MapPin, tone: "neutral" },
  VOICE: { label: "بالهاتف أو الصوت", icon: Phone, tone: "neutral" },
}

export const SIGNUP_STEPS = ["name", "year", "month", "day", "profession", "email", "review", "password"] as const

export function greeting(name: string | null): string {
  return name ? `أنا ${PERSONA}، مساعدك الشخصي يا ${name}.` : `أنا ${PERSONA}، مساعدك الشخصي.`
}

/* العدد بكلمته الصحيحة: «مهمة واحدة»، «مهمتان»، «11 مهمة»، «8 مهارات». */
export function countLabel(n: number, one: string, two: string, few: string, many: string): string {
  if (n === 1) return one
  if (n === 2) return two
  if (n >= 3 && n <= 10) return `${n} ${few}`
  return `${n} ${many}`
}
