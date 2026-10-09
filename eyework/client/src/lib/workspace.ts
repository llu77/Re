/*
 * مساحة العمل لكل مهنة
 * ====================
 * بوابةٌ واحدة: شريط التبويب (أو الشريط الجانبي) وورقتا الأقسام والأدوات واحدةٌ للجميع، وما يختلف بين المهن بياناتٌ
 * هنا يملؤها كل مسار مهنة من مواصفته (inventory_spec.md وmarketing_spec.md وsupport_spec.md):
 *
 *   • `home`     أزرار الرئيسية: كل زرٍّ يبدأ عملاً حقيقياً، ولا شيء يُقرأ قبله (تحديث المالك
 *                2026-10-09). وهي نفسها بنود ورقة الأقسام والشريط الجانبي، بعد «الرئيسية».
 *   • `help`     سطور «مساعدة» لكل شاشة.
 *
 * المهنة من الخادم (/api/me)، لا من العنوان: لا يُفتح قسمٌ لغير مهنته، والخادم يرفض أدواته
 * لغيرها مهما طُلب (require_profession). والمسارات تحت قاعدة المهنة: `#/inventory/…`.
 */

import {
  BarChart3, Boxes, ClipboardList, FilePlus2, Headset, Inbox, LibraryBig, Megaphone, PackagePlus, ReceiptText, SquarePen, Undo2, Wallet,
  type LucideIcon,
} from "lucide-react"

export type ProfessionCode = "STOREKEEPER" | "MARKETING" | "SUPPORT"

