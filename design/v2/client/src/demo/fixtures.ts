/*
 * بيانات صفحة العرض
 * =================
 * لمراجعة التصميم وحدها: تُبنى في dist-demo بـ`--mode demo`، ولا تدخل بناء الإنتاج (اختبار
 * source.test.ts يفحص dist). أسماءٌ وأرقامٌ مختلَقة لمنشأةٍ مختلَقة؛ لا اسم شركةٍ حقيقية.
 */

import type { ComboboxOption } from "@/components/ui/combobox"
import type { AssistantReply } from "@/components/tools/assistant-tool"
import type { Note } from "@/components/tools/notes-tool"
import type { ReturnInvoice } from "@/screens/return-flow"
import type { CampaignCard, ExpenseRow, InvoiceRow, Item, ReviewFlag, TicketDraft, TicketMessage, TicketRow } from "@/lib/work-types"
import { formatAmount } from "@/lib/money"

export const NOW = "2026-10-08T12:00:00+03:00"
export const TODAY = "2026-10-08"
export const USER = "سارة"
export const VAT_BP = 1500
export const CONTACT = "help@siyagha.example"

/** وحدات inventory_spec §3.0. */
export const UNITS = [
  { value: "PIECE", label: "قطعة" },
  { value: "BOX", label: "علبة" },
  { value: "CARTON", label: "كرتون" },
  { value: "PACK", label: "عبوة" },
  { value: "PALLET", label: "منصّة" },
  { value: "KG", label: "كغ" },
  { value: "LITRE", label: "لتر" },
  { value: "METRE", label: "م" },
]

export const SIZE_NAMES = { compact: "باللمس", gaze: "بتتبّع العين" } as const
export const UI_SIZES = [
  { code: "COMPACT" as const, name: "باللمس", line: "أزرارٌ وخطٌّ بالحجم المعتاد." },
  { code: "GAZE" as const, name: "بتتبّع العين", line: "أزرارٌ أكبر بينها مسافات، تُضغط بالنظر." },
]

export const ITEMS: Item[] = [
  { id: "i1", name: "كرسي مكتب شبكي", sku: "KRS-104", unit: "قطعة", salePrice: 34900, lastCost: 28500, onHand: 14, reorderLevel: 5 },
  { id: "i2", name: "كرسي زائر بلا عجلات", sku: "KRS-110", unit: "قطعة", salePrice: 18900, lastCost: 14000, onHand: 3, reorderLevel: 8 },
  { id: "i3", name: "كرسي اجتماعات جلد", sku: "KRS-131", unit: "قطعة", salePrice: 64000, lastCost: 52000, onHand: 6, reorderLevel: 4 },
  { id: "i4", name: "مكتب خشبي 140 سم", sku: "MKT-140", unit: "قطعة", salePrice: 115000, lastCost: 89000, onHand: 2, reorderLevel: 3 },
  { id: "i5", name: "ورق تصوير A4", sku: "PPR-A4", unit: "كرتون", salePrice: 11500, lastCost: 9200, onHand: 0, reorderLevel: 10 },
  { id: "i6", name: "حبر طابعة ليزر أسود", sku: "INK-305", unit: "قطعة", salePrice: 7900, lastCost: 5800, onHand: 4, reorderLevel: 6 },
  { id: "i7", name: "ملفّ علّاقي أزرق", sku: "FIL-020", unit: "علبة", salePrice: 4500, lastCost: 3100, onHand: 20, reorderLevel: 10 },
  { id: "i8", name: "رفّ معدني 5 أدوار", sku: "SHF-005", unit: "قطعة", salePrice: 42000, lastCost: 33000, onHand: 7, reorderLevel: 2 },
  { id: "i9", name: "خزانة ملفات 4 أدراج", sku: "CAB-004", unit: "قطعة", salePrice: 98000, lastCost: 76000, onHand: 1, reorderLevel: 2 },
]

export const itemOption = (item: Item): ComboboxOption => ({
  value: item.id,
  label: item.name,
  description: `${item.sku} · ${item.unit} · الرصيد ${item.onHand}`,
  meta: item.lastCost !== null ? `آخر شراء ${formatAmount(item.lastCost)}` : undefined,
})

