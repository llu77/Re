/*
 * المرتجع من فاتورة
 * =================
 * «مسترجع» بكلمة المالك: من فاتورةٍ مسجّلة، لا يُرجع أكثر ممّا بقي من سطرها، والسبب مطلوب، ومندوب
 * المورّد الذي استلم يُحفظ معه. المسودة في الخادم: كل كميةٍ تُحفظ حين تتغيّر. بعد التسجيل ينتظر
 * المرتجع إشعار المورّد الدائن (حتى الخامس عشر من الشهر التالي) فيُكتب رقمه وتاريخه.
 *
 *   • اختيار الفاتورة: بحثٌ بالمورّد أو الرقم، ثم «ابدأ المرتجع».
 *   • الكميات: لكل سطرٍ − و+ بحدّ ما بقي (أو حقلٌ للوحدات التي تُكسر)؛ في الحجم الكبير سطرٌ في كل شاشة.
 *   • السبب والمندوب والملاحظة، ثم «راجِع وسجّل» (review.tsx).
 */

import * as React from "react"
import { ClipboardCheck, Save, Trash, Undo2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Combobox, type ComboboxOption } from "@/components/ui/combobox"
import { DataTable } from "@/components/ui/data-table"
import { Dialog } from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input } from "@/components/ui/input"
import { QuantityStepper } from "@/components/ui/quantity"
import { Stepper } from "@/components/ui/stepper"
import { Tabs } from "@/components/ui/tabs"
import { formatDay } from "@/lib/format"
import {
  RETURN_STATUS, codeName, formatMilli, milliInput, parseMilli,
  type InventoryChoices, type Paged, type PurchaseRow, type Rep, type Return, type ReturnLine, type ReturnRow,
} from "@/lib/inventory"
import { formatAmount } from "@/lib/money"
import { useSize } from "@/lib/size"

import { Facts, GazeHost, GazeSlot, Money, Picker, Qty, useOpenReport, type Fact } from "./common"
import type { Fail } from "./setup"

/* ── القائمة ─────────────────────────────────────────────────────── */

export type ReturnsFilter = "awaiting" | "all" | "DRAFT"

