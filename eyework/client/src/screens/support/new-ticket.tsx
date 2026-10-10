/*
 * تذكرة جديدة: من أين، ثم رسالة العميل، ثم ما سيُحفظ
 * =================================================
 * الموظف يلصق رسالة العميل («الصق من الحافظة» داخل الضغطة) أو يكتبها، ثم يرى ما سيُحفظ بعد الحذف
 * (/api/support/mask-preview: البريد والروابط والأرقام الطويلة شاراتٍ، وسطر «حُذف: …»)، ثم يحفظ. الاسم
 * للتحية والموضوع والأولوية اختيارية؛ والاسم لا يصل سيمبول أبداً.
 *
 *   • الحجم العادي: صفحتان: الرسالة، ثم ما سيُحفظ وتفاصيله و«احفظ التذكرة».
 *   • الحجم الكبير: خمس خطوات (القناة، الرسالة، المعاينة، التفاصيل، الحفظ)؛ و«احفظ التذكرة» في أعلى
 *     الخطوة الأخيرة، لا في موضع «التالي».
 */

import * as React from "react"
import { ClipboardPaste, Eye, Save } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Field, Input, Textarea } from "@/components/ui/input"
import { PagedText } from "@/components/ui/paged-text"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { CHANNEL, CHANNELS, PRIORITY, PRIORITIES, type Channel, type MaskPreview, type Priority } from "@/lib/support"
import { useSize } from "@/lib/size"
import { GazeHost, GazeSlot, Picker } from "@/screens/inventory/common"

import { MaskedText, maskedSummary, readClipboard, type Fail } from "./common"

export interface NewTicketBody {
  channel: Channel
  text: string
  customer_label: string | null
  subject: string | null
  priority: Priority
}

const STEPS = [
  { id: "channel", label: "القناة" },
  { id: "message", label: "الرسالة" },
  { id: "preview", label: "ما سيُحفظ" },
  { id: "details", label: "التفاصيل" },
  { id: "save", label: "الحفظ" },
]
const TEXT_MAX = 4000

