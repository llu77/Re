/*
 * التذكرة: الرسالة، ومسودة سيمبول، وقرارك
 * =======================================
 * الشاشة نفسها من كل قائمة. سيمبول يقترح ولا يقرّر: المسودة بنوعها واقتباساتها من قاعدة المعرفة («KB-7»
 * واسم المقالة والجملة المقتبسة حرفياً)، وملاحظته للموظف، واقتراح الفئة والأولوية وسببه؛ والقرار بأزرار
 * الموظف وحده: «أرسل كما هي» «عدّل ثم أرسل» «اطلب معلومات» «صعّد» «ارفض المسودة»، وما بعدها في «المزيد».
 * والأزرار يقرّرها الخادم (`allowed`): لا يُعرض ما سيرفضه.
 *
 *   • الحجم العادي: صفحةٌ تمرّ: الردّ الجاهز إن وُجد، ثم الاقتراح، ثم المحادثة، ثم المسودة، ثم القرار.
 *   • الحجم الكبير: صفحاتٌ بالترتيب نفسه، كلٌّ بما يتّسع، و«السابق»/«التالي» في شريط الإجراءات.
 */

import * as React from "react"
import {
  ArrowUpRight, Ban, CheckCircle2, ChevronDown, ChevronUp, CircleHelp, FilePlus2, MessageSquarePlus, NotebookPen,
  PencilLine, RefreshCw, RotateCcw, Send, Sparkles, StickyNote, Undo2,
} from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { PagedText } from "@/components/ui/paged-text"
import { useToast } from "@/components/ui/toast"
import { formatDay, formatTime } from "@/lib/format"
import {
  AUTHOR, CATEGORY, CHANNEL, ESCALATION_TARGET, PRIORITY, REJECT_REASON, REPLY_KIND, ticketTitle, type DismissReason, type Message, type RuleFlag,
  type Ticket,
} from "@/lib/support"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

import { MaskedText, PriorityBadge, SlaBadge, StatusBadge, type Fail } from "./common"
import { RuleFlagCard } from "./reply"

export type TicketAction =
  | "compose-draft" | "compose-blank" | "ask" | "escalate" | "reject" | "resolve" | "customer" | "note" | "classify" | "redraft"
  | "reply" | "follow-up"

export interface TicketScreenProps {
  ticket: Ticket
  /** سيمبول يكتب المسودة الآن. */
  drafting: boolean
  /** رسالة الخادم حين لم تُكتب المسودة. */
  draftFail: string | null
  onRequestDraft: () => void
  onSendAsIs: () => Promise<Fail>
  onAcceptSuggestion: () => Promise<Fail>
  onReopen: () => Promise<Fail>
  onReturnEscalation: () => Promise<Fail>
  /** تنبيه قاعدةٍ على التذكرة (أولويةٌ أدنى من المقترحة): «تابع رغم ذلك» بسببه. */
  onAckRule: (flag: RuleFlag, action: "HEEDED" | "DISMISSED", reason: DismissReason | null) => Promise<Fail>
  onAction: (action: TicketAction) => void
  onBack: () => void
  backLabel: string
}

/** آخر رسالةٍ من العميل، وما قبلها. */
function splitThread(messages: Message[]): { last: Message | null; earlier: Message[] } {
  const index = messages.map((m) => m.author).lastIndexOf("CUSTOMER")
  if (index < 0) return { last: null, earlier: messages }
  return { last: messages[index], earlier: messages.filter((_, i) => i !== index) }
}

function when(iso: string | null): string {
  return iso ? `${formatDay(iso)} ${formatTime(iso)}` : ""
}

function suggestionPending(ticket: Ticket): boolean {
  const draft = ticket.draft
  if (!draft || !draft.current) return false
  const s = draft.suggestion
  if (ticket.status === "RESOLVED" || ticket.status === "CLOSED") return false
  // الموضوع الذي يقترحه سيمبول حين تُركت التذكرة بلا موضوع (كما يعد حقل التذكرة الجديدة).
  if (!ticket.subject && draft.subject) return true
  if (!s.priority && !s.category) return false
  return (s.priority !== null && s.priority !== ticket.priority) || (s.category !== null && s.category !== ticket.category)
}

