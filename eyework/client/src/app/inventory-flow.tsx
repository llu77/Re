/*
 * بوابة أمين المخزون: المسار
 * ==========================
 * كل شاشةٍ حاويةٌ تقرأ ما تحتاجه من /api/inventory وتكتب إليه، والمسودات تعيش في الخادم:
 *
 *   #/inventory                      الرئيسية (الملخّص والأزرار)، أو الإعداد الأوّل قبلها
 *   #/inventory/settings[/categories] إعدادات المخزن والتصنيفات
 *   #/inventory/purchases[/new]      فواتير الشراء، وفاتورةٌ جديدة (مسودةٌ فارغة تُعاد إن وُجدت)
 *   #/inventory/p/{id}[/review|/reverse]  المسودة أو الفاتورة المسجّلة، ومراجعتها، وعكسها
 *   #/inventory/returns[/new]        المرتجعات، ومرتجعٌ جديد من فاتورة
 *   #/inventory/r/{id}[/review]      مسودة المرتجع أو المرتجع المسجّل، ومراجعته
 *   #/inventory/stock · /items/new · /i/{id}[/edit|/voucher]   المخزون والمنتج وسنده
 *   #/inventory/suppliers[/new] · /s/{id}[/edit|/reps/new|/reps/{rid}]
 *   #/inventory/counts[/new] · /c/{id}[/l/{item}|/add]   الجرد
 *   #/inventory/expenses · /totals · /vouchers
 *
 * ما يصل بعد انتقالٍ أحدث لطلبٍ أقدم لا يُرسم (`current`)، ورسائل الخادم تُعرض كما هي في «حسناً».
 */

import * as React from "react"
import { Calculator, ClipboardCheck, PackageSearch } from "lucide-react"

import { assistantApi, navigate } from "@/app/workspace"
import { Redirect } from "@/components/redirect"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import type { ToolEntry } from "@/components/shell/tools-sheet"
import { VatCalculator } from "@/components/tools/vat-calculator"
import type { ComboboxOption } from "@/components/ui/combobox"
import { Notice } from "@/components/ui/notice"
import { useToast } from "@/components/ui/toast"
import { detail, errorCode, errorField, type ApiResult } from "@/lib/api"
import * as inv from "@/lib/inventory"
import { BASE, countRoute, itemRoute, purchaseRoute, returnRoute, supplierRoute } from "@/lib/inventory"
import { formatAmount } from "@/lib/money"
import { go } from "@/lib/router"
import type { Choices, Me } from "@/lib/store"
import type { Workspace } from "@/lib/workspace"
import { CountAddScreen, CountLineScreen, CountScreen, CountsScreen, NewCountScreen, type CountLineBody, type CountOpenBody } from "@/screens/inventory/counts"
import { InventoryHome } from "@/screens/inventory/home"
import { ExpensesScreen, TotalsScreen, VouchersScreen } from "@/screens/inventory/ledger"
import { ItemForm, ItemScreen, StockScreen, VoucherScreen, type ItemBody, type VoucherBody } from "@/screens/inventory/products"
import {
  PurchaseEditor, PurchaseView, PurchasesScreen, ReverseScreen, type HeaderFields, type LineBody, type QuickItem, type QuickSupplier,
} from "@/screens/inventory/purchase"
import { NewReturnScreen, ReturnEditor, ReturnView, ReturnsScreen, type ReturnsFilter } from "@/screens/inventory/returns"
import { DocumentReview } from "@/screens/inventory/review"
import { CategoriesScreen, SettingsScreen, type Fail, type SettingsBody } from "@/screens/inventory/setup"
import { RepForm, SupplierForm, SupplierScreen, SuppliersScreen, type RepBody, type SupplierBody } from "@/screens/inventory/suppliers"

type SetNotice = (message: string) => void

/** ردّ الخادم إلى رسالة حقلٍ أو رسالةٍ عامة؛ وnull حين نجح. */
function failOf(result: ApiResult): Fail {
  if (result.status >= 200 && result.status < 300) return null
  return { message: detail(result), field: errorField(result) }
}

const PURCHASE_STEPS = [
  { id: "supplier", label: "المورّد" },
  { id: "invoice", label: "الفاتورة" },
  { id: "amounts", label: "المبالغ" },
  { id: "lines", label: "المنتجات" },
  { id: "review", label: "المراجعة" },
]
const RETURN_STEPS = [
  { id: "quantities", label: "الكميات" },
  { id: "reason", label: "السبب" },
  { id: "review", label: "المراجعة" },
]

/**
 * يقرأ من الخادم ويعيد القراءة حين تتغيّر المفاتيح؛ وما يصل بعد تغييرٍ أحدث يُهمل. والبيانات مربوطةٌ
 * بمفاتيحها: بعد الانتقال من مستندٍ إلى آخر في الحاوية نفسها لا يُعرض الأوّل تحت معرّف الثاني (ولا
 * تُرسل كتابةٌ برقم صفّه) حتى يصل الثاني.
 */