export function NewTicketScreen({ onPreview, onSave, onBack, title = "تذكرة جديدة", channelFixed = null, saveLabel = "احفظ التذكرة" }: {
  onPreview: (text: string) => Promise<{ preview: MaskPreview | null; fail: Fail }>
  onSave: (body: NewTicketBody) => Promise<Fail>
  onBack: () => void
  /** «ردّ العميل» و«ملاحظة داخلية» و«تذكرة متابعة» تستعمل الشاشة نفسها بلا قناةٍ ولا تفاصيل. */
  title?: string
  channelFixed?: Channel | null
  saveLabel?: string
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const simple = channelFixed !== null
  const [step, setStep] = React.useState(simple ? 1 : 0)
  const [channel, setChannel] = React.useState<Channel | null>(channelFixed)
  const [text, setText] = React.useState("")
  const [preview, setPreview] = React.useState<MaskPreview | null>(null)
  const [label, setLabel] = React.useState("")
  const [subject, setSubject] = React.useState("")
  const [priority, setPriority] = React.useState<Priority>("NORMAL")
  const [fail, setFail] = React.useState<Fail>(null)
  const [busy, setBusy] = React.useState(false)
  const [pasteFailed, setPasteFailed] = React.useState(false)
  const spoken = channel === "PHONE" || channel === "IN_PERSON"

  async function paste() {
    const pasted = await readClipboard()
    setPasteFailed(pasted === null)
    if (pasted) {
      setText(pasted)
      setPreview(null)
    }
  }

  async function review(): Promise<boolean> {
    setBusy(true)
    setFail(null)
    const result = await onPreview(text)
    setBusy(false)
    setFail(result.fail)
    setPreview(result.preview)
    return result.preview !== null
  }

  async function save() {
    if (!channel || !preview) return
    setBusy(true)
    setFail(null)
    const result = await onSave({ channel, text, customer_label: label.trim() || null, subject: subject.trim() || null, priority })
    setBusy(false)
    if (result) setFail(result)
  }

  const failAlert = fail ? <Alert tone="danger" title="لم يُحفظ" live>{fail.message}</Alert> : null
  // في الحجم الكبير منتقٍ: زرٌّ آمنٌ في أعلى الخطوة، لا خيارٌ تحت نظرٍ وصل من زرّ الرئيسية.
  const channelField = gaze ? (
    <GazeHost>
      <Picker id="ticket-channel" label="من أين وصلت الرسالة؟" options={CHANNELS.map((code) => ({ value: code, label: CHANNEL[code] }))} value={channel} onValueChange={(value) => setChannel(value as Channel)} />
    </GazeHost>
  ) : (
    <RadioCards<Channel>
      label="من أين وصلت الرسالة؟"
      options={CHANNELS.map((code) => ({ value: code, title: CHANNEL[code] }))}
      value={channel}
      onValueChange={(value) => setChannel(value)}
      ids={Object.fromEntries(CHANNELS.map((code) => [code, `ticket-channel-${code}`]))}
    />
  )
  const messageField = (
    <div className="flex flex-col gap-tg">
      <Button id="ticket-paste" icon={ClipboardPaste} onClick={() => void paste()} className="self-start gaze:w-full">
        الصق من الحافظة
      </Button>
      {pasteFailed ? <p role="status" className="text-small font-semibold text-warning">لم يُقرأ شيءٌ من الحافظة. الصق في الحقل أو اكتب.</p> : null}
      <Field
        label={spoken ? "ما قاله العميل" : simple ? "النصّ" : "رسالة العميل"}
        hint={gaze ? `${[...text].length} من ${TEXT_MAX}` : `الصق ما يلزم لحلّ المشكلة وحده. يُحذف البريد والروابط والأرقام الطويلة قبل الحفظ. ${[...text].length} من ${TEXT_MAX}`}
        error={fail?.field === "text" ? fail.message : null}
      >
        <Textarea
          id="ticket-text"
          rows={gaze ? 3 : 6}
          maxLength={6000}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setPreview(null)
          }}
        />
      </Field>
    </div>
  )
  const previewBlock = preview ? (
    <section aria-label="ما سيُحفظ" className="flex flex-col gap-2 rounded-card border border-border bg-card p-pad">
      {gaze ? <PagedText text={preview.text} label="ما سيُحفظ" perPage={{ gaze: 220, gazeShort: 110 }} /> : <MaskedText text={preview.text} />}
      <p id="ticket-masked" className="text-small font-semibold text-muted-foreground">{maskedSummary(preview.masked) ?? "لم يُحذف شيء."}</p>
    </section>
  ) : null
  const detailFields = (
    <>
      <Field label="اسم العميل للتحية" hint={gaze ? undefined : "اختياري. لا يُرسل إلى سيمبول."} error={fail?.field === "customer_label" ? fail.message : null}>
        <Input id="ticket-label" autoComplete="off" maxLength={30} value={label} onChange={(event) => setLabel(event.target.value)} />
      </Field>
      <Field label="الموضوع" hint={gaze ? undefined : "اختياري؛ يقترحه سيمبول إن تركته."} error={fail?.field === "subject" ? fail.message : null}>
        <Input id="ticket-subject" autoComplete="off" maxLength={80} value={subject} onChange={(event) => setSubject(event.target.value)} />
      </Field>
      <RadioCards<Priority>
        label="الأولوية"
        options={PRIORITIES.map((code) => ({ value: code, title: PRIORITY[code] }))}
        value={priority}
        onValueChange={setPriority}
        ids={Object.fromEntries(PRIORITIES.map((code) => [code, `ticket-priority-${code}`]))}
      />
    </>
  )
  // الحجم الكبير: الحقلان في خطوة التفاصيل، والأولوية منتقٍ في خطوة الحفظ يفتح خياراته مكان «احفظ» (بطاقاتها
  // الأربع مع حقلين لا تتّسع لها الشاشة، ولا المنتقي معهما في 320×635).
  const gazeDetailFields = (
    <>
      <Field label="اسم العميل للتحية" error={fail?.field === "customer_label" ? fail.message : null}>
        <Input id="ticket-label" autoComplete="off" maxLength={30} value={label} onChange={(event) => setLabel(event.target.value)} />
      </Field>
      <Field label="الموضوع" error={fail?.field === "subject" ? fail.message : null}>
        <Input id="ticket-subject" autoComplete="off" maxLength={80} value={subject} onChange={(event) => setSubject(event.target.value)} />
      </Field>
    </>
  )
  const gazePriority = (
    <Picker id="ticket-priority" label="الأولوية" options={PRIORITIES.map((code) => ({ value: code, label: PRIORITY[code] }))} value={priority} onValueChange={(v) => setPriority(v as Priority)} />
  )
  const saveButton = (
    <Button id="ticket-save" variant="primary" size="lg" commit icon={Save} busy={busy} disabled={!preview || !channel} onClick={() => void save()} className="gaze:w-full">
      {saveLabel}
    </Button>
  )

  /* ── الحجم الكبير: خطوةٌ في كل شاشة ── */
  if (gaze) {
    const steps = simple ? STEPS.filter((s) => s.id === "message" || s.id === "preview" || s.id === "save") : STEPS
    const index = steps.findIndex((s) => s.id === STEPS[step].id)
    const prev = () => {
      setFail(null)
      if (step === (simple ? 1 : 0)) onBack()
      else setStep(simple && step === 4 ? 2 : step - 1)
    }
    const next = async () => {
      if (step === 1 && !(await review())) return
      setStep(simple && step === 2 ? 4 : step + 1)
    }
    const canNext = step === 0 ? channel !== null : step === 1 ? text.trim().length > 0 : true
    const actions = (
      <>
        <Button id="ticket-prev" icon={BackIcon} onClick={prev}>
          {step === (simple ? 1 : 0) ? "رجوع" : "السابق"}
        </Button>
        {step === 4 ? <span aria-hidden="true" /> : (
          <Button id="ticket-next" variant="secondary" iconEnd={NextIcon} busy={busy && step === 1} disabled={!canNext} onClick={() => void next()}>
            {step === 1 ? "راجع ما سيُحفظ" : "التالي"}
          </Button>
        )}
      </>
    )
    return (
      <Screen title={title} above={<Stepper steps={steps} current={index} />} actions={actions}>
        {step === 0 ? channelField : null}
        {step === 1 ? (
          <>
            {messageField}
            {fail && fail.field !== "text" ? failAlert : null}
          </>
        ) : null}
        {step === 2 ? previewBlock : null}
        {step === 3 ? gazeDetailFields : null}
        {step === 4 ? (
          <GazeHost>
            {simple ? null : <GazeSlot id="ticket-priority">{gazePriority}</GazeSlot>}
            <GazeSlot id="ticket-save-slot" field={false} className="flex flex-col gap-tg">
              {saveButton}
              {failAlert}
              <p className="text-small text-muted-foreground">
                {simple ? maskedSummary(preview?.masked ?? { email: 0, link: 0, number: 0 }) ?? "لم يُحذف شيء." : `${channel ? CHANNEL[channel] : ""}${label.trim() ? ` · ${label.trim()}` : ""}`}
              </p>
            </GazeSlot>
          </GazeHost>
        ) : null}
      </Screen>
    )
  }

  /* ── الحجم العادي: الرسالة، ثم ما سيُحفظ ── */
  if (!preview) {
    return (
      <Screen
        title={title}
        back={{ id: "ticket-back", label: "رجوع", onClick: onBack }}
        actions={
          <Button id="ticket-review" variant="secondary" icon={Eye} busy={busy} disabled={!text.trim() || !channel} onClick={() => void review()} className="ms-auto">
            راجع ما سيُحفظ
          </Button>
        }
      >
        {simple ? null : channelField}
        {messageField}
        {fail && fail.field !== "text" ? failAlert : null}
      </Screen>
    )
  }
  return (
    <Screen
      title={title}
      description="هذا ما سيُحفظ. ما حُذف لا يُحفظ ولا يُرسل."
      back={{ id: "ticket-edit", label: "عدّل الرسالة", onClick: () => setPreview(null) }}
      actions={<div className="ms-auto">{saveButton}</div>}
    >
      {failAlert}
      {previewBlock}
      {simple ? null : detailFields}
    </Screen>
  )
}