/** بحثٌ بالكلمات: يطابق ما فيه كلمةٌ ممّا كُتب، والأكثر تطابقاً أولاً. كما يفعل الخادم. */
export function searchItems(query: string): ComboboxOption[] {
  const words = query.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ITEMS.slice(0, 6).map(itemOption)
  return ITEMS.map((item) => ({ item, score: words.filter((w) => item.name.includes(w) || (item.sku ?? "").includes(w.toUpperCase())).length }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => itemOption(x.item))
}

export const SUPPLIERS: ComboboxOption[] = [
  { value: "s1", label: "مؤسسة الرواد للأثاث المكتبي", description: "الرقم الضريبي 300045678900003" },
  { value: "s2", label: "شركة الأفق للورق", description: "الرقم الضريبي 310298765400003" },
  { value: "s3", label: "مؤسسة النخبة للتجهيزات", description: "الرقم الضريبي 302113344500003" },
]

export const INVOICES: InvoiceRow[] = [
  { id: "v43", number: "ش-0043", supplier: "مؤسسة الرواد للأثاث المكتبي", date: "2026-10-08", gross: 1231650, lines: 3, status: "RECORDED" },
  { id: "v42", number: "ش-0042", supplier: "مؤسسة النخبة للتجهيزات", date: "2026-10-06", gross: 345000, lines: 2, status: "RECORDED" },
  { id: "v41", number: "ش-0041", supplier: "شركة الأفق للورق", date: "2026-10-03", gross: 211600, lines: 1, status: "PARTLY_RETURNED" },
  { id: "v40", number: "ش-0040", supplier: "مؤسسة الرواد للأثاث المكتبي", date: "2026-10-01", gross: 483000, lines: 4, status: "RECORDED" },
  { id: "v39", number: "ش-0039", supplier: "شركة الأفق للورق", date: "2026-09-27", gross: 98000, lines: 1, status: "RECORDED" },
]

export const TOTALS = {
  month: "أكتوبر 2026",
  purchasesNet: 3685217,
  purchasesVat: 552783,
  returns: 315000,
  stockValue: 18425000,
}

export const ATTENTION = [
  { id: "drafts", label: "مسوداتٌ لم تُسجَّل", count: 2 },
  { id: "reorder", label: "أصنافٌ بلغت حدّ الطلب", count: 5 },
  { id: "credit", label: "مرتجعاتٌ تنتظر إشعار المورّد الدائن", count: 1, late: 1 },
]

export const EXPENSES: ExpenseRow[] = [
  { id: "e1", number: "ش-0043", date: "2026-10-08", kind: "PURCHASE", supplier: "مؤسسة الرواد للأثاث المكتبي", net: 1071000, vat: 160650 },
  { id: "e2", number: "ر-0007", date: "2026-10-07", kind: "RETURN", supplier: "شركة الأفق للورق", net: -27391, vat: -4109 },
  { id: "e3", number: "ش-0042", date: "2026-10-06", kind: "PURCHASE", supplier: "مؤسسة النخبة للتجهيزات", net: 300000, vat: 45000 },
  { id: "e4", number: "ش-0041", date: "2026-10-03", kind: "PURCHASE", supplier: "شركة الأفق للورق", net: 184000, vat: 27600 },
  { id: "e5", number: "ع-0001", date: "2026-10-02", kind: "REVERSAL", supplier: "مؤسسة النخبة للتجهيزات", net: -96000, vat: -14400 },
  { id: "e6", number: "ش-0040", date: "2026-10-01", kind: "PURCHASE", supplier: "مؤسسة الرواد للأثاث المكتبي", net: 420000, vat: 63000 },
]

export const EXPENSE_TOTALS = {
  purchases: 1975000,
  returns: 27391,
  net: 1851609,
  vat: 277741,
}

/** تنبيهٌ من النموذج (inventory_spec §7.3: PRICE_IMPLAUSIBLE لصنفٍ بلا تاريخ). الرسالة قالب
 *  التطبيق لكل فحص، والسبب جملة النموذج؛ والاسم يضيفه التطبيق. */
export const FLAG: ReviewFlag = {
  id: "f-price-2",
  line: 2,
  field: "unitCost",
  message: "سعر القطعة في هذا السطر بعيدٌ عمّا يُتوقّع لمثل هذا الصنف.",
  reason: "كرسي مكتبٍ دوّار بـ5,200 ريال للقطعة، والمعتاد بضع مئات؛ لعلّ السعر لعشر قطعٍ لا لقطعة.",
}

export const RETURN_INVOICE: ReturnInvoice = {
  id: "v38",
  number: "ش-0038",
  supplier: "مؤسسة الرواد للأثاث المكتبي",
  date: "2026-09-12",
  lines: [
    { lineId: "r1", item: "كرسي اجتماعات جلد", unit: "قطعة", purchased: 6, returned: 0, unitCost: 52000 },
    { lineId: "r2", item: "كرسي زائر بلا عجلات", unit: "قطعة", purchased: 12, returned: 2, unitCost: 14000 },
    { lineId: "r3", item: "رفّ معدني 5 أدوار", unit: "قطعة", purchased: 4, returned: 4, unitCost: 33000 },
  ],
}

export const CAMPAIGNS: CampaignCard[] = [
  { id: "c1", title: null, status: "DRAFT", budget: null, days: null, updated: "2026-10-08T11:40:00+03:00", imageAlt: "صورة حقيبة يد جلدية", tone: 1 },
  { id: "c2", title: "حقيبة ظهرٍ جلدية بنّية بخياطةٍ ظاهرة", status: "COPY_PROPOSED", budget: null, days: null, updated: "2026-10-08T10:00:00+03:00", imageAlt: "حقيبة ظهر جلدية بنية", tone: 2 },
  { id: "c3", title: "كوب قهوةٍ خزفيّ بمقبضٍ خشبي", status: "COPY_PROPOSED", budget: null, days: null, updated: "2026-10-07T12:00:00+03:00", imageAlt: "كوب خزفي أبيض", tone: 3 },
  { id: "c4", title: "مصباح مكتبٍ معدنيّ قابلٌ للطيّ", status: "COPY_APPROVED", budget: 75000, days: null, updated: "2026-10-08T09:00:00+03:00", imageAlt: "مصباح مكتب أسود", tone: 4 },
  { id: "c5", title: "ساعة حائطٍ خشبية بأرقامٍ عربية", status: "READY", budget: 150000, days: 14, updated: "2026-10-06T12:00:00+03:00", imageAlt: "ساعة حائط خشبية", tone: 5 },
  { id: "c6", title: "سجّادة صلاةٍ مبطّنة بلونٍ زيتي", status: "READY", budget: 200000, days: 10, updated: "2026-10-04T12:00:00+03:00", imageAlt: "سجادة صلاة خضراء", tone: 6 },
]

export const TICKETS: TicketRow[] = [
  { id: "t1042", number: 1042, customer: "نورة", subject: "تعطّل الدفع بالبطاقة عند الشراء", channel: "WEB", received: "2026-10-08T11:35:00+03:00", status: "DRAFT_READY", priority: "HIGH" },
  { id: "t1041", number: 1041, customer: "فهد", subject: "وصل طلبي وفيه كوبان مكسوران", channel: "WHATSAPP", received: "2026-10-08T11:00:00+03:00", status: "DRAFT_READY", priority: "NORMAL" },
  { id: "t1040", number: 1040, customer: "ريم", subject: "متى يصل طلبي رقم 88213؟", channel: "EMAIL", received: "2026-10-08T10:02:00+03:00", status: "DRAFT_READY", priority: "NORMAL" },
  { id: "t1039", number: 1039, customer: "خالد", subject: "تغيير عنوان التوصيل", channel: "WHATSAPP", received: "2026-10-08T09:10:00+03:00", status: "NEW", priority: "NORMAL" },
  { id: "t1038", number: 1038, customer: "سلمى", subject: "الفاتورة لا تظهر فيها الضريبة", channel: "EMAIL", received: "2026-10-08T07:00:00+03:00", status: "DRAFT_READY", priority: "NORMAL" },
  { id: "t1036", number: 1036, customer: "ماجد", subject: "رمز الدخول لا يصلني", channel: "WEB", received: "2026-10-07T16:00:00+03:00", status: "NEW", priority: "NORMAL" },
]

export const TICKET_TABS = [
  { id: "new", label: "جديدة", count: 6 },
  { id: "mine", label: "بانتظار قراري", count: 4 },
  { id: "customer", label: "بانتظار العميل", count: 3 },
  { id: "escalated", label: "مصعّدة", count: 1 },
]

export const TICKET_MESSAGES: TicketMessage[] = [
  {
    id: "m1",
    from: "CUSTOMER",
    at: "2026-10-08T11:00:00+03:00",
    text: "السلام عليكم، وصلني اليوم الطلب رقم 88190 وفيه كوبان مكسوران من أصل ستة. صوّرتهما في الرسالة السابقة. أريد استبدالهما أو استرجاع ثمنهما.",
  },
]

export const TICKET_DRAFT: TicketDraft = {
  text:
    "وعليكم السلام يا فهد، نأسف لوصول الكوبين مكسورين. نستبدلهما لك دون أي تكلفة، ويتواصل معك مندوب الشحن خلال يومَي عمل. وإن فضّلت استرجاع ثمنهما فاكتب لنا ذلك.",
  basis: "الطلب داخل مدة الاستبدال، والعميل يذكر أن الضرر مصوّر. المسودة تعرض الاستبدال أولاً كما تقول السياسة.",
  sources: [
    { id: "r12", title: "سياسة الاستبدال والاسترجاع (ر-12)" },
    { id: "r07", title: "تالفٌ عند الوصول (ر-07)" },
  ],
  check: ["أن الطلب 88190 وصل في آخر 14 يوماً.", "أن الصورتين في المحادثة تُظهران الكسر."],
}

export const NOTES: Note[] = [
  { id: "n1", text: "اتّصل بمؤسسة الرواد بخصوص تأخّر كراسي الاجتماعات.", created_at: "2026-10-08T10:15:00+03:00" },
  { id: "n2", text: "الجرد الشهري يوم الخميس بعد الظهر.", created_at: "2026-10-07T14:40:00+03:00" },
  { id: "n3", text: "اطلب ورق A4 قبل نهاية الأسبوع.", created_at: "2026-10-06T09:05:00+03:00" },
]

export const ASSISTANT_QUESTION = "كيف أسجّل مرتجعاً جزئياً من فاتورةٍ سابقة؟"
export const ASSISTANT_REPLY: AssistantReply = {
  answer:
    "من «المرتجعات» اختر «مرتجعٌ من فاتورة» وابحث برقم الفاتورة أو باسم المورد. في الخطوة الثانية زِد الكمية للصنف الذي تُرجعه وحده، واترك غيره صفراً. ثم اختر السبب وسجّل: ينقص الرصيد ويُخصم المبلغ من المصروفات.",
  note: null,
  remaining: 27,
}
