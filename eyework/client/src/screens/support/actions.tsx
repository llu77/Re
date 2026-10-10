/*
 * قرارات التذكرة: اطلب معلومات، صعّد، ارفض المسودة، حُلّت دون ردٍّ مكتوب، غيّر التصنيف، أعد الكتابة
 * ===============================================================================================
 * كل قرارٍ شاشةٌ قصيرة يعود بعدها الموظف إلى التذكرة. الاختيارات في الحجم الكبير منتقٍ (`Picker`): زرٌّ آمن
 * يفتح الخيارات مكانه، فلا يقع خيارٌ تحت نظرٍ وصل من ضغطةٍ قبله؛ وفي الحجم العادي بطاقاتٌ أو قائمة.
 * وما يعتمد («صعّد التذكرة»، «ارفض المسودة»، «حُلّت») في خانة النهاية من شريط الإجراءات، أو في أعلى خطوته
 * الأخيرة حين يصل إليها «التالي».
 */

import * as React from "react"
import { ArrowUpRight, Ban, Check, CheckCircle2, ListChecks, Save, Sparkles } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Field, Input, Textarea } from "@/components/ui/input"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import {
  CATEGORIES, CATEGORY, ESCALATION_TARGET, PRESET, PRIORITIES, PRIORITY, REJECT_REASON, RESOLUTION, type Category, type EscalationTarget,
  type Phrases, type Preset, type Priority, type QuestionCode, type RejectReason, type Resolution, type Ticket,
} from "@/lib/support"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import { GazeHost, GazeSlot, Picker } from "@/screens/inventory/common"

import { usePages, type Fail } from "./common"

function FailAlert({ fail, title }: { fail: Fail; title: string }) {
  return fail ? <Alert tone="danger" title={title} live>{fail.message}</Alert> : null
}

function useRun() {
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const run = React.useCallback(async (action: () => Promise<Fail>) => {
    setBusy(true)
    setFail(null)
    const result = await action()
    setBusy(false)
    setFail(result)
  }, [])
  return { busy, fail, run, setFail }
}

/* ── اطلب معلومات ────────────────────────────────────────────────── */