/** قرارات الحجم الكبير في كل صفحة. */
const DECISIONS_PER_PAGE = 4

export function TicketScreen(props: TicketScreenProps) {
  const { ticket, drafting, draftFail, onRequestDraft, onSendAsIs, onAcceptSuggestion, onReopen, onReturnEscalation, onAction, onBack, backLabel } = props
  const { size } = useSize()
  const gaze = size === "gaze"
  const [fail, setFail] = React.useState<Fail>(null)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [showEarlier, setShowEarlier] = React.useState(false)
  const [page, setPage] = React.useState(0)
  const allowed = ticket.allowed
  const draft = ticket.draft
  const current = draft?.current ? draft : null
  const { last, earlier } = splitThread(ticket.messages)
  const pending = suggestionPending(ticket)
  // حين تتغيّر حال التذكرة تتغيّر صفحاتها: يُبدأ من أوّلها لا من رقم صفحةٍ صارت غيرها.
  React.useEffect(() => {
    setPage(0)
  }, [ticket.status])
  // رسالة القرار السابق («رُفضت المسودة») تُغلق حين تُقلَّب صفحات الحجم الكبير: لا تبقى فوق أعلى الصفحة التالية.
  const toast = useToast()
  const firstPage = React.useRef(true)
  React.useEffect(() => {
    if (firstPage.current) {
      firstPage.current = false
      return
    }
    if (gaze) {
      toast.dismiss()
      setFail(null)
    }
  }, [page, gaze, toast])

  async function run(id: string, action: () => Promise<Fail>) {
    setBusy(id)
    setFail(null)
    const result = await action()
    setBusy(null)
    if (result) setFail(result)
  }

  const failAlert = fail ? <Alert tone="danger" title="لم يتمّ" live>{fail.message}</Alert> : null

  /* ── الأجزاء ── */
  const live = ticket.live_reply ? (
    <section aria-label="الردّ" className="flex flex-col gap-tg rounded-card border border-primary-line bg-secondary p-pad">
      <p className="font-semibold">{ticket.live_reply.state === "RELEASED" ? "نسختَ الردّ ولم تؤكّد إرساله." : "ردٌّ جاهز لم يُنسخ بعد."}</p>
      <Button id="ticket-open-reply" variant="primary" icon={Send} onClick={() => onAction("reply")} className="self-start gaze:w-full">
        {ticket.live_reply.state === "RELEASED" ? "أكّد الإرسال" : "افتح الردّ"}
      </Button>
    </section>
  ) : null

  const suggestion = pending && current ? (
    <section aria-label="اقتراح سيمبول" className="flex flex-col gap-tg rounded-card border border-ai/30 bg-ai-tint p-pad">
      <p className="flex items-center gap-2 text-small font-bold"><Sparkles aria-hidden="true" className="size-4" />اقتراح سيمبول</p>
      <p className="text-flow">
        {current.suggestion.category ? `الفئة: ${CATEGORY[current.suggestion.category]}` : null}
        {current.suggestion.category && current.suggestion.priority ? " · " : null}
        {current.suggestion.priority ? `الأولوية: ${PRIORITY[current.suggestion.priority]}` : null}
      </p>
      {!ticket.subject && current.subject ? <p className="text-flow">الموضوع: {current.subject}</p> : null}
      {current.suggestion.because ? <p className="text-small text-muted-foreground gaze:short:hidden">{current.suggestion.because}</p> : null}
      <div className="flex flex-wrap gap-tg gaze:flex-col">
        <Button id="ticket-accept-suggestion" variant="secondary" icon={CheckCircle2} busy={busy === "accept"} onClick={() => void run("accept", onAcceptSuggestion)}>
          اعتمد المقترح
        </Button>
        <Button id="ticket-classify" icon={PencilLine} onClick={() => onAction("classify")}>
          غيّر التصنيف
        </Button>
      </div>
    </section>
  ) : null

  const ticketFlags = ticket.flags.filter((f) => f.state === "OPEN")
  // «عدّل» على تنبيه الأولوية يفتح التصنيف؛ و«تابع رغم ذلك» يقرّه بسببه فلا يبقى مفتوحاً على التذكرة.
  const flagNotes = ticketFlags.length ? (
    <div className="flex flex-col gap-tg">
      {ticketFlags.map((f) => <RuleFlagCard key={f.id} flag={f} gaze={gaze} onAck={(action, reason) => props.onAckRule(f, action, reason)} onEdit={() => onAction("classify")} />)}
    </div>
  ) : null

  const escalation = ticket.status === "ESCALATED" && ticket.escalation ? (
    <section aria-label="التصعيد" className="flex flex-col gap-1 rounded-card border border-warning-line bg-warning-tint p-pad">
      <p className="font-semibold">صُعّدت إلى {ESCALATION_TARGET[ticket.escalation.target]}</p>
      <p className="text-small text-muted-foreground gaze:line-clamp-3">{ticket.escalation.note}</p>
    </section>
  ) : null

  const lastMessage = ticket.texts_purged ? (
    <p className="text-flow text-muted-foreground">حُذفت نصوص هذه التذكرة بعد إغلاقها.</p>
  ) : last ? (
    <article aria-label="رسالة العميل" className="flex flex-col gap-1">
      <p className="text-small font-semibold text-muted-foreground">
        العميل{ticket.customer_label ? ` (${ticket.customer_label})` : ""} · {CHANNEL[ticket.channel]} · {when(last.at)}
      </p>
      {gaze ? <PagedText text={last.body} label="رسالة العميل" perPage={{ gaze: 260, gazeShort: 130 }} /> : <MaskedText text={last.body} />}
    </article>
  ) : (
    <p className="text-flow text-muted-foreground">لا رسالة من العميل.</p>
  )

  const thread = gaze ? lastMessage : (
    <section aria-label="المحادثة" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
      {earlier.length ? (
        <Button id="ticket-earlier" icon={showEarlier ? ChevronUp : ChevronDown} onClick={() => setShowEarlier(!showEarlier)} className="self-start">
          {showEarlier ? "أخفِ الرسائل السابقة" : `رسائل سابقة (${earlier.length})`}
        </Button>
      ) : null}
      {showEarlier
        ? earlier.map((m) => (
            <article key={m.id} className={cn("flex flex-col gap-1 border-s ps-3", m.author === "NOTE" ? "border-warning-line" : m.author === "AGENT" ? "border-primary-line" : "border-border")}>
              <p className="text-small font-semibold text-muted-foreground">{AUTHOR[m.author]} · {when(m.at)}</p>
              <MaskedText text={m.body} />
            </article>
          ))
        : null}
      {lastMessage}
    </section>
  )

  let draftBlock: React.ReactNode = null
  if (drafting) {
    draftBlock = <p id="ticket-drafting" role="status" className="flex items-center gap-2 font-semibold text-muted-foreground"><Sparkles aria-hidden="true" className="size-icon" />سيمبول يكتب المسودة…</p>
  } else if (current) {
    const notice =
      current.result === "CANNOT_ANSWER" ? `لم أجد في قاعدة المعرفة ما يجيب${current.note_to_employee ? `: ${current.note_to_employee}` : "."}`
        : current.result === "NOT_SUPPORT" ? `ليست طلب دعم${current.note_to_employee ? `: ${current.note_to_employee}` : "."}`
        : null
    draftBlock = (
      <section id="ticket-draft" aria-label="مسودة سيمبول" className="flex flex-col gap-tg rounded-card border border-border bg-card p-pad">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="ai" icon={Sparkles}>مسودة سيمبول</Badge>
          {current.reply_kind ? <Badge tone="neutral">{REPLY_KIND[current.reply_kind]}</Badge> : null}
        </div>
        {notice ? <Alert tone="warning" title={notice} /> : null}
        {current.body ? (gaze ? <PagedText text={current.body} label="المسودة" perPage={{ gaze: 240, gazeShort: 120 }} /> : <p className="text-flow whitespace-pre-line">{current.body}</p>) : null}
        {current.citations.length ? (
          <ul aria-label="من قاعدة المعرفة" className="flex flex-col gap-2">
            {current.citations.map((c) => (
              <li key={`${c.article_id}-${c.quote}`} className="flex flex-col gap-0.5 text-small">
                <span className="font-semibold">KB-{c.number} · {c.title}</span>
                <q className="text-muted-foreground gaze:hidden">{c.quote}</q>
              </li>
            ))}
          </ul>
        ) : null}
        {current.result === "DRAFT" && current.note_to_employee ? <p className="text-small text-muted-foreground gaze:hidden">{current.note_to_employee}</p> : null}
        {current.suggestion.escalate ? <p className="text-small font-semibold text-warning">يقترح التصعيد إلى: {ESCALATION_TARGET[current.suggestion.escalate]}</p> : null}
      </section>
    )
  } else if (draft?.rejected) {
    draftBlock = <p className="text-flow text-muted-foreground">رفضتَ المسودة: {REJECT_REASON[draft.rejected.reason]}.</p>
  }
  const draftAlert = draftFail && !drafting ? <Alert tone="warning" title="لم تُكتب المسودة" live>{draftFail}</Alert> : null
  const askDraft = !drafting && allowed.draft && !current ? (
    <Button id="ticket-request-draft" variant="secondary" icon={Sparkles} onClick={onRequestDraft} className="self-start gaze:w-full">
      {draft ? "اطلب مسودةً جديدة" : "اطلب مسودة من سيمبول"}
    </Button>
  ) : null

  const main: React.ReactNode[] = []
  if (allowed.send_as_is) {
    main.push(<Button key="send" id="decide-send" variant="primary" icon={Send} busy={busy === "send"} onClick={() => void run("send", onSendAsIs)}>أرسل كما هي</Button>)
  }
  if (allowed.edit) main.push(<Button key="edit" id="decide-edit" variant="secondary" icon={PencilLine} onClick={() => onAction("compose-draft")}>عدّل ثم أرسل</Button>)
  if (allowed.ask_info) main.push(<Button key="ask" id="decide-ask" icon={CircleHelp} onClick={() => onAction("ask")}>اطلب معلومات</Button>)
  if (allowed.escalate) main.push(<Button key="escalate" id="decide-escalate" icon={ArrowUpRight} onClick={() => onAction("escalate")}>صعّد</Button>)
  if (allowed.reject) main.push(<Button key="reject" id="decide-reject" icon={Ban} onClick={() => onAction("reject")}>ارفض المسودة</Button>)
  if (allowed.return_escalation) {
    main.push(<Button key="returned" id="decide-returned" variant="secondary" icon={Undo2} busy={busy === "returned"} onClick={() => void run("returned", onReturnEscalation)}>عاد الجواب من التصعيد</Button>)
  }
  if (allowed.reopen) main.push(<Button key="reopen" id="decide-reopen" icon={RotateCcw} busy={busy === "reopen"} onClick={() => void run("reopen", onReopen)}>أعد فتح التذكرة</Button>)
  if (allowed.follow_up) main.push(<Button key="follow" id="decide-follow-up" variant="secondary" icon={FilePlus2} onClick={() => onAction("follow-up")}>افتح تذكرة متابعة</Button>)

  const more: React.ReactNode[] = []
  if (allowed.write) more.push(<Button key="write" id="decide-write" icon={NotebookPen} onClick={() => onAction("compose-blank")}>اكتب الردّ بنفسك</Button>)
  if (allowed.draft && current) more.push(<Button key="redraft" id="decide-redraft" icon={RefreshCw} onClick={() => onAction("redraft")}>أعد الكتابة</Button>)
  if (allowed.note) {
    more.push(<Button key="customer" id="decide-customer" icon={MessageSquarePlus} onClick={() => onAction("customer")}>أضف ردّ العميل</Button>)
    more.push(<Button key="note" id="decide-note" icon={StickyNote} onClick={() => onAction("note")}>ملاحظة داخلية</Button>)
  }
  if (allowed.resolve) more.push(<Button key="resolve" id="decide-resolve" icon={CheckCircle2} onClick={() => onAction("resolve")}>حُلّت دون ردٍّ مكتوب</Button>)

  const header = (
    <div className="flex flex-wrap items-center gap-2">
      <StatusBadge status={ticket.status} />
      <PriorityBadge priority={ticket.priority} className="gaze:hidden" />
      <SlaBadge row={ticket} />
      {ticket.category ? <Badge tone="neutral" className="gaze:hidden">{CATEGORY[ticket.category]}</Badge> : null}
    </div>
  )

  /* ── الحجم الكبير: صفحةٌ لكل جزء ── */
  if (gaze) {
    type Page = { id: string; label: string; body: React.ReactNode }
    const pages: Page[] = []
    if (live) pages.push({ id: "reply", label: "الردّ", body: live })
    if (suggestion) pages.push({ id: "suggestion", label: "الاقتراح", body: suggestion })
    if (flagNotes) pages.push({ id: "flags", label: "تنبيه", body: flagNotes })
    if (escalation) pages.push({ id: "escalation", label: "التصعيد", body: escalation })
    pages.push({ id: "message", label: "الرسالة", body: lastMessage })
    // ما قبل آخر رسالة: رسائل العميل السابقة، وردودك المرسلة، وملاحظاتك الداخلية — نصّاً مقسّماً صفحات.
    if (earlier.length && !ticket.texts_purged) {
      const text = earlier.map((m) => `${AUTHOR[m.author]} · ${when(m.at)}\n${m.body}`).join("\n\n")
      pages.push({ id: "thread", label: "المحادثة", body: <PagedText text={text} label="المحادثة" perPage={{ gaze: 240, gazeShort: 120 }} /> })
    }
    if (drafting || current || draftAlert || askDraft || draftBlock) pages.push({ id: "draft", label: "المسودة", body: <>{draftAlert}{draftBlock}{askDraft}</> })
    // القرارات أربعةً في كل صفحة (ومعها تنبيه الخطأ إن وُجد): ستّةٌ في صفحةٍ لا تتّسع لها أقصر الهواتف حين يلتفّ
    // سطر الشارات أو يظهر التنبيه. والتالية «المزيد» بزرّ «التالي» في الشريط.
    const decisions = [...main, ...more]
    for (let start = 0; start < decisions.length; start += DECISIONS_PER_PAGE) {
      pages.push({
        id: `decide-${start}`, label: start === 0 ? "قرارك" : "المزيد",
        body: <div className="flex flex-col gap-tg [&>button]:w-full">{decisions.slice(start, start + DECISIONS_PER_PAGE)}</div>,
      })
    }
    const index = Math.min(page, pages.length - 1)
    const at = pages[index]
    return (
      <Screen
        title={`التذكرة #${ticket.number}`}
        description={<span className="block truncate">{ticket.subject ?? ""}</span>}
        above={<div className="flex items-center justify-between gap-tg">{header}<span className="text-small font-semibold text-muted-foreground">{at.label} · {index + 1} من {pages.length}</span></div>}
        actions={
          <>
            <Button id="ticket-prev" icon={BackIcon} onClick={index === 0 ? onBack : () => setPage(index - 1)}>
              {index === 0 ? backLabel : "السابق"}
            </Button>
            {index < pages.length - 1 ? (
              <Button id="ticket-next" variant="secondary" iconEnd={NextIcon} onClick={() => setPage(index + 1)}>
                {pages[index + 1].label}
              </Button>
            ) : <span aria-hidden="true" />}
          </>
        }
      >
        {/* ما لم يتمّ يُقال في الصفحة التي ضُغط فيها (الاقتراح أو القرارات)، ويُغلق حين تُقلَّب. */}
        {failAlert}
        {at.body}
      </Screen>
    )
  }

  /* ── الحجم العادي: صفحةٌ تمرّ ── */
  return (
    <Screen
      title={ticketTitle(ticket)}
      above={header}
      back={{ id: "ticket-back", label: backLabel, onClick: onBack }}
    >
      {failAlert}
      {live}
      {suggestion}
      {flagNotes}
      {escalation}
      {thread}
      {draftAlert}
      {draftBlock}
      {askDraft}
      {main.length || more.length ? (
        <section aria-label="قرارك" className="flex flex-col gap-tg">
          <h2 className="text-lead font-semibold">قرارك</h2>
          {main.length ? <div className="flex flex-wrap gap-tg">{main}</div> : null}
          {more.length ? <div className="flex flex-wrap gap-tg">{more}</div> : null}
        </section>
      ) : null}
    </Screen>
  )
}