export function ReturnsScreen({ data, filter, onFilter, page, onPage, onOpen, onNew, onBack }: {
  data: Paged<ReturnRow> | null
  filter: ReturnsFilter
  onFilter: (filter: ReturnsFilter) => void
  page: number
  onPage: (page: number) => void
  onOpen: (row: ReturnRow) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  return (
    <Screen
      title="المرتجعات"
      back={gaze ? undefined : { id: "returns-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "returns-new", label: "مرتجع جديد", icon: Undo2, onClick: onNew }}
    >
      <Tabs
        items={[{ id: "awaiting", label: "تنتظر إشعاراً دائناً" }, { id: "all", label: "الكل" }, { id: "DRAFT", label: "مسودات" }]}
        value={filter}
        onValueChange={(id) => onFilter(id as ReturnsFilter)}
        label="المرتجعات"
      >
        {data === null ? null : (
          <DataTable<ReturnRow>
            caption="المرتجعات"
            rows={data.items}
            rowKey={(row) => row.id}
            columns={[
              { id: "label", header: "الرقم", cell: (row) => <span className="num">{row.label ?? "مسودة"}</span> },
              { id: "purchase", header: "من الفاتورة", cell: (row) => <span className="num">{row.purchase_label}</span> },
              { id: "supplier", header: "المورّد", cell: (row) => row.supplier_name ?? "" },
              { id: "date", header: "التاريخ", cell: (row) => (row.return_date ? formatDay(row.return_date) : "") },
              { id: "credit", header: "الإشعار الدائن", cell: (row) => (row.credit_note_no ? <span className="num">{row.credit_note_no}</span> : row.status === "POSTED" ? <Badge tone={row.credit_note_overdue ? "danger" : "warning"}>{row.credit_note_overdue ? "تأخّر" : "ينتظر"}</Badge> : "") },
              { id: "total", header: "الإجمالي", numeric: true, cell: (row) => (row.total_halalas === null ? "" : formatAmount(row.total_halalas)) },
            ]}
            primary={(row) => row.supplier_name ?? row.purchase_label}
            secondary={(row) => `${row.label ?? RETURN_STATUS[row.status]} من ${row.purchase_label}${row.return_date ? ` · ${formatDay(row.return_date)}` : ""}`}
            trailing={(row) => (
              <>
                {row.total_halalas === null ? null : <span className="num font-bold" dir="ltr">{formatAmount(row.total_halalas)}</span>}
                {row.status === "POSTED" && !row.credit_note_no ? <Badge tone={row.credit_note_overdue ? "danger" : "warning"} className="gaze:hidden">{row.credit_note_overdue ? "تأخّر الإشعار" : "ينتظر الإشعار"}</Badge> : null}
              </>
            )}
            onOpen={onOpen}
            openLabel={(row) => `افتح ${row.label ?? "مسودة المرتجع"}`}
            pageSize={{ compact: 10, gaze: 3, gazeShort: 2 }}
            page={page}
            onPageChange={onPage}
            total={data.total}
            empty={<EmptyState icon={Undo2} title="لا مرتجعات هنا" description="يبدأ المرتجع من فاتورةٍ مسجّلة." />}
          />
        )}
      </Tabs>
    </Screen>
  )
}

/* ── من أيّ فاتورة؟ ──────────────────────────────────────────────── */

export function NewReturnScreen({ options, purchases, query, onQuery, onStart, onBack }: {
  options: ComboboxOption[]
  purchases: PurchaseRow[]
  query: string
  onQuery: (query: string) => void
  onStart: (purchaseId: string) => Promise<Fail>
  onBack: () => void
}) {
  const [choice, setChoice] = React.useState<ComboboxOption | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const chosen = choice ? purchases.find((row) => row.id === choice.value) ?? null : null
  const report = useOpenReport("return-purchase")
  async function start() {
    if (!choice) return
    setBusy(true)
    setFail(null)
    const result = await onStart(choice.value)
    setBusy(false)
    if (result) setFail(result)
  }
  return (
    <Screen
      title="من أيّ فاتورة؟"
      description="الفواتير المسجّلة التي بقي فيها ما يُرجَع."
      back={{ id: "return-new-back", label: "الرئيسية", onClick: onBack }}
      actions={
        <Button id="return-start" variant="primary" commit icon={Undo2} disabled={!choice} busy={busy} onClick={() => void start()}>
          ابدأ المرتجع
        </Button>
      }
    >
      {fail ? (
        <Alert tone="danger" title="لم يبدأ" live>
          {fail.message}
        </Alert>
      ) : null}
      <GazeHost>
        <GazeSlot id="return-purchase">
          <Field id="return-purchase" label="المورّد أو رقم الفاتورة">
            <Combobox
              listLabel="الفواتير المطابقة"
              options={options}
              value={choice}
              onValueChange={setChoice}
              query={query}
              onQueryChange={onQuery}
              pageSize={{ compact: 6, gaze: 3, gazeShort: 1 }}
              onOpenChange={report}
            />
          </Field>
        </GazeSlot>
        {chosen ? (
          <GazeSlot id="return-chosen">
            <p className="text-flow rounded-card border border-border bg-card p-pad">
              <span className="font-semibold">{chosen.supplier_name}</span> · <span className="num">{chosen.label}</span>
              {chosen.invoice_date ? ` · ${formatDay(chosen.invoice_date, true)}` : ""} · <span className="num">{chosen.lines}</span> أسطر ·{" "}
              {chosen.total_halalas === null ? "" : <Money halalas={chosen.total_halalas} />}
            </p>
          </GazeSlot>
        ) : null}
      </GazeHost>
    </Screen>
  )
}

/* ── المسودة ─────────────────────────────────────────────────────── */

const STEPS = [
  { id: "quantities", label: "الكميات" },
  { id: "reason", label: "السبب" },
  { id: "review", label: "المراجعة" },
]

export interface ReturnEditorProps {
  draft: Return
  choices: InventoryChoices
  reps: Rep[] | null
  onLine: (lineNo: number, quantityMilli: number) => Promise<Fail>
  onHeader: (fields: { reason?: string | null; note?: string | null; rep_id?: string | null; return_date?: string | null }) => Promise<Fail>
  onDiscard: () => Promise<Fail>
  onReview: () => void
  onBack: () => void
  today: string
}

export function ReturnEditor({ draft, choices, reps, onLine, onHeader, onDiscard, onReview, onBack, today }: ReturnEditorProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState(0)
  const [lineIndex, setLineIndex] = React.useState(0)
  const [reason, setReason] = React.useState<string | null>(draft.reason)
  const [note, setNote] = React.useState(draft.note ?? "")
  const [rep, setRep] = React.useState(draft.rep?.id ?? "")
  const [date, setDate] = React.useState(draft.return_date ?? today)
  const [texts, setTexts] = React.useState<Record<number, string>>({})
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)
  const [discarding, setDiscarding] = React.useState(false)
  const error = (field: string) => (fail?.field === field ? fail.message : null)
  const chosen = draft.lines.filter((line) => line.quantity_milli > 0)
  const gross = chosen.reduce((sum, line) => sum + Math.round((line.quantity_milli * line.unit_price_halalas) / 1000), 0)

  async function setQuantity(line: ReturnLine, milli: number) {
    setBusy(`line-${line.line_no}`)
    const result = await onLine(line.line_no, milli)
    setBusy(null)
    setFail(result)
  }

  async function commitHeader(): Promise<boolean> {
    const fields: Parameters<typeof onHeader>[0] = {}
    if (reason !== draft.reason) fields.reason = reason
    if ((note.trim() || null) !== draft.note) fields.note = note.trim() || null
    if ((rep || null) !== (draft.rep?.id ?? null)) fields.rep_id = rep || null
    if (date !== draft.return_date) fields.return_date = date
    if (Object.keys(fields).length === 0) return true
    setBusy("header")
    const result = await onHeader(fields)
    setBusy(null)
    setFail(result)
    return result === null
  }

  async function review() {
    if (!reason) {
      setFail({ message: "اختر سبب الإرجاع.", field: "reason" })
      if (gaze) setStep(1)
      return
    }
    if (reason === "OTHER" && !note.trim()) {
      setFail({ message: "اكتب السبب في الملاحظة.", field: "note" })
      if (gaze) setStep(1)
      return
    }
    if (chosen.length === 0) {
      setFail({ message: "اختر كميةً من سطرٍ واحد على الأقل.", field: null })
      if (gaze) setStep(0)
      return
    }
    if (await commitHeader()) onReview()
  }

  async function discard() {
    setBusy("discard")
    const result = await onDiscard()
    setBusy(null)
    setDiscarding(false)
    setFail(result)
  }

  function lineRow(line: ReturnLine) {
    const decimals = choices.units.find((u) => u.code === line.item.unit)?.decimals ?? false
    const left = line.remaining_milli
    const text = texts[line.line_no] ?? milliInput(line.quantity_milli || null)
    return (
      <li key={line.line_no} className="flex flex-wrap items-center justify-between gap-tg rounded-card border border-border bg-card p-3 gaze:flex-col gaze:items-stretch gaze:border-0 gaze:bg-transparent gaze:p-0">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="font-bold">{line.item.name}</span>
          <span className="text-small text-muted-foreground">
            اشتريت <Qty milli={line.bought_milli} unit={line.item.unit_name} />، بقي للإرجاع <Qty milli={left} className="font-semibold text-foreground" /> · <Money halalas={line.unit_price_halalas} /> للوحدة
          </span>
        </div>
        {left <= 0 ? (
          <span className="text-small font-semibold text-muted-foreground">لم يبقَ منه شيء</span>
        ) : decimals ? (
          <div className="flex items-end gap-tg">
            <Field label={`الكمية المرتجعة من ${line.item.name}`} error={error(`line-${line.line_no}`)}>
              <Input
                id={`return-line-${line.line_no}`}
                numeric
                inputMode="decimal"
                value={text}
                onChange={(event) => setTexts((all) => ({ ...all, [line.line_no]: event.target.value }))}
              />
            </Field>
            <Button
              id={`return-line-${line.line_no}-save`}
              variant="secondary"
              commit
              icon={Save}
              busy={busy === `line-${line.line_no}`}
              onClick={() => {
                const milli = text.trim() === "" || text.trim() === "0" ? 0 : parseMilli(text, true, left)
                if (milli === null) setFail({ message: "كميةٌ لا تزيد على ما بقي.", field: `line-${line.line_no}` })
                else void setQuantity(line, milli)
              }}
            >
              احفظ
            </Button>
          </div>
        ) : (
          <QuantityStepper
            label={`الكمية المرتجعة من ${line.item.name}`}
            value={Math.floor(line.quantity_milli / 1000)}
            max={Math.floor(left / 1000)}
            unit={line.item.unit_name}
            onChange={(value) => void setQuantity(line, value * 1000)}
          />
        )}
      </li>
    )
  }

  const reasonFields = (
    <GazeHost>
      <Picker id="return-reason" label="سبب الإرجاع" options={choices.return_reasons.map((r) => ({ value: r.code, label: r.name }))} value={reason} onValueChange={(value) => { setReason(value); if (!gaze) void onHeader({ reason: value }).then(setFail) }} error={error("reason")} required />
      <GazeSlot id="return-note">
        <Field label={reason === "OTHER" ? "اكتب السبب" : "ملاحظة"} error={error("note")}>
          <Input id="return-note" value={note} maxLength={280} onChange={(event) => setNote(event.target.value)} onBlur={() => { if (!gaze) void commitHeader() }} />
        </Field>
      </GazeSlot>
      <Picker
        id="return-rep"
        label="مندوب المورّد الذي استلم"
        options={[{ value: "", label: "بلا مندوب" }, ...(reps ?? []).filter((r) => r.is_active || r.id === rep).map((r) => ({ value: r.id, label: r.mobile ? `${r.name} · ${r.mobile}` : r.name }))]}
        value={rep}
        onValueChange={(value) => { setRep(value); if (!gaze) void onHeader({ rep_id: value || null }).then(setFail) }}
        error={error("rep_id")}
      />
      <GazeSlot id="return-date">
        <Field label="تاريخ الإرجاع" error={error("return_date")} className="gaze:short:hidden">
          <Input id="return-date" type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} onBlur={() => { if (!gaze) void commitHeader() }} />
        </Field>
      </GazeSlot>
    </GazeHost>
  )
  const failAlert = fail && !fail.field ? (
    <Alert tone="danger" title="لم يتمّ" live>
      {fail.message}
    </Alert>
  ) : null
  const summary = (
    <p className="text-flow font-semibold" aria-live="polite">
      يُرجَع من <span className="num">{chosen.length}</span> أسطر بقيمة <Money halalas={gross} /> قبل الضريبة.
    </p>
  )
  const header = `${draft.purchase.supplier_name ?? ""} · ${draft.purchase.label}`
  const discardDialog = (
    <Dialog open={discarding} onClose={() => setDiscarding(false)} alert title="حذف مسودة المرتجع" closeLabel="رجوع"
            footer={<Button id="return-discard-yes" variant="danger" commit icon={Trash} busy={busy === "discard"} onClick={() => void discard()}>نعم، احذف</Button>}>
      <p className="text-flow">{header}</p>
    </Dialog>
  )

  if (gaze) {
    const lines = draft.lines
    const current = Math.min(lineIndex, Math.max(0, lines.length - 1))
    return (
      <Screen
        title={step === 0 ? `السطر ${current + 1} من ${lines.length}` : "سبب الإرجاع"}
        description={header}
        above={<Stepper steps={STEPS} current={step} />}
        actions={
          <>
            <Button id="return-prev" icon={BackIcon} onClick={step === 0 ? (current === 0 ? onBack : () => setLineIndex(current - 1)) : () => setStep(0)}>
              {step === 0 ? (current === 0 ? "رجوع" : "السطر السابق") : "الكميات"}
            </Button>
            {step === 0 ? (
              current < lines.length - 1 ? (
                <Button id="return-next" variant="secondary" iconEnd={NextIcon} onClick={() => setLineIndex(current + 1)}>
                  السطر التالي
                </Button>
              ) : (
                <Button id="return-next" variant="secondary" iconEnd={NextIcon} disabled={chosen.length === 0} onClick={() => setStep(1)}>
                  السبب
                </Button>
              )
            ) : (
              <Button id="return-review" variant="secondary" icon={ClipboardCheck} busy={busy !== null} onClick={() => void review()}>
                راجِع وسجّل
              </Button>
            )}
          </>
        }
      >
        {failAlert}
        {step === 0 ? (
          <>
            {lines[current] ? <ul aria-label="أسطر الفاتورة" className="flex flex-col gap-tg">{lineRow(lines[current])}</ul> : null}
            {summary}
          </>
        ) : (
          reasonFields
        )}
      </Screen>
    )
  }
  return (
    <Screen
      title="مرتجع من فاتورة"
      above={<Badge tone="info" className="self-start">مسودة لم تُسجَّل</Badge>}
      description={header}
      back={{ id: "return-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "return-discard", label: "احذف المسودة", danger: true, icon: Trash, onClick: () => setDiscarding(true) }}
      actions={
        <Button id="return-review" variant="secondary" size="lg" icon={ClipboardCheck} busy={busy !== null} onClick={() => void review()} className="ms-auto">
          راجِع وسجّل
        </Button>
      }
    >
      {failAlert}
      <section aria-labelledby="return-lines" className="flex flex-col gap-tg">
        <h2 id="return-lines" className="text-lead font-semibold">ما الذي يُرجَع؟</h2>
        <ul aria-label="أسطر الفاتورة" className="flex flex-col gap-tg-min">{draft.lines.map(lineRow)}</ul>
        {summary}
      </section>
      <section aria-labelledby="return-reason-title" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <h2 id="return-reason-title" className="text-lead font-semibold">السبب والمندوب</h2>
        {reasonFields}
      </section>
      {discardDialog}
    </Screen>
  )
}

/* ── المرتجع المسجَّل ────────────────────────────────────────────── */

export function ReturnView({ draft, choices, onCreditNote, onOpenPurchase, onBack, today }: {
  draft: Return
  choices: InventoryChoices
  onCreditNote: (number: string, date: string) => Promise<Fail>
  onOpenPurchase: () => void
  onBack: () => void
  today: string
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [number, setNumber] = React.useState("")
  const [date, setDate] = React.useState(today)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  // الحجم الكبير: الإشعار الدائن في لسانه، ويُفتح عليه ما دام لم يُكتب: هو ما ينتظره المرتجع.
  const [tab, setTab] = React.useState(draft.credit_note ? "facts" : "credit")
  // بعد حفظ الإشعار يزول لسانه: يُعرض المرتجع بحقائقه ومعها الإشعار.
  const shown = draft.credit_note && tab === "credit" ? "facts" : tab
  const facts: Fact[] = [
    { label: "من الفاتورة", value: <span className="num">{draft.purchase.label}</span>, key: true },
    { label: "المورّد", value: draft.purchase.supplier_name, key: true },
    { label: "السبب", value: codeName(choices.return_reasons, draft.reason), key: true },
    { label: "المندوب", value: draft.rep ? (draft.rep.mobile ? `${draft.rep.name} · ${draft.rep.mobile}` : draft.rep.name) : null },
    { label: "التاريخ", value: draft.return_date ? formatDay(draft.return_date, true) : null, key: true },
    { label: "الإجمالي", value: draft.totals ? <Money halalas={draft.totals.gross} /> : null, key: true },
    { label: "ملاحظة", value: draft.note },
    { label: "الإشعار الدائن", value: draft.credit_note ? <span><span className="num" dir="ltr">{draft.credit_note.number}</span> · {formatDay(draft.credit_note.date, true)}</span> : null, key: true },
  ]
  async function save() {
    if (!number.trim()) return setFail({ message: "اكتب رقم الإشعار الدائن.", field: "number" })
    setBusy(true)
    setFail(null)
    const result = await onCreditNote(number.trim(), date)
    setBusy(false)
    if (result) setFail(result)
  }
  const creditForm = draft.credit_note ? null : (
    <section aria-labelledby="credit-note" className="flex flex-col gap-tg rounded-card border border-warning-line bg-warning-tint p-pad">
      <h2 id="credit-note" className="text-lead font-semibold">إشعار المورّد الدائن</h2>
      {draft.credit_note_due ? (
        <p className="text-small text-warning gaze:short:hidden">يستحقّ حتى {formatDay(draft.credit_note_due, true)}؛ اكتب رقمه وتاريخه حين يصل.</p>
      ) : null}
      <GazeHost>
        <GazeSlot id="credit-number">
          <Field label="رقم الإشعار" error={fail?.field === "number" ? fail.message : null} required>
            <Input id="credit-number" dir="ltr" value={number} maxLength={40} onChange={(event) => setNumber(event.target.value)} />
          </Field>
        </GazeSlot>
        <GazeSlot id="credit-date">
          <Field label="تاريخه" error={fail?.field === "date" ? fail.message : null}>
            <Input id="credit-date" type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} />
          </Field>
        </GazeSlot>
      </GazeHost>
      <div>
        <Button id="credit-save" variant="primary" commit icon={Save} busy={busy} onClick={() => void save()}>
          احفظ الإشعار
        </Button>
      </div>
    </section>
  )
  const lines = (
    <DataTable<ReturnLine>
      caption="أسطر المرتجع"
      rows={draft.lines.filter((line) => line.quantity_milli > 0)}
      rowKey={(row) => String(row.line_no)}
      columns={[
        { id: "item", header: "المنتج", cell: (row) => row.item.name },
        { id: "qty", header: "الكمية", numeric: true, cell: (row) => `${formatMilli(row.quantity_milli)} ${row.item.unit_name}` },
        { id: "price", header: "سعر الوحدة", numeric: true, cell: (row) => formatAmount(row.unit_price_halalas) },
        { id: "net", header: "قبل الضريبة", numeric: true, cell: (row) => (row.net_halalas === null ? "" : formatAmount(row.net_halalas)) },
        { id: "vat", header: "الضريبة", numeric: true, cell: (row) => (row.vat_halalas === null ? "" : formatAmount(row.vat_halalas)) },
      ]}
      primary={(row) => row.item.name}
      secondary={(row) => `${formatMilli(row.quantity_milli)} ${row.item.unit_name} × ${formatAmount(row.unit_price_halalas)}`}
      trailing={(row) => (row.net_halalas === null ? null : <span className="num font-bold" dir="ltr">{formatAmount(row.net_halalas + (row.vat_halalas ?? 0))}</span>)}
      pageSize={{ compact: 40, gaze: 3, gazeShort: 2 }}
    />
  )
  return (
    <Screen
      title={draft.label ?? "مرتجع"}
      above={<Badge tone="success" className="self-start">{RETURN_STATUS[draft.status]}</Badge>}
      back={{ id: "return-view-back", label: "رجوع", onClick: onBack }}
      end={gaze ? undefined : { id: "return-open-purchase", label: draft.purchase.label, onClick: onOpenPurchase }}
    >
      {fail && !fail.field ? (
        <Alert tone="danger" title="لم يُحفظ" live>
          {fail.message}
        </Alert>
      ) : null}
      {gaze ? (
        <Tabs
          items={[{ id: "facts", label: "المرتجع" }, { id: "lines", label: "الأسطر" }, ...(draft.credit_note ? [] : [{ id: "credit", label: "الإشعار الدائن" }])]}
          value={shown}
          onValueChange={setTab}
          label="المرتجع"
          stretch
        >
          {shown === "facts" ? <Facts facts={facts} columns={2} /> : shown === "lines" ? lines : creditForm}
        </Tabs>
      ) : (
        <>
          <Facts facts={facts} columns={3} />
          {creditForm}
          <section aria-labelledby="return-view-lines" className="flex flex-col gap-tg">
            <h2 id="return-view-lines" className="text-lead font-semibold">الأسطر</h2>
            {lines}
          </section>
        </>
      )}
    </Screen>
  )
}
