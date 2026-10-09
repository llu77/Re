/*
 * مساحة العمل لكل مهنة
 * ====================
 * بوابةٌ واحدة: الرأس وقائمة الأقسام وزرّ الأدوات واحدٌ للجميع، وما يختلف بين المهن بياناتٌ
 * هنا يملؤها كل مسار مهنة من مواصفته (inventory_spec.md وmarketing_spec.md وsupport_spec.md):
 *
 *   • `home`     أزرار الرئيسية: كل زرٍّ يبدأ عملاً حقيقياً، ولا شيء يُقرأ قبله (تحديث المالك
 *                2026-10-09). وهي نفسها بنود قائمة الأقسام في الرأس، بعد «الرئيسية».
 *   • `tools`    ما تضعه المهنة في زرّ الأدوات العائم، أوّلاً، قبل أدوات البوابة المشتركة.
 *   • `help`     سطور «مساعدة» لكل شاشة.
 *
 * المهنة من الخادم (/api/me)، لا من العنوان: لا يُفتح قسمٌ لغير مهنته، والخادم يرفض أدواته
 * لغيرها مهما طُلب (require_profession). والمسارات تحت قاعدة المهنة: `#/inventory/…`.
 */

import {
  BarChart3, Boxes, FilePlus2, Headset, Inbox, LibraryBig, Megaphone, PackagePlus, ReceiptText, SquarePen, Undo2, Wallet,
  type LucideIcon,
} from "lucide-react"

export type ProfessionCode = "STOREKEEPER" | "MARKETING" | "SUPPORT"

/** زرٌّ في الرئيسية وبندٌ في قائمة الأقسام. */
export interface WorkEntry {
  id: string
  label: string
  icon: LucideIcon
  /** المسار داخل التطبيق: `#/inventory/purchases/new`. */
  route: string
  /** الزرّ الأوّل في الرئيسية، بالتعبئة الملوّنة: أكثر ما يبدأ به الموظف يومه. */
  primary?: boolean
  /** يُنشئ مستنداً: في شريط الحاسوب تجتمع هذه تحت «جديد ▾» إن كانت اثنين فأكثر. */
  creates?: boolean
}

export interface SectionHelp {
  title: string
  lines: string[]
}

export interface Workspace {
  profession: ProfessionCode
  /** اسم المهنة كما يرسله الخادم (professions.NAMES). */
  name: string
  /** قاعدة المسارات: `#/inventory`. الرئيسية هي القاعدة نفسها. */
  base: string
  home: WorkEntry[]
  help: Record<string, SectionHelp>
}

