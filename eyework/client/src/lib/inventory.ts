/*
 * بوابة أمين المخزون: ما يردّه الخادم وما يُطلب منه
 * ==================================================
 * كل ما تعرضه الشاشات يأتي من /api/inventory كما هو: المبالغ بالهللة والكميات بالألف
 * (milli: 2500 = 2.5)، والتواريخ ISO، وأرقام المستندات بحروفها («ش-0007»، «ص-00012») من الخادم.
 * كل كتابةٍ مشروطةٌ بما رآه صاحبها (`expected_row_version`)، والضغطة المكرّرة على سندٍ أو جلسةٍ
 * تحمل `client_token` نفسه فتعيد ما سُجّل. والمراجعة الذكية عبر المسار المشترك /api/ai/review.
 */

import { api, type ApiResult } from "./api"

export const BASE = "#/inventory"
const API = "/api/inventory"

/* ── الأنواع ─────────────────────────────────────────────────────── */

export type Unit = "PIECE" | "BOX" | "CARTON" | "PACK" | "PALLET" | "KG" | "LITRE" | "METRE" | "SERVICE"
export type VatCategory = "S" | "Z" | "E" | "O"
export type ItemKind = "STOCK" | "SERVICE"
export type PurchaseStatus = "DRAFT" | "POSTED" | "REVERSED"
export type ReturnStatus = "DRAFT" | "POSTED"
export type CountStatus = "OPEN" | "POSTED" | "CANCELLED"
export type CountScope = "ALL" | "CATEGORY" | "LOW" | "SELECTED"
export type VoucherKind = "OPENING" | "ISSUE" | "COUNT"
export type MovementKind = "PURCHASE_IN" | "OPENING_IN" | "COUNT_IN" | "RETURN_OUT" | "REVERSAL_OUT" | "ISSUE_OUT" | "COUNT_OUT"

export interface Coded {
  code: string
  name: string
}

/** `inventory` في /api/choices: الوحدات والفئات والأسباب والحدود، من الخادم وحده. */
export interface InventoryChoices {
  units: { code: Unit; name: string; decimals: boolean }[]
  kinds: { code: ItemKind; name: string }[]
  vat_categories: { code: VatCategory; name: string; rate_bp: number }[]
  return_reasons: Coded[]
  reversal_reasons: Coded[]
  issue_reasons: Coded[]
  count_reasons: { SHORTAGE: Coded[]; SURPLUS: Coded[] }
  count_scopes: Coded[]
  document_prefixes: Record<string, string>
  page_sizes: number[]
  limits: {
    lines_per_document: number
    open_drafts: number
    items: number
    suppliers: number
    categories: number
    reps_per_supplier: number
    voucher_days_back: number
    expenses_max_days: number
  }
}

export interface Paged<T> {
  items: T[]
  page: number
  pages: number
  total: number
}

export interface Settings {
  cost_includes_vat: boolean
  cost_basis_locked: boolean
  store_name: string
  store_location: string | null
  row_version: number
}

export interface Rep {
  id: string
  supplier_id: string
  name: string
  mobile: string | null
  is_default: boolean
  is_active: boolean
  row_version: number
}

export interface Supplier {
  id: string
  name: string
  vat_number: string | null
  cr_number: string | null
  phone: string | null
  note: string | null
  is_active: boolean
  row_version: number
  reps?: Rep[]
  /** عند الإنشاء: مورّدون آخرون بالرقم الضريبي نفسه. */
  same_vat_number?: Supplier[]
}

export interface Category {
  id: string
  name: string
  is_active: boolean
  row_version: number
  items?: number
}

/** ما يحتاجه منتقي المنتج وسطر الفاتورة. */
export interface ItemOption {
  id: string
  number: number
  code: string
  name: string
  unit: Unit
  unit_name: string
  kind: ItemKind
  vat_category: VatCategory
  barcode: string | null
  supplier_code: string | null
  price_halalas: number
  /** السعر بأساس المسودة: شاملاً إن كانت أسعارها شاملة. */
  price_entry_halalas: number
  on_hand_milli: number
  last_price_halalas: number | null
}

