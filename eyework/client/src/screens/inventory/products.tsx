/*
 * المنتجات: المخزون، وبطاقة المنتج، ونموذجه، وسنده
 * ================================================
 * «البضاعة» بكلمات المالك: يضيف منتجاً ويكتب اسمه، فيظهر له رمزٌ مميّز («ص-00012») وسعره وضريبته.
 *   • المخزون: بحثٌ بالاسم أو الرمز أو الباركود، وتصفية (الكل، تحت حدّ الطلب، خدمات، لم تُجرد،
 *     مؤرشفة)، وصفوفٌ تُفتح، وقيمة المخزون بالتكلفة المتوسطة من الخادم.
 *   • البطاقة: الحقائق، وآخر المشتريات، والحركات صفحاتٍ. في الحجم الكبير لسانان: البطاقة والحركات.
 *   • النموذج: ثلاث مجموعات (الأساس، التعريف، البيع والطلب)؛ في الحجم الكبير ثلاث خطوات، وفي كل
 *     خطوةٍ منتقٍ واحد مفتوح.
 *   • السند: رصيدٌ افتتاحي (قبل أيّ حركة) أو صرفٌ أو جردٌ فردي، بمعرّف ضغطةٍ واحد.
 */

import * as React from "react"
import { Archive, ArchiveRestore, Boxes, ClipboardList, PackagePlus, PencilLine, Save, Truck } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, ButtonLink, NextIcon } from "@/components/ui/button"
import { Combobox, type ComboboxOption } from "@/components/ui/combobox"
import { DataTable } from "@/components/ui/data-table"
import { Dialog } from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input, Textarea } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { Tabs } from "@/components/ui/tabs"
import { formatDay } from "@/lib/format"
import {
  BASE, MOVEMENT_KIND, codeName, formatMilli, milliInput, parseMilli,
  type Category, type InventoryChoices, type Item, type ItemDetail, type ItemFilter, type Movement, type Paged, type VoucherKind,
} from "@/lib/inventory"
import { formatAmount, parseAmount } from "@/lib/money"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

import { Facts, GazeHost, GazeSlot, Money, Picker, Qty, useOpenReport, type Fact } from "./common"
import type { Fail } from "./setup"

/* ── المخزون ─────────────────────────────────────────────────────── */

const FILTERS: { id: ItemFilter; label: string }[] = [
  { id: "all", label: "الكل" },
  { id: "low", label: "تحت حدّ الطلب" },
  { id: "service", label: "خدمات" },
  { id: "uncounted", label: "لم تُجرد" },
  { id: "archived", label: "مؤرشفة" },
]