export const WORKSPACES: Record<ProfessionCode, Workspace> = {
  STOREKEEPER: {
    profession: "STOREKEEPER",
    name: "أمين المخزون",
    base: "#/inventory",
    // أزرار المالك كما كتبها، بأسماء شاشات inventory_spec §3.
    home: [
      { id: "purchase", label: "فاتورة شراء جديدة", icon: ReceiptText, route: "#/inventory/purchases/new", primary: true, creates: true },
      { id: "return", label: "مرتجع من فاتورة", icon: Undo2, route: "#/inventory/returns/new", creates: true },
      { id: "item", label: "صنف جديد", icon: PackagePlus, route: "#/inventory/items/new", creates: true },
      { id: "stock", label: "المخزون", icon: Boxes, route: "#/inventory/stock" },
      { id: "expenses", label: "المصاريف", icon: Wallet, route: "#/inventory/expenses" },
      { id: "totals", label: "المجاميع", icon: BarChart3, route: "#/inventory/totals" },
    ],
    help: {
      home: { title: "الرئيسية", lines: ["كل زرٍّ هنا يبدأ عملاً. والأدوات في الزرّ العائم في كل شاشة."] },
      purchase: {
        title: "فاتورة الشراء",
        lines: [
          "اختر المورّد، ثم أضف الأصناف: اكتب بعض الاسم واختر من القائمة، أو أنشئ صنفاً جديداً بسعره.",
          "قبل التسجيل يراجع سيمبول الفاتورة. إن رأى ما يُستغرب ناداك باسمك وقال السبب، وأنت تقرّر.",
          "الفاتورة المسجّلة تزيد المخزون وتُضاف إلى المصاريف، ولا تُعدَّل: يُرجع منها بمرتجع.",
        ],
      },
      return: { title: "المرتجع", lines: ["من فاتورةٍ مسجّلة: لا يُرجع أكثر ممّا بقي من سطرها، والسبب مطلوب."] },
      totals: { title: "المجاميع", lines: ["مجاميع الشهر من فواتيرك ومرتجعاتك، يحسبها الخادم عند فتح الشاشة."] },
      expenses: { title: "المصاريف", lines: ["فواتير الشراء تُضاف هنا حين تُسجَّل، والمرتجعات تخصم منها."] },
      stock: { title: "المخزون", lines: ["الرصيد يتغيّر بالمستندات وحدها، ولا يُكتب باليد."] },
    },
  },
  MARKETING: {
    profession: "MARKETING",
    name: "التسويق",
    base: "#/marketing",
    // زرّا أداة الحملة القائمة؛ «ما ينتظر الاعتماد» و«أدخل النتائج» و«تقويم المحتوى» مع حزمة
    // التسويق حين تصل شاشاتها، فلا زرٌّ يفتح ما ليس موجوداً.
    home: [
      { id: "new", label: "حملة جديدة", icon: FilePlus2, route: "#/marketing/new", primary: true, creates: true },
      { id: "campaigns", label: "حملاتي", icon: Megaphone, route: "#/marketing/campaigns" },
    ],
    help: {
      home: { title: "الرئيسية", lines: ["كل زرٍّ هنا يبدأ عملاً. والأدوات في الزرّ العائم في كل شاشة."] },
      new: {
        title: "حملة جديدة",
        lines: [
          "اختر صورة المنتج وحده، دون أشخاصٍ أو أوراق؛ ثم يكتب سيمبول العنوان والوصف.",
          "النصّ مقترح: اطلب تعديلاً أو وافق عليه، ثم الميزانية والمدّة، ثم راجع واعتمد.",
        ],
      },
      campaigns: {
        title: "حملاتي",
        lines: ["كل حملةٍ تمرّ بحالاتها: مسودة، ثم نصٌّ مقترح، ثم معتمد، ثم جاهزة.", "لا يُنشر شيءٌ ولا يُدفع أيّ مبلغٍ تلقائياً."],
      },
    },
  },
  SUPPORT: {
    profession: "SUPPORT",
    name: "الدعم الفني",
    base: "#/support",
    home: [
      { id: "open", label: "التذاكر المفتوحة", icon: Inbox, route: "#/support/tickets", primary: true },
      { id: "new", label: "تذكرة جديدة", icon: SquarePen, route: "#/support/tickets/new", creates: true },
      { id: "decide", label: "بانتظار قراري", icon: Headset, route: "#/support/tickets?waiting=me" },
      { id: "knowledge", label: "قاعدة المعرفة", icon: LibraryBig, route: "#/support/knowledge" },
    ],
    help: {
      home: { title: "الرئيسية", lines: ["كل زرٍّ هنا يبدأ عملاً. والأدوات في الزرّ العائم في كل شاشة."] },
      open: {
        title: "التذاكر",
        lines: [
          "سيمبول يقرأ رسالة العميل ويكتب مسودة ردّ، ولا يرسل شيئاً بنفسه.",
          "أنت تقرّر لكل تذكرة: أرسل كما هي، أو عدّل ثم أرسل، أو اكتب بنفسك، أو صعّد.",
        ],
      },
    },
  },
}

/** بند الرئيسية الحالي من المسار، أو null في الرئيسية نفسها وفي «حسابي». */
export function currentEntry(workspace: Workspace, route: string): WorkEntry | null {
  const path = route.split("?")[0]
  return workspace.home.find((entry) => path === entry.route.split("?")[0] || path.startsWith(`${entry.route.split("?")[0]}/`)) ?? null
}