export interface Item extends ItemOption {
  avg_cost_halalas: number | null
  stock_value_halalas: number
  reorder_level_milli: number | null
  target_level_milli: number | null
  below_reorder: boolean
  suggested_order_milli: number | null
  category: { id: string; name: string } | null
  preferred_supplier: { id: string; name: string; rep_name: string | null; rep_mobile: string | null } | null
  selling_price_halalas: number | null
  selling_price_includes_vat: boolean
  vat_exemption_reason: string | null
  note: string | null
  last_counted_on: string | null
  last_movement_at: string | null
  is_active: boolean
  row_version: number
  /** عند الإنشاء: منتجاتٌ بأسماءٍ قريبة. */
  similar?: { id: string; name: string; unit: Unit }[]
}

export interface ItemDetail extends Item {
  recent_purchases: { document: string; invoice_date: string; supplier_name: string | null; quantity_milli: number; unit_price_halalas: number | null }[]
  reorder_suggestion_milli: number | null
  counts: { session: string | null; occurred_on: string; book_milli: number; counted_milli: number; reason: string | null }[]
}

export interface Movement {
  kind: MovementKind
  occurred_on: string
  document: string
  in_milli: number
  out_milli: number
  unit_cost_halalas: number | null
  value_halalas: number
  on_hand_after_milli: number
  value_after_halalas: number
  reason: string | null
}

export interface RuleFlag {
  key: string
  source: "RULE"
  code: string
  line_no: number | null
  level: "high" | "normal"
  /** النصّ جاهزاً بنداء صاحب الحساب من الخادم. */
  text: string
}

export interface AiFlag {
  id: string
  check: string
  severity: string
  field: string | null
  line: number | null
  headline: string
  suggestion: string | null
  evidence: string[]
  decision: "EDIT" | "PROCEED" | "UNDO" | null
}

export interface Flags {
  row_version: number
  flags: RuleFlag[]
  ai: AiFlag[]
  digest: string | null
}

export interface Totals {
  net: number
  vat: number
  gross: number
}

export interface PurchaseLine {
  line_no: number
  item: ItemOption
  quantity_milli: number
  received_quantity_milli: number | null
  unit_price_halalas: number
  discount_halalas: number
  vat_category: VatCategory
  amount_halalas: number
  net_halalas: number
  vat_halalas: number
  remaining_milli: number
}

export interface Purchase {
  id: string
  status: PurchaseStatus
  row_version: number
  number: number | null
  label: string | null
  supplier: { id: string; name: string; vat_number: string | null; is_active: boolean } | null
  rep: { id: string; name: string; mobile: string | null } | null
  supplier_invoice_no: string | null
  invoice_date: string | null
  received_on: string | null
  delivery_note_no: string | null
  prices_include_vat: boolean
  printed_total_halalas: number | null
  printed_vat_halalas: number | null
  note: string | null
  lines: PurchaseLine[]
  totals: Totals
  missing: string[]
  posted_at: string | null
  acknowledged: RuleFlag[]
  returns: { id: string; number: number | null; status: ReturnStatus; label: string | null }[]
  returnable: boolean
  reversal: { number: number; label: string; at: string; reason: string; note: string | null } | null
  updated_at: string
}

export interface PurchaseRow {
  id: string
  status: PurchaseStatus
  row_version: number
  number: number | null
  label: string | null
  supplier_name: string | null
  supplier_invoice_no: string | null
  invoice_date: string | null
  total_halalas: number | null
  lines: number
  updated_at: string
  posted_at: string | null
  reversal_number: number | null
}

export interface ReturnLine {
  line_no: number
  item: ItemOption
  bought_milli: number
  remaining_milli: number
  quantity_milli: number
  unit_price_halalas: number
  net_halalas: number | null
  vat_halalas: number | null
}