function useLoad<T>(load: () => Promise<ApiResult<T>>, deps: React.DependencyList, setNotice: SetNotice, onMissing?: () => void) {
  const key = JSON.stringify(deps)
  const [state, setState] = React.useState<{ key: string; data: T | null }>({ key, data: null })
  const [tick, setTick] = React.useState(0)
  const reload = React.useCallback(() => setTick((t) => t + 1), [])
  const setData = React.useCallback((data: T | null) => setState({ key, data }), [key])
  React.useEffect(() => {
    let current = true
    void load().then((result) => {
      if (!current) return
      if (result.status === 200) setState({ key, data: result.data })
      else if (result.status === 404 && onMissing) onMissing()
      else if (result.status !== 401) setNotice(detail(result))
    })
    return () => {
      current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick])
  return { data: state.key === key ? state.data : null, setData, reload }
}

/** بحثٌ يعرض نتيجة آخر كلمةٍ وحدها. */
function useSearch<T>(search: (query: string) => Promise<ApiResult<T>>, empty: T) {
  const [result, setResult] = React.useState<T>(empty)
  const seq = React.useRef(0)
  const run = React.useCallback(
    (query: string) => {
      const mine = ++seq.current
      if (!query.trim()) {
        setResult(empty)
        return
      }
      void search(query).then((answer) => {
        if (seq.current !== mine) return
        if (answer.status === 200 && answer.data) setResult(answer.data)
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [search],
  )
  return [result, run] as const
}

const supplierOption = (s: inv.Supplier): ComboboxOption => ({ value: s.id, label: s.name, description: s.vat_number ? `ض ${s.vat_number}` : undefined })
const itemOption = (i: inv.ItemOption): ComboboxOption => ({ value: i.id, label: i.name, description: `${i.code} · ${i.unit_name}`, meta: `${inv.formatMilli(i.on_hand_milli)} ${i.unit_name}` })
const searchSuppliers = (q: string) => inv.listSuppliers(q, 1, 10)
const searchItemsPlain = (q: string) => inv.searchItems(q, null)
const EMPTY_SUPPLIERS: inv.Paged<inv.Supplier> = { items: [], page: 1, pages: 1, total: 0 }
const EMPTY_ITEMS: { items: inv.ItemOption[]; create: { name: string } | null } = { items: [], create: null }

function queryOf(path: string): URLSearchParams {
  return new URLSearchParams(path.split("?")[1] ?? "")
}

/* ── الإعداد والإعدادات ──────────────────────────────────────────── */

function SettingsContainer({ summary, first, onSaved }: { summary: inv.Summary; first: boolean; onSaved: () => void }) {
  const save = async (body: SettingsBody): Promise<Fail> => {
    const result = await inv.putSettings(body)
    const fail = failOf(result)
    if (!fail) onSaved()
    return fail
  }
  return (
    <SettingsScreen
      settings={summary.settings}
      onSave={save}
      onBack={() => go(BASE)}
      onCategories={first ? null : () => go(`${BASE}/settings/categories`)}
    />
  )
}

function CategoriesContainer({ setNotice }: { setNotice: SetNotice }) {
  const { data, reload } = useLoad(() => inv.listCategories(true), [], setNotice)
  return (
    <CategoriesScreen
      categories={data?.items ?? []}
      onAdd={async (name) => {
        const fail = failOf(await inv.createCategory(name))
        if (!fail) reload()
        return fail
      }}
      onToggle={async (category) => {
        const fail = failOf(await inv.patchCategory(category.id, category.row_version, { is_active: !category.is_active }))
        if (!fail) reload()
        return fail
      }}
      onBack={() => go(`${BASE}/settings`)}
    />
  )
}

/* ── المنتجات ────────────────────────────────────────────────────── */

function StockContainer({ path, setNotice }: { path: string; setNotice: SetNotice }) {
  const params = queryOf(path)
  const filter = (params.get("filter") as inv.ItemFilter | null) ?? "all"
  const [query, setQuery] = React.useState("")
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listItems(query, filter, null, page + 1, 10), [query, filter, page], setNotice)
  return (
    <StockScreen
      data={data}
      query={query}
      onQuery={(q) => {
        setQuery(q)
        setPage(0)
      }}
      filter={filter}
      onFilter={(f) => {
        setPage(0)
        go(f === "all" ? `${BASE}/stock` : `${BASE}/stock?filter=${f}`, { replace: true })
      }}
      page={page}
      onPage={setPage}
      onOpen={(item) => go(itemRoute(item.id))}
      onNew={() => go(`${BASE}/items/new`)}
      onBack={() => go(BASE)}
    />
  )
}

function ItemContainer({ id, choices, setNotice }: { id: string; choices: inv.InventoryChoices; setNotice: SetNotice }) {
  const [page, setPage] = React.useState(0)
  const item = useLoad(() => inv.getItem(id), [id], setNotice, () => go(`${BASE}/stock`, { replace: true }))
  const movements = useLoad(() => inv.itemMovements(id, page + 1, 10), [id, page], setNotice)
  if (!item.data) return null
  const current = item.data
  return (
    <ItemScreen
      item={current}
      movements={movements.data}
      movementsPage={page}
      onMovementsPage={setPage}
      choices={choices}
      onEdit={() => go(itemRoute(id, "/edit"))}
      onVoucher={() => go(itemRoute(id, "/voucher"))}
      onArchive={async () => {
        const fail = failOf(await inv.patchItem(id, current.row_version, { is_active: !current.is_active }))
        if (!fail) item.reload()
        return fail
      }}
      onBack={() => go(`${BASE}/stock`)}
    />
  )
}

function ItemFormContainer({ id, choices, initialName, setNotice }: { id: string | null; choices: inv.InventoryChoices; initialName: string; setNotice: SetNotice }) {
  const toast = useToast()
  const item = useLoad(() => (id ? inv.getItem(id) : Promise.resolve({ status: 200, data: null } as ApiResult<inv.ItemDetail>)), [id], setNotice, () => go(`${BASE}/stock`, { replace: true }))
  const categories = useLoad(() => inv.listCategories(), [], setNotice)
  const [suppliers, searchSupplier] = useSearch(searchSuppliers, EMPTY_SUPPLIERS)
  if (id && !item.data) return null
  return (
    <ItemForm
      key={id ?? "new"}
      item={item.data}
      initialName={initialName}
      choices={choices}
      categories={categories.data?.items ?? []}
      supplierOptions={suppliers.items.map(supplierOption)}
      onSupplierQuery={searchSupplier}
      onSave={async (body: ItemBody) => {
        const result = id && item.data ? await inv.patchItem(id, item.data.row_version, body) : await inv.createItem(body)
        const fail = failOf(result)
        if (fail || !result.data) return fail
        const saved = result.data
        if (saved.similar?.length) {
          toast.show({ title: `أُنشئ ${saved.code}`, description: `منتجاتٌ بأسماءٍ قريبة: ${saved.similar.map((s) => `«${s.name}»`).join("، ")}.`, tone: "info" })
        } else if (!id) {
          toast.show({ title: `أُنشئ المنتج ${saved.code}`, tone: "success" })
        }
        go(itemRoute(saved.id), { replace: true })
        return null
      }}
      onBack={() => go(id ? itemRoute(id) : `${BASE}/stock`)}
    />
  )
}

function VoucherContainer({ id, choices, today, setNotice }: { id: string; choices: inv.InventoryChoices; today: string; setNotice: SetNotice }) {
  const toast = useToast()
  const token = React.useRef(inv.clientToken())
  const item = useLoad(() => inv.getItem(id), [id], setNotice, () => go(`${BASE}/stock`, { replace: true }))
  if (!item.data) return null
  const current = item.data
  return (
    <VoucherScreen
      item={current}
      choices={choices}
      today={today}
      onSave={async (body: VoucherBody) => {
        const common = { client_token: token.current, item_id: id, occurred_on: body.occurred_on }
        const result =
          body.kind === "OPENING"
            ? await inv.openingVoucher({ ...common, quantity_milli: body.quantity_milli, unit_cost_halalas: body.unit_cost_halalas ?? 0 })
            : body.kind === "ISSUE"
              ? await inv.issueVoucher({ ...common, quantity_milli: body.quantity_milli, reason: body.reason ?? "OTHER", note: body.note })
              : await inv.countVoucher({ ...common, counted_milli: body.quantity_milli, expected_on_hand_milli: current.on_hand_milli, unit_cost_halalas: body.unit_cost_halalas, reason: body.reason, note: body.note })
        const fail = failOf(result)
        if (fail || !result.data) return fail
        toast.show({ title: `سُجّل السند ${result.data.label}`, tone: "success" })
        go(itemRoute(id), { replace: true })
        return null
      }}
      onBack={() => go(itemRoute(id))}
    />
  )
}

/* ── المورّدون ───────────────────────────────────────────────────── */

function SuppliersContainer({ setNotice }: { setNotice: SetNotice }) {
  const [query, setQuery] = React.useState("")
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listSuppliers(query, page + 1, 10), [query, page], setNotice)
  return (
    <SuppliersScreen
      data={data}
      query={query}
      onQuery={(q) => {
        setQuery(q)
        setPage(0)
      }}
      page={page}
      onPage={setPage}
      onOpen={(supplier) => go(supplierRoute(supplier.id))}
      onNew={() => go(`${BASE}/suppliers/new`)}
      onBack={() => go(`${BASE}/stock`)}
    />
  )
}

function SupplierContainer({ id, sub, setNotice }: { id: string; sub: string | null; setNotice: SetNotice }) {
  // تُقرأ من جديد عند العودة من التعديل أو المندوب (المسار الفرعي يتغيّر والحاوية نفسها تبقى).
  const supplier = useLoad(() => inv.getSupplier(id), [id, sub], setNotice, () => go(`${BASE}/suppliers`, { replace: true }))
  if (!supplier.data) return null
  const current = supplier.data
  if (sub === "edit") {
    return (
      <SupplierForm
        supplier={current}
        onSave={async (body: SupplierBody) => {
          const fail = failOf(await inv.patchSupplier(id, current.row_version, body))
          if (!fail) go(supplierRoute(id), { replace: true })
          return fail
        }}
        onBack={() => go(supplierRoute(id))}
      />
    )
  }
  if (sub && sub.startsWith("reps/")) {
    const repId = sub.slice(5)
    const rep = repId === "new" ? null : (current.reps ?? []).find((r) => r.id === repId) ?? null
    if (repId !== "new" && !rep) return <Redirect to={supplierRoute(id)} />
    return (
      <RepForm
        supplier={current}
        rep={rep}
        onSave={async (body: RepBody) => {
          const fail = failOf(rep ? await inv.patchRep(id, rep.id, rep.row_version, body) : await inv.createRep(id, body))
          if (!fail) go(supplierRoute(id), { replace: true })
          return fail
        }}
        onBack={() => go(supplierRoute(id))}
      />
    )
  }
  return (
    <SupplierScreen
      supplier={current}
      onEdit={() => go(supplierRoute(id, "/edit"))}
      onAddRep={() => go(supplierRoute(id, "/reps/new"))}
      onEditRep={(rep) => go(supplierRoute(id, `/reps/${rep.id}`))}
      onBack={() => go(`${BASE}/suppliers`)}
    />
  )
}

function NewSupplierContainer() {
  return (
    <SupplierForm
      supplier={null}
      onSave={async (body: SupplierBody) => {
        const result = await inv.createSupplier(body)
        const fail = failOf(result)
        if (!fail && result.data) go(supplierRoute(result.data.id), { replace: true })
        return fail
      }}
      onBack={() => go(`${BASE}/suppliers`)}
    />
  )
}

/* ── فواتير الشراء ───────────────────────────────────────────────── */

function PurchasesContainer({ path, setNotice }: { path: string; setNotice: SetNotice }) {
  const status = (queryOf(path).get("status")?.toUpperCase() as inv.PurchaseStatus | null) ?? "all"
  const [query, setQuery] = React.useState("")
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listPurchases(status === "all" ? null : status, query, page + 1, 10), [status, query, page], setNotice)
  return (
    <PurchasesScreen
      data={data}
      status={status}
      onStatus={(s) => {
        setPage(0)
        go(s === "all" ? `${BASE}/purchases` : `${BASE}/purchases?status=${s.toLowerCase()}`, { replace: true })
      }}
      query={query}
      onQuery={(q) => {
        setQuery(q)
        setPage(0)
      }}
      page={page}
      onPage={setPage}
      onOpen={(row) => go(purchaseRoute(row.id))}
      onNew={() => go(`${BASE}/purchases/new`)}
      onBack={() => go(BASE)}
    />
  )
}

/** مسودةٌ فارغة قائمة تُعاد، وإلا تُنشأ واحدة بأساس الضريبة من الإعدادات. */
function NewPurchaseContainer({ summary, setNotice }: { summary: inv.Summary; setNotice: SetNotice }) {
  React.useEffect(() => {
    let current = true
    void (async () => {
      const drafts = await inv.listPurchases("DRAFT", "", 1, 20)
      if (!current) return
      const empty = drafts.status === 200 && drafts.data ? drafts.data.items.find((row) => row.lines === 0 && !row.supplier_name && !row.supplier_invoice_no) : undefined
      if (empty) {
        go(purchaseRoute(empty.id), { replace: true })
        return
      }
      const created = await inv.createPurchase({ prices_include_vat: summary.settings?.cost_includes_vat ?? false })
      if (!current) return
      if (created.status === 201 && created.data) go(purchaseRoute(created.data.id), { replace: true })
      else if (created.status !== 401) {
        setNotice(detail(created))
        go(BASE, { replace: true })
      }
    })()
    return () => {
      current = false
    }
  }, [summary.settings?.cost_includes_vat, setNotice])
  return null
}

function PurchaseContainer({ id, sub, path, choices, today, setNotice }: {
  id: string
  sub: string | null
  path: string
  choices: inv.InventoryChoices
  today: string
  setNotice: SetNotice
}) {
  const toast = useToast()
  const purchase = useLoad(() => inv.getPurchase(id), [id], setNotice, () => go(BASE, { replace: true }))
  const [suppliers, searchSupplier] = useSearch(searchSuppliers, EMPTY_SUPPLIERS)
  const searchItems = React.useCallback((q: string) => inv.searchItems(q, id), [id])
  const [found, searchItem] = useSearch(searchItems, EMPTY_ITEMS)
  const supplierId = purchase.data?.supplier?.id ?? null
  const reps = useLoad(() => (supplierId ? inv.getSupplier(supplierId) : Promise.resolve({ status: 200, data: null } as ApiResult<inv.Supplier>)), [supplierId], setNotice)
  const focusLine = Number(queryOf(path).get("line") ?? "") || null
  if (!purchase.data) return null
  const current = purchase.data
  const apply = (result: ApiResult<inv.Purchase>): Fail => {
    const fail = failOf(result)
    if (!fail && result.data) purchase.setData(result.data)
    else if (result.status === 409 && errorCode(result) === "STALE") purchase.reload()
    return fail
  }
  const back = () => go(BASE)
  if (current.status === "DRAFT") {
    if (sub === "review") {
      return (
        <ReviewContainer
          kind="PURCHASE"
          id={id}
          title="مراجعة الفاتورة قبل تسجيلها"
          subject={`${current.supplier?.name ?? ""}${current.supplier_invoice_no ? ` · ${current.supplier_invoice_no}` : ""}`}
          lineNames={Object.fromEntries(current.lines.map((line) => [line.line_no, line.item.name]))}
          totals={current.totals}
          linesCount={current.lines.length}
          steps={PURCHASE_STEPS}
          loadFlags={() => inv.purchaseFlags(id)}
          post={(rowVersion, acknowledged) => inv.postPurchase(id, rowVersion, acknowledged)}
          onPosted={(posted) => {
            purchase.setData(posted)
            toast.show({ title: `سُجّلت الفاتورة ${posted.label ?? ""}`, description: "زاد المخزون ودخلت المصاريف.", tone: "success" })
            go(purchaseRoute(id), { replace: true })
          }}
          onEdit={(lineNo) => go(purchaseRoute(id) + (lineNo ? `?line=${lineNo}` : ""))}
          onBack={() => go(purchaseRoute(id))}
          setNotice={setNotice}
        />
      )
    }
    const entry = (item: inv.ItemOption): inv.ItemOption =>
      current.prices_include_vat && item.vat_category === "S" ? { ...item, price_entry_halalas: Math.round(item.price_halalas * 1.15) } : item
    return (
      <PurchaseEditor
        key={`${id}-${focusLine ?? ""}`}
        purchase={current}
        choices={choices}
        today={today}
        supplierOptions={suppliers.items.map(supplierOption)}
        onSupplierQuery={searchSupplier}
        reps={supplierId ? (reps.data?.reps ?? null) : []}
        itemOptions={found.items.map((i) => ({ ...itemOption(i), meta: `${formatAmount(i.price_entry_halalas)} ر.س` }))}
        items={found.items}
        onItemQuery={searchItem}
        onHeader={async (fields: HeaderFields) => apply(await inv.patchPurchase(id, current.row_version, fields))}
        onCreateSupplier={async (body: QuickSupplier) => {
          const result = await inv.createSupplier(body)
          const fail = failOf(result)
          if (fail || !result.data) return { fail: fail ?? { message: detail(result), field: null } }
          return { option: supplierOption(result.data) }
        }}
        onCreateItem={async (body: QuickItem) => {
          const result = await inv.createItem({ ...body, kind: "STOCK" })
          const fail = failOf(result)
          if (fail || !result.data) return { fail: fail ?? { message: detail(result), field: null } }
          if (result.data.similar?.length) {
            toast.show({ title: `أُنشئ ${result.data.code}`, description: `منتجاتٌ بأسماءٍ قريبة: ${result.data.similar.map((s) => `«${s.name}»`).join("، ")}.`, tone: "info" })
          }
          return { item: entry(result.data) }
        }}
        onAddLine={async (body: LineBody) => apply(await inv.addLine(id, current.row_version, body))}
        onPatchLine={async (lineNo, body: LineBody) => apply(await inv.patchLine(id, lineNo, current.row_version, body))}
        onRemoveLine={async (lineNo) => apply(await inv.removeLine(id, lineNo, current.row_version))}
        onDiscard={async () => {
          const result = await inv.discardPurchase(id, current.row_version)
          const fail = failOf(result)
          if (!fail) go(BASE, { replace: true })
          return fail
        }}
        onReview={() => go(purchaseRoute(id, "/review"))}
        onBack={back}
        focusLine={focusLine}
      />
    )
  }
  if (sub === "reverse" && current.status === "POSTED") {
    return (
      <ReverseScreen
        purchase={current}
        choices={choices}
        onReverse={async (reason, note) => {
          const result = await inv.reversePurchase(id, current.row_version, reason, note)
          const fail = apply(result)
          if (!fail) {
            toast.show({ title: `عُكست الفاتورة بالقيد ${result.data?.reversal?.label ?? ""}`, tone: "info" })
            go(purchaseRoute(id), { replace: true })
          }
          return fail
        }}
        onBack={() => go(purchaseRoute(id))}
      />
    )
  }
  if (sub) return <Redirect to={purchaseRoute(id)} />
  return (
    <PurchaseView
      purchase={current}
      choices={choices}
      onReturn={() => void inv.createReturn(id, current.rep?.id ?? null).then((result) => {
        if (result.status === 201 && result.data) go(returnRoute(result.data.id))
        else if (result.status !== 401) setNotice(detail(result))
      })}
      onReverse={() => go(purchaseRoute(id, "/reverse"))}
      onOpenReturn={(returnId) => go(returnRoute(returnId))}
      onBack={() => go(`${BASE}/purchases`)}
    />
  )
}

/* ── المراجعة ────────────────────────────────────────────────────── */

function ReviewContainer<T>({ kind, id, title, subject, lineNames, totals, linesCount, steps, loadFlags, post, onPosted, onEdit, onBack, setNotice }: {
  kind: "PURCHASE" | "RETURN"
  id: string
  title: string
  subject: string
  lineNames: Record<number, string>
  totals: inv.Totals
  linesCount: number
  steps: { id: string; label: string }[]
  loadFlags: () => Promise<ApiResult<inv.Flags>>
  post: (rowVersion: number, acknowledged: string[]) => Promise<ApiResult<T>>
  onPosted: (posted: T) => void
  onEdit: (lineNo: number | null) => void
  onBack: () => void
  setNotice: SetNotice
}) {
  const [flags, setFlags] = React.useState<inv.Flags | null>(null)
  const [answer, setAnswer] = React.useState<inv.ReviewAnswer | null>(null)
  const [reviewing, setReviewing] = React.useState(false)
  const [acknowledged, setAcknowledged] = React.useState<string[]>([])
  const [posting, setPosting] = React.useState(false)
  const latest = React.useRef(0)

  // الدوالّ من المضيف تتغيّر مع كل رسم؛ تُقرأ من مرجعٍ فلا تعيد المراجعة بنفسها: ضغطةٌ واحدة، استدعاءٌ واحد.
  const loader = React.useRef(loadFlags)
  loader.current = loadFlags

  const refresh = React.useCallback(async () => {
    const result = await loader.current()
    if (result.status === 200 && result.data) {
      setFlags(result.data)
      setAcknowledged((keys) => keys.filter((key) => result.data?.flags.some((flag) => flag.key === key)))
      return result.data
    }
    if (result.status !== 401) setNotice(detail(result))
    return null
  }, [setNotice])

  const review = React.useCallback(async () => {
    const mine = ++latest.current
    setReviewing(true)
    const current = await refresh()
    if (mine !== latest.current || !current) return
    const result = await inv.reviewDocument(kind, id, current.row_version)
    if (mine !== latest.current) return
    setReviewing(false)
    if (result.status === 200 && result.data) {
      setAnswer(result.data)
      await refresh()
    } else if (result.status !== 401) {
      // مراجعةٌ لم تتمّ ليست خطأً يحجب التسجيل: تُقال في سطر الحال.
      setAnswer({ subject: { kind, id, digest: current.digest ?? "" }, review: { status: "UNAVAILABLE", reason: errorCode(result), message: detail(result) }, flags: [] })
    }
  }, [kind, id, refresh])

  React.useEffect(() => {
    void review()
    return () => {
      latest.current += 1
    }
  }, [review])

  return (
    <DocumentReview
      kind={kind}
      title={title}
      subject={subject}
      lineNames={lineNames}
      totals={totals}
      linesCount={linesCount}
      flags={flags}
      answer={answer}
      reviewing={reviewing}
      onReviewAgain={() => void review()}
      acknowledged={acknowledged}
      onAcknowledge={(key, on) => setAcknowledged((keys) => (on ? [...new Set([...keys, key])] : keys.filter((k) => k !== key)))}
      onDecide={async (flag, choice) => {
        const digest = flags?.digest ?? answer?.subject.digest
        if (!digest) return
        const result = await inv.decideFlag(flag.id, choice, digest)
        if (result.status === 200) await refresh()
        else if (result.status !== 401) setNotice(detail(result))
      }}
      onEdit={onEdit}
      onPost={async () => {
        if (!flags) return { message: "انتظر التنبيهات ثم سجّل.", field: null }
        setPosting(true)
        const result = await post(flags.row_version, acknowledged)
        setPosting(false)
        if (result.status === 200 && result.data) {
          onPosted(result.data)
          return null
        }
        const code = errorCode(result)
        if (result.status === 409 && (code === "FLAGS_CHANGED" || code === "FLAGS_UNDECIDED" || code === "STALE")) {
          await refresh()
          return { message: code === "FLAGS_UNDECIDED" ? `قبل المتابعة: ${detail(result)}` : detail(result), field: null }
        }
        return failOf(result)
      }}
      posting={posting}
      onBack={onBack}
      steps={steps}
    />
  )
}

/* ── المرتجعات ───────────────────────────────────────────────────── */

function ReturnsContainer({ path, setNotice }: { path: string; setNotice: SetNotice }) {
  const params = queryOf(path)
  const filter: ReturnsFilter = params.get("awaiting") ? "awaiting" : params.get("status") === "draft" ? "DRAFT" : "all"
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listReturns(filter === "DRAFT" ? "DRAFT" : null, filter === "awaiting", page + 1, 10), [filter, page], setNotice)
  return (
    <ReturnsScreen
      data={data}
      filter={filter}
      onFilter={(f) => {
        setPage(0)
        go(f === "awaiting" ? `${BASE}/returns?awaiting=1` : f === "DRAFT" ? `${BASE}/returns?status=draft` : `${BASE}/returns`, { replace: true })
      }}
      page={page}
      onPage={setPage}
      onOpen={(row) => go(returnRoute(row.id))}
      onNew={() => go(`${BASE}/returns/new`)}
      onBack={() => go(BASE)}
    />
  )
}

