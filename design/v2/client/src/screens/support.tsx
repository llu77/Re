/*
 * الدعم الفني: الوارد والتذكرة
 * ===========================
 * الموظف «الإنسان في الحلقة»: سيمبول يقرأ رسالة العميل ويكتب مسودة ردٍّ مستنداً إلى الردود
 * الجاهزة المعتمدة، ولا يرسل شيئاً. الموظف يبدأ يومه بـ«ابدأ بالتذكرة التالية» (الأقدم أولاً)،
 * ويقرّر لكل تذكرة واحداً من خمسة:
 *
 *   أرسل المسودة كما هي   (يعتمد: يصل العميل)
 *   عدّل ثم أرسل           (يفتح المسودة للتحرير؛ والإرسال بعده)
 *   اكتب ردّك بنفسك        (محرّرٌ فارغ)
 *   صعّد إلى مختص          (يسأل عن السبب أولاً)
 *   أغلق دون ردّ           (يسأل تأكيداً)
 *
 * والمسودة تقول لماذا كُتبت كما كُتبت، ومن أيّ ردٍّ جاهز، وما يجب أن يتحقّق منه الموظف
 * قبل الإرسال. وفي الحجم الكبير خطوتان: الرسالة، ثم المسودة والقرار.
 */

import * as React from "react"
import {
  ArrowUpCircle, BookOpenCheck, Globe, Inbox, Mail, MessageCircle, PencilLine, Send, SquarePen, XCircle,
} from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { Screen } from "@/components/shell/screen"
import { Badge } from "@/components/ui/badge"
import { Button, BackIcon, NextIcon } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Textarea } from "@/components/ui/input"
import { Tabs } from "@/components/ui/tabs"
import { formatAgo } from "@/lib/format"
import { useShortScreen, useSize } from "@/lib/size"
import type { TicketDraft, TicketMessage, TicketRow } from "@/lib/work-types"

const CHANNEL = {
  EMAIL: { label: "بريد", icon: Mail },
  WHATSAPP: { label: "واتساب", icon: MessageCircle },
  WEB: { label: "الموقع", icon: Globe },
} as const

const STATUS: Record<TicketRow["status"], { label: string; tone: "ai" | "info" | "neutral" | "warning" | "success" }> = {
  NEW: { label: "جديدة", tone: "info" },
  DRAFT_READY: { label: "مسودة جاهزة", tone: "ai" },
  WAITING_CUSTOMER: { label: "بانتظار العميل", tone: "neutral" },
  ESCALATED: { label: "مصعّدة", tone: "warning" },
  CLOSED: { label: "مغلقة", tone: "success" },
}

/* ── الوارد ──────────────────────────────────────────────────────── */

export interface SupportQueueProps {
  tab: string
  tabs: { id: string; label: string; count: number }[]
  onTabChange: (id: string) => void
  tickets: TicketRow[]
  now: string
  onNext: () => void
  onOpen: (ticket: TicketRow) => void
}