export interface Return {
  id: string
  status: ReturnStatus
  row_version: number
  number: number | null
  label: string | null
  purchase: {
    id: string
    number: number
    status: PurchaseStatus
    label: string
    invoice_date: string | null
    supplier_invoice_no: string | null
    supplier_name: string | null
    supplier_id: string
    total_halalas: number | null
  }
  rep: { id: string; name: string; mobile: string | null } | null
  return_date: string | null
  reason: string | null
  note: string | null
  lines: ReturnLine[]
  totals: Totals | null
  posted_at: string | null
  credit_note: { number: string; date: string } | null
  credit_note_due: string | null
  acknowledged: RuleFlag[]
  updated_at: string
}

export interface ReturnRow {
  id: string
  status: ReturnStatus
  row_version: number
  number: number | null
  label: string | null
  purchase_label: string
  supplier_name: string | null
  return_date: string | null
  reason: string | null
  total_halalas: number | null
  credit_note_no: string | null
  credit_note_due: string | null
  credit_note_overdue: boolean
  updated_at: string
}

export interface Voucher {
  id: string
  number: number
  label: string
  kind: VoucherKind
  item: ItemOption
  quantity_milli: number
  on_hand_before_milli: number | null
  unit_cost_halalas: number | null
  reason: string | null
  note: string | null
  occurred_on: string
  count_label: string | null
  created_at: string
  replayed: boolean
}

export interface CountLine {
  line_no: number
  /** رصيد المنتج مخفيٌّ كذلك في العدّ المغلق حتى يُعدّ. */
  item: Omit<ItemOption, "on_hand_milli"> & { on_hand_milli: number | null }
  /** مخفيٌّ في العدّ المغلق حتى يُعدّ. */
  book_milli: number | null
  counted_milli: number | null
  difference_milli: number | null
  unit_cost_halalas: number | null
  reason: string | null
  note: string | null
  added_during_count: boolean
  counted_at: string | null
  /** تحرّك رصيده بعد اللقطة: يُحدَّث ويُعاد عدّه. */
  changed: boolean
  needs_cost: boolean
  /** تكلفة الوحدة تُطلب لعدٍّ موجب: رصيد المنتج صفر (لا يُرسل الرصيد نفسه في العدّ المغلق). */
  asks_cost: boolean
  posted: boolean
}

export interface CountSession {
  id: string
  number: number
  label: string
  status: CountStatus
  scope: CountScope
  scope_name: string
  category: { id: string; name: string } | null
  blind: boolean
  note: string | null
  snapshot_at: string
  last_purchase_label: string | null
  last_voucher_label: string | null
  items_total: number
  counted_so_far: number
  changed_lines: number
  items_counted: number | null
  items_matched: number | null
  posted_at: string | null
  cancelled_at: string | null
  row_version: number
  lines: CountLine[]
  updated_at: string
  /** بعد «حدّث»: عدد الأسطر التي أُعيد رصيدها الدفتري. */
  refreshed?: number
  replayed?: boolean
}

export interface CountRow {
  id: string
  number: number
  label: string
  status: CountStatus
  scope: CountScope
  scope_name: string
  blind: boolean
  items_total: number
  counted_so_far: number
  items_counted: number | null
  items_matched: number | null
  snapshot_at: string
  posted_at: string | null
  cancelled_at: string | null
  row_version: number
}

export interface LedgerTotals {
  purchases: Totals
  returns: Totals
  reversals: Totals
  net: Totals
}

export interface LedgerEntry {
  date: string
  kind: "PURCHASE" | "RETURN" | "REVERSAL"
  document: string
  purchase_id: string
  return_id: string | null
  supplier_name: string | null
  supplier_invoice_no: string | null
  net: number
  vat: number
  gross: number
}

export interface Expenses {
  from: string
  to: string
  totals: LedgerTotals
  entries: Paged<LedgerEntry>
}