const searchPosted = (q: string) => inv.listPurchases("POSTED", q, 1, 10)
const EMPTY_PURCHASES: inv.Paged<inv.PurchaseRow> = { items: [], page: 1, pages: 1, total: 0 }

function NewReturnContainer({ setNotice }: { setNotice: SetNotice }) {
  const [query, setQuery] = React.useState("")
  const initial = useLoad(() => inv.listPurchases("POSTED", "", 1, 10), [], setNotice)
  const [found, search] = useSearch(searchPosted, EMPTY_PURCHASES)
  const rows = (query.trim() ? found : initial.data ?? EMPTY_PURCHASES).items.filter((row) => row.reversal_number === null)
  return (
    <NewReturnScreen
      options={rows.map((row) => ({ value: row.id, label: `${row.supplier_name ?? ""} · ${row.label ?? ""}`, description: row.supplier_invoice_no ? `فاتورة ${row.supplier_invoice_no}` : undefined, meta: row.total_halalas === null ? undefined : `${formatAmount(row.total_halalas)} ر.س` }))}
      purchases={rows}
      query={query}
      onQuery={(q) => {
        setQuery(q)
        search(q)
      }}
      onStart={async (purchaseId) => {
        const result = await inv.createReturn(purchaseId, null)
        const fail = failOf(result)
        if (!fail && result.data) go(returnRoute(result.data.id), { replace: true })
        return fail
      }}
      onBack={() => go(BASE)}
    />
  )
}

