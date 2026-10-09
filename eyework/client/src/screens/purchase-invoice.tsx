/*
 * فاتورة شراء جديدة
 * =================
 * ما طلبه المالك: «يفتح المخزون وتظهر إنشاء فاتورة شراء… إنشاء/اختيار من منسدل للقطع
 * والأصناف، وعند إنشاء قطعةٍ تحديد سعرها، وتظهر المجاميع، وتُسجَّل في المصروفات».
 *
 *   تحرير  →  مراجعة (الخادم يفحص، وسيمبول يراجع)  →  تسجيل
 *
 *   • الحجم العادي: النموذج كلّه في صفحةٍ واحدة تمرّ: المورد والفاتورة، ثم الأسطر، ثم
 *     المجموع. والحجم الكبير: خطوة لكل شاشة بلا تمرير — المورد، ثم سطرٌ واحد في كل مرّة.
 *   • الصنف من Combobox: يُكتب بعض الاسم أو الرمز ويُختار، أو «صنف جديد باسم "…"» (آخر
 *     القائمة) فيُفتح تحت الحقل نموذج الصنف (inventory_spec §3.5): الاسم والوحدة وسعر الشراء
 *     للوحدة قبل الضريبة — «عند إنشاء قطعةٍ تحديد سعرها» — وفئة الضريبة. ويعود إلى سطره بسعره.
 *   • المجاميع تُعرض محسوبةً بالهللة كما يحسبها الخادم (lib/money.ts)، والخادم يعتمدها.
 *   • «راجِع وسجّل»: الخادم يرفض المستحيل (كميةٌ صفر، صنفٌ غير موجود) في حقله، ثم
 *     يراجع سيمبول ما يمكن ويُستغرب (سعرٌ أعلى بكثير من آخر شراء، فاتورةٌ مكرّرة الرقم)
 *     ويقول السبب. التنبيه تحت سطره، و«عدّل» يعيد إلى الحقل، و«تابع رغم ذلك» يُحفظ.
 *   • «سجّل الفاتورة» في أعلى المراجعة، بعيداً عن «راجع الفاتورة» في أسفل التحرير؛ ومعطّلٌ
 *     ما بقي تنبيهٌ بلا قرار. والتسجيل يزيد الرصيد ويُضيف الفاتورة إلى المصروفات معاً.
 */

import * as React from "react"
import { ClipboardCheck, PackagePlus, Plus, Save, Trash2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { AIFlag } from "@/components/ui/ai-flag"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Combobox, type ComboboxOption } from "@/components/ui/combobox"
import { Field, Input } from "@/components/ui/input"
import { Select, type SelectOption } from "@/components/ui/select"
import { Stepper } from "@/components/ui/stepper"
import { formatAmount, invoiceTotals, lineTotals, parseAmount, parseQuantity } from "@/lib/money"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { ReviewFlag } from "@/lib/work-types"

/* ── الأنواع ──────────────────────────────────────────────────────── */

export interface DraftLine {
  key: string
  item: ComboboxOption | null
  query: string
  quantity: string
  unitCost: string
}

export interface PurchaseDraft {
  supplierId: string
  supplierInvoiceNumber: string
  date: string
  lines: { itemId: string; quantity: number; unitCost: number }[]
}

export interface NewItem {
  name: string
  unit: string
  /** سعر الشراء للوحدة قبل الضريبة، بالهللة (مطلوب). */
  unitCost: number
  /** فئة الضريبة: S خاضع 15%، Z نسبة الصفر، E معفى، O غير خاضع. */
  vatCategory: "S" | "Z" | "E" | "O"
}

export const VAT_CATEGORIES = [
  { value: "S", label: "خاضع 15%" },
  { value: "Z", label: "نسبة الصفر" },
  { value: "E", label: "معفى" },
  { value: "O", label: "غير خاضع" },
]

type Fail = { ok: false; message: string; line?: number; field?: string }

export interface PurchaseApi {
  searchItems: (query: string) => Promise<ComboboxOption[]>
  searchSuppliers: (query: string) => Promise<ComboboxOption[]>
  createItem: (input: NewItem) => Promise<{ ok: true; option: ComboboxOption } | Fail>
  review: (draft: PurchaseDraft) => Promise<{ ok: true; flags: ReviewFlag[] } | Fail>
  record: (draft: PurchaseDraft, acknowledged: string[]) => Promise<{ ok: true; number: string } | Fail>
}

