/*
 * فاتورة الشراء
 * =============
 * ما طلبه المالك: «فاتورة شراء» من مورّدٍ ومندوبه، بمنتجاتٍ تُختار من منسدلٍ أو تُنشأ بسعرها،
 * وتظهر المجاميع، وتُسجَّل في المصاريف. المسودة تعيش في الخادم: كل حقلٍ يُحفظ حين يُغادَر، وكل
 * سطرٍ حين يُضاف، فلا يضيع شيءٌ بإغلاق الصفحة، وتعود من «يحتاج انتباهك».
 *
 *   • الحجم العادي: رأس الفاتورة، ثم الأسطر المحفوظة وسطرٌ يُحرَّر، ثم المجموع؛ الصفحة تمرّ.
 *   • الحجم الكبير: أربع خطوات بلا تمرير — المورّد، والفاتورة، والمبالغ، والمنتجات سطراً سطراً.
 *   • «راجِع وسجّل» يحفظ ما في اليد ويفتح المراجعة (review.tsx).
 *   • الفاتورة المسجَّلة تُقرأ ولا تُعدَّل: منها مرتجع، أو قيدٌ عكسي كامل.
 */

import * as React from "react"
import { ClipboardCheck, PencilLine, Plus, ReceiptText, Save, Trash, Undo2, X } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Slots } from "@/components/shell/slots"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Combobox, type ComboboxOption } from "@/components/ui/combobox"
import { DataTable } from "@/components/ui/data-table"
import { Dialog } from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { Tabs } from "@/components/ui/tabs"
import { formatDay } from "@/lib/format"
import {
  MISSING, PURCHASE_STATUS, codeName, formatMilli, milliInput, parseMilli,
  type InventoryChoices, type ItemOption, type Paged, type Purchase, type PurchaseLine, type PurchaseRow, type PurchaseStatus, type Rep,
} from "@/lib/inventory"
import { formatAmount, parseAmount } from "@/lib/money"
import { LIST_PAGE, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

import { Facts, GazeHost, GazeSlot, Money, Picker, Qty, useOpenReport, type Fact } from "./common"
import type { Fail } from "./setup"

/* ── القائمة ─────────────────────────────────────────────────────── */

const STATUS_TONE: Record<PurchaseStatus, "info" | "success" | "neutral"> = { DRAFT: "info", POSTED: "success", REVERSED: "neutral" }

export function PurchasesScreen({ data, status, onStatus, query, onQuery, page, onPage, onOpen, onNew, onBack }: {
  data: Paged<PurchaseRow> | null
  status: PurchaseStatus | "all"
  onStatus: (status: PurchaseStatus | "all") => void
  query: string
  onQuery: (query: string) => void
  page: number
  onPage: (page: number) => void
  onOpen: (row: PurchaseRow) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  return (
    <Screen
      title="فواتير الشراء"
      back={gaze ? undefined : { id: "purchases-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "purchases-new", label: "فاتورة جديدة", icon: Plus, onClick: onNew }}
    >
      <Field label="ابحث" hint={gaze ? undefined : "باسم المورّد أو رقم فاتورته أو رقمنا."}>
        <Input id="purchases-search" type="search" autoComplete="off" value={query} onChange={(event) => onQuery(event.target.value)} />
      </Field>
      <Tabs
        items={[{ id: "all", label: "الكل" }, { id: "DRAFT", label: "مسودات" }, { id: "POSTED", label: "مسجّلة" }, { id: "REVERSED", label: "معكوسة" }]}
        value={status}
        onValueChange={(id) => onStatus(id as PurchaseStatus | "all")}
        label="الحالة"
      >
        {data === null ? null : (
          <DataTable<PurchaseRow>
            caption="فواتير الشراء"
            rows={data.items}
            rowKey={(row) => row.id}
            columns={[
              { id: "label", header: "الرقم", cell: (row) => <span className="num">{row.label ?? "مسودة"}</span> },
              { id: "supplier", header: "المورّد", cell: (row) => row.supplier_name ?? "" },
              { id: "no", header: "فاتورة المورّد", cell: (row) => <span className="num">{row.supplier_invoice_no ?? ""}</span> },
              { id: "date", header: "التاريخ", cell: (row) => (row.invoice_date ? formatDay(row.invoice_date) : "") },
              { id: "status", header: "الحالة", cell: (row) => <Badge tone={STATUS_TONE[row.status]}>{PURCHASE_STATUS[row.status]}</Badge> },
              { id: "total", header: "الإجمالي", numeric: true, cell: (row) => (row.total_halalas === null ? "" : formatAmount(row.total_halalas)) },
            ]}
            primary={(row) => row.supplier_name ?? "بلا مورّد بعد"}
            secondary={(row) => `${row.label ?? PURCHASE_STATUS[row.status]}${row.supplier_invoice_no ? ` · ${row.supplier_invoice_no}` : ""}${row.invoice_date ? ` · ${formatDay(row.invoice_date)}` : ""}`}
            trailing={(row) => (
              <>
                {row.total_halalas === null ? null : <span className="num font-bold" dir="ltr">{formatAmount(row.total_halalas)}</span>}
                <Badge tone={STATUS_TONE[row.status]} className="gaze:hidden">{PURCHASE_STATUS[row.status]}</Badge>
              </>
            )}
            onOpen={onOpen}
            openLabel={(row) => `افتح ${row.label ?? "المسودة"}`}
            pageSize={LIST_PAGE}
            page={page}
            onPageChange={onPage}
            total={data.total}
            empty={<EmptyState icon={ReceiptText} title={query ? "لا فاتورة تطابق" : "لا فواتير بعد"} action={query ? undefined : <Button variant="primary" icon={Plus} onClick={onNew}>فاتورة شراء جديدة</Button>} />}
          />
        )}
      </Tabs>
    </Screen>
  )
}

/* ── المسودة ─────────────────────────────────────────────────────── */

export interface HeaderFields {
  supplier_id?: string | null
  rep_id?: string | null
  supplier_invoice_no?: string | null
  invoice_date?: string | null
  received_on?: string | null
  delivery_note_no?: string | null
  prices_include_vat?: boolean
  printed_total_halalas?: number | null
  printed_vat_halalas?: number | null
  note?: string | null
}

export interface LineBody {
  item_id: string
  quantity_milli: number
  unit_price_halalas: number
  discount_halalas: number
  received_quantity_milli: number | null
}

export interface QuickItem {
  name: string
  unit: string
  price_halalas: number
  vat_category: string
}

export interface QuickSupplier {
  name: string
  vat_number: string | null
}

export interface PurchaseEditorProps {
  purchase: Purchase
  choices: InventoryChoices
  today: string
  supplierOptions: ComboboxOption[]
  onSupplierQuery: (query: string) => void
  /** مندوبو المورّد المختار، أو null وهم يُقرؤون. */
  reps: Rep[] | null
  /** المورّد المختار الآن (قبل حفظه في الحجم الكبير): تُحمَّل مندوبوه ليُقترح افتراضيُّهم. */
  onSupplierChosen: (supplierId: string | null) => void
  itemOptions: ComboboxOption[]
  /** المنتجات المطابقة بأسعارها بأساس المسودة. */
  items: ItemOption[]
  onItemQuery: (query: string) => void
  onHeader: (fields: HeaderFields) => Promise<Fail>
  onCreateSupplier: (body: QuickSupplier) => Promise<{ option: ComboboxOption } | { fail: NonNullable<Fail> }>
  onCreateItem: (body: QuickItem) => Promise<{ item: ItemOption } | { fail: NonNullable<Fail> }>
  onAddLine: (body: LineBody) => Promise<Fail>
  onPatchLine: (lineNo: number, body: LineBody) => Promise<Fail>
  onRemoveLine: (lineNo: number) => Promise<Fail>
  onDiscard: () => Promise<Fail>
  onReview: () => void
  onBack: () => void
  /** يفتح على سطرٍ بعينه («عدّل» من تنبيه). */
  focusLine?: number | null
}

interface LineDraft {
  lineNo: number | null
  item: ComboboxOption | null
  query: string
  quantity: string
  price: string
  discount: string
  received: string
}

const EMPTY_LINE: LineDraft = { lineNo: null, item: null, query: "", quantity: "1", price: "", discount: "", received: "" }
const STEPS = [
  { id: "supplier", label: "المورّد" },
  { id: "invoice", label: "الفاتورة" },
  { id: "amounts", label: "المبالغ" },
  { id: "lines", label: "المنتجات" },
]

function money(halalas: number | null): string {
  return halalas === null ? "" : formatAmount(halalas).replace(/,/g, "")
}

function itemOption(item: ItemOption): ComboboxOption {
  return { value: item.id, label: item.name, description: `${item.code} · ${item.unit_name}`, meta: `${formatAmount(item.price_entry_halalas)} ر.س` }
}

function lineDraft(line: PurchaseLine): LineDraft {
  return {
    lineNo: line.line_no, item: itemOption(line.item), query: line.item.name, quantity: milliInput(line.quantity_milli),
    price: money(line.unit_price_halalas), discount: line.discount_halalas ? money(line.discount_halalas) : "",
    received: milliInput(line.received_quantity_milli),
  }
}

/*
 * زرّا الإنشاء السريع. في الحجم الكبير يُعرضان في شريط الإجراءات لا في البطاقة: الخيار «جديد باسم»
 * يُضغط في قائمةٍ تحلّ محلّ الحقول، فلو جاء «أنشئ» في البطاقة لوقع تحت النظر نفسه.
 */
function quickButtons(kind: "supplier" | "item", label: string, busy: boolean, onCancel: () => void) {
  return (
    <>
      <Button id={`quick-${kind}-cancel`} icon={X} onClick={onCancel}>
        إلغاء
      </Button>
      <Button id={`quick-${kind}-create`} type="submit" form={`quick-${kind}-form`} variant="primary" commit icon={Plus} busy={busy}>
        {label}
      </Button>
    </>
  )
}

/* منتجٌ جديد من سطر الفاتورة: الاسم والوحدة وسعر الشراء وفئة الضريبة؛ والباقي من بطاقته لاحقاً. */
function QuickItemCard({ name: initialName, choices, onCreate, onCancel, inBar, onBusy }: {
  name: string
  choices: InventoryChoices
  onCreate: (body: QuickItem) => Promise<string | null>
  onCancel: () => void
  inBar: boolean
  onBusy: (busy: boolean) => void
}) {
  const [name, setName] = React.useState(initialName)
  const [unit, setUnit] = React.useState<string | null>(null)
  const [price, setPrice] = React.useState("")
  const [vat, setVat] = React.useState("S")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<string | null>(null)
  const units = choices.units.filter((u) => u.code !== "SERVICE").map((u) => ({ value: u.code, label: u.name }))

  async function submit() {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) return setFail("اكتب اسم المنتج.")
    if (!unit) return setFail("اختر الوحدة.")
    const halalas = parseAmount(price)
    if (halalas === null) return setFail("اكتب سعر الشراء للوحدة، مثل 45.50.")
    setBusy(true)
    onBusy(true)
    setFail(null)
    const message = await onCreate({ name: trimmed, unit, price_halalas: halalas, vat_category: vat })
    setBusy(false)
    onBusy(false)
    if (message) setFail(message)
  }

  return (
    <form id="quick-item-form" noValidate aria-labelledby="quick-item" onSubmit={(event) => { event.preventDefault(); void submit() }}
          className="flex flex-col gap-tg rounded-card border border-primary-line bg-secondary/40 p-pad gaze:border-0 gaze:bg-transparent gaze:p-0">
      <h3 id="quick-item" className="text-lead font-semibold gaze:hidden">منتجٌ جديد بسعره</h3>
      <GazeHost>
        <GazeSlot id="quick-item-name">
          <Field label="اسم المنتج" required>
            <Input id="quick-item-name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
          </Field>
        </GazeSlot>
        <Picker id="quick-item-unit" label="الوحدة" options={units} value={unit} onValueChange={setUnit} required />
        <GazeSlot id="quick-item-price">
          <Field label="سعر الشراء للوحدة" required>
            <Input id="quick-item-price" numeric unit="ر.س" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} />
          </Field>
        </GazeSlot>
        <Picker id="quick-item-vat" label="فئة الضريبة" options={choices.vat_categories.map((c) => ({ value: c.code, label: c.name }))} value={vat} onValueChange={setVat} />
      </GazeHost>
      {fail ? (
        <Alert tone="danger" title="لم يُنشأ المنتج" live>
          {fail}
        </Alert>
      ) : null}
      {inBar ? null : <div className="grid grid-cols-2 gap-tg">{quickButtons("item", "أنشئ المنتج", busy, onCancel)}</div>}
    </form>
  )
}

function QuickSupplierCard({ name: initialName, onCreate, onCancel, inBar, onBusy }: {
  name: string
  onCreate: (body: QuickSupplier) => Promise<string | null>
  onCancel: () => void
  inBar: boolean
  onBusy: (busy: boolean) => void
}) {
  const [name, setName] = React.useState(initialName)
  const [vat, setVat] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<string | null>(null)
  async function submit() {
    if ([...name.trim()].length < 2) return setFail("اكتب اسم المورّد.")
    setBusy(true)
    onBusy(true)
    setFail(null)
    const message = await onCreate({ name: name.trim(), vat_number: vat.trim() || null })
    setBusy(false)
    onBusy(false)
    if (message) setFail(message)
  }
  return (
    <form id="quick-supplier-form" noValidate aria-labelledby="quick-supplier" onSubmit={(event) => { event.preventDefault(); void submit() }}
          className="flex flex-col gap-tg rounded-card border border-primary-line bg-secondary/40 p-pad gaze:border-0 gaze:bg-transparent gaze:p-0">
      <h3 id="quick-supplier" className="text-lead font-semibold gaze:hidden">مورّدٌ جديد</h3>
      <Field label="اسم المورّد" required>
        <Input id="quick-supplier-name" value={name} maxLength={60} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="الرقم الضريبي" hint="اختياري الآن؛ والباقي من بطاقة المورّد.">
        <Input id="quick-supplier-vat" numeric inputMode="numeric" value={vat} maxLength={15} onChange={(event) => setVat(event.target.value)} />
      </Field>
      {fail ? (
        <Alert tone="danger" title="لم يُنشأ المورّد" live>
          {fail}
        </Alert>
      ) : null}
      {inBar ? null : <div className="grid grid-cols-2 gap-tg">{quickButtons("supplier", "أنشئ المورّد", busy, onCancel)}</div>}
    </form>
  )
}

export function PurchaseEditor(props: PurchaseEditorProps) {
  const { purchase, choices, today, supplierOptions, onSupplierQuery, reps, onSupplierChosen, itemOptions, items, onItemQuery, onHeader, onCreateSupplier, onCreateItem,
          onAddLine, onPatchLine, onRemoveLine, onDiscard, onReview, onBack, focusLine = null } = props
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState(focusLine ? 3 : 0)
  // رأس الفاتورة: نسخةٌ محلية تُحفظ حين تُغادَر حقولها (العادي) أو عند «التالي» (الكبير).
  const [supplier, setSupplier] = React.useState<ComboboxOption | null>(purchase.supplier ? { value: purchase.supplier.id, label: purchase.supplier.name } : null)
  const [supplierQuery, setSupplierQuery] = React.useState(purchase.supplier?.name ?? "")
  const [creatingSupplier, setCreatingSupplier] = React.useState<string | null>(null)
  const [rep, setRep] = React.useState<string>(purchase.rep?.id ?? "")
  // مورّدٌ اختير للتوّ: حين يصل مندوبوه يُختار افتراضيُّهم («الافتراضي في الفاتورة» في بطاقة المورّد).
  const wantDefault = React.useRef(false)
  const [invoiceNo, setInvoiceNo] = React.useState(purchase.supplier_invoice_no ?? "")
  const [invoiceDate, setInvoiceDate] = React.useState(purchase.invoice_date ?? today)
  const [receivedOn, setReceivedOn] = React.useState(purchase.received_on ?? "")
  const [deliveryNote, setDeliveryNote] = React.useState(purchase.delivery_note_no ?? "")
  const [printedTotal, setPrintedTotal] = React.useState(money(purchase.printed_total_halalas))
  const [printedVat, setPrintedVat] = React.useState(money(purchase.printed_vat_halalas))
  const [basis, setBasis] = React.useState<"net" | "gross">(purchase.prices_include_vat ? "gross" : "net")
  // الأسطر: المحفوظة من الخادم، وسطرٌ في اليد.
  const initialLine = focusLine ? purchase.lines.find((line) => line.line_no === focusLine) : undefined
  const [line, setLine] = React.useState<LineDraft>(initialLine ? lineDraft(initialLine) : EMPTY_LINE)
  // في الحجم الكبير: حقول السطر صفحتان (الكمية والسعر، ثم الخصم وما وصل).
  const [linePage, setLinePage] = React.useState<"main" | "more">("main")
  const [creatingItem, setCreatingItem] = React.useState<string | null>(null)
  const [quickBusy, setQuickBusy] = React.useState(false)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)
  const [discarding, setDiscarding] = React.useState(false)
  const reportSupplier = useOpenReport("purchase-supplier")
  const reportItem = useOpenReport("line-item")
  const decimals = (() => {
    const found = items.find((i) => i.id === line.item?.value) ?? purchase.lines.find((l) => l.item.id === line.item?.value)?.item
    return found ? (choices.units.find((u) => u.code === found.unit)?.decimals ?? false) : true
  })()

  const error = (field: string) => (fail?.field === field ? fail.message : null)
  // خطأ حقلٍ في صفحة السطر الأخرى يفتحها، فلا يبقى الخطأ مخفياً.
  React.useEffect(() => {
    if (fail?.field === "discount_halalas" || fail?.field === "received_quantity_milli") setLinePage("more")
    else if (fail?.field === "quantity_milli" || fail?.field === "unit_price_halalas") setLinePage("main")
  }, [fail])

  /** يحفظ ما تغيّر من الرأس؛ ويعيد false إن رفض الخادم. */
  async function commitHeader(): Promise<boolean> {
    const fields: HeaderFields = {}
    const text = (value: string) => value.trim() || null
    if ((supplier?.value ?? null) !== (purchase.supplier?.id ?? null)) fields.supplier_id = supplier?.value ?? null
    if ((rep || null) !== (purchase.rep?.id ?? null)) fields.rep_id = rep || null
    if (text(invoiceNo) !== purchase.supplier_invoice_no) fields.supplier_invoice_no = text(invoiceNo)
    if (text(invoiceDate) !== purchase.invoice_date) fields.invoice_date = text(invoiceDate)
    if (text(receivedOn) !== purchase.received_on) fields.received_on = text(receivedOn)
    if (text(deliveryNote) !== purchase.delivery_note_no) fields.delivery_note_no = text(deliveryNote)
    if ((basis === "gross") !== purchase.prices_include_vat) fields.prices_include_vat = basis === "gross"
    if (printedTotal.trim() !== money(purchase.printed_total_halalas)) {
      const parsed = printedTotal.trim() ? parseAmount(printedTotal) : null
      if (printedTotal.trim() && parsed === null) {
        setFail({ message: "اكتب الإجمالي المكتوب على الفاتورة مبلغاً.", field: "printed_total_halalas" })
        return false
      }
      fields.printed_total_halalas = parsed
    }
    if (printedVat.trim() !== money(purchase.printed_vat_halalas)) {
      const parsed = printedVat.trim() ? parseAmount(printedVat) : null
      if (printedVat.trim() && parsed === null) {
        setFail({ message: "اكتب الضريبة المكتوبة على الفاتورة مبلغاً.", field: "printed_vat_halalas" })
        return false
      }
      fields.printed_vat_halalas = parsed
    }
    if (Object.keys(fields).length === 0) return true
    setBusy("header")
    const result = await onHeader(fields)
    setBusy(null)
    setFail(result)
    return result === null
  }

  function lineBody(): LineBody | NonNullable<Fail> {
    if (!line.item) return { message: "اختر المنتج من القائمة أو أنشئه.", field: "item_id" }
    const quantity = parseMilli(line.quantity, decimals)
    if (quantity === null) return { message: decimals ? "اكتب الكمية، ويجوز كسرٌ بثلاث منازل." : "اكتب الكمية عدداً صحيحاً من 1.", field: "quantity_milli" }
    const price = parseAmount(line.price)
    if (price === null) return { message: "اكتب سعر الوحدة مبلغاً.", field: "unit_price_halalas" }
    // خصم السطر مبلغٌ مطبوعٌ يُطرح من (الكمية × السعر) على أساس أسعار الفاتورة نفسه، ولا يتجاوزه.
    const discount = line.discount.trim() ? parseAmount(line.discount) : 0
    if (discount === null || discount > Math.round((quantity * price) / 1000)) return { message: "الخصم من صفرٍ إلى مبلغ السطر.", field: "discount_halalas" }
    const received = line.received.trim() ? parseMilli(line.received, decimals, quantity) : null
    if (line.received.trim() && received === null) return { message: "ما وصل كميةٌ لا تزيد على كمية السطر.", field: "received_quantity_milli" }
    return { item_id: line.item.value, quantity_milli: quantity, unit_price_halalas: price, discount_halalas: discount, received_quantity_milli: received }
  }

  const lineDirty = line.item !== null || line.query.trim() !== "" || line.price.trim() !== "" || line.discount.trim() !== "" || (line.lineNo !== null)

  /** يحفظ السطر الذي في اليد إن كان فيه شيء؛ ويعيد false إن رُفض. */
  async function commitLine(): Promise<boolean> {
    if (!lineDirty) return true
    const body = lineBody()
    if ("message" in body) {
      setFail(body)
      return false
    }
    setBusy("line")
    const result = line.lineNo === null ? await onAddLine(body) : await onPatchLine(line.lineNo, body)
    setBusy(null)
    setFail(result)
    if (result) return false
    setLine(EMPTY_LINE)
    setLinePage("main")
    onItemQuery("")
    return true
  }

  async function removeLine(lineNo: number) {
    setBusy("remove")
    const result = await onRemoveLine(lineNo)
    setBusy(null)
    setFail(result)
    if (!result && line.lineNo === lineNo) setLine(EMPTY_LINE)
  }

  async function review() {
    if (!(await commitHeader())) return
    if (!(await commitLine())) return
    onReview()
  }

  async function discard() {
    setBusy("discard")
    const result = await onDiscard()
    setBusy(null)
    setDiscarding(false)
    setFail(result)
  }

  function pickItem(option: ComboboxOption | null) {
    const found = option ? items.find((i) => i.id === option.value) : null
    setLine((current) => ({ ...current, item: option, price: found && !current.price.trim() ? money(found.price_entry_halalas) : current.price }))
  }

  /* ── الرأس ── */
  const supplierField = (
    <GazeSlot id="purchase-supplier">
      {creatingSupplier !== null ? (
        <QuickSupplierCard
          name={creatingSupplier}
          inBar={gaze}
          onBusy={setQuickBusy}
          onCancel={() => setCreatingSupplier(null)}
          onCreate={async (body) => {
            const result = await onCreateSupplier(body)
            if ("fail" in result) return result.fail.message
            setSupplier(result.option)
            setSupplierQuery(result.option.label)
            setCreatingSupplier(null)
            setBusy("header")
            const saved = await onHeader({ supplier_id: result.option.value })
            setBusy(null)
            setFail(saved)
            return null
          }}
        />
      ) : (
        <Field id="purchase-supplier" label="المورّد" error={error("supplier_id")} required>
          <Combobox
            listLabel="المورّدون المطابقون"
            options={supplierOptions}
            value={supplier}
            onValueChange={(option) => {
              setSupplier(option)
              setRep("")
              wantDefault.current = option !== null
              onSupplierChosen(option?.value ?? null)
              if (!gaze) void onHeader({ supplier_id: option?.value ?? null, rep_id: null }).then(setFail)
            }}
            query={supplierQuery}
            onQueryChange={(query) => {
              setSupplierQuery(query)
              onSupplierQuery(query)
            }}
            onCreate={(name) => setCreatingSupplier(name)}
            createLabel="مورّد جديد باسم"
            pageSize={{ compact: 6, gaze: 2, gazeShort: 1 }}
            onOpenChange={reportSupplier}
          />
        </Field>
      )}
    </GazeSlot>
  )
  React.useEffect(() => {
    if (!wantDefault.current || !reps) return
    wantDefault.current = false
    const preferred = reps.find((r) => r.is_default && r.is_active)
    if (!preferred) return
    setRep(preferred.id)
    if (!gaze) void onHeader({ rep_id: preferred.id }).then(setFail)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reps])
  const repField = supplier ? (
    <Picker
      id="purchase-rep"
      label="مندوب المورّد"
      options={[{ value: "", label: "بلا مندوب" }, ...(reps ?? []).filter((r) => r.is_active || r.id === rep).map((r) => ({ value: r.id, label: r.mobile ? `${r.name} · ${r.mobile}` : r.name }))]}
      value={rep}
      onValueChange={(value) => {
        setRep(value)
        if (!gaze) void onHeader({ rep_id: value || null }).then(setFail)
      }}
      hint={gaze || (reps && reps.length) ? undefined : "يُضاف المندوب من بطاقة المورّد."}
      error={error("rep_id")}
    />
  ) : null
  const blur = () => {
    if (!gaze) void commitHeader()
  }
  const invoiceFields = (
    <>
      <GazeSlot id="purchase-no">
        <Field label="رقم فاتورة المورّد" error={error("supplier_invoice_no")} required>
          <Input id="purchase-no" dir="ltr" value={invoiceNo} maxLength={40} onChange={(event) => setInvoiceNo(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
      <GazeSlot id="purchase-date">
        <Field label="تاريخ الفاتورة" error={error("invoice_date")} required>
          <Input id="purchase-date" type="date" dir="ltr" value={invoiceDate} max={today} onChange={(event) => setInvoiceDate(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
      <GazeSlot id="purchase-received">
        <Field label="تاريخ الاستلام" hint={gaze ? undefined : "إن خالف تاريخ الفاتورة."} error={error("received_on")}>
          <Input id="purchase-received" type="date" dir="ltr" value={receivedOn} max={today} onChange={(event) => setReceivedOn(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
      <GazeSlot id="purchase-delivery">
        <Field label="رقم سند التسليم" error={error("delivery_note_no")} className="gaze:short:hidden">
          <Input id="purchase-delivery" dir="ltr" value={deliveryNote} maxLength={40} onChange={(event) => setDeliveryNote(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
    </>
  )
  const amountFields = (
    <>
      <GazeSlot id="purchase-printed">
        <Field label="الإجمالي المكتوب على الفاتورة" hint={gaze ? undefined : "شاملاً الضريبة؛ يُقارَن بمجموع الأسطر."} error={error("printed_total_halalas")} required>
          <Input id="purchase-printed" numeric unit="ر.س" inputMode="decimal" value={printedTotal} onChange={(event) => setPrintedTotal(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
      <GazeSlot id="purchase-printed-vat">
        <Field label="الضريبة المكتوبة" hint={gaze ? undefined : "اختياري."} error={error("printed_vat_halalas")} className="gaze:short:hidden">
          <Input id="purchase-printed-vat" numeric unit="ر.س" inputMode="decimal" value={printedVat} onChange={(event) => setPrintedVat(event.target.value)} onBlur={blur} />
        </Field>
      </GazeSlot>
      <GazeSlot id="purchase-basis">
        <RadioCards<"net" | "gross">
          label="أسعار الأسطر في هذه الفاتورة"
          value={basis}
          onValueChange={(value) => {
            setBasis(value)
            if (!gaze) void onHeader({ prices_include_vat: value === "gross" }).then(setFail)
          }}
          ids={{ net: "purchase-basis-net", gross: "purchase-basis-gross" }}
          options={[
            { value: "net", title: "قبل الضريبة" },
            { value: "gross", title: "شاملةً الضريبة" },
          ]}
        />
      </GazeSlot>
    </>
  )

  /* ── السطر في اليد ── */
  const lineEditor = creatingItem !== null ? (
    <QuickItemCard
      name={creatingItem}
      choices={choices}
      inBar={gaze}
      onBusy={setQuickBusy}
      onCancel={() => setCreatingItem(null)}
      onCreate={async (body) => {
        const result = await onCreateItem(body)
        if ("fail" in result) return result.fail.message
        setLine((current) => ({ ...current, item: itemOption(result.item), query: result.item.name, price: money(result.item.price_entry_halalas) }))
        setCreatingItem(null)
        return null
      }}
    />
  ) : (
    <GazeHost>
      <GazeSlot id="line-item">
        <Field id="line-item" label={line.lineNo === null ? "المنتج" : `المنتج (السطر ${line.lineNo})`} error={error("item_id")} required>
          <Combobox
            listLabel="المنتجات المطابقة"
            options={itemOptions}
            value={line.item}
            onValueChange={pickItem}
            query={line.query}
            onQueryChange={(query) => {
              setLine((current) => ({ ...current, query }))
              onItemQuery(query)
            }}
            onCreate={(name) => setCreatingItem(name)}
            createLabel="منتج جديد باسم"
            createHint="بوحدته وسعره"
            pageSize={{ compact: 6, gaze: 2, gazeShort: 1 }}
            onOpenChange={reportItem}
          />
        </Field>
      </GazeSlot>
      {!gaze || linePage === "main" ? (
        <>
          <GazeSlot id="line-quantity">
            <Field label="الكمية" error={error("quantity_milli")} required>
              <Input id="line-quantity" numeric inputMode={decimals ? "decimal" : "numeric"} value={line.quantity} onChange={(event) => setLine((current) => ({ ...current, quantity: event.target.value }))} />
            </Field>
          </GazeSlot>
          <GazeSlot id="line-price">
            <Field label={basis === "gross" ? "سعر الوحدة شاملاً" : "سعر الوحدة قبل الضريبة"} error={error("unit_price_halalas")} required>
              <Input id="line-price" numeric unit="ر.س" inputMode="decimal" value={line.price} onChange={(event) => setLine((current) => ({ ...current, price: event.target.value }))} />
            </Field>
          </GazeSlot>
        </>
      ) : null}
      {/* الخصم وما وصل اختياريان. في الحجم الكبير يحلّان محلّ الكمية والسعر بزرّ «الخصم وما وصل» في مكانه نفسه، فلا تزيد الخطوة على 12 هدفاً ولا تتجاوز أقصر الهواتف. */}
      {!gaze || linePage === "more" ? (
        <>
          <GazeSlot id="line-discount">
            <Field label="خصم السطر" hint={gaze ? undefined : "مبلغٌ مطبوعٌ على السطر يُطرح منه؛ يُترك فارغاً إن لم يكن."} error={error("discount_halalas")}>
              <Input id="line-discount" numeric unit="ر.س" inputMode="decimal" value={line.discount} onChange={(event) => setLine((current) => ({ ...current, discount: event.target.value }))} />
            </Field>
          </GazeSlot>
          <GazeSlot id="line-received">
            <Field label="ما وصل فعلاً" hint={gaze ? undefined : "يُترك فارغاً إن وصل كلّه."} error={error("received_quantity_milli")}>
              <Input id="line-received" numeric inputMode={decimals ? "decimal" : "numeric"} value={line.received} onChange={(event) => setLine((current) => ({ ...current, received: event.target.value }))} />
            </Field>
          </GazeSlot>
        </>
      ) : null}
      {gaze ? (
        <GazeSlot id="line-more">
          <Button id="line-more" className="w-full" icon={linePage === "more" ? BackIcon : undefined} iconEnd={linePage === "main" ? NextIcon : undefined}
                  onClick={() => setLinePage((current) => (current === "main" ? "more" : "main"))}>
            {linePage === "main" ? "الخصم وما وصل" : "الكمية والسعر"}
          </Button>
        </GazeSlot>
      ) : null}
    </GazeHost>
  )

  const totals = purchase.totals
  const printed = purchase.printed_total_halalas
  const totalsBlock = (
    <dl className="flex flex-col gap-1 rounded-card border border-border bg-card p-pad">
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">قبل الضريبة</dt>
        <dd><Money halalas={totals.net} unit={false} /></dd>
      </div>
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">الضريبة</dt>
        <dd><Money halalas={totals.vat} unit={false} /></dd>
      </div>
      <div className="flex justify-between gap-tg border-t border-border pt-1 text-lead font-bold text-heading">
        <dt>الإجمالي</dt>
        <dd><Money halalas={totals.gross} /></dd>
      </div>
      {printed !== null && printed !== totals.gross ? (
        <p className="text-small font-semibold text-warning">
          المكتوب على الفاتورة <Money halalas={printed} unit={false} />؛ الفرق <Money halalas={Math.abs(printed - totals.gross)} unit={false} />.
        </p>
      ) : null}
    </dl>
  )
  const failAlert = fail && !fail.field ? (
    <Alert tone="danger" title="لم يُحفظ" live>
      {fail.message}
    </Alert>
  ) : null
  const missingText = purchase.missing.length ? `ينقص قبل التسجيل: ${purchase.missing.map((key) => MISSING[key] ?? key).join("، ")}.` : null
  const discardDialog = (
    <Dialog open={discarding} onClose={() => setDiscarding(false)} alert title="حذف المسودة" description="تُحذف المسودة وأسطرها ولا تعود." closeLabel="رجوع"
            footer={<Button id="purchase-discard-yes" variant="danger" commit icon={Trash} busy={busy === "discard"} onClick={() => void discard()}>نعم، احذف</Button>}>
      <p className="text-flow">{purchase.supplier?.name ?? "مسودة بلا مورّد"}{purchase.supplier_invoice_no ? ` · ${purchase.supplier_invoice_no}` : ""}</p>
    </Dialog>
  )

  /* ── الحجم الكبير: خطوةٌ في كل شاشة ── */
  if (gaze) {
    const savedLines = purchase.lines
    const index = line.lineNo === null ? savedLines.length : savedLines.findIndex((l) => l.line_no === line.lineNo)
    const goToLine = async (next: number) => {
      if (!(await commitLine())) return
      const target = savedLines[next]
      setLine(target ? lineDraft(target) : EMPTY_LINE)
      setLinePage("main")
      if (target) onItemQuery("")
    }
    const nextStep = async () => {
      if (await commitHeader()) setStep(step + 1)
    }
    const title = step === 0 ? "المورّد" : step === 1 ? "فاتورة المورّد" : step === 2 ? "المبالغ" : creatingItem !== null ? "منتجٌ جديد" : line.lineNo === null ? `سطرٌ جديد (${savedLines.length + 1})` : `السطر ${line.lineNo} من ${savedLines.length}`
    return (
      <Screen
        title={title}
        description={step === 3 && !creatingItem && savedLines.length ? <span>الإجمالي حتى الآن <Money halalas={totals.gross} className="font-semibold text-foreground" /></span> : undefined}
        // حذف المسودة في الخطوة الأولى كما في الحجم العادي: لا تبقى مسودةٌ لا تُحذف (والحدّ عشرون).
        end={step === 0 && creatingItem === null && creatingSupplier === null ? { id: "purchase-discard", label: "احذف المسودة", danger: true, icon: Trash, onClick: () => setDiscarding(true) } : undefined}
        // خطوة الأسطر على الهواتف القصيرة: يكفي عنوانها («سطرٌ جديد (1)»)، فيتّسع السطر لحقوله وزرّ «الخصم وما وصل».
        above={<Stepper steps={STEPS} current={step} className={step === 3 ? "gaze:[@media(max-height:40rem)]:hidden" : undefined} />}
        actions={
          creatingSupplier !== null ? quickButtons("supplier", "أنشئ المورّد", quickBusy, () => setCreatingSupplier(null))
          : creatingItem !== null ? quickButtons("item", "أنشئ المنتج", quickBusy, () => setCreatingItem(null)) : (
            <>
              <Button id="purchase-prev" icon={BackIcon} busy={busy === "header"} onClick={step === 0 ? onBack : step === 3 && index > 0 ? () => void goToLine(index - 1) : () => setStep(step - 1)}>
                {step === 0 ? "الرئيسية" : step === 3 && index > 0 ? "السطر السابق" : STEPS[step - 1].label}
              </Button>
              {step < 3 ? (
                <Button id="purchase-next" variant="secondary" iconEnd={NextIcon} busy={busy === "header"} onClick={() => void nextStep()}>
                  {STEPS[step + 1].label}
                </Button>
              ) : (
                <Button id="purchase-review" variant="secondary" icon={ClipboardCheck} busy={busy !== null} onClick={() => void review()}>
                  راجِع وسجّل
                </Button>
              )}
            </>
          )
        }
      >
        {failAlert}
        {step === 0 ? (
          <GazeHost>
            {supplierField}
            {repField}
          </GazeHost>
        ) : step === 1 ? (
          <GazeHost>{invoiceFields}</GazeHost>
        ) : step === 2 ? (
          <GazeHost>{amountFields}</GazeHost>
        ) : (
          <>
            {lineEditor}
            {creatingItem !== null ? null : (
              <div className="grid grid-cols-2 gap-tg">
                {line.lineNo === null ? (
                  <Button id="line-save" variant="primary" commit icon={Plus} disabled={!line.item} busy={busy === "line"} onClick={() => void commitLine()}>
                    أضف السطر
                  </Button>
                ) : (
                  <Button id="line-remove" variant="danger-outline" commit icon={Trash} busy={busy === "remove"} onClick={() => void removeLine(line.lineNo as number)}>
                    احذف السطر
                  </Button>
                )}
                <Button id="line-next" iconEnd={NextIcon} disabled={line.lineNo === null && !lineDirty && savedLines.length === 0} busy={busy === "line"}
                        onClick={() => void goToLine(line.lineNo === null ? savedLines.length : index + 1)}>
                  {index < savedLines.length - 1 || (line.lineNo !== null && index === savedLines.length - 1) ? (index === savedLines.length - 1 ? "سطرٌ جديد" : "السطر التالي") : "احفظ وسطرٌ جديد"}
                </Button>
              </div>
            )}
          </>
        )}
        {discardDialog}
      </Screen>
    )
  }

  /* ── الحجم العادي: الصفحة كلّها ── */
  return (
    <Screen
      title="فاتورة شراء"
      above={<Badge tone="info" className="self-start">مسودة لم تُسجَّل</Badge>}
      description={missingText ?? "تزيد المخزون وتدخل المصاريف حين تسجّلها بعد المراجعة."}
      back={{ id: "purchase-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "purchase-discard", label: "احذف المسودة", danger: true, icon: Trash, onClick: () => setDiscarding(true) }}
      actions={
        <Button id="purchase-review" variant="secondary" size="lg" icon={ClipboardCheck} busy={busy !== null} onClick={() => void review()} className="ms-auto">
          راجِع وسجّل
        </Button>
      }
    >
      {failAlert}
      <section aria-labelledby="purchase-header" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <h2 id="purchase-header" className="text-lead font-semibold">المورّد والفاتورة</h2>
        <GazeHost className="tablet:grid tablet:grid-cols-2 tablet:gap-tg">
          {supplierField}
          {repField}
          {invoiceFields}
          {amountFields}
        </GazeHost>
      </section>
      <section aria-labelledby="purchase-lines" className="flex flex-col gap-tg">
        <div className="flex items-center justify-between gap-tg">
          <h2 id="purchase-lines" className="text-lead font-semibold">المنتجات</h2>
          <span className="text-small text-muted-foreground"><span className="num">{purchase.lines.length}</span> أسطر</span>
        </div>
        {purchase.lines.length ? (
          <ol id="purchase-line-list" className="flex flex-col gap-tg-min">
            {purchase.lines.map((saved) => (
              <li key={saved.line_no} className={cn("flex flex-wrap items-center justify-between gap-tg rounded-card border bg-card px-3 py-2", line.lineNo === saved.line_no ? "border-primary-line" : "border-border")}>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-semibold"><span className="num text-muted-foreground">{saved.line_no}. </span>{saved.item.name}</span>
                  <span className="text-small text-muted-foreground">
                    <Qty milli={saved.quantity_milli} unit={saved.item.unit_name} /> × <Money halalas={saved.unit_price_halalas} unit={false} />
                    {saved.discount_halalas ? <span> − خصم <Money halalas={saved.discount_halalas} unit={false} /></span> : null}
                    {saved.received_quantity_milli !== null && saved.received_quantity_milli !== saved.quantity_milli ? <span className="text-warning"> · وصل {formatMilli(saved.received_quantity_milli)}</span> : null}
                  </span>
                </span>
                <Money halalas={saved.net_halalas + saved.vat_halalas} className="font-bold" />
                <span className="flex gap-tg-min">
                  <Button icon={PencilLine} aria-label={`عدّل السطر ${saved.line_no}: ${saved.item.name}`} onClick={() => { setLine(lineDraft(saved)); onItemQuery("") }}>عدّل</Button>
                  <Button variant="danger-outline" commit icon={Trash} busy={busy === "remove"} aria-label={`احذف السطر ${saved.line_no}: ${saved.item.name}`} onClick={() => void removeLine(saved.line_no)}>احذف</Button>
                </span>
              </li>
            ))}
          </ol>
        ) : null}
        <div className={cn("flex flex-col gap-tg rounded-card border bg-card p-pad", line.lineNo === null ? "border-border" : "border-primary-line")}>
          <h3 className="text-body font-semibold">{line.lineNo === null ? "سطرٌ جديد" : `تعديل السطر ${line.lineNo}`}</h3>
          {lineEditor}
          {creatingItem !== null ? null : (
            <div className="flex flex-wrap gap-tg">
              <Button id="line-save" variant="primary" commit icon={line.lineNo === null ? Plus : Save} busy={busy === "line"} disabled={!line.item} onClick={() => void commitLine()}>
                {line.lineNo === null ? "أضف السطر" : "احفظ السطر"}
              </Button>
              {line.lineNo !== null ? (
                <Button icon={X} onClick={() => { setLine(EMPTY_LINE); onItemQuery("") }}>
                  إلغاء التعديل
                </Button>
              ) : null}
            </div>
          )}
        </div>
      </section>
      <section aria-labelledby="purchase-totals" className="flex flex-col gap-tg">
        <h2 id="purchase-totals" className="text-lead font-semibold">المجموع</h2>
        {totalsBlock}
      </section>
      {discardDialog}
    </Screen>
  )
}

/* ── الفاتورة المسجَّلة أو المعكوسة ──────────────────────────────── */

export function PurchaseView({ purchase, choices, onReturn, onReverse, onOpenReturn, onBack }: {
  purchase: Purchase
  choices: InventoryChoices
  onReturn: () => void
  onReverse: () => void
  onOpenReturn: (id: string) => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [tab, setTab] = React.useState("facts")
  const facts: Fact[] = [
    { label: "المورّد", value: purchase.supplier?.name, key: true },
    { label: "المندوب", value: purchase.rep ? (purchase.rep.mobile ? `${purchase.rep.name} · ${purchase.rep.mobile}` : purchase.rep.name) : null, key: true },
    { label: "فاتورة المورّد", value: purchase.supplier_invoice_no ? <span className="num" dir="ltr">{purchase.supplier_invoice_no}</span> : null, key: true },
    { label: "تاريخها", value: purchase.invoice_date ? formatDay(purchase.invoice_date, true) : null, key: true },
    { label: "الاستلام", value: purchase.received_on ? formatDay(purchase.received_on, true) : null },
    { label: "سند التسليم", value: purchase.delivery_note_no ? <span className="num" dir="ltr">{purchase.delivery_note_no}</span> : null },
    { label: "الإجمالي", value: <Money halalas={purchase.totals.gross} />, key: true },
    { label: "الضريبة", value: <Money halalas={purchase.totals.vat} /> },
    { label: "المكتوب على الفاتورة", value: purchase.printed_total_halalas === null ? null : <Money halalas={purchase.printed_total_halalas} /> },
    { label: "سُجّلت", value: purchase.posted_at ? formatDay(purchase.posted_at, true) : null },
    { label: "ملاحظة", value: purchase.note },
  ]
  const reversal = purchase.reversal ? (
    <Alert tone="warning" title={`عُكست بالقيد ${purchase.reversal.label}`}>
      {codeName(choices.reversal_reasons, purchase.reversal.reason)}{purchase.reversal.note ? ` · ${purchase.reversal.note}` : ""} · {formatDay(purchase.reversal.at, true)}
    </Alert>
  ) : null
  const lines = (
    <DataTable<PurchaseLine>
      caption="أسطر الفاتورة"
      rows={purchase.lines}
      rowKey={(row) => String(row.line_no)}
      columns={[
        { id: "no", header: "#", numeric: true, cell: (row) => row.line_no },
        { id: "item", header: "المنتج", cell: (row) => row.item.name },
        { id: "qty", header: "الكمية", numeric: true, cell: (row) => `${formatMilli(row.quantity_milli)} ${row.item.unit_name}` },
        { id: "received", header: "وصل", numeric: true, cell: (row) => formatMilli(row.received_quantity_milli ?? row.quantity_milli) },
        { id: "price", header: "سعر الوحدة", numeric: true, cell: (row) => formatAmount(row.unit_price_halalas) },
        ...(purchase.lines.some((row) => row.discount_halalas) ? [{ id: "discount", header: "الخصم", numeric: true, cell: (row: PurchaseLine) => formatAmount(row.discount_halalas) }] : []),
        { id: "net", header: "قبل الضريبة", numeric: true, cell: (row) => formatAmount(row.net_halalas) },
        { id: "vat", header: "الضريبة", numeric: true, cell: (row) => formatAmount(row.vat_halalas) },
        { id: "remaining", header: "بقي للإرجاع", numeric: true, cell: (row) => formatMilli(row.remaining_milli) },
      ]}
      primary={(row) => `${row.line_no}. ${row.item.name}`}
      secondary={(row) => `${formatMilli(row.quantity_milli)} ${row.item.unit_name} × ${formatAmount(row.unit_price_halalas)}${row.discount_halalas ? ` − خصم ${formatAmount(row.discount_halalas)}` : ""}${row.received_quantity_milli !== null && row.received_quantity_milli !== row.quantity_milli ? ` · وصل ${formatMilli(row.received_quantity_milli)}` : ""}${row.remaining_milli !== row.quantity_milli ? ` · بقي ${formatMilli(row.remaining_milli)}` : ""}`}
      trailing={(row) => <span className="num font-bold" dir="ltr">{formatAmount(row.net_halalas + row.vat_halalas)}</span>}
      pageSize={{ compact: 40, gaze: 3, gazeShort: 2 }}
    />
  )
  const extras = (
    <>
      {purchase.acknowledged.length ? (
        <section aria-labelledby="purchase-acks" className="flex flex-col gap-1.5 gaze:hidden">
          <h2 id="purchase-acks" className="text-lead font-semibold">تنبيهاتٌ أُقرّ بها عند التسجيل</h2>
          <ul className="flex list-disc flex-col gap-1 ps-5 text-small">
            {purchase.acknowledged.map((flag) => (
              <li key={flag.key}>{flag.text}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {purchase.returns.length ? (
        <section aria-labelledby="purchase-returns" className="flex flex-col gap-1.5 gaze:hidden">
          <h2 id="purchase-returns" className="text-lead font-semibold">مرتجعاتها</h2>
          <ul className="flex flex-wrap gap-tg">
            {purchase.returns.map((r) => (
              <li key={r.id}>
                <Button icon={Undo2} onClick={() => onOpenReturn(r.id)}>
                  {r.label ?? "مسودة مرتجع"}
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  )
  return (
    <Screen
      title={purchase.label ?? "فاتورة شراء"}
      above={<Badge tone={STATUS_TONE[purchase.status]} className="self-start">{PURCHASE_STATUS[purchase.status]}</Badge>}
      description={gaze ? undefined : `${purchase.supplier?.name ?? ""}${purchase.supplier_invoice_no ? ` · فاتورة ${purchase.supplier_invoice_no}` : ""}`}
      back={{ id: "purchase-view-back", label: "رجوع", onClick: onBack }}
      actions={
        purchase.status === "POSTED" ? (
          // «قيد عكسي» في الخانة الأولى: يفتح شاشةً «رجوع» في خانتها الأولى، و«اعكس» في الثانية.
          <Slots
            actions
            start={
              <Button id="purchase-reverse" variant="danger-outline" icon={Trash} disabled={purchase.returns.some((r) => r.status === "POSTED")} onClick={onReverse}>
                قيد عكسي
              </Button>
            }
            end={
              <Button id="purchase-return" variant="secondary" icon={Undo2} disabled={!purchase.returnable} onClick={onReturn}>
                مرتجع منها
              </Button>
            }
          />
        ) : undefined
      }
    >
      {reversal}
      {gaze ? (
        <Tabs items={[{ id: "facts", label: "الفاتورة" }, { id: "lines", label: "الأسطر" }]} value={tab} onValueChange={setTab} label="الفاتورة" stretch>
          {tab === "facts" ? <Facts facts={facts} columns={2} /> : lines}
        </Tabs>
      ) : (
        <>
          <Facts facts={facts} columns={3} />
          <section aria-labelledby="purchase-view-lines" className="flex flex-col gap-tg">
            <h2 id="purchase-view-lines" className="text-lead font-semibold">الأسطر</h2>
            {lines}
          </section>
          {extras}
        </>
      )}
    </Screen>
  )
}

/* ── القيد العكسي ────────────────────────────────────────────────── */

export function ReverseScreen({ purchase, choices, onReverse, onBack }: {
  purchase: Purchase
  choices: InventoryChoices
  onReverse: (reason: string, note: string | null) => Promise<Fail>
  onBack: () => void
}) {
  const [reason, setReason] = React.useState<string | null>(null)
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  async function submit() {
    if (!reason) return setFail({ message: "اختر السبب.", field: "reason" })
    if (reason === "OTHER" && !note.trim()) return setFail({ message: "اكتب السبب في الملاحظة.", field: "note" })
    setBusy(true)
    setFail(null)
    const result = await onReverse(reason, note.trim() || null)
    setBusy(false)
    if (result) setFail(result)
  }
  return (
    <Screen
      title={`عكس ${purchase.label ?? "الفاتورة"}`}
      description="يخرج ما أدخلته الفاتورة من المخزون ويُخصم من المصاريف، وتبقى الفاتورة في السجلّ معكوسة."
      actions={
        <Slots
          actions
          start={
            <Button id="reverse-back" icon={BackIcon} onClick={onBack}>
              الفاتورة
            </Button>
          }
          end={
            <Button id="reverse-yes" variant="danger" commit icon={Trash} busy={busy} onClick={() => void submit()}>
              اعكس الفاتورة
            </Button>
          }
        />
      }
    >
      {fail && !fail.field ? (
        <Alert tone="danger" title="لم يُعكس" live>
          {fail.message}
        </Alert>
      ) : null}
      <GazeHost>
        <Picker id="reverse-reason" label="السبب" options={choices.reversal_reasons.map((r) => ({ value: r.code, label: r.name }))} value={reason} onValueChange={setReason} error={fail?.field === "reason" ? fail.message : null} required />
        <GazeSlot id="reverse-note">
          <Field label={reason === "OTHER" ? "اكتب السبب" : "ملاحظة"} error={fail?.field === "note" ? fail.message : null}>
            <Input id="reverse-note" value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} />
          </Field>
        </GazeSlot>
      </GazeHost>
      <p className="text-small text-muted-foreground">
        {purchase.supplier?.name} · الإجمالي <Money halalas={purchase.totals.gross} /> · <span className="num">{purchase.lines.length}</span> أسطر
      </p>
    </Screen>
  )
}