function ReturnContainer({ id, sub, choices, today, setNotice }: { id: string; sub: string | null; choices: inv.InventoryChoices; today: string; setNotice: SetNotice }) {
  const toast = useToast()
  const draft = useLoad(() => inv.getReturn(id), [id], setNotice, () => go(BASE, { replace: true }))
  const supplierId = draft.data?.purchase.supplier_id ?? null
  const reps = useLoad(() => (supplierId ? inv.getSupplier(supplierId) : Promise.resolve({ status: 200, data: null } as ApiResult<inv.Supplier>)), [supplierId], setNotice)
  if (!draft.data) return null
  const current = draft.data
  const apply = (result: ApiResult<inv.Return>): Fail => {
    const fail = failOf(result)
    if (!fail && result.data) draft.setData(result.data)
    else if (result.status === 409 && errorCode(result) === "STALE") draft.reload()
    return fail
  }
  if (current.status === "DRAFT") {
    if (sub === "review") {
      return (
        <ReviewContainer
          kind="RETURN"
          id={id}
          title="مراجعة المرتجع قبل تسجيله"
          subject={`${current.purchase.supplier_name ?? ""} · ${current.purchase.label}`}
          lineNames={Object.fromEntries(current.lines.map((line) => [line.line_no, line.item.name]))}
          totals={{ net: 0, vat: 0, gross: current.lines.reduce((sum, line) => sum + Math.round((line.quantity_milli * line.unit_price_halalas) / 1000), 0) }}
          linesCount={current.lines.filter((line) => line.quantity_milli > 0).length}
          steps={RETURN_STEPS}
          loadFlags={() => inv.returnFlags(id)}
          post={(rowVersion, acknowledged) => inv.postReturn(id, rowVersion, acknowledged)}
          onPosted={(posted) => {
            draft.setData(posted)
            toast.show({ title: `سُجّل المرتجع ${posted.label ?? ""}`, description: "نقص المخزون وخُصم من المصاريف؛ ينتظر إشعار المورّد الدائن.", tone: "success" })
            go(returnRoute(id), { replace: true })
          }}
          onEdit={() => go(returnRoute(id))}
          onBack={() => go(returnRoute(id))}
          setNotice={setNotice}
        />
      )
    }
    return (
      <ReturnEditor
        key={id}
        draft={current}
        choices={choices}
        reps={reps.data?.reps ?? null}
        today={today}
        onLine={async (lineNo, quantity) => apply(await inv.putReturnLine(id, lineNo, current.row_version, quantity))}
        onHeader={async (fields) => apply(await inv.patchReturn(id, current.row_version, fields))}
        onDiscard={async () => {
          const fail = failOf(await inv.discardReturn(id, current.row_version))
          if (!fail) go(BASE, { replace: true })
          return fail
        }}
        onReview={() => go(returnRoute(id, "/review"))}
        onBack={() => go(BASE)}
      />
    )
  }
  if (sub) return <Redirect to={returnRoute(id)} />
  return (
    <ReturnView
      draft={current}
      choices={choices}
      today={today}
      onCreditNote={async (number, date) => apply(await inv.putCreditNote(id, current.row_version, number, date))}
      onOpenPurchase={() => go(purchaseRoute(current.purchase.id))}
      onBack={() => go(`${BASE}/returns`)}
    />
  )
}

