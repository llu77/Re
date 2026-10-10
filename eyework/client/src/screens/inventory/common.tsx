/*
 * ما تشترك فيه شاشات المخزون
 * ===========================
 *   • `Money` و`Qty`: المبلغ بالهللة والكمية بالألف كما يقرؤهما أمين المخزون، بأرقامٍ لاتينية.
 *   • `Facts`: بطاقة حقائق (dl) بسطرين لكل حقيقة.
 *   • `Picker`: اختيارٌ من قائمةٍ قصيرة. في الحجم العادي قائمة `Select`؛ وفي الحجم الكبير زرٌّ يفتح
 *     الخيارات مكان بقية حقول الخطوة (ثلاثةٌ في الصفحة و«السابقة» و«التالية» و«إلغاء»)، فلا تزيد الشاشة
 *     على اثني عشر هدفاً مهما كثرت الخيارات (وحدات القياس تسع، والأسباب ثمانية).
 *   • `GazeHost` و`GazeSlot`: في الحجم الكبير حين يُفتح منتقٍ أو قائمة بحثٍ تُخفى الحقول الأخرى في
 *     الخطوة نفسها (تبقى في الذاكرة بقيمها) حتى يُغلق.
 *   • `RuleFlagCard`: تنبيه قاعدةٍ من التطبيق بنصّه الجاهز من الخادم، بإقرارٍ أو «عدّل».
 */

import * as React from "react"
import { Check, ChevronDown, X } from "lucide-react"

import { AIFlag } from "@/components/ui/ai-flag"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Field } from "@/components/ui/input"
import { Select, type SelectOption } from "@/components/ui/select"
import { formatAmount } from "@/lib/money"
import { formatMilli, type RuleFlag } from "@/lib/inventory"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

/* ── الأرقام ─────────────────────────────────────────────────────── */

export function Money({ halalas, unit = true, className }: { halalas: number; unit?: boolean; className?: string }) {
  return (
    <span className={cn("num whitespace-nowrap", className)}>
      <span dir="ltr">{formatAmount(halalas)}</span>
      {unit ? <span className="font-sans text-small font-semibold text-muted-foreground"> ر.س</span> : null}
    </span>
  )
}

export function Qty({ milli, unit, className }: { milli: number; unit?: string; className?: string }) {
  return (
    <span className={cn("whitespace-nowrap", className)}>
      <span className="num" dir="ltr">
        {formatMilli(milli)}
      </span>
      {unit ? ` ${unit}` : ""}
    </span>
  )
}

/* ── الحقائق ─────────────────────────────────────────────────────── */

export interface Fact {
  label: string
  value: React.ReactNode
  /** يظهر في الحجم الكبير أيضاً (ما سواه يُخفى فيه ليتّسع). */
  key?: boolean
}