export function AskInfoScreen({ ticket, phrases, onQuestions, onRedraft, onBack }: {
  ticket: Ticket
  phrases: Phrases | null
  onQuestions: (codes: QuestionCode[]) => Promise<Fail>
  /** «اطلب من سيمبول صياغتها»: مسودة طلب معلومات (بلا انتظار هنا؛ تعود التذكرة وسيمبول يكتب). */
  onRedraft: (() => void) | null
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const english = ticket.language === "EN"
  const questions = phrases?.questions ?? []
  const [chosen, setChosen] = React.useState<QuestionCode[]>([])
  const [step, setStep] = React.useState(0)
  const { busy, fail, run } = useRun()
  const pages = usePages(questions, { compact: 20, gaze: 3, gazeShort: 2 }, "صفحات الأسئلة")

  const toggle = (code: QuestionCode) =>
    setChosen(chosen.includes(code) ? chosen.filter((c) => c !== code) : chosen.length >= 4 ? chosen : [...chosen, code])
  const list = (
    <ul aria-label="الأسئلة" className="flex flex-col gap-tg">
      {pages.slice.map((q) => {
        const on = chosen.includes(q.code)
        return (
          <li key={q.code}>
            <Button id={`ask-q-${q.code}`} isValue aria-pressed={on} width="full" icon={on ? Check : undefined} disabled={!on && chosen.length >= 4}
              onClick={() => toggle(q.code)} className={cn("justify-start text-start font-normal", on && "border-primary-line bg-secondary font-semibold")}>
              <span className="line-clamp-2">{english ? q.en : q.ar}</span>
            </Button>
          </li>
        )
      })}
    </ul>
  )
  const prepare = (
    <Button id="ask-prepare" variant="primary" size="lg" icon={ListChecks} busy={busy} disabled={chosen.length === 0} onClick={() => void run(() => onQuestions(chosen))} className="gaze:w-full">
      جهّز الطلب ({chosen.length})
    </Button>
  )
  const redraft = onRedraft ? (
    <Button id="ask-symbol" variant="secondary" icon={Sparkles} onClick={onRedraft} className="gaze:w-full">
      اطلب من سيمبول صياغتها
    </Button>
  ) : null

  if (gaze) {
    const steps = [{ id: "how", label: "الطريقة" }, { id: "questions", label: "الأسئلة" }, { id: "prepare", label: "الطلب" }]
    return (
      <Screen
        title="اطلب معلومات"
        above={<Stepper steps={steps} current={step} />}
        actions={
          <>
            <Button id="ask-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(step - 1)}>{step === 0 ? "التذكرة" : "السابق"}</Button>
            {step === 1 ? <Button id="ask-next" variant="secondary" iconEnd={NextIcon} disabled={chosen.length === 0} onClick={() => setStep(2)}>التالي</Button> : <span aria-hidden="true" />}
          </>
        }
      >
        {step === 0 ? (
          <>
            {/* «اختر الأسئلة» أوّلاً: في موضعه من الخطوة التالية صفّ الصفحات، لا سؤالٌ يُختار. */}
            <Button id="ask-choose" variant="secondary" icon={ListChecks} onClick={() => setStep(1)} className="w-full">اختر الأسئلة</Button>
            {redraft}
          </>
        ) : null}
        {step === 1 ? (
          <>
            {pages.pager ?? <p className="min-h-ctl text-small text-muted-foreground">اختر حتى أربعة أسئلة.</p>}
            {list}
          </>
        ) : null}
        {step === 2 ? (
          <>
            {prepare}
            <FailAlert fail={fail} title="لم يُجهَّز الطلب" />
            <p className="text-small text-muted-foreground">{chosen.length} من الأسئلة بلغة العميل، بتمهيدٍ وختام.</p>
          </>
        ) : null}
      </Screen>
    )
  }
  return (
    <Screen title="اطلب معلومات" description="اختر حتى أربعة أسئلة؛ يكتبها التطبيق بلغة العميل بتمهيدٍ وختام." back={{ id: "ask-back", label: "التذكرة", onClick: onBack }}
      actions={<><div>{redraft}</div><div className="ms-auto">{prepare}</div></>}>
      <FailAlert fail={fail} title="لم يُجهَّز الطلب" />
      {list}
    </Screen>
  )
}

/* ── صعّد ─────────────────────────────────────────────────────────── */

export function escalationNote(ticket: Ticket): string {
  const last = [...ticket.messages].reverse().find((m) => m.author === "CUSTOMER")
  const problem = last ? [...last.body.replace(/\s+/g, " ")].slice(0, 200).join("") : ""
  return [
    `التذكرة #${ticket.number}${ticket.category ? ` · ${CATEGORY[ticket.category]}` : ""} · أولوية ${PRIORITY[ticket.priority]}`,
    `المشكلة: ${problem}`,
    "ما جُرّب: ",
  ].join("\n")
}

export function EscalateScreen({ ticket, onEscalate, onBack }: {
  ticket: Ticket
  onEscalate: (target: EscalationTarget, note: string, notify: boolean) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const suggested = ticket.draft?.current ? ticket.draft.suggestion.escalate : null
  const [target, setTarget] = React.useState<EscalationTarget | null>(suggested)
  const [note, setNote] = React.useState(() => escalationNote(ticket))
  const [notify, setNotify] = React.useState<"yes" | "no">("no")
  const [step, setStep] = React.useState(0)
  const { busy, fail, run } = useRun()
  const targets = Object.keys(ESCALATION_TARGET) as EscalationTarget[]
  const noteOk = note.trim().length >= 10

  const targetField = gaze ? (
    <GazeHost>
      <Picker id="escalate-target" label="إلى من؟" options={targets.map((t) => ({ value: t, label: ESCALATION_TARGET[t] }))} value={target} onValueChange={(v) => setTarget(v as EscalationTarget)} />
    </GazeHost>
  ) : (
    <RadioCards<EscalationTarget> label="إلى من؟" options={targets.map((t) => ({ value: t, title: ESCALATION_TARGET[t] }))} value={target} onValueChange={setTarget}
      ids={Object.fromEntries(targets.map((t) => [t, `escalate-target-${t}`]))} />
  )
  const noteField = (
    <Field label="ملاحظة التصعيد" hint={gaze ? undefined : "عشرة أحرفٍ على الأقل: المشكلة وما جُرّب."} error={fail?.field === "note" ? fail.message : null}>
      <Textarea id="escalate-note" rows={gaze ? 4 : 5} maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
    </Field>
  )
  const notifyField = (
    <RadioCards<"yes" | "no"> label="أبلغ العميل؟" options={[{ value: "yes", title: "نعم، بردٍّ يفيد بالإحالة" }, { value: "no", title: "لا الآن" }]} value={notify} onValueChange={setNotify}
      columns={1} ids={{ yes: "escalate-notify-yes", no: "escalate-notify-no" }} />
  )
  const submit = (
    <Button id="escalate-submit" variant="primary" size="lg" commit icon={ArrowUpRight} busy={busy} disabled={!target || !noteOk} onClick={() => void run(() => onEscalate(target!, note, notify === "yes"))} className="gaze:w-full">
      صعّد التذكرة
    </Button>
  )
  if (gaze) {
    const steps = [{ id: "target", label: "الجهة" }, { id: "note", label: "الملاحظة" }, { id: "notify", label: "العميل" }, { id: "submit", label: "التصعيد" }]
    const canNext = step === 0 ? target !== null : step === 1 ? noteOk : true
    return (
      <Screen title="صعّد" above={<Stepper steps={steps} current={step} />}
        actions={
          <>
            <Button id="escalate-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(step - 1)}>{step === 0 ? "التذكرة" : "السابق"}</Button>
            {step < 3 ? <Button id="escalate-next" variant="secondary" iconEnd={NextIcon} disabled={!canNext} onClick={() => setStep(step + 1)}>التالي</Button> : <span aria-hidden="true" />}
          </>
        }>
        {step === 0 ? targetField : null}
        {step === 1 ? noteField : null}
        {step === 2 ? notifyField : null}
        {step === 3 ? (
          <>
            {submit}
            <FailAlert fail={fail} title="لم تُصعَّد" />
            <p className="text-small text-muted-foreground">إلى {target ? ESCALATION_TARGET[target] : ""}{notify === "yes" ? "، ويُجهَّز ردٌّ للعميل يفيد بالإحالة." : "."}</p>
          </>
        ) : null}
      </Screen>
    )
  }
  return (
    <Screen title="صعّد" back={{ id: "escalate-back", label: "التذكرة", onClick: onBack }} actions={<div className="ms-auto">{submit}</div>}>
      <FailAlert fail={fail && fail.field !== "note" ? fail : null} title="لم تُصعَّد" />
      {targetField}
      {noteField}
      {notifyField}
    </Screen>
  )
}

/* ── ارفض المسودة ────────────────────────────────────────────────── */

export function RejectScreen({ onReject, onBack }: { onReject: (reason: RejectReason, note: string | null) => Promise<Fail>; onBack: () => void }) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [reason, setReason] = React.useState<RejectReason | null>(null)
  const [note, setNote] = React.useState("")
  const { busy, fail, run } = useRun()
  const reasons = Object.keys(REJECT_REASON) as RejectReason[]
  return (
    <Screen
      title="ارفض المسودة"
      description={gaze ? undefined : "سببك يحسّن المسودات التالية. «معلومةٌ خاطئة» و«المقالة قديمة» تعلّمان المقالة المقتبسة «تحتاج مراجعة»."}
      back={gaze ? undefined : { id: "reject-back", label: "التذكرة", onClick: onBack }}
      actions={
        <>
          {gaze ? <Button id="reject-prev" icon={BackIcon} onClick={onBack}>التذكرة</Button> : null}
          <Button id="reject-submit" variant="danger" commit icon={Ban} busy={busy} disabled={!reason} onClick={() => void run(() => onReject(reason!, note.trim() || null))} className="ms-auto">
            ارفض المسودة
          </Button>
        </>
      }
    >
      <FailAlert fail={fail} title="لم تُرفض" />
      <GazeHost>
        <Picker id="reject-reason" label="لماذا؟" options={reasons.map((r) => ({ value: r, label: REJECT_REASON[r] }))} value={reason} onValueChange={(v) => setReason(v as RejectReason)} />
        {/* حقلٌ في المضيف يُخفى حين يُفتح المنتقي، فلا تقع خياراته فوق حقلٍ ظاهر. */}
        <GazeSlot id="reject-note-field">
          <Field label="ملاحظة" hint={gaze ? undefined : "اختيارية، حتى 200 حرف."}>
            <Input id="reject-note" autoComplete="off" maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
        </GazeSlot>
      </GazeHost>
    </Screen>
  )
}

/* ── حُلّت دون ردٍّ مكتوب ───────────────────────────────────────── */

export function ResolveScreen({ ticket, onResolve, onBack }: {
  ticket: Ticket
  onResolve: (resolution: Resolution, confirmed: boolean) => Promise<{ fail: Fail; unanswered: { message: string; reason: string; confirmable: boolean } | null }>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const options = (Object.keys(RESOLUTION) as Resolution[]).filter((r) => r !== "NO_RESPONSE" || ticket.status === "PENDING")
  const [resolution, setResolution] = React.useState<Resolution | null>(null)
  const [unanswered, setUnanswered] = React.useState<{ message: string; reason: string; confirmable: boolean } | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)

  async function resolve(confirmed: boolean) {
    if (!resolution) return
    setBusy(true)
    setFail(null)
    const result = await onResolve(resolution, confirmed)
    setBusy(false)
    setFail(result.fail)
    setUnanswered(result.unanswered)
  }

  if (unanswered) {
    // «رجوع» في خانة «حُلّت» نفسها، و«أغلقها رغم ذلك» في المحتوى بعد التذكير: النظر الذي ضغط «حُلّت» لا يقع على
    // اعتمادٍ ثانٍ في مكانه.
    return (
      <Screen title="قبل الحلّ"
        actions={
          <>
            <span aria-hidden="true" />
            <Button id="resolve-cancel" icon={BackIcon} onClick={() => setUnanswered(null)} className="ms-auto">رجوع</Button>
          </>
        }>
        <Alert tone="warning" title={unanswered.message}>{unanswered.reason}</Alert>
        {unanswered.confirmable ? (
          <Button id="resolve-confirm" variant="primary" commit icon={CheckCircle2} busy={busy} onClick={() => void resolve(true)} className="gaze:w-full self-start">
            أغلقها رغم ذلك
          </Button>
        ) : <p className="text-small text-muted-foreground">ردّ على العميل أولاً، أو اختر «حُلّت بالهاتف» أو «حُلّت حضورياً».</p>}
        <FailAlert fail={fail} title="لم تُحلّ" />
      </Screen>
    )
  }
  return (
    <Screen
      title="حُلّت دون ردٍّ مكتوب"
      back={gaze ? undefined : { id: "resolve-back", label: "التذكرة", onClick: onBack }}
      actions={
        <>
          {gaze ? <Button id="resolve-prev" icon={BackIcon} onClick={onBack}>التذكرة</Button> : null}
          <Button id="resolve-submit" variant="primary" commit icon={CheckCircle2} busy={busy} disabled={!resolution} onClick={() => void resolve(false)} className="ms-auto">حُلّت</Button>
        </>
      }
    >
      <FailAlert fail={fail} title="لم تُحلّ" />
      {gaze ? (
        <GazeHost>
          <Picker id="resolve-resolution" label="كيف حُلّت؟" options={options.map((r) => ({ value: r, label: RESOLUTION[r] }))} value={resolution} onValueChange={(v) => setResolution(v as Resolution)} />
        </GazeHost>
      ) : (
        <RadioCards<Resolution> label="كيف حُلّت؟" options={options.map((r) => ({ value: r, title: RESOLUTION[r] }))} value={resolution} onValueChange={setResolution}
          ids={Object.fromEntries(options.map((r) => [r, `resolve-${r}`]))} />
      )}
    </Screen>
  )
}

/* ── غيّر التصنيف ─────────────────────────────────────────────────── */

export function ClassifyScreen({ ticket, onSave, onBack }: {
  ticket: Ticket
  onSave: (body: { category: Category | null; priority: Priority; subject: string | null }) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [category, setCategory] = React.useState<Category | null>(ticket.category)
  const [priority, setPriority] = React.useState<Priority>(ticket.priority)
  const [subject, setSubject] = React.useState(ticket.subject ?? "")
  const { busy, fail, run } = useRun()
  return (
    <Screen
      title="التصنيف"
      back={gaze ? undefined : { id: "classify-back", label: "التذكرة", onClick: onBack }}
      actions={
        <>
          {gaze ? <Button id="classify-prev" icon={BackIcon} onClick={onBack}>التذكرة</Button> : null}
          <Button id="classify-save" variant="primary" icon={Save} busy={busy} onClick={() => void run(() => onSave({ category, priority, subject: subject.trim() || null }))} className="ms-auto">احفظ التصنيف</Button>
        </>
      }
    >
      <FailAlert fail={fail && fail.field !== "subject" ? fail : null} title="لم يُحفظ" />
      <GazeHost>
        <Picker id="classify-category" label="الفئة" options={CATEGORIES.map((c) => ({ value: c, label: CATEGORY[c] }))} value={category} onValueChange={(v) => setCategory(v as Category)} />
        <Picker id="classify-priority" label="الأولوية" options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY[p] }))} value={priority} onValueChange={(v) => setPriority(v as Priority)} />
        <GazeSlot id="classify-subject-field">
          <Field label="الموضوع" error={fail?.field === "subject" ? fail.message : null}>
            <Input id="classify-subject" autoComplete="off" maxLength={80} value={subject} onChange={(event) => setSubject(event.target.value)} />
          </Field>
        </GazeSlot>
      </GazeHost>
    </Screen>
  )
}

