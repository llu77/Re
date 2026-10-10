/*
 * الجرد
 * =====
 * «جرد» بكلمة المالك: جلسةٌ تلتقط الأرصدة الدفترية لحظة فتحها (كل المنتجات، أو تصنيف، أو ما تحت
 * حدّ الطلب، أو منتجاتٌ مختارة)، ويُعدّ كل منتجٍ ويُكتب ما وُجد. العدّ مغلقٌ افتراضياً: الرصيد
 * الدفتري لا يظهر حتى يُكتب العدّ، ثم يظهر الفرق ويُطلب سببه. ما تحرّك رصيده بعد اللقطة يُحدَّث
 * ويُعاد عدّه. الترحيل يسوّي كل فرقٍ بسند جرد، والإلغاء يحتفظ بالرقم.
 *
 *   • القائمة، ثم «جلسة جديدة» (النطاق ثم التفاصيل ثم العدّ المغلق).
 *   • الجلسة: صفوفٌ تُفتح للعدّ؛ في الحجم الكبير ثلاثةٌ في الصفحة وزرّان: «رحّل» و«خيارات».
 *   • سطر العدّ: العدد، والسبب إن اختلف، والتكلفة إن كان الرصيد صفراً، ثم «احفظ والتالي».
 */

import * as React from "react"
import { ClipboardCheck, ClipboardList, ListPlus, Plus, RefreshCw, Save, Settings2, X } from "lucide-react"