/* ── الجرد ───────────────────────────────────────────────────────── */

function CountsContainer({ summary, setNotice }: { summary: inv.Summary; setNotice: SetNotice }) {
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listCounts(page + 1, 10), [page], setNotice)
  const open = summary.attention.open_count
  return (
    <CountsScreen
      data={data}
      page={page}
      onPage={setPage}
      openSession={open}
      onOpen={(row) => go(countRoute(row.id))}
      onNew={() => go(open ? countRoute(open.id) : `${BASE}/counts/new`)}
      onBack={() => go(BASE)}
    />
  )
}

function NewCountContainer({ choices, onOpened, setNotice }: { choices: inv.InventoryChoices; onOpened: () => void; setNotice: SetNotice }) {
  const token = React.useRef(inv.clientToken())
  const categories = useLoad(() => inv.listCategories(), [], setNotice)
  const [found, search] = useSearch(searchItemsPlain, EMPTY_ITEMS)
  return (
    <NewCountScreen
      choices={choices}
      categories={categories.data?.items ?? []}
      itemOptions={found.items.map(itemOption)}
      onItemQuery={search}
      onOpen={async (body: CountOpenBody) => {
        const result = await inv.openCount({ client_token: token.current, ...body })
        const fail = failOf(result)
        if (!fail && result.data) {
          onOpened()
          go(countRoute(result.data.id), { replace: true })
        }
        return fail
      }}
      onBack={() => go(`${BASE}/counts`)}
    />
  )
}