export function StockScreen({ data, query, onQuery, filter, onFilter, page, onPage, onOpen, onNew, onBack }: {
  data: (Paged<Item> & { stock_value_halalas: number }) | null
  query: string
  onQuery: (query: string) => void
  filter: ItemFilter
  onFilter: (filter: ItemFilter) => void
  page: number
  onPage: (page: number) => void
  onOpen: (item: Item) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const links = (suffix: string) => (
    <>
      <ButtonLink id={`stock-suppliers${suffix}`} href={`${BASE}/suppliers`} icon={Truck}>
        المورّدون
      </ButtonLink>
      <ButtonLink id={`stock-vouchers${suffix}`} href={`${BASE}/vouchers`} icon={ClipboardList}>
        السندات
      </ButtonLink>
    </>
  )
  return (
    <Screen
      title="المخزون"
      description={
        data ? (
          <span>
            قيمة المخزون <Money halalas={data.stock_value_halalas} className="font-semibold text-foreground" />
            <span className="gaze:hidden"> · {data.total} منتج</span>
          </span>
        ) : undefined
      }
      back={gaze ? undefined : { id: "stock-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "stock-new", label: "منتج جديد", icon: PackagePlus, onClick: onNew }}
      aside={gaze ? undefined : links("")}
    >
      <Field label="ابحث" hint={gaze ? undefined : "بالاسم أو الرمز أو الباركود."}>
        <Input id="stock-search" type="search" autoComplete="off" value={query} onChange={(event) => onQuery(event.target.value)} />
      </Field>
      <Tabs items={FILTERS} value={filter} onValueChange={(id) => onFilter(id as ItemFilter)} label="التصفية">
        {data === null ? null : (
          <DataTable<Item>
            caption="المنتجات"
            rows={data.items}
            rowKey={(row) => row.id}
            columns={[
              { id: "code", header: "الرمز", cell: (row) => <span className="num">{row.code}</span> },
              { id: "name", header: "المنتج", cell: (row) => row.name },
              { id: "on_hand", header: "الرصيد", numeric: true, cell: (row) => (row.kind === "SERVICE" ? "—" : `${formatMilli(row.on_hand_milli)} ${row.unit_name}`) },
              { id: "price", header: "سعر الشراء", numeric: true, cell: (row) => formatAmount(row.price_halalas) },
              { id: "value", header: "القيمة", numeric: true, cell: (row) => formatAmount(row.stock_value_halalas) },
              { id: "state", header: "الحالة", cell: (row) => (row.below_reorder ? <Badge tone="warning">تحت حدّ الطلب</Badge> : row.is_active ? "" : <Badge>مؤرشف</Badge>) },
            ]}
            primary={(row) => row.name}
            secondary={(row) => `${row.code} · ${row.unit_name}${row.category ? ` · ${row.category.name}` : ""}`}
            trailing={(row) =>
              row.kind === "SERVICE" ? (
                <span className="text-small text-muted-foreground">خدمة</span>
              ) : (
                <>
                  <span className={cn("num font-bold", row.below_reorder && "text-warning")} dir="ltr">
                    {formatMilli(row.on_hand_milli)}
                  </span>
                  <span className="text-small text-muted-foreground gaze:hidden">{formatAmount(row.stock_value_halalas)} ر.س</span>
                </>
              )
            }
            onOpen={onOpen}
            openLabel={(row) => `افتح ${row.name}`}
            pageSize={{ compact: 10, gaze: 3, gazeShort: 2 }}
            page={page}
            onPageChange={onPage}
            total={data.total}
            empty={
              <EmptyState
                icon={Boxes}
                title={query ? "لا منتج يطابق" : "لا منتجات بعد"}
                description={query ? undefined : "أضف منتجك الأوّل باسمه وسعره، أو أنشئه من سطر فاتورة شراء."}
              />
            }
          />
        )}
      </Tabs>
      {gaze ? null : <div className="flex flex-wrap gap-tg tablet:hidden">{links("-phone")}</div>}
    </Screen>
  )
}

/* ── بطاقة المنتج ────────────────────────────────────────────────── */

export function ItemScreen({ item, movements, movementsPage, onMovementsPage, choices, onEdit, onVoucher, onArchive, onBack }: {
  item: ItemDetail
  movements: Paged<Movement> | null
  movementsPage: number
  onMovementsPage: (page: number) => void
  choices: InventoryChoices
  onEdit: () => void
  onVoucher: () => void
  onArchive: () => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [tab, setTab] = React.useState("card")
  const [confirm, setConfirm] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const service = item.kind === "SERVICE"
  const vat = codeName(choices.vat_categories, item.vat_category)
  const facts: Fact[] = [
    { label: "الرصيد", value: service ? "خدمة" : <Qty milli={item.on_hand_milli} unit={item.unit_name} />, key: true },
    { label: "قيمة المخزون", value: service ? null : <Money halalas={item.stock_value_halalas} />, key: true },
    { label: "سعر الشراء", value: <Money halalas={item.price_halalas} />, key: true },
    { label: "فئة الضريبة", value: item.vat_exemption_reason ? `${vat} (${item.vat_exemption_reason})` : vat, key: true },
    { label: "متوسط التكلفة", value: item.avg_cost_halalas === null ? null : <Money halalas={item.avg_cost_halalas} /> },
    { label: "آخر سعر شراء", value: item.last_price_halalas === null ? null : <Money halalas={item.last_price_halalas} /> },
    { label: "سعر البيع", value: item.selling_price_halalas === null ? null : <span><Money halalas={item.selling_price_halalas} /> {item.selling_price_includes_vat ? "شاملاً" : "قبل الضريبة"}</span> },
    { label: "حدّ الطلب", value: item.reorder_level_milli === null ? null : <Qty milli={item.reorder_level_milli} unit={item.unit_name} /> },
    { label: "المستوى المستهدف", value: item.target_level_milli === null ? null : <Qty milli={item.target_level_milli} unit={item.unit_name} /> },
    { label: "المقترح طلبه", value: item.suggested_order_milli ? <Qty milli={item.suggested_order_milli} unit={item.unit_name} /> : null, key: true },
    { label: "الباركود", value: item.barcode ? <span className="num" dir="ltr">{item.barcode}</span> : null },
    { label: "رمز المورّد", value: item.supplier_code ? <span className="num" dir="ltr">{item.supplier_code}</span> : null },
    { label: "التصنيف", value: item.category?.name ?? null },
    { label: "المورّد المفضّل", value: item.preferred_supplier ? `${item.preferred_supplier.name}${item.preferred_supplier.rep_name ? ` · ${item.preferred_supplier.rep_name}` : ""}` : null },
    { label: "آخر جرد", value: item.last_counted_on ? formatDay(item.last_counted_on, true) : null },
    { label: "ملاحظة", value: item.note },
  ]
  const movementsTable = movements === null ? null : (
    <DataTable<Movement>
      caption="حركات المنتج"
      rows={movements.items}
      rowKey={(row) => `${row.document}-${row.kind}-${row.occurred_on}-${row.on_hand_after_milli}`}
      columns={[
        { id: "date", header: "التاريخ", cell: (row) => formatDay(row.occurred_on) },
        { id: "document", header: "المستند", cell: (row) => <span className="num">{row.document}</span> },
        { id: "kind", header: "النوع", cell: (row) => MOVEMENT_KIND[row.kind] },
        { id: "in", header: "وارد", numeric: true, cell: (row) => (row.in_milli ? formatMilli(row.in_milli) : "") },
        { id: "out", header: "منصرف", numeric: true, cell: (row) => (row.out_milli ? formatMilli(row.out_milli) : "") },
        { id: "after", header: "الرصيد بعد", numeric: true, cell: (row) => formatMilli(row.on_hand_after_milli) },
        { id: "value", header: "القيمة بعد", numeric: true, cell: (row) => formatAmount(row.value_after_halalas) },
      ]}
      primary={(row) => `${MOVEMENT_KIND[row.kind]} ${row.document}`}
      secondary={(row) => `${formatDay(row.occurred_on)} · الرصيد بعدها ${formatMilli(row.on_hand_after_milli)}`}
      trailing={(row) => (
        <span className={cn("num font-bold", row.in_milli ? "text-success" : "text-destructive")} dir="ltr">
          {row.in_milli ? `+${formatMilli(row.in_milli)}` : `−${formatMilli(row.out_milli)}`}
        </span>
      )}
      pageSize={{ compact: 10, gaze: 3, gazeShort: 2 }}
      page={movementsPage}
      onPageChange={onMovementsPage}
      total={movements.total}
      empty={<p className="text-small text-muted-foreground">لا حركات بعد.</p>}
    />
  )
  const recent = item.recent_purchases.length ? (
    <section aria-labelledby="item-recent" className="flex flex-col gap-1.5 gaze:hidden">
      <h2 id="item-recent" className="text-lead font-semibold">آخر المشتريات</h2>
      <ul className="flex flex-col gap-1 text-small">
        {item.recent_purchases.map((line) => (
          <li key={`${line.document}-${line.invoice_date}`} className="flex flex-wrap justify-between gap-x-tg">
            <span>
              <span className="num">{line.document}</span>
              {line.supplier_name ? ` · ${line.supplier_name}` : ""} · {line.invoice_date ? formatDay(line.invoice_date) : ""}
            </span>
            <span className="num" dir="ltr">
              {formatMilli(line.quantity_milli)} × {line.unit_price_halalas === null ? "—" : formatAmount(line.unit_price_halalas)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  ) : null
  const suggestion =
    item.reorder_suggestion_milli !== null && item.reorder_suggestion_milli !== item.reorder_level_milli ? (
      <p className="text-small text-muted-foreground gaze:hidden">
        من مصروف آخر تسعين يوماً يُقترح حدّ طلبٍ عند <Qty milli={item.reorder_suggestion_milli} unit={item.unit_name} className="font-semibold text-foreground" />؛ يُطبَّق من «عدّل» إن شئت.
      </p>
    ) : null
  const card = (
    <>
      <Facts facts={facts} columns={3} />
      {suggestion}
      {recent}
    </>
  )
  return (
    <Screen
      title={item.name}
      above={
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="info" className="num">{item.code}</Badge>
          {!item.is_active ? <Badge>مؤرشف</Badge> : item.below_reorder ? <Badge tone="warning">تحت حدّ الطلب</Badge> : null}
        </div>
      }
      description={gaze ? undefined : `${codeName(choices.kinds, item.kind)} · بال${item.unit_name}${item.category ? ` · ${item.category.name}` : ""}`}
      back={{ id: "item-back", label: "المخزون", onClick: onBack }}
      end={{
        id: "item-archive", label: item.is_active ? "أرشف" : "أعد", danger: item.is_active, icon: item.is_active ? Archive : ArchiveRestore,
        onClick: () => setConfirm(true),
      }}
      actions={
        <>
          <Button id="item-edit" variant="secondary" icon={PencilLine} onClick={onEdit}>
            عدّل
          </Button>
          {service ? null : (
            <Button id="item-voucher" icon={ClipboardList} onClick={onVoucher}>
              سند
            </Button>
          )}
        </>
      }
    >
      {fail ? (
        <Alert tone="danger" title="لم يتمّ" live>
          {fail.message}
        </Alert>
      ) : null}
      {gaze ? (
        <Tabs items={[{ id: "card", label: "البطاقة" }, { id: "moves", label: "الحركات" }]} value={tab} onValueChange={setTab} label="بطاقة المنتج" stretch>
          {tab === "card" ? card : movementsTable}
        </Tabs>
      ) : (
        <>
          {card}
          <section aria-labelledby="item-moves" className="flex flex-col gap-tg">
            <h2 id="item-moves" className="text-lead font-semibold">الحركات</h2>
            {movementsTable}
          </section>
        </>
      )}
      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        alert
        title={item.is_active ? "أرشفة المنتج" : "إعادة المنتج"}
        description={item.is_active ? "لا يظهر المؤرشف في البحث ولا في فواتير الشراء الجديدة، ويبقى في بطاقاته وحركاته." : "يعود المنتج إلى البحث والفواتير."}
        closeLabel="رجوع"
        footer={
          <Button
            id="item-archive-yes"
            variant={item.is_active ? "danger" : "primary"}
            commit
            onClick={() => void onArchive().then((result) => { setConfirm(false); setFail(result) })}
          >
            {item.is_active ? "نعم، أرشف" : "نعم، أعد"}
          </Button>
        }
      >
        <p className="text-flow">{item.name}</p>
      </Dialog>
    </Screen>
  )
}

/* ── نموذج المنتج ────────────────────────────────────────────────── */

export interface ItemBody {
  name: string
  kind: "STOCK" | "SERVICE"
  unit: string
  price_halalas: number
  vat_category: string
  vat_exemption_reason: string | null
  supplier_code: string | null
  barcode: string | null
  category_id: string | null
  selling_price_halalas: number | null
  selling_price_includes_vat: boolean
  reorder_level_milli: number | null
  target_level_milli: number | null
  preferred_supplier_id: string | null
  note: string | null
}

/** الحجم الكبير: خمس خطواتٍ قصيرة لا تطول عن شاشة 635px؛ والحجم العادي ثلاث مجموعاتٍ في صفحةٍ تمرّ. */
const ITEM_STEPS = [
  { id: "base", label: "الأساس" },
  { id: "price", label: "السعر والضريبة" },
  { id: "identity", label: "التعريف" },
  { id: "selling", label: "البيع" },
  { id: "ordering", label: "الطلب" },
]

export function ItemForm({ item, initialName = "", choices, categories, supplierOptions, onSupplierQuery, onSave, onBack }: {
  /** المنتج في التعديل، أو null لمنتجٍ جديد. */
  item: Item | null
  initialName?: string
  choices: InventoryChoices
  categories: Category[]
  supplierOptions: ComboboxOption[]
  onSupplierQuery: (query: string) => void
  onSave: (body: ItemBody) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState(0)
  const [name, setName] = React.useState(item?.name ?? initialName)
  const [kind, setKind] = React.useState<"STOCK" | "SERVICE">(item?.kind ?? "STOCK")
  const [unit, setUnit] = React.useState<string | null>(item?.unit ?? null)
  const [price, setPrice] = React.useState(item ? formatAmount(item.price_halalas).replace(/,/g, "") : "")
  const [vat, setVat] = React.useState<string>(item?.vat_category ?? "S")
  const [exemption, setExemption] = React.useState(item?.vat_exemption_reason ?? "")
  const [supplierCode, setSupplierCode] = React.useState(item?.supplier_code ?? "")
  const [barcode, setBarcode] = React.useState(item?.barcode ?? "")
  const [category, setCategory] = React.useState<string | null>(item?.category?.id ?? null)
  const [selling, setSelling] = React.useState(item?.selling_price_halalas === null || item?.selling_price_halalas === undefined ? "" : formatAmount(item.selling_price_halalas).replace(/,/g, ""))
  const [sellingIncludes, setSellingIncludes] = React.useState<"gross" | "net">(item?.selling_price_includes_vat === false ? "net" : "gross")
  const [reorder, setReorder] = React.useState(milliInput(item?.reorder_level_milli ?? null))
  const [target, setTarget] = React.useState(milliInput(item?.target_level_milli ?? null))
  const [supplier, setSupplier] = React.useState<ComboboxOption | null>(item?.preferred_supplier ? { value: item.preferred_supplier.id, label: item.preferred_supplier.name } : null)
  const [supplierQuery, setSupplierQuery] = React.useState(item?.preferred_supplier?.name ?? "")
  const [note, setNote] = React.useState(item?.note ?? "")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const reportSupplier = useOpenReport("item-supplier")

  const unitOptions = choices.units
    .filter((u) => (kind === "SERVICE" ? u.code === "SERVICE" : u.code !== "SERVICE"))
    .map((u) => ({ value: u.code, label: u.name }))
  const decimals = choices.units.find((u) => u.code === unit)?.decimals ?? false
  const unitLocked = Boolean(item && item.kind === "STOCK" && item.on_hand_milli > 0)

  React.useEffect(() => {
    if (kind === "SERVICE") setUnit("SERVICE")
    else if (unit === "SERVICE") setUnit(null)
  }, [kind, unit])

  function validate(): Fail {
    const trimmed = name.trim()
    if ([...trimmed].length < 2) return { message: "اكتب اسم المنتج (حرفان على الأقل).", field: "name" }
    if (!unit) return { message: "اختر الوحدة.", field: "unit" }
    if (parseAmount(price) === null) return { message: "اكتب سعر الشراء مبلغاً، مثل 45.50.", field: "price_halalas" }
    if (vat !== "S" && [...exemption.trim()].length > 80) return { message: "سبب الإعفاء حتى ثمانين حرفاً.", field: "vat_exemption_reason" }
    if (barcode.trim() && !/^(\d{8}|\d{12,14})$/.test(barcode.trim())) return { message: "الباركود 8 أو 12–14 رقماً.", field: "barcode" }
    if (selling.trim() && parseAmount(selling) === null) return { message: "اكتب سعر البيع مبلغاً.", field: "selling_price_halalas" }
    if (reorder.trim() && parseMilli(reorder, decimals) === null) return { message: "حدّ الطلب كميةٌ بالوحدة.", field: "reorder_level_milli" }
    if (target.trim() && parseMilli(target, decimals) === null) return { message: "المستهدف كميةٌ بالوحدة.", field: "target_level_milli" }
    return null
  }

  const stepOf = (field: string | null) =>
    ["name", "unit", "kind"].includes(field ?? "") ? 0
    : ["price_halalas", "vat_category", "vat_exemption_reason"].includes(field ?? "") ? 1
    : ["supplier_code", "barcode", "category_id", "note"].includes(field ?? "") ? 2
    : ["selling_price_halalas", "selling_price_includes_vat"].includes(field ?? "") ? 3 : 4

  async function save() {
    const local = validate()
    if (local) {
      setFail(local)
      if (gaze) setStep(stepOf(local.field))
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onSave({
      name: name.trim(),
      kind,
      unit: unit as string,
      price_halalas: parseAmount(price) as number,
      vat_category: vat,
      vat_exemption_reason: vat !== "S" && exemption.trim() ? exemption.trim() : null,
      supplier_code: supplierCode.trim() || null,
      barcode: barcode.trim() || null,
      category_id: category,
      selling_price_halalas: selling.trim() ? parseAmount(selling) : null,
      selling_price_includes_vat: sellingIncludes === "gross",
      reorder_level_milli: reorder.trim() ? parseMilli(reorder, decimals) : null,
      target_level_milli: target.trim() ? parseMilli(target, decimals) : null,
      preferred_supplier_id: supplier?.value ?? null,
      note: note.trim() || null,
    })
    setBusy(false)
    if (result) {
      setFail(result)
      if (gaze) setStep(stepOf(result.field))
    }
  }

  const error = (field: string) => (fail?.field === field ? fail.message : null)
  const vatOptions = choices.vat_categories.map((c) => ({ value: c.code, label: c.name }))
  const categoryOptions = [{ value: "", label: "بلا تصنيف" }, ...categories.filter((c) => c.is_active).map((c) => ({ value: c.id, label: c.name }))]

  const base = (
    <GazeHost>
      <GazeSlot id="item-name">
        <Field label="اسم المنتج" error={error("name")} required>
          <Input id="item-name" value={name} maxLength={80} onChange={(event) => setName(event.target.value)} />
        </Field>
      </GazeSlot>
      {/* النوع منتقٍ لا بطاقتان: زرّه آمن، فلا يقع تحت ضغطة «منتج جديد» ما يغيّر قيمةً (قاعدة الهبوط). */}
      {item ? null : (
        <Picker
          id="item-kind"
          label="النوع"
          options={choices.kinds.map((k) => ({ value: k.code, label: k.name }))}
          value={kind}
          onValueChange={(value) => setKind(value as "STOCK" | "SERVICE")}
        />
      )}
      {kind === "SERVICE" ? null : (
        <Picker id="item-unit" label="الوحدة" options={unitOptions} value={unit} onValueChange={setUnit} error={error("unit")} required disabled={unitLocked}
                hint={unitLocked ? "لا تتغيّر الوحدة ومنتجٌ له رصيد." : undefined} />
      )}
    </GazeHost>
  )
  const pricing = (
    <GazeHost>
      <GazeSlot id="item-price">
        <Field label="سعر الشراء للوحدة" hint={gaze ? undefined : "كما يُكتب في فواتير مورّديك."} error={error("price_halalas")} required>
          <Input id="item-price" numeric unit="ر.س" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} />
        </Field>
      </GazeSlot>
      <Picker id="item-vat" label="فئة الضريبة" options={vatOptions} value={vat} onValueChange={setVat} error={error("vat_category")} />
      {vat === "S" ? null : (
        <GazeSlot id="item-exemption">
          <Field label="سبب الإعفاء أو الصفرية" hint={gaze ? undefined : "كما يُكتب في الفاتورة الضريبية."} error={error("vat_exemption_reason")}>
            <Input id="item-exemption" value={exemption} maxLength={80} onChange={(event) => setExemption(event.target.value)} />
          </Field>
        </GazeSlot>
      )}
    </GazeHost>
  )
  const identity = (
    <GazeHost>
      <GazeSlot id="item-barcode">
        <Field label="الباركود" hint={gaze ? undefined : "8 أو 12–14 رقماً كما على العبوة."} error={error("barcode")}>
          <Input id="item-barcode" numeric inputMode="numeric" value={barcode} maxLength={14} onChange={(event) => setBarcode(event.target.value)} />
        </Field>
      </GazeSlot>
      <GazeSlot id="item-supplier-code">
        <Field label="رمز المورّد" hint={gaze ? undefined : "رمز المنتج في فواتير المورّد، إن وُجد."} error={error("supplier_code")}>
          <Input id="item-supplier-code" dir="ltr" value={supplierCode} maxLength={40} onChange={(event) => setSupplierCode(event.target.value)} />
        </Field>
      </GazeSlot>
      <Picker id="item-category" label="التصنيف" options={categoryOptions} value={category ?? ""} onValueChange={(value) => setCategory(value || null)} error={error("category_id")} />
      <GazeSlot id="item-note">
        <Field label="ملاحظة" error={error("note")} className="gaze:short:hidden">
          <Textarea id="item-note" rows={2} maxLength={280} value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
      </GazeSlot>
    </GazeHost>
  )
  const selling_ = (
    <GazeHost>
      <GazeSlot id="item-selling">
        <Field label="سعر البيع" error={error("selling_price_halalas")}>
          <Input id="item-selling" numeric unit="ر.س" inputMode="decimal" value={selling} onChange={(event) => setSelling(event.target.value)} />
        </Field>
      </GazeSlot>
      <GazeSlot id="item-selling-basis">
        <RadioCards<"gross" | "net">
          label="سعر البيع"
          value={sellingIncludes}
          onValueChange={setSellingIncludes}
          options={[
            { value: "gross", title: "شاملٌ الضريبة" },
            { value: "net", title: "قبل الضريبة" },
          ]}
        />
      </GazeSlot>
    </GazeHost>
  )
  const ordering = (
    <GazeHost>
      {kind === "SERVICE" ? null : (
        <>
          <GazeSlot id="item-reorder">
            <Field label="حدّ الطلب" hint={gaze ? undefined : "حين ينزل الرصيد إليه يظهر المنتج في «تحت حدّ الطلب»."} error={error("reorder_level_milli")}>
              <Input id="item-reorder" numeric inputMode={decimals ? "decimal" : "numeric"} value={reorder} onChange={(event) => setReorder(event.target.value)} />
            </Field>
          </GazeSlot>
          <GazeSlot id="item-target">
            <Field label="المستوى المستهدف" hint={gaze ? undefined : "ما يُطلب حتى يبلغه الرصيد."} error={error("target_level_milli")}>
              <Input id="item-target" numeric inputMode={decimals ? "decimal" : "numeric"} value={target} onChange={(event) => setTarget(event.target.value)} />
            </Field>
          </GazeSlot>
        </>
      )}
      <GazeSlot id="item-supplier">
        <Field id="item-supplier" label="المورّد المفضّل" error={error("preferred_supplier_id")}>
          <Combobox
            listLabel="المورّدون المطابقون"
            options={supplierOptions}
            value={supplier}
            onValueChange={setSupplier}
            query={supplierQuery}
            onQueryChange={(query) => {
              setSupplierQuery(query)
              onSupplierQuery(query)
            }}
            pageSize={{ compact: 6, gaze: 3, gazeShort: 1 }}
            onOpenChange={reportSupplier}
          />
        </Field>
      </GazeSlot>
    </GazeHost>
  )
  const alert = fail && !fail.field ? (
    <Alert tone="danger" title="لم يُحفظ" live>
      {fail.message}
    </Alert>
  ) : null
  const saveButton = (
    <Button id="item-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
      {item ? "احفظ التعديل" : "أنشئ المنتج"}
    </Button>
  )
  const title = item ? `تعديل ${item.name}` : "منتج جديد"

  if (gaze) {
    const last = step === ITEM_STEPS.length - 1
    const views = [base, pricing, identity, selling_, ordering]
    return (
      <Screen
        title={title}
        above={<Stepper steps={ITEM_STEPS} current={step} />}
        actions={
          <>
            <Button id="item-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(step - 1)}>
              {step === 0 ? "رجوع" : "السابق"}
            </Button>
            {last ? saveButton : (
              <Button id="item-next" variant="secondary" iconEnd={NextIcon} onClick={() => setStep(step + 1)}>
                التالي
              </Button>
            )}
          </>
        }
      >
        {alert}
        {views[step]}
      </Screen>
    )
  }
  return (
    <Screen
      title={title}
      description={item ? undefined : "الاسم والوحدة والسعر والضريبة مطلوبة، ويُعطى المنتج رمزه تلقائياً؛ والباقي يُستكمل لاحقاً."}
      back={{ id: "item-form-back", label: "رجوع", onClick: onBack }}
      actions={saveButton}
    >
      {alert}
      <section aria-labelledby="item-base" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <h2 id="item-base" className="text-lead font-semibold">الأساس</h2>
        {base}
        {pricing}
      </section>
      <section aria-labelledby="item-identity" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <h2 id="item-identity" className="text-lead font-semibold">التعريف</h2>
        {identity}
      </section>
      <section aria-labelledby="item-selling-title" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <h2 id="item-selling-title" className="text-lead font-semibold">البيع والطلب</h2>
        {selling_}
        {ordering}
      </section>
    </Screen>
  )
}

/* ── السند ───────────────────────────────────────────────────────── */

export interface VoucherBody {
  kind: VoucherKind
  quantity_milli: number
  unit_cost_halalas: number | null
  reason: string | null
  note: string | null
  occurred_on: string
}

export function VoucherScreen({ item, choices, today, onSave, onBack }: {
  item: ItemDetail
  choices: InventoryChoices
  today: string
  onSave: (body: VoucherBody) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const canOpen = item.last_movement_at === null
  const [kind, setKind] = React.useState<VoucherKind>(canOpen ? "OPENING" : "COUNT")
  const [step, setStep] = React.useState(0)
  const [quantity, setQuantity] = React.useState("")
  const [cost, setCost] = React.useState("")
  const [reason, setReason] = React.useState<string | null>(null)
  const [note, setNote] = React.useState("")
  const [date, setDate] = React.useState(today)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const decimals = choices.units.find((u) => u.code === item.unit)?.decimals ?? false
  const counted = kind === "COUNT" ? parseMilli(quantity || "0", decimals, 1_000_000_000_000) ?? (quantity.trim() === "" || quantity.trim() === "0" ? 0 : null) : null
  const difference = counted === null ? null : counted - item.on_hand_milli
  const direction = difference === null || difference === 0 ? null : difference < 0 ? "SHORTAGE" : "SURPLUS"
  const needsCost = kind === "OPENING" || (kind === "COUNT" && item.on_hand_milli === 0 && (counted ?? 0) > 0)
  const reasons = kind === "ISSUE" ? choices.issue_reasons : direction ? choices.count_reasons[direction] : []

  async function save() {
    const qty = kind === "COUNT" ? counted : parseMilli(quantity, decimals)
    if (qty === null) {
      setFail({ message: decimals ? "اكتب الكمية، ويجوز كسرٌ بثلاث منازل." : "اكتب الكمية عدداً صحيحاً.", field: "quantity_milli" })
      return
    }
    const unitCost = needsCost ? parseAmount(cost) : null
    if (needsCost && unitCost === null) {
      setFail({ message: "اكتب تكلفة الوحدة مبلغاً.", field: "unit_cost_halalas" })
      return
    }
    if ((kind === "ISSUE" || (kind === "COUNT" && direction)) && !reason) {
      setFail({ message: "اختر السبب.", field: "reason" })
      return
    }
    if (reason === "OTHER" && !note.trim()) {
      setFail({ message: "اكتب السبب في الملاحظة.", field: "note" })
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onSave({
      kind, quantity_milli: qty, unit_cost_halalas: unitCost, reason: kind === "OPENING" ? null : reason,
      note: note.trim() || null, occurred_on: date,
    })
    setBusy(false)
    if (result) setFail(result)
  }

  const error = (field: string) => (fail?.field === field ? fail.message : null)
  const kinds = (
    <RadioCards<VoucherKind>
      label="نوع السند"
      value={kind}
      columns={1}
      onValueChange={(value) => {
        setKind(value)
        setReason(null)
        setFail(null)
      }}
      ids={{ OPENING: "voucher-kind-opening", ISSUE: "voucher-kind-issue", COUNT: "voucher-kind-count" }}
      options={[
        ...(canOpen ? [{ value: "OPENING" as const, title: "رصيد افتتاحي", description: "ما في المخزن قبل أوّل حركة، بتكلفته." }] : []),
        { value: "ISSUE", title: "صرف", description: "بيعٌ أو استعمالٌ أو تلف: ينقص الرصيد." },
        { value: "COUNT", title: "جرد", description: "ما عددته الآن؛ والفرق يُسوّى بسببه." },
      ]}
    />
  )
  const fields = (
    <GazeHost>
      <GazeSlot id="voucher-quantity">
        <Field
          label={kind === "COUNT" ? "العدد الفعلي" : "الكمية"}
          hint={kind === "COUNT" ? <span>الرصيد الدفتري <Qty milli={item.on_hand_milli} unit={item.unit_name} /></span> : `بال${item.unit_name}`}
          error={error("quantity_milli")}
          required
        >
          <Input id="voucher-quantity" numeric inputMode={decimals ? "decimal" : "numeric"} value={quantity} onChange={(event) => setQuantity(event.target.value)} />
        </Field>
      </GazeSlot>
      {needsCost ? (
        <GazeSlot id="voucher-cost">
          <Field label="تكلفة الوحدة" error={error("unit_cost_halalas")} required>
            <Input id="voucher-cost" numeric unit="ر.س" inputMode="decimal" value={cost} onChange={(event) => setCost(event.target.value)} />
          </Field>
        </GazeSlot>
      ) : null}
      {kind === "COUNT" && difference !== null && difference !== 0 ? (
        <p role="status" className={cn("text-small font-semibold", difference < 0 ? "text-destructive" : "text-success")}>
          الفرق <Qty milli={difference} unit={item.unit_name} /> ({difference < 0 ? "عجز" : "زيادة"}).
        </p>
      ) : null}
      {reasons.length ? (
        <Picker id="voucher-reason" label="السبب" options={reasons.map((r) => ({ value: r.code, label: r.name }))} value={reason} onValueChange={setReason} error={error("reason")} required />
      ) : null}
      <GazeSlot id="voucher-note">
        <Field label={reason === "OTHER" ? "اكتب السبب" : "ملاحظة"} error={error("note")} className={cn(reason !== "OTHER" && "gaze:short:hidden")}>
          <Input id="voucher-note" value={note} maxLength={280} onChange={(event) => setNote(event.target.value)} />
        </Field>
      </GazeSlot>
      <GazeSlot id="voucher-date">
        <Field label="التاريخ" error={error("occurred_on")}>
          <Input id="voucher-date" type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} />
        </Field>
      </GazeSlot>
    </GazeHost>
  )
  const alert = fail && !fail.field ? (
    <Alert tone="danger" title="لم يُسجَّل" live>
      {fail.message}
    </Alert>
  ) : null
  const saveButton = (
    <Button id="voucher-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
      سجّل السند
    </Button>
  )
  if (gaze) {
    return (
      <Screen
        title={step === 0 ? "سندٌ جديد" : kind === "OPENING" ? "رصيد افتتاحي" : kind === "ISSUE" ? "سند صرف" : "سند جرد"}
        description={item.name}
        above={<Stepper steps={[{ id: "kind", label: "النوع" }, { id: "fields", label: "البيانات" }]} current={step} />}
        actions={
          <>
            <Button id="voucher-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(0)}>
              {step === 0 ? "رجوع" : "النوع"}
            </Button>
            {step === 0 ? (
              <Button id="voucher-next" variant="secondary" iconEnd={NextIcon} onClick={() => setStep(1)}>
                التالي
              </Button>
            ) : saveButton}
          </>
        }
      >
        {alert}
        {step === 0 ? kinds : fields}
      </Screen>
    )
  }
  return (
    <Screen title="سندٌ جديد" description={item.name} back={{ id: "voucher-back", label: "المنتج", onClick: onBack }} actions={saveButton}>
      {alert}
      {kinds}
      {fields}
    </Screen>
  )
}
