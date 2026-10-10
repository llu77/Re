/*
 * مرتجعٌ من فاتورةٍ سابقة
 * ======================
 * «إنشاء مسترجعٍ من فاتورةٍ سابقة» (inventory_spec §3.8، S7–S9): ثلاث خطوات في الحجمين،
 * لأن كل خطوةٍ تعتمد على ما قبلها.
 *   1. «من أيّ فاتورة؟»: يُبحث بالمورّد أو برقمنا «ش-…» أو برقم المورّد (Combobox) ويُختار.
 *   2. «ما الذي يُرجَع؟»: كل سطرٍ وما بقي للإرجاع منه، وزرّا − و+ لا يتجاوزان الباقي.
 *      الحدّ في القاعدة أيضاً: لا يُرجع أكثر ممّا بقي من السطر.
 *   3. «سبب الإرجاع»: ستة أسباب، و«سببٌ آخر» يطلب ملاحظة؛ ثم «راجِع وسجّل» إلى المراجعة (S5).
 * المرتجع ينقص المخزون ويخصم من المصاريف معاً، ولا يُعدَّل بعد تسجيله.
 */

import * as React from "react"
import { ClipboardCheck } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Combobox, type ComboboxOption } from "@/components/ui/combobox"
import { Field, Textarea } from "@/components/ui/input"
import { QuantityStepper } from "@/components/ui/quantity"
import { Select } from "@/components/ui/select"
import { Stepper } from "@/components/ui/stepper"
import { formatDay } from "@/lib/format"
import { formatAmount, invoiceTotals } from "@/lib/money"
import { usePageSize, useSize } from "@/lib/size"

export interface ReturnLine {
  lineId: string
  item: string
  unit: string
  purchased: number
  returned: number
  unitCost: number
}

export interface ReturnInvoice {
  id: string
  number: string
  supplier: string
  date: string
  lines: ReturnLine[]
}

type Fail = { ok: false; message: string }

export interface ReturnApi {
  searchInvoices: (query: string) => Promise<ComboboxOption[]>
  loadInvoice: (id: string) => Promise<{ ok: true; invoice: ReturnInvoice } | Fail>
  /** يفتح المراجعة (S5) بما اختير؛ والتسجيل هناك. */
  review: (input: { invoiceId: string; reason: string; note: string; lines: { lineId: string; quantity: number }[] }) => Promise<{ ok: true } | Fail>
}

const REASONS = [
  { value: "DAMAGED", label: "تالفة" },
  { value: "WRONG_ITEM", label: "صنفٌ غير المطلوب" },
  { value: "NOT_TO_SPEC", label: "مخالفة للمواصفات" },
  { value: "OVER_ORDER", label: "زائدة عن الطلب" },
  { value: "EXPIRED", label: "منتهية الصلاحية" },
  { value: "OTHER", label: "سببٌ آخر" },
]

const STEPS = [
  { id: "invoice", label: "الفاتورة" },
  { id: "quantities", label: "الكميات" },
  { id: "reason", label: "السبب" },
]

export interface ReturnFlowProps {
  vatRateBp: number
  api: ReturnApi
  onCancel: () => void
  initial?: { step?: 0 | 1 | 2; invoice?: ReturnInvoice; query?: string; quantities?: Record<string, number>; reason?: string }
}