/* ── أعد الكتابة ─────────────────────────────────────────────────── */

type Style = Exclude<Preset, "ASK_INFO"> | "SAME"

export function RedraftScreen({ left, onRedraft, onBack }: {
  /** ما بقي من مسودات هذه التذكرة اليوم، أو null بلا حدّ معروف. */
  left: number | null
  onRedraft: (presets: Preset[], hint: string | null) => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [style, setStyle] = React.useState<Style>("SAME")
  const [hint, setHint] = React.useState("")
  const styles: Style[] = ["SAME", "SHORTER", "SIMPLER", "MORE_FORMAL", "WARMER"]
  const label = (s: Style) => (s === "SAME" ? "الأسلوب نفسه" : PRESET[s])
  return (
    <Screen
      title="أعد الكتابة"
      description={gaze ? undefined : left === null ? undefined : `بقي لهذه التذكرة اليوم ${left} من المسودات.`}
      back={gaze ? undefined : { id: "redraft-back", label: "التذكرة", onClick: onBack }}
      actions={
        <>
          {gaze ? <Button id="redraft-prev" icon={BackIcon} onClick={onBack}>التذكرة</Button> : null}
          <Button id="redraft-submit" variant="primary" icon={Sparkles} disabled={left === 0} onClick={() => onRedraft(style === "SAME" ? [] : [style], hint.trim() || null)} className="ms-auto">
            اكتب مسودةً جديدة
          </Button>
        </>
      }
    >
      <GazeHost>
        <Field label="ملاحظةٌ لسيمبول" hint={gaze ? undefined : "اختيارية، حتى 200 حرف: ما الذي ينقص المسودة؟"}>
          <Input id="redraft-hint" autoComplete="off" maxLength={200} value={hint} onChange={(event) => setHint(event.target.value)} />
        </Field>
        <Picker id="redraft-style" label="الأسلوب" options={styles.map((s) => ({ value: s, label: label(s) }))} value={style} onValueChange={(v) => setStyle(v as Style)} />
      </GazeHost>
    </Screen>
  )
}