function CountContainer({ id, sub, choices, today, onChanged, setNotice }: {
  id: string
  sub: string | null
  choices: inv.InventoryChoices
  today: string
  onChanged: () => void
  setNotice: SetNotice
}) {
  const toast = useToast()
  const [page, setPage] = React.useState(0)
  const session = useLoad(() => inv.getCount(id), [id], setNotice, () => go(`${BASE}/counts`, { replace: true }))
  const [found, search] = useSearch(searchItemsPlain, EMPTY_ITEMS)
  if (!session.data) return null
  const current = session.data
  const apply = (result: ApiResult<inv.CountSession>): Fail => {
    const fail = failOf(result)
    if (!fail && result.data) session.setData(result.data)
    else if (result.status === 409 && errorCode(result) === "STALE") session.reload()
    return fail
  }
  if (sub && sub.startsWith("l/") && current.status === "OPEN") {
    const itemId = sub.slice(2)
    const index = current.lines.findIndex((line) => line.item.id === itemId)
    const line = current.lines[index]
    if (!line) return <Redirect to={countRoute(id)} />
    const previous = current.lines[index - 1]
    const next = current.lines[index + 1]
    return (
      <CountLineScreen
        key={itemId}
        session={current}
        line={line}
        choices={choices}
        onSave={async (body: CountLineBody) => apply(await inv.setCountLine(id, itemId, current.row_version, body))}
        onPrevious={previous ? () => go(countRoute(id, `/l/${previous.item.id}`)) : null}
        onNext={next ? () => go(countRoute(id, `/l/${next.item.id}`)) : null}
        onBack={() => go(countRoute(id))}
      />
    )
  }
  if (sub === "add" && current.status === "OPEN") {
    return (
      <CountAddScreen
        session={current}
        itemOptions={found.items.map(itemOption)}
        onItemQuery={search}
        onAdd={async (itemId) => {
          const fail = apply(await inv.addCountItem(id, itemId))
          if (!fail) go(countRoute(id), { replace: true })
          return fail
        }}
        onBack={() => go(countRoute(id))}
      />
    )
  }
  if (sub) return <Redirect to={countRoute(id)} />
  return (
    <CountScreen
      session={current}
      page={page}
      onPage={setPage}
      today={today}
      onOpenLine={(line) => go(countRoute(id, `/l/${line.item.id}`))}
      onRefresh={async () => {
        const result = await inv.refreshCount(id)
        const fail = apply(result)
        if (!fail) toast.show({ title: result.data?.refreshed ? `حُدّث الرصيد الدفتري لـ${result.data.refreshed} منتج؛ أعد عدّه.` : "الأرصدة كما هي.", tone: "info" })
        return fail
      }}
      onAdd={() => go(countRoute(id, "/add"))}
      onPost={async (occurredOn) => {
        const result = await inv.postCount(id, current.row_version, occurredOn)
        const fail = apply(result)
        if (!fail) {
          onChanged()
          toast.show({ title: `رُحّل الجرد ${current.label}`, description: `عُدّ ${result.data?.items_counted ?? 0} منتج، مطابق ${result.data?.items_matched ?? 0}.`, tone: "success" })
        }
        return fail
      }}
      onCancel={async () => {
        const fail = apply(await inv.cancelCount(id, current.row_version))
        if (!fail) onChanged()
        return fail
      }}
      onBack={() => go(`${BASE}/counts`)}
    />
  )
}