export interface Summary {
  today: string
  month: string
  month_totals: LedgerTotals
  stock_value: number
  settings: Settings | null
  attention: {
    drafts: number
    purchase_drafts: number
    return_drafts: number
    low_stock: number
    awaiting_credit_note: number
    credit_note_overdue: number
    uncounted: number
    short_delivery: number
    open_count: { id: string; label: string } | null
  }
  counts: { items: number; suppliers: number; movements: number }
}

/** جواب /api/ai/review: الموضوع ببصمته، وحال المراجعة، وملاحظات سيمبول. */
export interface ReviewAnswer {
  subject: { kind: string; id: string; digest: string }
  review: { status: "DONE" | "PENDING" | "UNAVAILABLE"; reason: string | null; message: string | null }
  flags: AiFlag[]
}

/* ── الكلمات ─────────────────────────────────────────────────────── */

export const PURCHASE_STATUS: Record<PurchaseStatus, string> = { DRAFT: "مسودة", POSTED: "مسجّلة", REVERSED: "معكوسة" }
export const RETURN_STATUS: Record<ReturnStatus, string> = { DRAFT: "مسودة", POSTED: "مسجّل" }
export const COUNT_STATUS: Record<CountStatus, string> = { OPEN: "مفتوحة", POSTED: "مرحّلة", CANCELLED: "ملغاة" }
export const VOUCHER_KIND: Record<VoucherKind, string> = { OPENING: "رصيد افتتاحي", ISSUE: "صرف", COUNT: "جرد" }
export const MOVEMENT_KIND: Record<MovementKind, string> = {
  PURCHASE_IN: "شراء", OPENING_IN: "رصيد افتتاحي", COUNT_IN: "زيادة جرد", RETURN_OUT: "مرتجع", REVERSAL_OUT: "قيد عكسي",
  ISSUE_OUT: "صرف", COUNT_OUT: "عجز جرد",
}
export const LEDGER_KIND: Record<LedgerEntry["kind"], string> = { PURCHASE: "شراء", RETURN: "مرتجع", REVERSAL: "قيد عكسي" }
/** ما ينقص المسودة قبل التسجيل، بكلماته. */
export const MISSING: Record<string, string> = {
  supplier: "المورّد", supplier_invoice_no: "رقم فاتورة المورّد", invoice_date: "تاريخ الفاتورة",
  printed_total: "الإجمالي المكتوب على الفاتورة", lines: "سطرٌ واحد على الأقل",
}

export function codeName(list: Coded[], code: string | null): string {
  return list.find((entry) => entry.code === code)?.name ?? code ?? ""
}

/* ── المسارات ────────────────────────────────────────────────────── */

export const purchaseRoute = (id: string, suffix = "") => `${BASE}/p/${id}${suffix}`
export const returnRoute = (id: string, suffix = "") => `${BASE}/r/${id}${suffix}`
export const itemRoute = (id: string, suffix = "") => `${BASE}/i/${id}${suffix}`
export const supplierRoute = (id: string, suffix = "") => `${BASE}/s/${id}${suffix}`
export const countRoute = (id: string, suffix = "") => `${BASE}/c/${id}${suffix}`

/* ── الكميات بالألف ──────────────────────────────────────────────── */

const DIGITS: Record<string, string> = {
  "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
  "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}

function latin(text: string): string {
  const value = text.replace(/[٠-٩۰-۹]/g, (d) => DIGITS[d] ?? d).replace(/٫/g, ".").replace(/٬/g, ",").replace(/\s/g, "")
  // الفاصلة فاصلة آلافٍ وحدها (1,250): «2,5» من لوحةٍ فاصلتها العشرية فاصلة خطأٌ يُرفض، لا 25.
  return /^\d{1,3}(,\d{3})+(\.\d*)?$/.test(value) ? value.replace(/,/g, "") : value
}

/**
 * «2.5» → 2500؛ وبلا كسورٍ للوحدات التي تُعدّ؛ أو null. الحدّ الأعلى مليار وحدة. والصفر بـ`zero`
 * وحده (العدّ والمرتجع وحدّ الطلب)، بالأرقام العربية واللاتينية سواء.
 */
export function parseMilli(text: string, decimals: boolean, max = 1_000_000_000_000, { zero = false }: { zero?: boolean } = {}): number | null {
  const value = latin(text.trim())
  if (!(decimals ? /^\d{1,9}(\.\d{1,3})?$/ : /^\d{1,9}$/).test(value)) return null
  const [whole, fraction = ""] = value.split(".")
  const milli = Number(whole) * 1000 + Number(fraction.padEnd(3, "0"))
  return milli >= (zero ? 0 : 1) && milli <= max ? milli : null
}

const group = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 })