export function SupportQueue({ tab, tabs, onTabChange, tickets, now, onNext, onOpen }: SupportQueueProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const next = (
    <Button variant="primary" size="lg" icon={Inbox} iconEnd={NextIcon} onClick={onNext}>
      ابدأ بالتذكرة التالية
    </Button>
  )
  return (
    <Screen
      title="التذاكر المفتوحة"
      quietTitle
      description={gaze ? undefined : "سيمبول كتب مسودةً لكل رسالة، ولا يصل العميلَ شيءٌ قبل قرارك."}
      aside={gaze ? undefined : next}
      actions={gaze ? next : undefined}
    >
      <Tabs label="حالة التذكرة" items={tabs} value={tab} onValueChange={onTabChange}>
        <DataTable<TicketRow>
          caption="التذاكر"
          rows={tickets}
          rowKey={(t) => t.id}
          columns={[
            { id: "number", header: "الرقم", cell: (t) => <span className="num">#{t.number}</span> },
            { id: "subject", header: "الموضوع", cell: (t) => t.subject },
            { id: "customer", header: "العميل", cell: (t) => t.customer },
            {
              id: "channel",
              header: "القناة",
              cell: (t) => (
                <Badge icon={CHANNEL[t.channel].icon}>{CHANNEL[t.channel].label}</Badge>
              ),
            },
            { id: "received", header: "وصلت", cell: (t) => formatAgo(t.received, now) },
            {
              id: "status",
              header: "الحالة",
              cell: (t) => (
                <span className="flex flex-wrap gap-1">
                  <Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge>
                  {t.priority === "HIGH" ? <Badge tone="danger">عاجلة</Badge> : null}
                </span>
              ),
            },
          ]}
          primary={(t) => t.subject}
          secondary={(t) => `#${t.number} · ${t.customer} · ${CHANNEL[t.channel].label} · ${formatAgo(t.received, now)}`}
          trailing={(t) => (
            <>
              {/* في الكبير الحالة في زرّ التصفية فوق القائمة: لا تُكرَّر في كل صفّ. */}
              {gaze ? null : <Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge>}
              {t.priority === "HIGH" ? <Badge tone="danger">عاجلة</Badge> : null}
            </>
          )}
          onOpen={onOpen}
          openLabel={(t) => `افتح التذكرة ${t.number}: ${t.subject}`}
          pageSize={{ compact: 10, gaze: 3 }}
          empty={<EmptyState icon={Inbox} title="لا تذاكر هنا" description="ما يصل من العملاء يظهر هنا بترتيب وصوله." />}
        />
      </Tabs>
    </Screen>
  )
}

/* ── التذكرة ─────────────────────────────────────────────────────── */

export type TicketDecision =
  | { kind: "send"; text: string; edited: boolean; ownWords: boolean }
  | { kind: "escalate" }
  | { kind: "close" }

export interface SupportTicketProps {
  ticket: TicketRow
  messages: TicketMessage[]
  draft: TicketDraft | null
  now: string
  onDecide: (decision: TicketDecision) => void
  onBack: () => void
  /** صفحة العرض: الخطوة في الحجم الكبير. */
  initialStep?: 0 | 1 | 2
}

/** في الحجم الكبير: مسودةٌ أطول من هذا تُقرأ في خطوتها، والقرار في خطوةٍ بعدها. */
export const GAZE_DRAFT_WITH_DECISION = 220

export function SupportTicket({ ticket, messages, draft, now, onDecide, onBack, initialStep = 0 }: SupportTicketProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [step, setStep] = React.useState<0 | 1 | 2>(initialStep)
  const short = useShortScreen()
  const split = gaze && (short || (draft?.text.length ?? 0) > GAZE_DRAFT_WITH_DECISION)
  const [mode, setMode] = React.useState<"read" | "edit" | "own">("read")
  const [text, setText] = React.useState(draft?.text ?? "")
  const customer = messages.filter((m) => m.from === "CUSTOMER")
  const latest = customer[customer.length - 1]
  const Channel = CHANNEL[ticket.channel].icon

  const message = (
    <Card as="article" aria-labelledby="customer-message">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle as="h2" id="customer-message" className="text-lead">
          رسالة {ticket.customer}
        </CardTitle>
        <span className="flex items-center gap-1.5 text-small text-muted-foreground">
          <Channel aria-hidden="true" className="size-4" />
          {formatAgo(latest.at, now)}
        </span>
      </CardHeader>
      <CardContent>
        <p className="text-flow whitespace-pre-line">{latest.text}</p>
      </CardContent>
    </Card>
  )

  const draftCard = draft ? (
    <Card as="section" aria-labelledby="draft-title" className="border-2 border-ai/40 bg-ai-tint shadow-none">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle as="h2" id="draft-title" className="flex items-center gap-2 text-lead">
          <SymbolMark className="size-4" />
          {mode === "own" ? "ردّك" : "مسودة سيمبول"}
        </CardTitle>
        {mode === "read" ? <Badge tone="ai">لم تُرسل</Badge> : <Badge tone="info">تحرّرها أنت</Badge>}
      </CardHeader>
      <CardContent className="flex flex-col gap-tg">
        {mode === "read" ? (
          <p className="text-flow whitespace-pre-line rounded-ctl bg-card p-3">{draft.text}</p>
        ) : (
          <Field label={mode === "own" ? "اكتب ردّك" : "عدّل المسودة"} hint={`${[...text].length} من 2000`}>
            <Textarea rows={gaze ? 4 : 7} maxLength={2000} value={text} onChange={(event) => setText(event.target.value)} />
          </Field>
        )}
        {mode !== "own" && !gaze ? (
          <div className="flex flex-col gap-1.5 text-small">
            <p>
              <span className="font-bold">لماذا كتبها هكذا: </span>
              {draft.basis}
            </p>
            <p className="flex flex-wrap items-center gap-1.5">
              <span className="font-bold">استند إلى:</span>
              {draft.sources.map((source) => (
                <Badge key={source.id} icon={BookOpenCheck}>
                  {source.title}
                </Badge>
              ))}
            </p>
            {draft.check.length > 0 ? (
              <div>
                <p className="font-bold text-warning">تحقّق قبل الإرسال:</p>
                <ul className="list-disc ps-5">
                  {draft.check.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
        {mode !== "own" && gaze && !split ? (
          <p className="text-small">
            <span className="font-bold">تحقّق: </span>
            {draft.check[0] ?? draft.basis}
          </p>
        ) : null}
      </CardContent>
    </Card>
  ) : (
    <Card>
      <CardContent className="text-flow text-muted-foreground">لم يكتب سيمبول مسودةً لهذه الرسالة. اكتب ردّك بنفسك.</CardContent>
    </Card>
  )

  // التصعيد والإغلاق لا يحتاجان المسودة: في الحجم الكبير مع الرسالة في الخطوة الأولى، فتتّسع
  // خطوة المسودة بلا تمرير.
  const other = (
    <>
      <Button icon={ArrowUpCircle} onClick={() => onDecide({ kind: "escalate" })}>
        صعّد إلى مختص
      </Button>
      <Button variant="danger-outline" icon={XCircle} onClick={() => onDecide({ kind: "close" })}>
        أغلق دون ردّ
      </Button>
    </>
  )

  // القرار: «أرسل» في أوّل الشبكة (بعيداً عن «التالي» في أسفل الخطوة السابقة)، و«عدّل ثم أرسل»
  // في موضع «التالي» نفسه؛ والتصعيد والإغلاق يسألان قبل أن يفعلا.
  const decisions =
    mode === "read" ? (
      <section aria-label="قرارك" className="grid grid-cols-2 gap-tg md:grid-cols-4">
        <Button variant="primary" commit icon={Send} disabled={!draft} onClick={() => draft && onDecide({ kind: "send", text: draft.text, edited: false, ownWords: false })} className="col-span-2 md:col-span-1">
          أرسل المسودة كما هي
        </Button>
        <Button variant="secondary" icon={PencilLine} disabled={!draft} onClick={() => setMode("edit")}>
          عدّل ثم أرسل
        </Button>
        <Button
          icon={SquarePen}
          onClick={() => {
            setText("")
            setMode("own")
          }}
        >
          اكتب بنفسك
        </Button>
        {gaze ? null : other}
      </section>
    ) : (
      <section aria-label="قرارك" className="grid grid-cols-2 gap-tg">
        <Button
          icon={BackIcon}
          onClick={() => {
            setMode("read")
            setText(draft?.text ?? "")
          }}
        >
          تراجع
        </Button>
        <Button
          variant="primary"
          commit
          icon={Send}
          disabled={!text.trim()}
          onClick={() => onDecide({ kind: "send", text: text.trim(), edited: mode === "edit", ownWords: mode === "own" })}
        >
          أرسل ردّك
        </Button>
      </section>
    )

  const badges = (
    <div className="flex flex-wrap gap-1.5">
      <Badge icon={Channel}>{CHANNEL[ticket.channel].label}</Badge>
      <Badge tone={STATUS[ticket.status].tone}>{STATUS[ticket.status].label}</Badge>
      {ticket.priority === "HIGH" ? <Badge tone="danger">عاجلة</Badge> : null}
    </div>
  )

  if (gaze) {
    // خطوتان: الرسالة، ثم المسودة والقرار؛ وثلاثٌ إن طالت المسودة: الرسالة، ثم المسودة،
    // ثم القرار. وفي كلٍّ منها «رجوع» في أوّل الشريط و«التالي» بعده، والقرار أعلى خطوته.
    const last = split ? 2 : 1
    const titles = split ? [ticket.subject, "مسودة سيمبول", "قرارك"] : [ticket.subject, "مسودة سيمبول وقرارك"]
    return (
      <Screen
        title={titles[step]}
        above={badges}
        actions={
          <>
            <Button icon={BackIcon} onClick={step === 0 ? onBack : () => setStep((step - 1) as 0 | 1)}>
              {step === 0 ? "التذاكر" : step === 1 ? "الرسالة" : "المسودة"}
            </Button>
            {step < last ? (
              <Button variant="secondary" iconEnd={NextIcon} onClick={() => setStep((step + 1) as 1 | 2)}>
                {step === 0 ? "المسودة" : "القرار"}
              </Button>
            ) : null}
          </>
        }
      >
        {step === 0 ? (
          <>
            {message}
            <section aria-label="بلا ردّ" className="grid grid-cols-2 gap-tg">
              {other}
            </section>
          </>
        ) : step === 1 && split ? (
          draftCard
        ) : step === 1 ? (
          <>
            {draftCard}
            {decisions}
          </>
        ) : (
          <>
            {decisions}
            {draft && draft.check.length > 0 ? (
              <p className="text-small">
                <span className="font-bold text-warning">قبل أن ترسل، تحقّق: </span>
                {draft.check[0]}
              </p>
            ) : null}
            <p className="text-small text-muted-foreground">
              يصل الردّ إلى {ticket.customer} عبر {CHANNEL[ticket.channel].label} حين تضغط «أرسل».
            </p>
          </>
        )}
      </Screen>
    )
  }

  return (
    <Screen
      title={ticket.subject}
      back={{ label: "التذاكر", onBack }}
      above={
        <p className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
          <span className="num font-semibold text-foreground">#{ticket.number}</span>
          {badges}
        </p>
      }
    >
      <div className="grid grid-cols-1 gap-sec lg:grid-cols-2">
        {message}
        <div className="flex flex-col gap-tg">
          {draftCard}
          {decisions}
        </div>
      </div>
    </Screen>
  )
}