/* ── المصاريف والمجاميع والسندات ─────────────────────────────────── */

function ExpensesContainer({ summary, setNotice }: { summary: inv.Summary; setNotice: SetNotice }) {
  const [month, setMonth] = React.useState(summary.month)
  const [page, setPage] = React.useState(0)
  const range = inv.monthRange(month)
  const { data } = useLoad(() => inv.expenses(range.from, range.to, page + 1, 20), [month, page], setNotice)
  return (
    <ExpensesScreen
      month={month}
      data={data}
      canNext={month < summary.month}
      onPrevious={() => {
        setMonth(inv.shiftMonth(month, -1))
        setPage(0)
      }}
      onNext={() => {
        setMonth(inv.shiftMonth(month, 1))
        setPage(0)
      }}
      page={page}
      onPage={setPage}
      onOpen={(entry) => go(entry.kind === "RETURN" && entry.return_id ? returnRoute(entry.return_id) : purchaseRoute(entry.purchase_id))}
      onBack={() => go(BASE)}
    />
  )
}

function TotalsContainer({ summary, setNotice }: { summary: inv.Summary; setNotice: SetNotice }) {
  const recent = useLoad(() => inv.listPurchases(null, "", 1, 5), [], setNotice)
  return <TotalsScreen summary={summary} recent={recent.data?.items ?? null} onNavigate={navigate} onOpenPurchase={(row) => go(purchaseRoute(row.id))} onBack={() => go(BASE)} />
}

function VouchersContainer({ choices, setNotice }: { choices: inv.InventoryChoices; setNotice: SetNotice }) {
  const [page, setPage] = React.useState(0)
  const { data } = useLoad(() => inv.listVouchers(page + 1, 10), [page], setNotice)
  return <VouchersScreen data={data} page={page} onPage={setPage} choices={choices} onOpenItem={(voucher) => go(itemRoute(voucher.item.id))} onBack={() => go(`${BASE}/stock`)} />
}

/* ── المسار ──────────────────────────────────────────────────────── */

const UUID = "[0-9a-f-]{36}"
const DOC = new RegExp(`^/(p|r|i|s|c)/(${UUID})(?:/(.+))?$`)