export interface PurchaseInitial {
  supplier?: ComboboxOption | null
  supplierQuery?: string
  number?: string
  date?: string
  lines?: DraftLine[]
  stage?: "edit" | "review"
  gazeStep?: 0 | 1
  activeLine?: string
  openLine?: string
  creating?: { lineKey: string; name: string }
  flags?: ReviewFlag[]
  acknowledged?: string[]
}

export interface PurchaseInvoiceProps {
  userName: string | null
  vatRateBp: number
  units: SelectOption[]
  today: string
  api: PurchaseApi
  onDone: (number: string) => void
  onCancel: () => void
  initial?: PurchaseInitial
}

let counter = 0
const newLine = (): DraftLine => ({ key: `l${++counter}`, item: null, query: "", quantity: "1", unitCost: "" })
const fieldId = (key: string, field: string) => `line-${key}-${field}`

/* ── نموذج الصنف الجديد ───────────────────────────────────────────── */

function CreateItemCard({ name: initialName, units, onCreate, onCancel }: {
  name: string
  units: SelectOption[]
  onCreate: (input: NewItem) => Promise<string | null>
  /** «إلغاء» في البطاقة؛ وفي الحجم الكبير هو في شريط الإجراءات فلا يُمرَّر. */
  onCancel: (() => void) | null
}) {
  const [name, setName] = React.useState(initialName)
  const [unit, setUnit] = React.useState<string | null>(units[0]?.value ?? null)
  const [cost, setCost] = React.useState("")
  const [vat, setVat] = React.useState<string | null>("S")
  const [errors, setErrors] = React.useState<Record<string, string>>({})
  const [busy, setBusy] = React.useState(false)
  const [failure, setFailure] = React.useState<string | null>(null)

  async function submit() {
    const next: Record<string, string> = {}
    const trimmed = name.trim()
    if ([...trimmed].length < 2 || [...trimmed].length > 80) next.name = "الاسم بين حرفين و80 حرفاً."
    if (!unit) next.unit = "اختر الوحدة."
    const unitCost = parseAmount(cost)
    if (unitCost === null || unitCost === 0) next.cost = "اكتب سعر الشراء، مثل 520 أو 519.50."
    setErrors(next)
    if (Object.keys(next).length > 0 || unitCost === null || !unit || !vat) return
    setBusy(true)
    setFailure(null)
    const message = await onCreate({ name: trimmed, unit, unitCost, vatCategory: vat as NewItem["vatCategory"] })
    setBusy(false)
    if (message) setFailure(message)
  }

  return (
    <Card as="div" className="border border-primary/50 bg-secondary/40 shadow-none gaze:border-0 gaze:bg-transparent">
      <CardHeader className="gaze:hidden">
        <CardTitle as="h3" className="flex items-center gap-2 text-lead">
          <PackagePlus aria-hidden="true" className="size-icon text-primary" />
          صنف جديد
        </CardTitle>
        <CardDescription>يُضاف إلى المخزون بسعره، ويُختار في هذا السطر.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-tg gaze:p-0">
        <Field label="اسم الصنف" error={errors.name} required>
          <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} />
        </Field>
        <div className="grid grid-cols-2 gap-tg">
          <Field label="الوحدة" error={errors.unit} required>
            <Select options={units} value={unit} onValueChange={setUnit} />
          </Field>
          <Field label="سعر الشراء للوحدة" hint="قبل الضريبة" error={errors.cost} required>
            <Input numeric unit="ر.س" inputMode="decimal" value={cost} onChange={(event) => setCost(event.target.value)} />
          </Field>
        </div>
        <Field label="فئة الضريبة" className="gaze:short:hidden">
          <Select options={VAT_CATEGORIES} value={vat} onValueChange={setVat} />
        </Field>
        {failure ? (
          <Alert tone="danger" title="لم يُنشأ الصنف" live>
            {failure}
          </Alert>
        ) : null}
        <div className={cn("grid gap-tg", onCancel ? "grid-cols-2" : "grid-cols-1")}>
          {onCancel ? <Button onClick={onCancel}>إلغاء</Button> : null}
          <Button variant="primary" commit icon={Plus} busy={busy} onClick={() => void submit()}>
            أنشئ الصنف
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

/* ── سطرٌ في التحرير ──────────────────────────────────────────────── */

function LineEditor({ line, index, count, rateBp, options, open, creating, error, onChange, onSearch, onCreate, onRemove, onChoosing, children }: {
  line: DraftLine
  index: number
  count: number
  rateBp: number
  options: ComboboxOption[]
  open: boolean
  /** نموذج الصنف الجديد مفتوحٌ لهذا السطر: في الحجم الكبير يأخذ الخطوة وحده. */
  creating: boolean
  error: { field?: string; message: string } | null
  onChange: (patch: Partial<DraftLine>) => void
  onSearch: (query: string) => void
  onCreate: (query: string) => void
  onRemove: (() => void) | null
  onChoosing?: (open: boolean) => void
  children?: React.ReactNode
}) {
  const { size } = useSize()
  // في الحجم الكبير تأخذ قائمة الأصناف مكان الكمية والسعر حتى يُختار صنف.
  const [choosing, setChoosing] = React.useState(open)
  const hideRest = size === "gaze" && choosing
  const quantity = parseQuantity(line.quantity)
  const unitCost = parseAmount(line.unitCost)
  const total = quantity !== null && unitCost !== null ? lineTotals({ quantity, unitCost }, rateBp) : null
  return (
    <li className="flex flex-col gap-tg">
      <div className={cn("flex flex-col gap-tg rounded-card border border-border bg-card p-pad", size === "gaze" && creating && "!hidden",
        " tablet:grid tablet:grid-cols-[minmax(0,2.2fr)_minmax(0,0.8fr)_minmax(0,1fr)_minmax(0,1fr)_auto] tablet:items-start gaze:flex gaze:border-0 gaze:bg-transparent gaze:p-0")}>
        <Field label={`الصنف (السطر ${index + 1} من ${count})`} id={fieldId(line.key, "item")} error={error?.field === "item" ? error.message : null}>
          <Combobox
            listLabel="الأصناف المطابقة"
            options={options}
            value={line.item}
            onValueChange={(item) => onChange({ item })}
            query={line.query}
            onQueryChange={(query) => {
              onChange({ query })
              onSearch(query)
            }}
            onCreate={onCreate}
            createLabel="صنف جديد باسم"
            createHint="بوحدته وسعر شرائه"
            pageSize={{ compact: 6, gaze: 3, gazeShort: 1 }}
            defaultOpen={open}
            onOpenChange={(shown) => {
              setChoosing(shown)
              onChoosing?.(shown)
            }}
          />
        </Field>
        <div className={cn("grid grid-cols-2 gap-tg tablet:contents", hideRest && "!hidden")}>
          <Field label="الكمية" id={fieldId(line.key, "quantity")} error={error?.field === "quantity" ? error.message : null}>
            <Input numeric inputMode="numeric" value={line.quantity} onChange={(event) => onChange({ quantity: event.target.value })} />
          </Field>
          <Field label="سعر الوحدة" id={fieldId(line.key, "unitCost")} error={error?.field === "unitCost" ? error.message : null}>
            <Input numeric unit="ر.س" inputMode="decimal" value={line.unitCost} onChange={(event) => onChange({ unitCost: event.target.value })} />
          </Field>
        </div>
        <div className="flex items-center justify-between gap-tg tablet:flex-col tablet:items-stretch tablet:justify-start tablet:gap-1.5 gaze:hidden">
          <span className="text-small font-semibold text-muted-foreground tablet:block">الإجمالي مع الضريبة</span>
          <span className="num flex min-h-ctl items-center font-bold tablet:justify-end" dir="ltr">
            {total ? formatAmount(total.gross) : "—"}
          </span>
        </div>
        {onRemove ? (
          <div className="flex justify-end tablet:pt-[1.9rem] gaze:hidden">
            <Button variant="danger-outline" icon={Trash2} onClick={onRemove}>
              احذف
            </Button>
          </div>
        ) : null}
      </div>
      {children}
    </li>
  )
}

/* ── المجموع ──────────────────────────────────────────────────────── */

function Totals({ net, vat, gross, rateBp, className }: { net: number; vat: number; gross: number; rateBp: number; className?: string }) {
  return (
    <dl className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">المجموع قبل الضريبة</dt>
        <dd className="num" dir="ltr">{formatAmount(net)}</dd>
      </div>
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">
          الضريبة <span className="num">{rateBp / 100}%</span>
        </dt>
        <dd className="num" dir="ltr">{formatAmount(vat)}</dd>
      </div>
      <div className="flex justify-between gap-tg border-t border-border pt-1.5 text-lead font-bold text-heading">
        <dt>الإجمالي</dt>
        <dd className="num" dir="ltr">
          {formatAmount(gross)} <span className="font-sans text-small font-semibold text-muted-foreground">ر.س</span>
        </dd>
      </div>
    </dl>
  )
}

/* ── الفاتورة ─────────────────────────────────────────────────────── */

const STEPS = [
  { id: "supplier", label: "المورّد" },
  { id: "lines", label: "الأصناف" },
  { id: "review", label: "المراجعة" },
]

export function PurchaseInvoice({ userName, vatRateBp, units, today, api, onDone, onCancel, initial = {} }: PurchaseInvoiceProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [supplier, setSupplier] = React.useState<ComboboxOption | null>(initial.supplier ?? null)
  const [supplierQuery, setSupplierQuery] = React.useState(initial.supplierQuery ?? initial.supplier?.label ?? "")
  const [supplierOptions, setSupplierOptions] = React.useState<ComboboxOption[]>([])
  const [number, setNumber] = React.useState(initial.number ?? "")
  const [date, setDate] = React.useState(initial.date ?? today)
  const [lines, setLines] = React.useState<DraftLine[]>(initial.lines ?? [newLine()])
  const [options, setOptions] = React.useState<Record<string, ComboboxOption[]>>({})
  const [creating, setCreating] = React.useState(initial.creating ?? null)
  const [stage, setStage] = React.useState<"edit" | "review">(initial.stage ?? "edit")
  const [gazeStep, setGazeStep] = React.useState<0 | 1>(initial.gazeStep ?? 0)
  const [activeLine, setActiveLine] = React.useState(initial.activeLine ?? lines[0].key)
  const [flags, setFlags] = React.useState<ReviewFlag[]>(initial.flags ?? [])
  const [acknowledged, setAcknowledged] = React.useState<string[]>(initial.acknowledged ?? [])
  const [busy, setBusy] = React.useState<"review" | "record" | null>(null)
  const [choosing, setChoosing] = React.useState(Boolean(initial.openLine))
  // الحجم الكبير: كل تنبيهٍ في شاشته قبل شاشة التسجيل (0..عدد التنبيهات).
  const [flagStep, setFlagStep] = React.useState(0)
  const [problem, setProblem] = React.useState<{ message: string; line?: number; field?: string } | null>(null)
  const searches = React.useRef(new Map<string, number>())

  // نتيجة البحث الأحدث وحدها تُعرض: ردٌّ متأخّر لكلمةٍ قديمة لا يغلب الأحدث.
  const search = React.useCallback(
    (key: string, query: string) => {
      const seq = (searches.current.get(key) ?? 0) + 1
      searches.current.set(key, seq)
      void api.searchItems(query).then((found) => {
        if (searches.current.get(key) === seq) setOptions((all) => ({ ...all, [key]: found }))
      })
    },
    [api],
  )

  React.useEffect(() => {
    for (const line of initial.lines ?? []) if (line.query && !line.item) search(line.key, line.query)
    void api.searchSuppliers(initial.supplierQuery ?? "").then(setSupplierOptions)
    // مرّةً عند الفتح: ما يُكتب بعدها يبحث بنفسه.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const parsed = lines.map((line) => ({ line, quantity: parseQuantity(line.quantity), unitCost: parseAmount(line.unitCost) }))
  const complete = parsed.filter((p) => p.line.item && p.quantity !== null && p.unitCost !== null)
  const totals = invoiceTotals(complete.map((p) => ({ quantity: p.quantity!, unitCost: p.unitCost! })), vatRateBp)
  const openFlags = flags.filter((flag) => !acknowledged.includes(flag.id))

  function patch(key: string, change: Partial<DraftLine>) {
    setLines((all) => all.map((line) => (line.key === key ? { ...line, ...change } : line)))
    if (stage === "edit" && flags.length > 0) setFlags([])
  }

  // التركيز بعد الرسم: الحقل في الشاشة التي فُتحت للتوّ («عدّل»، أو بعد إنشاء صنف).
  const [focusTarget, setFocusTarget] = React.useState<string | null>(null)
  React.useEffect(() => {
    if (!focusTarget) return
    document.getElementById(focusTarget)?.focus()
    setFocusTarget(null)
  }, [focusTarget])
  const focusField = (key: string, field: string) => setFocusTarget(fieldId(key, field))

  function validate(): { message: string; line?: number; field?: string } | null {
    if (!supplier) return { message: "اختر المورد.", field: "supplier" }
    if (!number.trim()) return { message: "اكتب رقم فاتورة المورد.", field: "number" }
    if (complete.length === 0) return { message: "أضف صنفاً واحداً على الأقل بكميته وسعره." }
    for (const [index, p] of parsed.entries()) {
      if (!p.line.item && !p.line.query.trim()) continue
      if (!p.line.item) return { message: "اختر الصنف من القائمة أو أنشئه.", line: index + 1, field: "item" }
      if (p.quantity === null) return { message: "الكمية عددٌ صحيح من 1.", line: index + 1, field: "quantity" }
      if (p.unitCost === null) return { message: "اكتب سعر الوحدة مبلغاً.", line: index + 1, field: "unitCost" }
    }
    return null
  }

  function draft(): PurchaseDraft {
    return {
      supplierId: supplier!.value,
      supplierInvoiceNumber: number.trim(),
      date,
      lines: complete.map((p) => ({ itemId: p.line.item!.value, quantity: p.quantity!, unitCost: p.unitCost! })),
    }
  }

  async function review() {
    const local = validate()
    setProblem(local)
    if (local) return
    setBusy("review")
    const result = await api.review(draft())
    setBusy(null)
    if (!result.ok) {
      setProblem(result)
      return
    }
    setFlags(result.flags)
    // معرّف التنبيه من الخادم ثابتٌ لما رآه (القاعدة والسطر والقيم): قرارٌ اتُّخذ في تنبيهٍ
    // لم يتغيّر يبقى، وتنبيهٌ تغيّر سببه يُعرض من جديد.
    setAcknowledged((ids) => ids.filter((id) => result.flags.some((flag) => flag.id === id)))
    setFlagStep(0)
    setStage("review")
  }

  async function record() {
    setBusy("record")
    const result = await api.record(draft(), acknowledged)
    setBusy(null)
    if (result.ok) onDone(result.number)
    else setProblem(result)
  }

  function edit(flag: ReviewFlag) {
    setStage("edit")
    const line = flag.line ? lines[flag.line - 1] : null
    if (gaze) {
      setGazeStep(line ? 1 : 0)
      if (line) setActiveLine(line.key)
    }
    if (line) focusField(line.key, flag.field)
  }

  const lineError = (index: number) => (problem && problem.line === index + 1 ? { field: problem.field, message: problem.message } : null)

  function editorFor(line: DraftLine, index: number, removable: boolean) {
    // بعد «عدّل» يبقى تنبيه السطر تحته حتى يُغيَّر شيءٌ فيه: يرى الموظف ما يعدّله ولماذا.
    const flag = flags.find((f) => f.line === index + 1) ?? null
    return (
      <LineEditor
        key={line.key}
        line={line}
        index={index}
        count={lines.length}
        rateBp={vatRateBp}
        options={options[line.key] ?? []}
        open={initial.openLine === line.key}
        creating={creating?.lineKey === line.key}
        error={lineError(index)}
        onChange={(change) => patch(line.key, change)}
        onSearch={(query) => search(line.key, query)}
        onCreate={(name) => setCreating({ lineKey: line.key, name })}
        onRemove={removable && lines.length > 1 ? () => setLines((all) => all.filter((l) => l.key !== line.key)) : null}
        onChoosing={setChoosing}
      >
        {flag ? (
          <AIFlag
            name={userName}
            subject={`السطر ${index + 1}${line.item ? `: ${line.item.label}` : ""}`}
            message={flag.message}
            reason={flag.reason}
            evidence={gaze ? undefined : flag.evidence}
            status={acknowledged.includes(flag.id) ? "acknowledged" : "open"}
            onEdit={() => focusField(line.key, flag.field)}
            onProceed={() => setAcknowledged((ids) => [...ids, flag.id])}
            onUndo={() => setAcknowledged((ids) => ids.filter((id) => id !== flag.id))}
          />
        ) : null}
        {creating?.lineKey === line.key ? (
          <CreateItemCard
            name={creating.name}
            units={units}
            onCancel={gaze ? null : () => setCreating(null)}
            onCreate={async (input) => {
              const result = await api.createItem(input)
              if (!result.ok) return result.message
              patch(line.key, {
                item: result.option,
                query: result.option.label,
                unitCost: formatAmount(input.unitCost).replace(/,/g, ""),
              })
              setCreating(null)
              focusField(line.key, "quantity")
              return null
            }}
          />
        ) : null}
      </LineEditor>
    )
  }

  /* ── المراجعة في الحجم الكبير: كل تنبيهٍ في شاشة، ثم التسجيل ── */
  if (stage === "review" && gaze) {
    const flag = flagStep < flags.length ? flags[flagStep] : null
    if (flag) {
      const decided = acknowledged.includes(flag.id)
      return (
        <Screen
          title={flags.length > 1 ? `تنبيه ${flagStep + 1} من ${flags.length}` : "قبل التسجيل"}
          above={<Stepper steps={STEPS} current={2} />}
          actions={
            <>
              <Button icon={BackIcon} onClick={() => setStage("edit")}>
                عدّل الفاتورة
              </Button>
              <Button variant="secondary" iconEnd={NextIcon} disabled={!decided} onClick={() => setFlagStep(flagStep + 1)}>
                التالي
              </Button>
            </>
          }
        >
          <AIFlag
            name={userName}
            subject={flag.line ? `السطر ${flag.line}: ${lines[flag.line - 1]?.item?.label ?? ""}` : undefined}
            message={flag.message}
            reason={flag.reason}
            status={decided ? "acknowledged" : "open"}
            actionsFirst
            onEdit={() => edit(flag)}
            onProceed={() => setAcknowledged((ids) => [...ids, flag.id])}
            onUndo={() => setAcknowledged((ids) => ids.filter((id) => id !== flag.id))}
          />
        </Screen>
      )
    }
    return (
      <Screen
        title="سجّل الفاتورة"
        above={<Stepper steps={STEPS} current={2} />}
        actions={
          <Button icon={BackIcon} onClick={() => (flags.length > 0 ? setFlagStep(flags.length - 1) : setStage("edit"))}>
            {flags.length > 0 ? "التنبيه" : "عدّل الفاتورة"}
          </Button>
        }
      >
        <RecordButton disabled={openFlags.length > 0} busy={busy === "record"} onRecord={() => void record()} />
        {problem ? (
          <Alert tone="danger" title="لم تُسجَّل" live>
            {problem.message}
          </Alert>
        ) : null}
        <dl className="text-flow flex flex-col gap-1">
          <div className="flex justify-between gap-tg">
            <dt className="text-muted-foreground">المورد</dt>
            <dd className="truncate font-semibold">{supplier?.label}</dd>
          </div>
          <div className="flex justify-between gap-tg">
            <dt className="text-muted-foreground">الأسطر</dt>
            <dd className="num font-semibold">{complete.length}</dd>
          </div>
          <div className="flex justify-between gap-tg text-lead font-bold text-heading">
            <dt>الإجمالي</dt>
            <dd className="num" dir="ltr">
              {formatAmount(totals.gross)}
            </dd>
          </div>
        </dl>
        {acknowledged.length > 0 ? (
          <p className="text-small text-muted-foreground">تابعتَ رغم تنبيه سيمبول، ويُحفظ قرارك مع الفاتورة.</p>
        ) : null}
      </Screen>
    )
  }

  /* ── المراجعة في الحجم العادي: التنبيه تحت سطره، والتسجيل في أعلى الصفحة ── */
  if (stage === "review") {
    return (
      <Screen
        title="مراجعة الفاتورة قبل تسجيلها"
        above={<Badge tone="info" className="self-start">لم تُسجَّل بعد</Badge>}
        description="تزيد المخزون وتُضاف إلى المصاريف حين تسجّلها."
        aside={<RecordButton disabled={openFlags.length > 0} busy={busy === "record"} onRecord={() => void record()} />}
        actions={
          <Button icon={BackIcon} onClick={() => setStage("edit")}>
            عدّل الفاتورة
          </Button>
        }
      >
        {openFlags.length > 0 ? (
          <p role="status" className="text-small font-semibold text-warning">
            {openFlags.length === 1 ? "تنبيهٌ واحد من سيمبول ينتظر قرارك قبل التسجيل." : `${openFlags.length} تنبيهات تنتظر قرارك قبل التسجيل.`}
          </p>
        ) : null}
        {problem ? (
          <Alert tone="danger" title="لم تُسجَّل" live>
            {problem.message}
          </Alert>
        ) : null}
        <div className="grid grid-cols-1 gap-sec lg:grid-cols-[minmax(0,1fr)_20rem]">
            <Card>
              <CardHeader>
                <CardTitle>
                  {supplier?.label} · فاتورة <span className="num">{number}</span>
                </CardTitle>
                <CardDescription>
                  <span className="num">{date}</span> · <span className="num">{complete.length}</span> أسطر
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ol className="flex flex-col gap-tg-min">
                  {complete.map((p, index) => {
                    const flag = flags.find((f) => f.line === index + 1)
                    const t = lineTotals({ quantity: p.quantity!, unitCost: p.unitCost! }, vatRateBp)
                    return (
                      <li key={p.line.key} className="flex flex-col gap-tg-min">
                        <div
                          className={cn(
                            "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-tg gap-y-0.5 rounded-ctl border px-3 py-2",
                            flag && !acknowledged.includes(flag.id) ? "border-warning-line" : "border-transparent bg-muted",
                          )}
                        >
                          <span className="font-semibold">
                            <span className="num text-muted-foreground">{index + 1}. </span>
                            {p.line.item!.label}
                          </span>
                          <span className="num font-bold" dir="ltr">
                            {formatAmount(t.gross)}
                          </span>
                          <span className="text-small text-muted-foreground">
                            <span className="num">{p.quantity}</span> ×{" "}
                            <span className="num" dir="ltr">
                              {formatAmount(p.unitCost!)}
                            </span>{" "}
                            ر.س
                          </span>
                        </div>
                        {flag ? (
                          <AIFlag
                            name={userName}
                            subject={`السطر ${index + 1}: ${p.line.item!.label}`}
                            message={flag.message}
                            reason={flag.reason}
                            evidence={flag.evidence}
                            status={acknowledged.includes(flag.id) ? "acknowledged" : "open"}
                            onEdit={() => edit(flag)}
                            onProceed={() => setAcknowledged((ids) => [...ids, flag.id])}
                            onUndo={() => setAcknowledged((ids) => ids.filter((id) => id !== flag.id))}
                          />
                        ) : null}
                      </li>
                    )
                  })}
                </ol>
              </CardContent>
            </Card>
            <Card className="self-start">
              <CardHeader>
                <CardTitle as="h2">المجموع</CardTitle>
              </CardHeader>
              <CardContent>
                <Totals {...totals} rateBp={vatRateBp} />
              </CardContent>
            </Card>
          </div>
      </Screen>
    )
  }

  /* ── التحرير: الحجم الكبير، خطوةٌ في كل شاشة ── */
  if (gaze) {
    const index = Math.max(0, lines.findIndex((line) => line.key === activeLine))
    const line = lines[index]
    const last = index === lines.length - 1
    return (
      <Screen
        title={gazeStep === 0 ? "فاتورة المورّد" : creating ? `صنفٌ جديد للسطر ${index + 1}` : `السطر ${index + 1} من ${lines.length}`}
        above={choosing || creating ? undefined : <Stepper steps={STEPS} current={gazeStep} />}
        actions={
          creating ? (
            <Button icon={BackIcon} onClick={() => setCreating(null)}>
              إلغاء الصنف الجديد
            </Button>
          ) : (
          <>
            <Button icon={BackIcon} onClick={gazeStep === 0 ? onCancel : () => setGazeStep(0)}>
              {gazeStep === 0 ? "الرئيسية" : "المورّد"}
            </Button>
            {gazeStep === 0 ? (
              <Button variant="secondary" iconEnd={NextIcon} onClick={() => setGazeStep(1)}>
                الأصناف
              </Button>
            ) : (
              <Button variant="secondary" icon={ClipboardCheck} busy={busy === "review"} onClick={() => void review()}>
                راجِع وسجّل
              </Button>
            )}
          </>
          )
        }
      >
        {gazeStep === 0 ? (
          <>
            <Field label="المورّد" error={problem?.field === "supplier" ? problem.message : null}>
              <Combobox
                listLabel="المورّدون المطابقون"
                options={supplierOptions}
                value={supplier}
                onValueChange={setSupplier}
                query={supplierQuery}
                onQueryChange={(query) => {
                  setSupplierQuery(query)
                  void api.searchSuppliers(query).then(setSupplierOptions)
                }}
              />
            </Field>
            <div className="grid grid-cols-2 gap-tg">
              <Field label="رقم فاتورته" error={problem?.field === "number" ? problem.message : null}>
                <Input dir="ltr" value={number} onChange={(event) => setNumber(event.target.value)} />
              </Field>
              <Field label="التاريخ">
                <Input type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} />
              </Field>
            </div>
          </>
        ) : (
          <>
            <ul className="flex flex-col gap-tg">{editorFor(line, index, false)}</ul>
            {creating || choosing ? null : (
              <div className="grid grid-cols-2 gap-tg">
                <Button icon={BackIcon} disabled={index === 0} onClick={() => setActiveLine(lines[index - 1].key)}>
                  السطر السابق
                </Button>
                <Button
                  icon={last ? Plus : undefined}
                  iconEnd={last ? undefined : NextIcon}
                  onClick={() => {
                    if (last) {
                      const added = newLine()
                      setLines((all) => [...all, added])
                      setActiveLine(added.key)
                    } else {
                      setActiveLine(lines[index + 1].key)
                    }
                  }}
                >
                  {last ? "سطرٌ جديد" : "السطر التالي"}
                </Button>
              </div>
            )}
            {problem && !problem.line ? (
              <Alert tone="danger" title="قبل المراجعة" live>
                {problem.message}
              </Alert>
            ) : null}
          </>
        )}
      </Screen>
    )
  }

  /* ── التحرير: الحجم العادي، النموذج كلّه ── */
  return (
    <Screen
      title="فاتورة شراء جديدة"
      back={{ id: "invoice-home", label: "الرئيسية", onClick: onCancel }}
      description="تزيد المخزون وتُضاف إلى المصاريف حين تسجّلها بعد المراجعة."
      actions={
        <>
          <Button variant="danger-outline" icon={Trash2} onClick={onCancel}>
            احذف المسودة
          </Button>
          <Button variant="secondary" size="lg" icon={ClipboardCheck} busy={busy === "review"} onClick={() => void review()} className="ms-auto">
            {busy === "review" ? "سيمبول يراجع الأسطر…" : "راجِع وسجّل"}
          </Button>
        </>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>فاتورة المورّد</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-tg tablet:grid-cols-3 [&>*:first-child]:col-span-2 tablet:[&>*:first-child]:col-span-1">
          <Field label="المورّد" error={problem?.field === "supplier" ? problem.message : null}>
            <Combobox
              listLabel="المورّدون المطابقون"
              options={supplierOptions}
              value={supplier}
              onValueChange={setSupplier}
              query={supplierQuery}
              onQueryChange={(query) => {
                setSupplierQuery(query)
                void api.searchSuppliers(query).then(setSupplierOptions)
              }}
            />
          </Field>
          <Field label="رقم فاتورة المورّد" error={problem?.field === "number" ? problem.message : null}>
            <Input dir="ltr" value={number} onChange={(event) => setNumber(event.target.value)} />
          </Field>
          <Field label="تاريخ الفاتورة">
            <Input type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} />
          </Field>
        </CardContent>
      </Card>

      <section aria-labelledby="lines-title" className="flex flex-col gap-tg">
        <div className="flex items-center justify-between gap-tg">
          <h2 id="lines-title" className="text-title font-bold">
            الأصناف
          </h2>
          <span className="text-small text-muted-foreground">
            <span className="num">{complete.length}</span> من <span className="num">{lines.length}</span> مكتملة
          </span>
        </div>
        <ol className="flex flex-col gap-tg">{lines.map((line, index) => editorFor(line, index, true))}</ol>
        <div>
          <Button icon={Plus} onClick={() => setLines((all) => [...all, newLine()])}>
            أضف سطراً
          </Button>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>المجموع</CardTitle>
          <CardDescription className="flex items-center gap-1.5">
            <Save aria-hidden="true" className="size-4" />
            يُضاف الإجمالي إلى المصاريف حين تُسجَّل الفاتورة.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Totals {...totals} rateBp={vatRateBp} />
        </CardContent>
      </Card>

      {problem && !problem.line ? (
        <Alert tone="danger" title="قبل المراجعة" live>
          {problem.message}
        </Alert>
      ) : null}
    </Screen>
  )
}

function RecordButton({ disabled, busy, onRecord }: { disabled: boolean; busy: boolean; onRecord: () => void }) {
  return (
    <Button variant="primary" size="lg" commit icon={Save} disabled={disabled} busy={busy} onClick={onRecord} className="gaze:w-full">
      سجّل الفاتورة
    </Button>
  )
}
