/*
 * أنواع بيانات الشاشات
 * ====================
 * كما يردّها الخادم (المبالغ بالهللة، والتواريخ ISO). الحقول التي تخصّ كل مهنةٍ تحدّدها
 * مواصفتها (inventory_spec.md، marketing_spec.md، support_spec.md)؛ هذه ما تحتاجه
 * المكوّنات لتعرض، ولا تحسب شيئاً يعتمده الخادم.
 */

export interface Item {
  id: string
  name: string
  sku: string | null
  unit: string
  /** سعر البيع بالهللة. */
  salePrice: number
  /** آخر سعر شراءٍ للوحدة، أو null لصنفٍ لم يُشترَ بعد. */
  lastCost: number | null
  onHand: number
  reorderLevel: number | null
}

export interface Supplier {
  id: string
  name: string
  vatNumber: string | null
}

/** تنبيهٌ من مراجعة سيمبول: مقترحٌ يُعرض، والقرار للمستخدم. */
export interface ReviewFlag {
  id: string
  /** رقم السطر من 1، أو null لتنبيهٍ على الفاتورة كلّها. */
  line: number | null
  /** الحقل الذي يعيد إليه «عدّل». */
  field: "item" | "quantity" | "unitCost" | "supplier" | "number" | "date"
  message: string
  reason: string
  evidence?: string[]
}

export interface InvoiceRow {
  id: string
  number: string
  supplier: string
  date: string
  gross: number
  lines: number
  status: "RECORDED" | "PARTLY_RETURNED" | "RETURNED"
}

/** قيدٌ في دفتر المشتريات (inventory_spec §3.13): شراء، أو مرتجعٌ يخصم، أو قيدٌ عكسي. */
export interface ExpenseRow {
  id: string
  /** «ش-0042»، «ر-0003»، «ع-0001». */
  number: string
  date: string
  kind: "PURCHASE" | "RETURN" | "REVERSAL"
  supplier: string
  /** قبل الضريبة بالهللة؛ سالبٌ للمرتجع والعكسي. */
  net: number
  vat: number
}

export interface CampaignCard {
  id: string
  title: string | null
  status: "DRAFT" | "COPY_PROPOSED" | "COPY_APPROVED" | "READY"
  budget: number | null
  days: number | null
  updated: string
  imageAlt: string
  tone: number
}

export interface TicketRow {
  id: string
  number: number
  customer: string
  subject: string
  channel: "EMAIL" | "WHATSAPP" | "WEB"
  received: string
  status: "NEW" | "DRAFT_READY" | "WAITING_CUSTOMER" | "ESCALATED" | "CLOSED"
  priority: "NORMAL" | "HIGH"
}

export interface TicketMessage {
  id: string
  from: "CUSTOMER" | "EMPLOYEE"
  text: string
  at: string
}

export interface TicketDraft {
  text: string
  /** لماذا كتب سيمبول ما كتب. */
  basis: string
  /** الردود الجاهزة التي استند إليها. */
  sources: { id: string; title: string }[]
  /** ما لا يعرفه سيمبول ويحتاج الموظف أن يتحقّق منه. */
  check: string[]
}