/** بند الرئيسية الذي تنتمي إليه الشاشة (للشريط والمساعدة). */
export function sectionOf(rel: string): string {
  const [head, second] = rel.replace(/^\//, "").split("?")[0].split("/")
  if (!head) return "home"
  if (head === "purchases" || head === "p") return "purchase"
  if (head === "returns" || head === "r") return "return"
  if (head === "items" && second === "new") return "item"
  if (head === "i" || head === "stock" || head === "suppliers" || head === "s" || head === "vouchers" || head === "items") return "stock"
  if (head === "counts" || head === "c") return "count"
  if (head === "expenses") return "expenses"
  if (head === "totals") return "totals"
  return "home"
}

export function InventoryFlow({ path, choices, me, workspace }: { path: string; choices: Choices; me: Me; workspace: Workspace }) {
  const toast = useToast()
  const [notice, setNoticeState] = React.useState<string | null>(null)
  const setNotice = React.useCallback((message: string) => setNoticeState(message), [])
  const rel = path.slice(BASE.length)
  const clean = rel.split("?")[0]
  const summary = useLoad(() => inv.summary(), [], setNotice)
  const section = sectionOf(rel)
  const inventory = choices.inventory

  // الملخّص يُقرأ من جديد عند العودة إلى الرئيسية والمجاميع والجرد: ما تغيّر في الطريق يظهر. المفتاح
  // يحمل القسم لأن مسار الرئيسية نفسه فارغ؛ وأوّل عرضٍ لا يعيد القراءة لأن `useLoad` قرأ للتوّ.
  const summaryKey = section === "home" || section === "totals" || section === "count" ? `${section}:${clean}` : ""
  const reloadSummary = summary.reload
  const lastSummaryKey = React.useRef(summaryKey)
  React.useEffect(() => {
    if (summaryKey && summaryKey !== lastSummaryKey.current) reloadSummary()
    lastSummaryKey.current = summaryKey
  }, [summaryKey, reloadSummary])

  const match = clean.match(DOC)
  const docKind = match?.[1] ?? null
  const docId = match?.[2] ?? null
  const docSub = match?.[3] ?? null
  const screenKind = docKind === "p" ? "INVENTORY_PURCHASE" : docKind === "i" ? "INVENTORY_ITEM" : docKind === "c" ? "INVENTORY_COUNT" : "HOME"
  const data = summary.data
  const today = data?.today ?? ""

  const standardRate = inventory.vat_categories.find((c) => c.code === "S")?.rate_bp ?? 1500
  const tools: ToolEntry[] = [
    ...(docKind === "p" && !docSub ? [{ id: "review-now", label: "راجِع الآن", description: "تنبيهات الفاتورة ومراجعة سيمبول", icon: ClipboardCheck, route: purchaseRoute(docId as string, "/review") }] : []),
    { id: "vat", label: "حاسبة الضريبة", description: "قبل الضريبة وبعدها", icon: Calculator,
      panel: () => <VatCalculator rateBp={standardRate} compute={async (amount, basis) => {
        const result = await inv.vatTool(amount, basis)
        return result.status === 200 && result.data ? { net: result.data.net_halalas, vat: result.data.vat_halalas, gross: result.data.gross_halalas } : { error: detail(result) }
      }} /> },
    { id: "find-item", label: "ابحث عن منتج", description: "بالاسم أو الرمز أو الباركود", icon: PackageSearch, route: `${BASE}/stock` },
  ]

  let content: React.ReactNode = null
  if (!data) {
    content = null
  } else if (data.settings === null && clean !== "/settings") {
    content = <SettingsContainer summary={data} first onSaved={() => { summary.reload(); go(BASE, { replace: true }) }} />
  } else if (clean === "" || clean === "/") {
    content = <InventoryHome workspace={workspace} userName={me.display_name} summary={data} onNavigate={navigate} />
  } else if (clean === "/settings") {
    content = <SettingsContainer summary={data} first={data.settings === null} onSaved={() => summary.reload()} />
  } else if (clean === "/settings/categories") {
    content = <CategoriesContainer setNotice={setNotice} />
  } else if (clean === "/stock") {
    content = <StockContainer path={path} setNotice={setNotice} />
  } else if (clean === "/items/new") {
    content = <ItemFormContainer id={null} choices={inventory} initialName={queryOf(path).get("name") ?? ""} setNotice={setNotice} />
  } else if (clean === "/vouchers") {
    content = <VouchersContainer choices={inventory} setNotice={setNotice} />
  } else if (clean === "/suppliers") {
    content = <SuppliersContainer setNotice={setNotice} />
  } else if (clean === "/suppliers/new") {
    content = <NewSupplierContainer />
  } else if (clean === "/purchases") {
    content = <PurchasesContainer path={path} setNotice={setNotice} />
  } else if (clean === "/purchases/new") {
    content = <NewPurchaseContainer summary={data} setNotice={setNotice} />
  } else if (clean === "/returns") {
    content = <ReturnsContainer path={path} setNotice={setNotice} />
  } else if (clean === "/returns/new") {
    content = <NewReturnContainer setNotice={setNotice} />
  } else if (clean === "/counts") {
    content = <CountsContainer summary={data} setNotice={setNotice} />
  } else if (clean === "/counts/new") {
    content = data.attention.open_count ? <Redirect to={countRoute(data.attention.open_count.id)} /> : <NewCountContainer choices={inventory} onOpened={summary.reload} setNotice={setNotice} />
  } else if (clean === "/expenses") {
    content = <ExpensesContainer summary={data} setNotice={setNotice} />
  } else if (clean === "/totals") {
    content = <TotalsContainer summary={data} setNotice={setNotice} />
  } else if (docKind === "p" && docId) {
    content = <PurchaseContainer id={docId} sub={docSub} path={path} choices={inventory} today={today} setNotice={setNotice} />
  } else if (docKind === "r" && docId) {
    content = <ReturnContainer id={docId} sub={docSub} choices={inventory} today={today} setNotice={setNotice} />
  } else if (docKind === "i" && docId) {
    content = docSub === "edit" ? <ItemFormContainer id={docId} choices={inventory} initialName="" setNotice={setNotice} />
      : docSub === "voucher" ? <VoucherContainer id={docId} choices={inventory} today={today} setNotice={setNotice} />
      : docSub ? <Redirect to={itemRoute(docId)} />
      : <ItemContainer id={docId} choices={inventory} setNotice={setNotice} />
  } else if (docKind === "s" && docId) {
    content = <SupplierContainer id={docId} sub={docSub} setNotice={setNotice} />
  } else if (docKind === "c" && docId) {
    content = <CountContainer id={docId} sub={docSub} choices={inventory} today={today} onChanged={summary.reload} setNotice={setNotice} />
  } else {
    content = <Redirect to={BASE} />
  }

  return (
    <Notice message={notice} onAck={() => setNoticeState(null)}>
      <WorkspaceShell
        workspace={workspace}
        current={section}
        userName={me.display_name}
        onNavigate={(href) => {
          toast.dismiss()
          navigate(href)
        }}
        tools={{
          userName: me.display_name,
          assistant: assistantApi(me, choices, screenKind, screenKind === "HOME" ? null : docId),
          supportContact: choices.support_contact,
          context: tools,
        }}
      >
        {content}
      </WorkspaceShell>
    </Notice>
  )
}