import { Screen } from "@/components/shell/screen"
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
import { formatDay, formatTime } from "@/lib/format"
import {
  COUNT_STATUS, codeName, formatMilli, milliInput, parseMilli,
  type Category, type CountLine, type CountRow, type CountScope, type CountSession, type InventoryChoices, type Paged,
} from "@/lib/inventory"
import { formatAmount, parseAmount } from "@/lib/money"
import { LIST_PAGE, useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

import { Facts, GazeHost, GazeSlot, Picker, Qty, useOpenReport, type Fact } from "./common"
import type { Fail } from "./setup"

const STATUS_TONE: Record<CountSession["status"], "info" | "success" | "neutral"> = { OPEN: "info", POSTED: "success", CANCELLED: "neutral" }

/* ── القائمة ─────────────────────────────────────────────────────── */

export function CountsScreen({ data, page, onPage, openSession, onOpen, onNew, onBack }: {
  data: Paged<CountRow> | null
  page: number
  onPage: (page: number) => void
  /** الجلسة المفتوحة إن وُجدت: الزرّ يفتحها بدل جلسةٍ جديدة. */
  openSession: { id: string; label: string } | null
  onOpen: (row: CountRow) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  return (
    <Screen
      title="الجرد"
      description={gaze ? undefined : "جلسةٌ تعدّ ما في المخزن وتسوّي الفرق بسنداتٍ حين تُرحَّل."}
      back={gaze ? undefined : { id: "counts-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "counts-new", label: openSession ? `تابع ${openSession.label}` : "جلسة جديدة", icon: openSession ? ClipboardList : Plus, onClick: onNew }}
    >
      {data === null ? null : (
        <DataTable<CountRow>
          caption="جلسات الجرد"
          rows={data.items}
          rowKey={(row) => row.id}
          columns={[
            { id: "label", header: "الجلسة", cell: (row) => <span className="num">{row.label}</span> },
            { id: "scope", header: "النطاق", cell: (row) => row.scope_name },
            { id: "date", header: "التاريخ", cell: (row) => formatDay(row.snapshot_at) },
            { id: "progress", header: "العدّ", numeric: true, cell: (row) => `${row.status === "OPEN" ? row.counted_so_far : (row.items_counted ?? 0)} / ${row.items_total}` },
            { id: "status", header: "الحالة", cell: (row) => <Badge tone={STATUS_TONE[row.status]}>{COUNT_STATUS[row.status]}</Badge> },
          ]}
          primary={(row) => `${row.label} · ${row.scope_name}`}
          secondary={(row) => `${formatDay(row.snapshot_at)} · عُدّ ${row.status === "OPEN" ? row.counted_so_far : (row.items_counted ?? 0)} من ${row.items_total}`}
          trailing={(row) => <Badge tone={STATUS_TONE[row.status]}>{COUNT_STATUS[row.status]}</Badge>}
          onOpen={onOpen}
          openLabel={(row) => `افتح ${row.label}`}
          pageSize={LIST_PAGE}
          page={page}
          onPageChange={onPage}
          total={data.total}
          empty={<EmptyState icon={ClipboardList} title="لا جلسات جرد بعد" action={<Button variant="primary" icon={Plus} onClick={onNew}>جلسة جديدة</Button>} />}
        />
      )}
    </Screen>
  )
}

/* ── جلسة جديدة ──────────────────────────────────────────────────── */

export interface CountOpenBody {
  scope: CountScope
  category_id: string | null
  item_ids: string[] | null
  blind: boolean
}

const NEW_STEPS = [
  { id: "scope", label: "النطاق" },
  { id: "details", label: "التفاصيل" },
  { id: "blind", label: "طريقة العدّ" },
]

export function NewCountScreen({ choices, categories, itemOptions, onItemQuery, onOpen, onBack }: {
  choices: InventoryChoices
  categories: Category[]
  itemOptions: ComboboxOption[]
  onItemQuery: (query: string) => void
  onOpen: (body: CountOpenBody) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState(0)
  const [scope, setScope] = React.useState<CountScope>("ALL")
  const [category, setCategory] = React.useState<string | null>(null)
  const [picked, setPicked] = React.useState<ComboboxOption[]>([])
  const [choice, setChoice] = React.useState<ComboboxOption | null>(null)
  const [query, setQuery] = React.useState("")
  const [blind, setBlind] = React.useState<"yes" | "no">("yes")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const report = useOpenReport("count-items")
  const needsDetails = scope === "CATEGORY" || scope === "SELECTED"

  async function open() {
    if (scope === "CATEGORY" && !category) {
      setFail({ message: "اختر التصنيف.", field: "category_id" })
      if (gaze) setStep(1)
      return
    }
    if (scope === "SELECTED" && picked.length === 0) {
      setFail({ message: "اختر منتجاً واحداً على الأقل.", field: "item_ids" })
      if (gaze) setStep(1)
      return
    }
    setBusy(true)
    setFail(null)
    const result = await onOpen({ scope, category_id: scope === "CATEGORY" ? category : null, item_ids: scope === "SELECTED" ? picked.map((p) => p.value) : null, blind: blind === "yes" })
    setBusy(false)
    if (result) setFail(result)
  }

  const scopeCards = (
    <RadioCards<CountScope>
      label="ما الذي يُجرد؟"
      value={scope}
      columns={1}
      gazeColumns={2}
      onValueChange={(value) => { setScope(value); setFail(null) }}
      ids={{ ALL: "count-scope-all", CATEGORY: "count-scope-category", LOW: "count-scope-low", SELECTED: "count-scope-selected" }}
      options={choices.count_scopes.map((s) => ({ value: s.code as CountScope, title: s.name }))}
    />
  )
  const details = (
    <GazeHost>
      {scope === "CATEGORY" ? (
        <Picker id="count-category" label="التصنيف" options={categories.filter((c) => c.is_active).map((c) => ({ value: c.id, label: c.name }))} value={category} onValueChange={setCategory} error={fail?.field === "category_id" ? fail.message : null} required />
      ) : null}
      {scope === "SELECTED" ? (
        <>
          <GazeSlot id="count-items">
            <Field id="count-items" label="أضف منتجاً" hint={gaze ? undefined : "اكتب بعض الاسم واختر؛ يُضاف إلى القائمة."} error={fail?.field === "item_ids" ? fail.message : null}>
              <Combobox
                listLabel="المنتجات المطابقة"
                options={itemOptions.filter((option) => !picked.some((p) => p.value === option.value))}
                value={choice}
                onValueChange={(option) => {
                  setChoice(null)
                  setQuery("")
                  onItemQuery("")
                  if (option) setPicked((all) => [...all, option])
                }}
                query={query}
                onQueryChange={(text) => { setQuery(text); onItemQuery(text) }}
                pageSize={{ compact: 6, gaze: 3, gazeShort: 1 }}
                onOpenChange={report}
              />
            </Field>
          </GazeSlot>
          <GazeSlot id="count-picked" field={false}>
            {picked.length ? (
              <ul aria-label="المنتجات المختارة" className="flex flex-wrap gap-tg-min">
                {picked.slice(gaze ? -3 : 0).map((option) => (
                  <li key={option.value}>
                    <Button isValue icon={X} onClick={() => setPicked((all) => all.filter((p) => p.value !== option.value))} className="rounded-pill">
                      {option.label}
                    </Button>
                  </li>
                ))}
                {gaze && picked.length > 3 ? <li className="self-center text-small text-muted-foreground">و{picked.length - 3} غيرها</li> : null}
              </ul>
            ) : (
              <p className="text-small text-muted-foreground">لم يُختر شيءٌ بعد.</p>
            )}
          </GazeSlot>
        </>
      ) : null}
      {!needsDetails ? <p className="text-flow text-muted-foreground">{scope === "ALL" ? "كل المنتجات التي تُخزَّن." : "المنتجات التي رصيدها عند حدّ الطلب أو تحته."}</p> : null}
    </GazeHost>
  )
  const blindCards = (
    <RadioCards<"yes" | "no">
      label="طريقة العدّ"
      value={blind}
      columns={1}
      onValueChange={setBlind}
      ids={{ yes: "count-blind-yes", no: "count-blind-no" }}
      options={[
        { value: "yes", title: "عدٌّ مغلق", description: "الرصيد الدفتري لا يظهر حتى تكتب ما عددت: أدقّ." },
        { value: "no", title: "عدٌّ مفتوح", description: "يظهر الرصيد الدفتري بجانب كل منتج." },
      ]}
    />
  )
  const failAlert = fail && !fail.field ? (
    <Alert tone="danger" title="لم تُفتح الجلسة" live>
      {fail.message}
    </Alert>
  ) : null
  const openButton = (
    <Button id="count-open" variant="primary" commit icon={ClipboardList} busy={busy} onClick={() => void open()}>
      افتح الجلسة
    </Button>
  )
  if (gaze) {
    const steps = needsDetails ? NEW_STEPS : [NEW_STEPS[0], NEW_STEPS[2]]
    const view = steps[step]?.id ?? "scope"
    const last = step === steps.length - 1
    return (
      <Screen
        title="جلسة جرد جديدة"
        above={<Stepper steps={steps} current={Math.min(step, steps.length - 1)} />}
        actions={
          // «السابق» حيث كان «التالي» في الخطوة الأخيرة، و«ابدأ الجرد» في الخانة الأخرى.
          last ? (
            <>
              <React.Fragment key="open">{openButton}</React.Fragment>
              <Button key="prev" id="count-prev" icon={BackIcon} onClick={() => setStep(step - 1)}>
                السابق
              </Button>
            </>
          ) : (
            <>
              <Button key="prev" id="count-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(step - 1)}>
                {step === 0 ? "رجوع" : "السابق"}
              </Button>
              <Button key="next" id="count-next" variant="secondary" iconEnd={NextIcon} onClick={() => setStep(step + 1)}>
                التالي
              </Button>
            </>
          )
        }
      >
        {failAlert}
        {view === "scope" ? scopeCards : view === "details" ? details : blindCards}
      </Screen>
    )
  }
  return (
    <Screen title="جلسة جرد جديدة" back={{ id: "count-new-back", label: "الجرد", onClick: onBack }} actions={openButton}>
      {failAlert}
      {scopeCards}
      {details}
      {blindCards}
    </Screen>
  )
}

/* ── الجلسة ──────────────────────────────────────────────────────── */

export function CountScreen({ session, page, onPage, onOpenLine, onRefresh, onAdd, onPost, onCancel, onBack, today }: {
  session: CountSession
  page: number
  onPage: (page: number) => void
  onOpenLine: (line: CountLine) => void
  onRefresh: () => Promise<Fail>
  onAdd: () => void
  onPost: (occurredOn: string) => Promise<Fail>
  onCancel: () => Promise<Fail>
  onBack: () => void
  today: string
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const open = session.status === "OPEN"
  const [more, setMore] = React.useState(false)
  const [posting, setPosting] = React.useState(false)
  const [cancelling, setCancelling] = React.useState(false)
  const [date, setDate] = React.useState(today)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)

  async function run(name: string, action: () => Promise<Fail>) {
    setBusy(name)
    const result = await action()
    setBusy(null)
    setFail(result)
    setPosting(false)
    setCancelling(false)
    setMore(false)
    return result
  }

  const facts: Fact[] = [
    { label: "النطاق", value: session.category ? `${session.scope_name}: ${session.category.name}` : session.scope_name, key: true },
    { label: "اللقطة", value: `${formatDay(session.snapshot_at)} ${formatTime(session.snapshot_at)}` },
    { label: "آخر فاتورة في اللقطة", value: session.last_purchase_label },
    { label: "العدّ", value: open ? `${session.counted_so_far} من ${session.items_total}` : `${session.items_counted ?? 0} من ${session.items_total}، مطابق ${session.items_matched ?? 0}`, key: true },
    { label: "طريقة العدّ", value: session.blind ? "مغلق" : "مفتوح" },
    { label: "ملاحظة", value: session.note },
  ]
  // لا ترحيل وسطرٌ فيه فرقٌ بلا سبب: الخادم يرفضه أيضاً (inv_count_needs_reason).
  const unreasoned = session.lines.filter((line) => line.counted_milli !== null && line.difference_milli !== null && line.difference_milli !== 0 && !line.reason).length
  const canPost = session.counted_so_far > 0 && session.changed_lines === 0 && unreasoned === 0
  const changed = open && session.changed_lines > 0 ? (
    <Alert tone="warning" title={session.changed_lines === 1 ? "منتجٌ تحرّك رصيده بعد اللقطة" : `${session.changed_lines} منتجات تحرّك رصيدها بعد اللقطة`}>
      اضغط «حدّث الأرصدة» ثم أعد عدّها قبل الترحيل.
    </Alert>
  ) : null
  const lines = (
    <DataTable<CountLine>
      caption="أسطر الجرد"
      rows={session.lines}
      rowKey={(row) => row.item.id}
      columns={[
        { id: "item", header: "المنتج", cell: (row) => row.item.name },
        { id: "book", header: "الدفتري", numeric: true, cell: (row) => (row.book_milli === null ? "•••" : formatMilli(row.book_milli)) },
        { id: "counted", header: "المعدود", numeric: true, cell: (row) => (row.counted_milli === null ? "" : formatMilli(row.counted_milli)) },
        { id: "diff", header: "الفرق", numeric: true, cell: (row) => (row.difference_milli === null ? "" : (row.difference_milli > 0 ? "+" : "") + formatMilli(row.difference_milli)) },
        { id: "state", header: "", cell: (row) => (row.changed ? <Badge tone="warning">تحرّك</Badge> : row.counted_milli === null ? "" : row.difference_milli === 0 ? <Badge tone="success">مطابق</Badge> : <Badge tone="warning">فرق</Badge>) },
      ]}
      primary={(row) => row.item.name}
      secondary={(row) =>
        row.counted_milli === null
          ? `${row.item.code} · لم يُعدّ بعد${row.book_milli === null ? "" : ` · الدفتري ${formatMilli(row.book_milli)}`}`
          : `عُدّ ${formatMilli(row.counted_milli)} ${row.item.unit_name}${row.difference_milli === null ? "" : row.difference_milli === 0 ? " · مطابق" : ` · الفرق ${row.difference_milli > 0 ? "+" : ""}${formatMilli(row.difference_milli)}`}`
      }
      trailing={(row) => (row.changed ? <Badge tone="warning">تحرّك</Badge> : row.counted_milli === null ? <span className="text-small text-muted-foreground">يُعدّ</span> : <Badge tone={row.difference_milli === 0 ? "success" : row.reason ? "info" : "warning"}>{row.difference_milli === 0 ? "مطابق" : row.reason ? "فرقٌ بسببه" : "فرقٌ بلا سبب"}</Badge>)}
      onOpen={open ? onOpenLine : undefined}
      openLabel={(row) => `عُدّ ${row.item.name}`}
      pageSize={{ compact: 20, gaze: 2, gazeShort: 1 }}
      page={page}
      onPageChange={onPage}
      empty={<p className="text-small text-muted-foreground">لا منتجات في هذه الجلسة.</p>}
    />
  )
  const postDialog = (
    <Dialog open={posting} onClose={() => setPosting(false)} alert title="ترحيل الجرد" description="يُسوّى كل فرقٍ بسند جرد بتاريخه، وتُغلق الجلسة." closeLabel="رجوع"
            footer={<Button id="count-post-yes" variant="primary" commit icon={ClipboardCheck} busy={busy === "post"} onClick={() => void run("post", () => onPost(date))}>نعم، رحّل</Button>}>
      <Field label="تاريخ الجرد">
        <Input id="count-post-date" type="date" dir="ltr" value={date} max={today} onChange={(event) => setDate(event.target.value)} />
      </Field>
      <p className="text-small text-muted-foreground">عُدّ {session.counted_so_far} من {session.items_total}؛ ما لم يُعدّ يبقى على رصيده.</p>
    </Dialog>
  )
  const cancelDialog = (
    <Dialog open={cancelling} onClose={() => setCancelling(false)} alert title="إلغاء الجلسة" description="لا يتغيّر أيّ رصيد، وتبقى الجلسة في السجلّ ملغاة." closeLabel="رجوع"
            footer={<Button id="count-cancel-yes" variant="danger" commit icon={X} busy={busy === "cancel"} onClick={() => void run("cancel", onCancel)}>نعم، ألغِ</Button>}>
      <p className="text-flow">{session.label}</p>
    </Dialog>
  )
  const failAlert = fail ? (
    <Alert tone="danger" title="لم يتمّ" live>
      {fail.message}
    </Alert>
  ) : null
  const title = `${session.label}`
  const badge = <Badge tone={STATUS_TONE[session.status]} className="self-start">{COUNT_STATUS[session.status]}</Badge>

  if (gaze && open && more) {
    return (
      <Screen title="خيارات الجلسة" description={session.label} above={badge} actions={<Button id="count-more-back" icon={BackIcon} onClick={() => setMore(false)}>رجوع</Button>}>
        {failAlert}
        <div className="flex flex-col gap-tg">
          <Button id="count-refresh" icon={RefreshCw} busy={busy === "refresh"} onClick={() => void run("refresh", onRefresh)}>
            حدّث الأرصدة
          </Button>
          <Button id="count-add" icon={ListPlus} onClick={onAdd}>
            أضف منتجاً
          </Button>
          <Button id="count-cancel" variant="danger-outline" icon={X} onClick={() => setCancelling(true)}>
            ألغِ الجلسة
          </Button>
        </div>
        {cancelDialog}
      </Screen>
    )
  }
  return (
    <Screen
      title={title}
      above={badge}
      description={gaze ? undefined : facts[0].value}
      back={{ id: "count-back", label: "الجرد", onClick: onBack }}
      actions={
        open ? (
          gaze ? (
            <>
              <Button id="count-more" icon={Settings2} onClick={() => setMore(true)}>
                خيارات
              </Button>
              <Button id="count-post" variant="primary" commit icon={ClipboardCheck} disabled={!canPost} onClick={() => setPosting(true)}>
                رحّل الجرد
              </Button>
            </>
          ) : (
            <>
              <Button id="count-refresh" icon={RefreshCw} busy={busy === "refresh"} onClick={() => void run("refresh", onRefresh)}>
                حدّث الأرصدة
              </Button>
              <Button id="count-add" icon={ListPlus} onClick={onAdd}>
                أضف منتجاً
              </Button>
              <Button id="count-cancel" variant="danger-outline" icon={X} onClick={() => setCancelling(true)}>
                ألغِ الجلسة
              </Button>
              <Button id="count-post" variant="primary" commit icon={ClipboardCheck} disabled={!canPost} onClick={() => setPosting(true)} className="ms-auto">
                رحّل الجرد
              </Button>
            </>
          )
        ) : undefined
      }
    >
      {failAlert}
      {changed}
      {open && unreasoned ? (
        <Alert tone="warning" title={unreasoned === 1 ? "منتجٌ فيه فرقٌ بلا سبب" : `${unreasoned} منتجات فيها فرقٌ بلا سبب`}>
          افتح كلّاً منها واختر سبب الفرق قبل الترحيل.
        </Alert>
      ) : null}
      {gaze ? null : <Facts facts={facts} columns={3} />}
      {gaze ? (
        <p className="text-small text-muted-foreground">عُدّ <span className="num">{session.counted_so_far}</span> من <span className="num">{session.items_total}</span></p>
      ) : null}
      {lines}
      {postDialog}
      {cancelDialog}
    </Screen>
  )
}

/* ── سطر العدّ ───────────────────────────────────────────────────── */

export interface CountLineBody {
  counted_milli: number | null
  unit_cost_halalas: number | null
  reason: string | null
  note: string | null
}

export function CountLineScreen({ session, line, choices, onSave, onPrevious, onNext, onBack }: {
  session: CountSession
  line: CountLine
  choices: InventoryChoices
  onSave: (body: CountLineBody) => Promise<Fail>
  onPrevious: (() => void) | null
  onNext: (() => void) | null
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [counted, setCounted] = React.useState(milliInput(line.counted_milli))
  const [cost, setCost] = React.useState(line.unit_cost_halalas === null ? "" : formatAmount(line.unit_cost_halalas).replace(/,/g, ""))
  const [reason, setReason] = React.useState<string | null>(line.reason)
  const [note, setNote] = React.useState(line.note ?? "")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const decimals = choices.units.find((u) => u.code === line.item.unit)?.decimals ?? false
  const value = counted.trim() === "" ? null : parseMilli(counted, decimals, undefined, { zero: true })
  const book = line.book_milli
  const difference = value === null || book === null ? null : value - book
  const direction = difference === null || difference === 0 ? null : difference < 0 ? "SHORTAGE" : "SURPLUS"
  const reasons = direction ? choices.count_reasons[direction] : []
  const needsCost = value !== null && value > 0 && line.asks_cost
  const index = session.lines.findIndex((l) => l.item.id === line.item.id)
  // الحجم الكبير: صفحتان حين يكون فرق — العدد (وتكلفة الوحدة إن لزمت)، ثم سبب الفرق وملاحظته — يبدّل بينهما زرّ
  // الصفّ العلوي في مكانه. وبعد حفظ عدٍّ ظهر به فرقٌ بلا سبب تُفتح صفحة السبب: هي ما ينتظره السطر.
  const unexplained = line.counted_milli !== null && book !== null && line.counted_milli !== book && !line.reason
  const [part, setPart] = React.useState<"count" | "reason">(unexplained ? "reason" : "count")
  React.useEffect(() => {
    if (unexplained) setPart("reason")
  }, [unexplained, line.counted_milli, book])
  React.useEffect(() => {
    if (fail?.field === "reason" || fail?.field === "note") setPart("reason")
    else if (fail?.field === "counted_milli" || fail?.field === "unit_cost_halalas") setPart("count")
  }, [fail])
  const reasonPage = gaze && direction !== null && part === "reason"

  async function save(then: (() => void) | null) {
    if (counted.trim() !== "" && value === null) return setFail({ message: decimals ? "اكتب العدد، ويجوز كسرٌ بثلاث منازل." : "اكتب العدد عدداً صحيحاً.", field: "counted_milli" })
    if (needsCost && parseAmount(cost) === null) return setFail({ message: "اكتب تكلفة الوحدة: الرصيد الدفتري صفر.", field: "unit_cost_halalas" })
    if (direction && !reason) return setFail({ message: "اختر سبب الفرق.", field: "reason" })
    if (reason === "OTHER" && !note.trim()) return setFail({ message: "اكتب السبب في الملاحظة.", field: "note" })
    setBusy(true)
    setFail(null)
    const result = await onSave({
      counted_milli: value,
      unit_cost_halalas: needsCost ? parseAmount(cost) : null,
      reason: direction ? reason : null,
      note: note.trim() || null,
    })
    setBusy(false)
    if (result) setFail(result)
    else then?.()
  }

  const error = (field: string) => (fail?.field === field ? fail.message : null)
  const differenceText = difference !== null && difference !== 0 ? (
    <>الفرق <Qty milli={difference} unit={line.item.unit_name} /> ({difference < 0 ? "عجز" : "زيادة"})</>
  ) : null
  const bookText = book === null ? null : <>الرصيد الدفتري <Qty milli={book} unit={line.item.unit_name} /></>
  return (
    <Screen
      title={line.item.name}
      above={<Badge tone="info" className="num self-start">{line.item.code}{gaze ? "" : ` · ${index + 1} من ${session.lines.length}`}</Badge>}
      description={!gaze ? `${session.label} · بال${line.item.unit_name}` : reasonPage ? <span>{bookText} · {differenceText}</span> : undefined}
      back={{ id: "count-line-back", label: "الجلسة", onClick: onBack }}
      end={gaze && direction !== null ? { id: "count-line-switch", label: reasonPage ? "العدد" : "سبب الفرق", onClick: () => setPart(reasonPage ? "count" : "reason") } : undefined}
      actions={
        <>
          <Button id="count-line-prev" icon={BackIcon} disabled={!onPrevious} onClick={() => onPrevious?.()}>
            السابق
          </Button>
          <Button id="count-line-save" variant="primary" commit icon={onNext ? NextIcon : Save} busy={busy} onClick={() => void save(onNext)}>
            {onNext ? "احفظ والتالي" : "احفظ"}
          </Button>
        </>
      }
    >
      {fail && !fail.field ? (
        <Alert tone="danger" title="لم يُحفظ" live>
          {fail.message}
        </Alert>
      ) : null}
      {line.changed ? (
        <Alert tone="warning" title="تحرّك رصيد هذا المنتج بعد اللقطة">حدّث الأرصدة من الجلسة ثم أعد عدّه.</Alert>
      ) : null}
      <GazeHost>
        {reasonPage ? null : (
          <GazeSlot id="count-line-counted">
            <Field
              label={`العدد الفعلي بال${line.item.unit_name}`}
              // الحجم الكبير: الفرق في سطر المساعدة نفسه، فلا يأخذ صفّاً بين الحقلين.
              hint={book === null ? (gaze ? undefined : "عدٌّ مغلق: يظهر الرصيد الدفتري بعد الحفظ.")
                : gaze && differenceText ? <span role="status">{bookText} · {differenceText}</span> : <span>{bookText}</span>}
              error={error("counted_milli")}
            >
              <Input id="count-line-counted" numeric inputMode={decimals ? "decimal" : "numeric"} value={counted} onChange={(event) => setCounted(event.target.value)} />
            </Field>
          </GazeSlot>
        )}
        {gaze ? null : differenceText ? (
          <p role="status" className={cn("text-small font-semibold", difference !== null && difference < 0 ? "text-destructive" : "text-success")}>
            {differenceText}
          </p>
        ) : difference === 0 ? (
          <p role="status" className="text-small font-semibold text-success">مطابقٌ للدفتر.</p>
        ) : null}
        {reasons.length && (!gaze || reasonPage) ? (
          <Picker id="count-line-reason" label="سبب الفرق" options={reasons.map((r) => ({ value: r.code, label: r.name }))} value={reason} onValueChange={setReason} error={error("reason")} required />
        ) : null}
        {needsCost && !reasonPage ? (
          <GazeSlot id="count-line-cost">
            <Field label="تكلفة الوحدة" hint={gaze ? undefined : "الرصيد الدفتري صفر: تُقيَّم الزيادة بها."} error={error("unit_cost_halalas")} required>
              <Input id="count-line-cost" numeric unit="ر.س" inputMode="decimal" value={cost} onChange={(event) => setCost(event.target.value)} />
            </Field>
          </GazeSlot>
        ) : null}
        {!gaze || reasonPage ? (
          <GazeSlot id="count-line-note">
            <Field label={reason === "OTHER" ? "اكتب السبب" : "ملاحظة"} error={error("note")} className={cn(reason !== "OTHER" && "gaze:short:hidden")}>
              <Input id="count-line-note" value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} />
            </Field>
          </GazeSlot>
        ) : null}
      </GazeHost>
      {line.reason && !gaze ? <p className="text-small text-muted-foreground">حُفظ من قبل بسبب «{codeName([...choices.count_reasons.SHORTAGE, ...choices.count_reasons.SURPLUS], line.reason)}».</p> : null}
    </Screen>
  )
}

/* ── إضافة منتجٍ إلى جلسة ────────────────────────────────────────── */

export function CountAddScreen({ session, itemOptions, onItemQuery, onAdd, onBack }: {
  session: CountSession
  itemOptions: ComboboxOption[]
  onItemQuery: (query: string) => void
  onAdd: (itemId: string) => Promise<Fail>
  onBack: () => void
}) {
  const [query, setQuery] = React.useState("")
  const [choice, setChoice] = React.useState<ComboboxOption | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const report = useOpenReport("count-add-item")
  async function add() {
    if (!choice) return
    setBusy(true)
    setFail(null)
    const result = await onAdd(choice.value)
    setBusy(false)
    if (result) setFail(result)
  }
  return (
    <Screen
      title="أضف منتجاً إلى الجلسة"
      description={session.label}
      back={{ id: "count-add-back", label: "الجلسة", onClick: onBack }}
      actions={
        <Button id="count-add-yes" variant="primary" commit icon={Plus} disabled={!choice} busy={busy} onClick={() => void add()}>
          أضف
        </Button>
      }
    >
      {fail ? (
        <Alert tone="danger" title="لم يُضف" live>
          {fail.message}
        </Alert>
      ) : null}
      <GazeHost>
        <GazeSlot id="count-add-item">
          <Field id="count-add-item" label="المنتج">
            <Combobox
              listLabel="المنتجات المطابقة"
              options={itemOptions.filter((option) => !session.lines.some((line) => line.item.id === option.value))}
              value={choice}
              onValueChange={setChoice}
              query={query}
              onQueryChange={(text) => { setQuery(text); onItemQuery(text) }}
              pageSize={{ compact: 6, gaze: 3, gazeShort: 1 }}
              onOpenChange={report}
            />
          </Field>
        </GazeSlot>
      </GazeHost>
    </Screen>
  )
}