/** 2500 → «2.5»، و12000 → «12»، و1250000 → «1,250». */
export function formatMilli(milli: number): string {
  return group.format(milli / 1000)
}

/** القيمة كما تُكتب في حقل: بلا فواصل آلاف. */
export function milliInput(milli: number | null): string {
  return milli === null ? "" : formatMilli(milli).replace(/,/g, "")
}

export function quantityText(milli: number, unitName: string): string {
  return `${formatMilli(milli)} ${unitName}`
}

/* ── الأشهر ──────────────────────────────────────────────────────── */

const monthName = new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", { month: "long", year: "numeric" })

/** «2026-10» → «أكتوبر 2026». */
export function monthLabel(month: string): string {
  const [year, m] = month.split("-").map(Number)
  return monthName.format(new Date(year, m - 1, 1))
}

/** أوّل الشهر وآخره: ما يُطلب من /expenses. */
export function monthRange(month: string): { from: string; to: string } {
  const [year, m] = month.split("-").map(Number)
  const last = new Date(year, m, 0).getDate()
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}` }
}

export function shiftMonth(month: string, delta: number): string {
  const [year, m] = month.split("-").map(Number)
  const index = year * 12 + (m - 1) + delta
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`
}

/* ── الطلبات ─────────────────────────────────────────────────────── */

type Query = Record<string, string | number | boolean | null | undefined>