export function Facts({ facts, columns = 2, className }: { facts: Fact[]; columns?: 1 | 2 | 3; className?: string }) {
  const shown = facts.filter((fact) => fact.value !== null && fact.value !== undefined && fact.value !== "")
  return (
    <dl className={cn("grid gap-x-tg gap-y-2 rounded-card border border-border bg-card p-pad", columns === 1 ? "grid-cols-1" : columns === 2 ? "grid-cols-2" : "grid-cols-2 tablet:grid-cols-3", className)}>
      {shown.map((fact) => (
        <div key={fact.label} className={cn("flex min-w-0 flex-col gap-0.5", !fact.key && "gaze:hidden")}>
          <dt className="text-small text-muted-foreground">{fact.label}</dt>
          <dd className="truncate font-semibold text-foreground">{fact.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/* ── الحجم الكبير: حقلٌ واحد مفتوح في كل مرّة ───────────────────── */

interface Host {
  focused: string | null
  setFocused: (id: string | null) => void
  /** ترتيب الحقول كما رُكّبت (ترتيب الشاشة). */
  register: (id: string) => void
  precedes: (id: string, other: string) => boolean
}

const HostContext = React.createContext<Host | null>(null)

/**
 * يحتضن حقول خطوةٍ واحدة. في الحجم الكبير حين يُفتح منتقٍ أو قائمة بحث: ما قبله من الحقول يُخفى
 * ويبقى مكانه (فلا يتحرّك الحقل المفتوح تحت نظرٍ ضغطه)، وما بعده يُخفى ويُطوى حتى يُغلق.
 */
export function GazeHost({ children, className }: { children: React.ReactNode; className?: string }) {
  const [focused, setFocused] = React.useState<string | null>(null)
  const order = React.useRef<string[]>([])
  const value = React.useMemo<Host>(
    () => ({
      focused,
      setFocused,
      register: (id) => {
        if (!order.current.includes(id)) order.current.push(id)
      },
      precedes: (id, other) => order.current.indexOf(id) < order.current.indexOf(other),
    }),
    [focused],
  )
  return (
    <HostContext.Provider value={value}>
      <div data-gaze-host="" className={cn("relative flex flex-col gap-tg", className)}>{children}</div>
    </HostContext.Provider>
  )
}

const NO_HOST: Host = { focused: null, setFocused: () => {}, register: () => {}, precedes: () => false }

export function useGazeHost(): Host {
  return React.useContext(HostContext) ?? NO_HOST
}

/** غلاف حقل: في الحجم الكبير حين يكون حقلٌ آخر في الخطوة مفتوحاً يُخفى (ويبقى مكانه إن سبقه). */
export function GazeSlot({ id, children, className }: { id: string; children: React.ReactNode; className?: string }) {
  const { size } = useSize()
  const { focused, register, precedes } = useGazeHost()
  React.useEffect(() => register(id), [id, register])
  const away = size === "gaze" && focused !== null && focused !== id
  const keepSpace = away && precedes(id, focused as string)
  return (
    <div hidden={away && !keepSpace} className={cn("min-w-0", keepSpace && "invisible", className)}>
      {children}
    </div>
  )
}

/** يبلّغ المضيف أن هذا الحقل فُتح أو أُغلق (قائمة البحث). */
export function useOpenReport(id: string) {
  const { setFocused } = useGazeHost()
  return React.useCallback((open: boolean) => setFocused(open ? id : null), [id, setFocused])
}

/* ── المنتقي ─────────────────────────────────────────────────────── */

export interface PickerProps {
  id: string
  label: React.ReactNode
  options: SelectOption[]
  value: string | null
  onValueChange: (value: string) => void
  emptyLabel?: string
  hint?: React.ReactNode
  error?: string | null
  required?: boolean
  disabled?: boolean
  className?: string
}

const GAZE_PER_PAGE = 3

interface Layout {
  side: "above" | "below"
  perPage: number
}

/** رمزٌ من globals.css بالبكسل («--ctl»، «--tg»): تُقاس به سعة القائمة كما رُسمت، لا برقمٍ منسوخ. */
function token(name: string): number {
  const style = getComputedStyle(document.documentElement)
  const value = parseFloat(style.getPropertyValue(name))
  return value * (parseFloat(style.fontSize) || 16)
}

/** كم خياراً يتّسع في مساحةٍ: مع صفّ التقليب إن لم تتّسع الخيارات كلّها. */
function capacity(space: number, total: number): number {
  const target = token("--ctl")
  const gap = token("--tg")
  const row = target + gap
  const all = Math.floor((space - gap) / row)
  if (all >= total) return total
  return Math.max(0, Math.floor((space - gap - row) / row))
}

export function Picker({ id, label, options, value, onValueChange, emptyLabel = "اختر", hint, error, required, disabled, className }: PickerProps) {
  const { size } = useSize()
  const { focused, setFocused } = useGazeHost()
  const [page, setPage] = React.useState(0)
  const [layout, setLayout] = React.useState<Layout>({ side: "below", perPage: GAZE_PER_PAGE })
  const wrapper = React.useRef<HTMLDivElement>(null)
  if (size !== "gaze") {
    return (
      <Field id={id} label={label} hint={hint} error={error} required={required} className={className}>
        <Select options={options} value={value} onValueChange={onValueChange} emptyLabel={emptyLabel} disabled={disabled} />
      </Field>
    )
  }
  const open = focused === id
  const selected = options.find((option) => option.value === value) ?? null
  const perPage = Math.max(1, Math.min(GAZE_PER_PAGE, layout.perPage))
  const pages = Math.max(1, Math.ceil(options.length / perPage))
  const current = Math.min(page, pages - 1)
  const visible = options.slice(current * perPage, current * perPage + perPage)
  const close = () => setFocused(null)

  /*
   * الخيارات مكان الحقول المخفية: فوق الزرّ إن كان المكان فوقه أوسع، وإلا تحته، وبعددٍ يتّسع بلا قصّ
   * (ثلاثةٌ على الأكثر). والزرّ نفسه يصير «إلغاء» في موضعه، فما يقع تحت الضغطة التي فتحته آمن.
   */
  function show() {
    const box = wrapper.current?.getBoundingClientRect()
    const host = wrapper.current?.closest("[data-gaze-host]")?.getBoundingClientRect()
    const actions = document.querySelector("[data-screen-actions]")?.getBoundingClientRect()
    // شريط التبويب أسفل الهاتف وحده يحدّ ما تحت؛ وفي الآيباد العنصر نفسه شريطٌ جانبي من أعلى الشاشة.
    const tabs = document.querySelector('nav[aria-label="أقسام البوابة"]')?.getBoundingClientRect()
    const bar = box && tabs && tabs.top > box.bottom ? tabs : undefined
    const limit = Math.min(actions?.top ?? Infinity, bar?.top ?? Infinity, window.innerHeight)
    const above = box && host ? box.top - host.top : 0
    const below = box ? limit - box.bottom : 0
    const nBelow = Math.min(GAZE_PER_PAGE, capacity(below, options.length))
    const nAbove = Math.min(GAZE_PER_PAGE, capacity(above, options.length))
    const side: Layout["side"] = nBelow >= Math.min(GAZE_PER_PAGE, options.length) || nBelow >= nAbove ? "below" : "above"
    const n = Math.max(1, side === "below" ? nBelow : nAbove)
    setLayout({ side, perPage: n })
    setPage(Math.max(0, Math.floor(options.findIndex((option) => option.value === value) / n)))
    setFocused(id)
  }

  // أزرارٌ بـaria-pressed لا listbox وoption: «الانتقال إلى العنصر» في تتبّع العين والرأس يقصد ما له سمة الزرّ،
  // وWebKit لا يعطيها role="option".
  const list = (
    <ul data-options="" aria-label={typeof label === "string" ? label : undefined} className="flex flex-col gap-tg">
      {visible.map((option) => {
        const checked = option.value === value
        return (
          <li key={option.value}>
            <button
              type="button"
              aria-pressed={checked}
              data-value=""
              data-key={option.value}
              onClick={() => {
                onValueChange(option.value)
                close()
              }}
              className={cn(
                "flex min-h-ctl w-full items-center justify-between gap-2 rounded-ctl border px-4 text-start font-semibold shadow-pop",
                checked ? "border-primary-line bg-secondary text-secondary-foreground" : "border-control bg-card text-foreground",
              )}
            >
              {option.label}
              {checked ? <Check aria-hidden="true" className="size-icon shrink-0 text-primary" /> : null}
            </button>
          </li>
        )
      })}
    </ul>
  )
  const pager =
    pages > 1 ? (
      <div className="grid grid-cols-2 gap-tg">
        <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)} className="shadow-pop">
          السابقة
        </Button>
        <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)} className="shadow-pop">
          التالية
        </Button>
      </div>
    ) : null

  return (
    <GazeSlot id={id} className={cn("relative", className)}>
      <div ref={wrapper} className="flex flex-col gap-1">
        <span className="text-small font-semibold text-foreground">
          {label}
          {required && !open ? <span className="text-muted-foreground"> (مطلوب)</span> : null}
        </span>
        {open ? (
          <Button id={`${id}-cancel`} icon={X} onClick={close}>
            إلغاء
          </Button>
        ) : (
          <button
            id={id}
            type="button"
            data-safe=""
            aria-expanded={false}
            disabled={disabled}
            onClick={show}
            className={cn(
              "flex min-h-ctl w-full items-center justify-between gap-2 rounded-ctl border border-control bg-card px-3 text-start text-body",
              "disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground",
              error && "border-destructive",
            )}
          >
            <span className={cn("truncate", !selected && "text-muted-foreground")}>{selected ? selected.label : emptyLabel}</span>
            <ChevronDown aria-hidden="true" className="size-icon shrink-0 text-muted-foreground" />
          </button>
        )}
        {!open && error ? <p className="text-small font-medium text-destructive">{error}</p> : !open && hint ? <p className="text-small text-muted-foreground">{hint}</p> : null}
      </div>
      {open ? (
        <div
          role="group"
          aria-label={typeof label === "string" ? label : undefined}
          className={cn("absolute inset-x-0 z-20 flex flex-col gap-tg", layout.side === "above" ? "bottom-[calc(100%+var(--tg))]" : "top-[calc(100%+var(--tg))]")}
        >
          {layout.side === "above" ? (
            <>
              {pager}
              {list}
            </>
          ) : (
            <>
              {list}
              {pager}
            </>
          )}
        </div>
      ) : null}
    </GazeSlot>
  )
}

/* ── تنبيه قاعدةٍ من التطبيق ─────────────────────────────────────── */

/** سبب كل قاعدةٍ بسطرٍ ثابت؛ والنصّ نفسه من الخادم بتفاصيله وبنداء صاحب الحساب. */
export const RULE_REASONS: Record<string, string> = {
  DUPLICATE_SUPPLIER_INVOICE: "رقم فاتورة المورّد هذا سُجّل من قبل للمورّد نفسه؛ قد تكون الفاتورة نفسها مرّتين.",
  POSSIBLE_DUPLICATE: "فاتورةٌ أخرى للمورّد نفسه بالتاريخ والإجمالي نفسيهما.",
  TOTAL_MISMATCH: "إجمالي الأسطر لا يساوي الإجمالي المكتوب على فاتورة المورّد: سطرٌ ناقص، أو سعرٌ أو كميةٌ غير الصحيحة.",
  VAT_MISMATCH: "ضريبة الأسطر لا تساوي الضريبة المكتوبة على الفاتورة.",
  VAT_WITHOUT_SUPPLIER_VAT_NUMBER: "لا يُحتسب خصم ضريبةٍ من مورّدٍ بلا رقمٍ ضريبي.",
  NO_VAT_CHARGED: "فاتورةٌ من مورّدٍ مسجّلٍ في الضريبة بلا ضريبة.",
  OLD_INVOICE_DATE: "تاريخ الفاتورة قديم؛ تأكّد منه.",
  ZERO_PRICE: "سطرٌ بسعر صفر: هديةٌ، أو سعرٌ لم يُكتب.",
  PRICE_FAR_FROM_HISTORY: "السعر بعيدٌ عن وسيط آخر مشتريات هذا المنتج.",
  QUANTITY_FAR_FROM_HISTORY: "الكمية بعيدةٌ عن المعتاد لهذا المنتج.",
  CATEGORY_CHANGED: "فئة ضريبة السطر تخالف فئة المنتج المعتادة.",
  SHORT_DELIVERY: "ما وصل أقلّ ممّا في الفاتورة: تُسجَّل الفاتورة كما هي، ثم مرتجعٌ بسبب نقص التسليم بما لم يصل.",
  FULL_RETURN: "يُرجع كل ما في الفاتورة.",
  OLD_PURCHASE: "الفاتورة المرجوع منها قديمة.",
}

export function RuleFlagCard({ flag, acknowledged, subject, onAcknowledge, onUndo, onEdit, actionsFirst }: {
  flag: RuleFlag
  acknowledged: boolean
  subject?: string
  onAcknowledge: () => void
  onUndo: () => void
  onEdit: () => void
  actionsFirst?: boolean
}) {
  return (
    <AIFlag
      name={null}
      source="rule"
      subject={subject}
      message={flag.text}
      reason={RULE_REASONS[flag.code] ?? flag.code}
      status={acknowledged ? "acknowledged" : "open"}
      onEdit={onEdit}
      onProceed={onAcknowledge}
      onUndo={onUndo}
      actionsFirst={actionsFirst}
    />
  )
}

/** «السطر 2: كرتونة ماء». */
export function lineSubject(lineNo: number | null, name: string | undefined): string | undefined {
  if (lineNo === null) return undefined
  return name ? `السطر ${lineNo}: ${name}` : `السطر ${lineNo}`
}

/** رسالة خطأ الحقل من ردّ الخادم إن سمّى حقلاً، وإلا عامّة. */
export function fieldError(field: string | null, message: string, name: string): string | null {
  return field === name ? message : null
}