/** زرٌّ في الرئيسية وبندٌ في ورقة الأقسام والشريط الجانبي. */
export interface WorkEntry {
  id: string
  label: string
  icon: LucideIcon
  /** المسار داخل التطبيق: `#/inventory/purchases/new`. */
  route: string
  /** الزرّ الأوّل في الرئيسية، بالتعبئة الملوّنة: أكثر ما يبدأ به الموظف يومه. */
  primary?: boolean
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
    // أزرار المالك بكلماته (2026-10-09): فاتورة شراء، ومرتجع، ومنتج، ومخزن وبضاعة، وجرد؛ والمصاريف والمجاميع.
    home: [
      { id: "purchase", label: "فاتورة شراء جديدة", icon: ReceiptText, route: "#/inventory/purchases/new", primary: true },
      { id: "return", label: "مرتجع من فاتورة", icon: Undo2, route: "#/inventory/returns/new" },
      { id: "item", label: "منتج جديد", icon: PackagePlus, route: "#/inventory/items/new" },
      { id: "stock", label: "المخزون", icon: Boxes, route: "#/inventory/stock" },
      { id: "count", label: "الجرد", icon: ClipboardList, route: "#/inventory/counts" },
      { id: "expenses", label: "المصاريف", icon: Wallet, route: "#/inventory/expenses" },
      { id: "totals", label: "المجاميع", icon: BarChart3, route: "#/inventory/totals" },
    ],
    help: {
      home: {
        title: "الرئيسية",
        lines: [
          "كل زرٍّ هنا يبدأ عملاً. والأدوات («اسأل سيمبول» و«حاسبة الضريبة» و«مساعدة») في شريط التبويب أو الشريط الجانبي في كل شاشة.",
          "«يحتاج انتباهك» يعدّ المسودات والمنتجات تحت حدّ الطلب والمرتجعات التي تنتظر إشعاراً دائناً.",
        ],
      },
      purchase: {
        title: "فاتورة الشراء",
        lines: [
          "اختر المورّد ومندوبه، واكتب رقم فاتورته وتاريخها والإجمالي المكتوب عليها، ثم أضف المنتجات: اكتب بعض الاسم أو الرمز أو الباركود واختر، أو أنشئ منتجاً جديداً بسعره.",
          "قبل التسجيل تظهر تنبيهات التطبيق (فرق الإجمالي، نقص التسليم، فاتورة مكرّرة) وتقرّ بها، ويراجع سيمبول الفاتورة إن طلبت: ينادِيك باسمك ويقول السبب، وأنت تقرّر.",
          "الفاتورة المسجّلة تزيد المخزون وتدخل المصاريف، ولا تُعدَّل: يُرجع منها بمرتجع، أو تُعكس كلّها بقيدٍ عكسي.",
        ],
      },
      return: {
        title: "المرتجع",
        lines: [
          "من فاتورةٍ مسجّلة: لا يُرجع أكثر ممّا بقي من سطرها، والسبب مطلوب، ومندوب المورّد الذي استلم يُحفظ معه.",
          "بعد التسجيل ينتظر المرتجع إشعار المورّد الدائن حتى الخامس عشر من الشهر التالي؛ اكتب رقمه وتاريخه حين يصل.",
        ],
      },
      item: {
        title: "المنتج",
        lines: [
          "الاسم والوحدة وسعر الشراء وفئة الضريبة مطلوبة؛ ويُعطى المنتج رمزاً مميّزاً تلقائياً («ص-00012»).",
          "الباركود والتصنيف وسعر البيع وحدّ الطلب والمورّد المفضّل ومندوبه اختيارية، وتظهر في بطاقته.",
        ],
      },
      stock: {
        title: "المخزون",
        lines: [
          "الرصيد يتغيّر بالمستندات وحدها: فاتورة، أو مرتجع، أو سند صرف أو جرد أو رصيد افتتاحي؛ ولا يُكتب باليد.",
          "ابحث بالاسم أو الرمز أو الباركود، وصفِّ «تحت حدّ الطلب» لترى ما يُطلب. و«المورّدون» من أعلى الشاشة.",
        ],
      },
      count: {
        title: "الجرد",
        lines: [
          "افتح جلسةً على كل المنتجات أو تصنيفٍ أو المنتجات تحت حدّ الطلب أو منتجاتٍ مختارة، وعُدّ كل منتجٍ واكتب ما وجدت.",
          "العدّ مغلقٌ افتراضياً: الرصيد الدفتري لا يظهر حتى تكتب العدّ، ثم يظهر الفرق وسببه. والترحيل يسوّي الرصيد بسندات جرد.",
        ],
      },
      expenses: { title: "المصاريف", lines: ["فواتير الشراء تُضاف هنا حين تُسجَّل، والمرتجعات والقيود العكسية تخصم منها. الشهر بزرّيه."] },
      totals: { title: "المجاميع", lines: ["مجاميع الشهر من فواتيرك ومرتجعاتك وقيمة المخزون بالتكلفة المتوسطة، يحسبها الخادم عند فتح الشاشة."] },
    },
  },
  MARKETING: {
    profession: "MARKETING",
    name: "التسويق",
    base: "#/marketing",
    // زرّا أداة الحملة القائمة؛ «ما ينتظر الاعتماد» و«أدخل النتائج» و«تقويم المحتوى» مع حزمة
    // التسويق حين تصل شاشاتها، فلا زرٌّ يفتح ما ليس موجوداً.
    home: [
      { id: "new", label: "حملة جديدة", icon: FilePlus2, route: "#/marketing/new", primary: true },
      { id: "campaigns", label: "حملاتي", icon: Megaphone, route: "#/marketing/campaigns" },
    ],
    help: {
      home: { title: "الرئيسية", lines: ["كل زرٍّ هنا يبدأ عملاً. والأدوات («اسأل سيمبول» و«مساعدة») في شريط التبويب أو الشريط الجانبي في كل شاشة."] },
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
      { id: "new", label: "تذكرة جديدة", icon: SquarePen, route: "#/support/tickets/new" },
      { id: "decide", label: "بانتظار قراري", icon: Headset, route: "#/support/tickets?waiting=me" },
      { id: "knowledge", label: "قاعدة المعرفة", icon: LibraryBig, route: "#/support/knowledge" },
    ],
    help: {
      home: { title: "الرئيسية", lines: ["كل زرٍّ هنا يبدأ عملاً. والأدوات («اسأل سيمبول» و«مساعدة») في شريط التبويب أو الشريط الجانبي في كل شاشة."] },
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