function url(path: string, query: Query = {}): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${API}${path}?${text}` : `${API}${path}`
}

const get = <T,>(path: string, query?: Query) => api<T>("GET", url(path, query))
const post = <T,>(path: string, json: unknown) => api<T>("POST", url(path), { json })
const put = <T,>(path: string, json: unknown) => api<T>("PUT", url(path), { json })
const patch = <T,>(path: string, json: unknown) => api<T>("PATCH", url(path), { json })

export const summary = () => get<Summary>("/summary")
export const getSettings = () => get<Settings>("/settings")
export const putSettings = (body: { cost_includes_vat: boolean; store_name?: string | null; store_location?: string | null; expected_row_version?: number }) =>
  put<Settings>("/settings", body)

export const listSuppliers = (q: string, page: number, size: number, archived = false) =>
  get<Paged<Supplier>>("/suppliers", { q, page, size, archived: archived || undefined })
export const getSupplier = (id: string) => get<Supplier>(`/suppliers/${id}`)
export const createSupplier = (body: { name: string; vat_number?: string | null; cr_number?: string | null; phone?: string | null; note?: string | null }) =>
  post<Supplier>("/suppliers", body)
export const patchSupplier = (id: string, rowVersion: number, fields: object) =>
  patch<Supplier>(`/suppliers/${id}`, { expected_row_version: rowVersion, ...fields })
export const createRep = (supplierId: string, body: { name: string; mobile?: string | null; is_default?: boolean }) =>
  post<Rep>(`/suppliers/${supplierId}/reps`, body)
export const patchRep = (supplierId: string, repId: string, rowVersion: number, fields: object) =>
  patch<Rep>(`/suppliers/${supplierId}/reps/${repId}`, { expected_row_version: rowVersion, ...fields })

export const listCategories = (archived = false) => get<{ items: Category[] }>("/categories", { archived: archived || undefined })
export const createCategory = (name: string) => post<Category>("/categories", { name })
export const patchCategory = (id: string, rowVersion: number, fields: object) =>
  patch<Category>(`/categories/${id}`, { expected_row_version: rowVersion, ...fields })

export type ItemFilter = "all" | "low" | "service" | "archived" | "uncounted"
export const listItems = (q: string, filter: ItemFilter, categoryId: string | null, page: number, size: number) =>
  get<Paged<Item> & { stock_value_halalas: number }>("/items", { q, filter, category_id: categoryId, page, size })
export const searchItems = (q: string, purchaseId: string | null = null) =>
  get<{ items: ItemOption[]; create: { name: string } | null }>("/items/search", { q, purchase_id: purchaseId })
export const createItem = (body: object) => post<Item>("/items", body)
export const getItem = (id: string) => get<ItemDetail>(`/items/${id}`)
export const itemMovements = (id: string, page: number, size: number) => get<Paged<Movement>>(`/items/${id}/movements`, { page, size })
export const patchItem = (id: string, rowVersion: number, fields: object) =>
  patch<Item>(`/items/${id}`, { expected_row_version: rowVersion, ...fields })

export const listPurchases = (status: PurchaseStatus | "RETURNABLE" | null, q: string, page: number, size: number) =>
  get<Paged<PurchaseRow>>("/purchases", { status: status?.toLowerCase(), q, page, size })
export const createPurchase = (body: object = {}) => post<Purchase>("/purchases", body)
export const getPurchase = (id: string) => get<Purchase>(`/purchases/${id}`)
export const patchPurchase = (id: string, rowVersion: number, fields: object) =>
  patch<Purchase>(`/purchases/${id}`, { expected_row_version: rowVersion, ...fields })
export const discardPurchase = (id: string, rowVersion: number) => post<null>(`/purchases/${id}/discard`, { expected_row_version: rowVersion })
export const addLine = (id: string, rowVersion: number, body: object) =>
  post<Purchase>(`/purchases/${id}/lines`, { expected_row_version: rowVersion, ...body })
export const patchLine = (id: string, lineNo: number, rowVersion: number, fields: object) =>
  patch<Purchase>(`/purchases/${id}/lines/${lineNo}`, { expected_row_version: rowVersion, ...fields })
export const removeLine = (id: string, lineNo: number, rowVersion: number) =>
  post<Purchase>(`/purchases/${id}/lines/${lineNo}/remove`, { expected_row_version: rowVersion })
export const purchaseFlags = (id: string) => get<Flags>(`/purchases/${id}/flags`)
export const postPurchase = (id: string, rowVersion: number, acknowledged: string[]) =>
  post<Purchase>(`/purchases/${id}/post`, { expected_row_version: rowVersion, acknowledged })
export const reversePurchase = (id: string, rowVersion: number, reason: string, note: string | null) =>
  post<Purchase>(`/purchases/${id}/reverse`, { expected_row_version: rowVersion, reason, note })

export const listReturns = (status: ReturnStatus | null, awaitingCreditNote: boolean, page: number, size: number) =>
  get<Paged<ReturnRow>>("/returns", { status: status?.toLowerCase(), awaiting_credit_note: awaitingCreditNote || undefined, page, size })
export const createReturn = (purchaseId: string, repId: string | null) => post<Return>("/returns", { purchase_id: purchaseId, rep_id: repId })
export const getReturn = (id: string) => get<Return>(`/returns/${id}`)
export const patchReturn = (id: string, rowVersion: number, fields: object) =>
  patch<Return>(`/returns/${id}`, { expected_row_version: rowVersion, ...fields })
export const discardReturn = (id: string, rowVersion: number) => post<null>(`/returns/${id}/discard`, { expected_row_version: rowVersion })
export const putReturnLine = (id: string, lineNo: number, rowVersion: number, quantityMilli: number) =>
  put<Return>(`/returns/${id}/lines/${lineNo}`, { expected_row_version: rowVersion, quantity_milli: quantityMilli })
export const returnFlags = (id: string) => get<Flags>(`/returns/${id}/flags`)
export const postReturn = (id: string, rowVersion: number, acknowledged: string[]) =>
  post<Return>(`/returns/${id}/post`, { expected_row_version: rowVersion, acknowledged })
export const putCreditNote = (id: string, rowVersion: number, number: string, date: string) =>
  put<Return>(`/returns/${id}/credit-note`, { expected_row_version: rowVersion, number, date })

export const openingVoucher = (body: { client_token: string; item_id: string; quantity_milli: number; unit_cost_halalas: number; occurred_on: string }) =>
  post<Voucher>("/stock/opening", body)
export const issueVoucher = (body: { client_token: string; item_id: string; quantity_milli: number; reason: string; note: string | null; occurred_on: string }) =>
  post<Voucher>("/stock/issue", body)
export const countVoucher = (body: {
  client_token: string
  item_id: string
  counted_milli: number
  expected_on_hand_milli: number
  unit_cost_halalas: number | null
  reason: string | null
  note: string | null
  occurred_on: string
}) => post<Voucher>("/stock/count", body)
export const listVouchers = (page: number, size: number) => get<Paged<Voucher>>("/vouchers", { page, size })

export const listCounts = (page: number, size: number) => get<Paged<CountRow>>("/counts", { page, size })
export const openCount = (body: { client_token: string; scope: CountScope; category_id?: string | null; item_ids?: string[] | null; blind: boolean; note?: string | null }) =>
  post<CountSession>("/counts", body)
export const getCount = (id: string) => get<CountSession>(`/counts/${id}`)
export const patchCount = (id: string, rowVersion: number, fields: { blind?: boolean; note?: string | null }) =>
  patch<CountSession>(`/counts/${id}`, { expected_row_version: rowVersion, ...fields })
export const setCountLine = (id: string, itemId: string, rowVersion: number, fields: { counted_milli: number | null; unit_cost_halalas?: number | null; reason?: string | null; note?: string | null }) =>
  put<CountSession>(`/counts/${id}/lines/${itemId}`, { expected_row_version: rowVersion, ...fields })
export const addCountItem = (id: string, itemId: string) => post<CountSession>(`/counts/${id}/items`, { item_id: itemId })
export const refreshCount = (id: string) => post<CountSession>(`/counts/${id}/refresh`, {})
export const postCount = (id: string, rowVersion: number, occurredOn: string) =>
  post<CountSession>(`/counts/${id}/post`, { expected_row_version: rowVersion, occurred_on: occurredOn })
export const cancelCount = (id: string, rowVersion: number) => post<CountSession>(`/counts/${id}/cancel`, { expected_row_version: rowVersion })

export const expenses = (from: string, to: string, page: number, size: number) => get<Expenses>("/expenses", { from, to, page, size })
export const vatTool = (amountHalalas: number, basis: "net" | "gross", category: VatCategory = "S") =>
  get<{ net_halalas: number; vat_halalas: number; gross_halalas: number }>("/tools/vat", { amount_halalas: amountHalalas, basis, category })

/** ضغطة «راجِع»: الأداة STOCK_REVIEW على فاتورةٍ أو مرتجع، وتنتظر الجواب أو «غير متاح». */
export const reviewDocument = (kind: "PURCHASE" | "RETURN", id: string, rowVersion: number) =>
  api<ReviewAnswer>("POST", "/api/ai/review", { json: { feature: "STOCK_REVIEW", subject_kind: kind, subject_id: id, expected_row_version: rowVersion } })
export const decideFlag = (flagId: string, choice: "EDIT" | "PROCEED" | "UNDO", digest: string) =>
  api<AiFlag>("POST", `/api/ai/flags/${flagId}/decision`, { json: { choice, digest } })

export type Result<T> = ApiResult<T>

/** معرّفٌ للضغطة: الضغطة المكرّرة بالمعرّف نفسه تعيد ما سُجّل ولا تسجّل مرّتين. */
export function clientToken(): string {
  return crypto.randomUUID()
}