export function ReturnFlow({ vatRateBp, api, onCancel, initial = {} }: ReturnFlowProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState<0 | 1 | 2>(initial.step ?? 0)
  const [query, setQuery] = React.useState(initial.query ?? (initial.invoice ? `${initial.invoice.number} — ${initial.invoice.supplier}` : ""))
  const [options, setOptions] = React.useState<ComboboxOption[]>([])
  const [choice, setChoice] = React.useState<ComboboxOption | null>(
    initial.invoice ? { value: initial.invoice.id, label: `${initial.invoice.number} — ${initial.invoice.supplier}` } : null,
  )
  const [invoice, setInvoice] = React.useState<ReturnInvoice | null>(initial.invoice ?? null)
  const [quantities, setQuantities] = React.useState<Record<string, number>>(initial.quantities ?? {})
  const [reason, setReason] = React.useState<string | null>(initial.reason ?? null)
  const [note, setNote] = React.useState("")
  const [page, setPage] = React.useState(0)
  const [busy, setBusy] = React.useState(false)
  const [problem, setProblem] = React.useState<string | null>(null)

  React.useEffect(() => {
    let live = true
    void api.searchInvoices(query).then((found) => live && setOptions(found))
    return () => {
      live = false
    }
  }, [api, query])

  const chosen = invoice?.lines.filter((line) => (quantities[line.lineId] ?? 0) > 0) ?? []
  const totals = invoiceTotals(chosen.map((line) => ({ quantity: quantities[line.lineId], unitCost: line.unitCost })), vatRateBp)
  const perPage = usePageSize({ compact: 50, gaze: 1, gazeShort: 1 })
  const lines = invoice?.lines ?? []
  const pages = Math.max(1, Math.ceil(lines.length / perPage))
  const visible = lines.slice(page * perPage, page * perPage + perPage)

  async function pick(option: ComboboxOption | null) {
    setChoice(option)
    setProblem(null)
    if (!option) {
      setInvoice(null)
      return
    }
    const result = await api.loadInvoice(option.value)
    if (result.ok) {
      setInvoice(result.invoice)
      setQuantities({})
    } else {
      setProblem(result.message)
    }
  }

  async function review() {
    if (!invoice || !reason || chosen.length === 0) return
    if (reason === "OTHER" && !note.trim()) {
      setProblem("اكتب السبب في الملاحظة.")
      return
    }
    setBusy(true)
    setProblem(null)
    const result = await api.review({
      invoiceId: invoice.id,
      reason,
      note: note.trim(),
      lines: chosen.map((line) => ({ lineId: line.lineId, quantity: quantities[line.lineId] })),
    })
    setBusy(false)
    if (!result.ok) setProblem(result.message)
  }

  const summary = invoice ? (
    <p className="text-small text-muted-foreground gaze:short:hidden">
      فاتورة <span className="num font-semibold text-foreground">{invoice.number}</span> من {invoice.supplier} ·{" "}
      {formatDay(invoice.date, true)}
    </p>
  ) : null

  return (
    <Screen
      title={step === 0 ? "من أيّ فاتورة؟" : step === 1 ? "ما الذي يُرجَع؟" : "سبب الإرجاع"}
      above={<Stepper steps={STEPS} current={step} />}
      back={gaze ? undefined : { label: step === 0 ? "الرئيسية" : "الخطوة السابقة", onBack: step === 0 ? onCancel : () => setStep((step - 1) as 0 | 1) }}
      actions={
        <>
          {gaze ? (
            <Button icon={BackIcon} onClick={step === 0 ? onCancel : () => setStep((step - 1) as 0 | 1)}>
              رجوع
            </Button>
          ) : null}
          {step < 2 ? (
            <Button
              variant="secondary"
              iconEnd={NextIcon}
              disabled={step === 0 ? !invoice : chosen.length === 0}
              onClick={() => setStep((step + 1) as 1 | 2)}
              className="compact:ms-auto"
            >
              {step === 0 ? "التالي: الكميات" : "التالي: السبب"}
            </Button>
          ) : (
            <Button
              variant="secondary"
              icon={ClipboardCheck}
              busy={busy}
              disabled={!reason || chosen.length === 0}
              onClick={() => void review()}
              className="compact:ms-auto"
            >
              راجِع وسجّل
            </Button>
          )}
        </>
      }
    >
      {problem ? (
        <Alert tone="danger" title="لم يتمّ" live>
          {problem}
        </Alert>
      ) : null}

      {step === 0 ? (
        <>
          <Field label="المورّد أو رقم الفاتورة" hint="الفواتير المسجّلة التي بقي فيها ما يُرجَع.">
            <Combobox listLabel="الفواتير المطابقة" options={options} value={choice} onValueChange={(option) => void pick(option)} query={query} onQueryChange={setQuery} />
          </Field>
          {invoice ? (
            <Card>
              <CardHeader>
                <CardTitle as="h2">{invoice.supplier}</CardTitle>
                <CardDescription>
                  فاتورة <span className="num">{invoice.number}</span> · {formatDay(invoice.date, true)} ·{" "}
                  <span className="num">{invoice.lines.length}</span> أسطر
                </CardDescription>
              </CardHeader>
            </Card>
          ) : null}
        </>
      ) : null}

      {step === 1 && invoice ? (
        <>
          {summary}
          <ul aria-label="أسطر الفاتورة" className="flex flex-col gap-tg-min gaze:gap-tg">
            {visible.map((line) => {
              const left = line.purchased - line.returned
              return (
                <li
                  key={line.lineId}
                  className="flex flex-wrap items-center justify-between gap-tg rounded-card border border-border bg-card p-3 gaze:flex-col gaze:items-stretch gaze:border-0 gaze:bg-transparent gaze:p-0"
                >
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="font-bold">{line.item}</span>
                    <span className="text-small text-muted-foreground">
                      بقي للإرجاع: <span className="num font-semibold text-foreground">{left}</span> {line.unit} ·{" "}
                      <span className="num" dir="ltr">{formatAmount(line.unitCost)}</span> ر.س للوحدة
                    </span>
                  </div>
                  {left > 0 ? (
                    <QuantityStepper
                      label={`الكمية المرتجعة من ${line.item}`}
                      value={quantities[line.lineId] ?? 0}
                      max={left}
                      unit={line.unit}
                      onChange={(value) => setQuantities((all) => ({ ...all, [line.lineId]: value }))}
                    />
                  ) : (
                    <span className="text-small font-semibold text-muted-foreground">لم يبقَ منه شيء</span>
                  )}
                </li>
              )
            })}
          </ul>
          {pages > 1 ? (
            <div className="grid grid-cols-2 gap-tg">
              <Button icon={BackIcon} disabled={page === 0} onClick={() => setPage(page - 1)}>
                السطر السابق
              </Button>
              <Button iconEnd={NextIcon} disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>
                السطر التالي
              </Button>
            </div>
          ) : null}
          <p className="text-flow font-semibold" aria-live="polite">
            يُخصم <span className="num" dir="ltr">{formatAmount(totals.gross)}</span> ر.س مع الضريبة
            {gaze ? null : (
              <span className="font-normal text-muted-foreground">
                {" "}
                (<span className="num">{chosen.length}</span> أسطر)
              </span>
            )}
          </p>
        </>
      ) : null}

      {step === 2 && invoice ? (
        <>
          {summary}
          <Field label="السبب" required>
            <Select options={REASONS} value={reason} onValueChange={setReason} emptyLabel="اختر السبب" />
          </Field>
          {reason === "OTHER" || !gaze ? (
            <Field label={reason === "OTHER" ? "اكتب السبب" : "ملاحظة (اختيارية)"} hint="تُحفظ مع المرتجع.">
              <Textarea rows={2} maxLength={280} value={note} onChange={(event) => setNote(event.target.value)} />
            </Field>
          ) : null}
          <p className="text-flow">
            ينقص المخزون في <span className="num">{chosen.length}</span> أصناف، ويُخصم{" "}
            <span className="num font-bold" dir="ltr">
              {formatAmount(totals.gross)}
            </span>{" "}
            ر.س من المصاريف بعد التسجيل.
          </p>
        </>
      ) : null}
    </Screen>
  )
}
