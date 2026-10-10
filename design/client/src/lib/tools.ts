/*
 * أداة البوابة في خانتها من الرئيسية. الرمز من الخادم (`portal.tools`)، والبلاطة من
 * هنا. CAMPAIGN أداة التسويق اليوم؛ STOCK_COUNT مثالٌ على أداة أمين المخزون في
 * النموذج وحده — اسمها ووظيفتها قرارُ مسار الأدوات، لا هذه الطبقة.
 */
import { ClipboardCheck, Megaphone, type LucideIcon } from "lucide-react"

export const TOOL_TILES: Record<string, { title: string; description: string; icon: LucideIcon; route: string }> = {
  CAMPAIGN: { title: "حملة جديدة", description: "صورة المنتج ونصٌّ يقترحه سيمبول", icon: Megaphone, route: "#/new" },
  STOCK_COUNT: { title: "جرد المخزون", description: "عدٌّ ومطابقةٌ بالسجلّ", icon: ClipboardCheck, route: "#/tool" },
}
