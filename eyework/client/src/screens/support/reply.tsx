/*
 * الردّ: التنبيهات، ومراجعة سيمبول، ثم «انسخ الردّ»، ثم «أرسلتُه»
 * ================================================================
 * التطبيق لا يرسل شيئاً: الموظف ينسخ الردّ (أو يشاركه، أو يقرؤه للعميل في المكالمة) ويرسله من قناته، ثم
 * يؤكّد. قبل النسخ:
 *   • تنبيهات القواعد من الخادم (وعدٌ بموعدٍ أو مبلغ، طلب سرّ، رابطٌ ليس في المقالات…): «عدّل» يسحب الردّ
 *     ويعيد المحرّر بنصّه، و«تابع رغم ذلك» بسببٍ يُختار.
 *   • ملاحظات سيمبول على ردٍّ عدّله الموظف أو كتبه (المراجعة تبدأ وحدها حين تُفتح الشاشة): باسم صاحب الحساب
 *     وسببها، و«عدّل» أو «تابع رغم ذلك». لا تنتظر المراجعة: يُنسخ الردّ وهي جارية، والقاعدة ترفض ما بقي بلا قرار.
 * والنصّ المنسوخ هو المحفوظ بعينه (البصمة)؛ والنسخ يُسجَّل بعد نجاحه وحده.
 *
 *   • الحجم العادي: صفحةٌ واحدة.
 *   • الحجم الكبير: تنبيهٌ في كل صفحة، ثم النصّ، ثم «انسخ الردّ» في أعلى صفحته؛ وبعد النسخ صفحة التأكيد وفي
 *     أعلاها «انسخه مرةً أخرى» حيث كان «انسخ الردّ».
 */

import * as React from "react"
import { CheckCircle2, Copy, Mic, PencilLine, RefreshCw, Share2, Undo2, X } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { AIFlag } from "@/components/ui/ai-flag"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { PagedText } from "@/components/ui/paged-text"
import { DISMISS_REASON, REPLY_KIND, type AiFlag, type DismissReason, type ReleaseVia, type ReviewAnswer, type RuleFlag, type Ticket } from "@/lib/support"
import { useSize } from "@/lib/size"
import { GazeHost, Picker } from "@/screens/inventory/common"

import type { Fail } from "./common"

export interface ReplyScreenProps {
  ticket: Ticket
  reviewing: boolean
  answer: ReviewAnswer | null
  /** ملاحظات سيمبول من 409 FLAGS_UNDECIDED: وصلت بعد العرض. */
  late: AiFlag[] | null
  onReviewAgain: () => void
  onDecideAi: (flag: AiFlag, choice: "EDIT" | "PROCEED" | "UNDO") => Promise<void>
  onAckRule: (flag: RuleFlag, action: "HEEDED" | "DISMISSED", reason: DismissReason | null) => Promise<Fail>
  onRelease: (via: ReleaseVia) => Promise<Fail>
  onConfirm: (sent: boolean) => Promise<Fail>
  /** «عدّل»: يُسحب الردّ ويُفتح المحرّر بنصّه. */
  onEdit: () => Promise<Fail>
  /** «عدّل» على تنبيه قاعدة: يُسجَّل الأخذ به (HEEDED)، فيسحب الخادم الردّ، ويُفتح المحرّر بنصّه. */
  onHeedRule: (flag: RuleFlag) => Promise<Fail>
  onBack: () => void
}

function reviewLine(reply: Ticket["live_reply"], reviewing: boolean, answer: ReviewAnswer | null, flags: AiFlag[]): string | null {
  if (!reply?.needs_review) return null
  if (reviewing) return "سيمبول يراجع الردّ… يمكنك نسخه دون انتظار."
  if (!answer) return null
  if (answer.review.status !== "DONE") return answer.review.message ?? "مراجعة سيمبول غير متاحة الآن. يمكنك المتابعة."
  if (!flags.length) return "راجع سيمبول الردّ ولم يجد ما يُستغرب."
  const open = flags.filter((f) => f.decision !== "PROCEED").length
  if (open === 0) return "قرّرتَ في ملاحظات سيمبول."
  return open === 1 ? "ملاحظةٌ من سيمبول تنتظر قرارك." : `${open} ملاحظات من سيمبول تنتظر قرارك.`
}

export function RuleFlagCard({ flag, gaze, onAck, onEdit }: {
  flag: RuleFlag
  gaze: boolean
  onAck: (action: "HEEDED" | "DISMISSED", reason: DismissReason | null) => Promise<Fail>
  onEdit: () => void
}) {
  const [reason, setReason] = React.useState<DismissReason | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const open = flag.state === "OPEN"
  async function dismiss() {
    setBusy(true)
    const result = await onAck("DISMISSED", reason)
    setBusy(false)
    setFail(result)
  }
  return (
    <section role="group" aria-label={flag.message} data-flag-status={open ? "open" : "acknowledged"} className={open ? "flex flex-col gap-tg rounded-card border border-warning-line bg-warning-tint p-pad" : "flex flex-col gap-tg rounded-card border border-border bg-muted p-pad"}>
      {/* في الحجم الكبير عنوان الشاشة «تنبيه 1 من 2»، والسبب ثلاثة أسطرٍ على الأكثر: ارتفاع البطاقة محدود مهما طال
          الاقتباس، فتتّسع خيارات «سبب المتابعة» تحتها في أقصر الهواتف. */}
      <p className="text-small font-bold gaze:hidden">تنبيه</p>
      <p className="font-semibold">{flag.message}</p>
      <p className="text-small text-muted-foreground gaze:line-clamp-3">{flag.reason}</p>
      {fail ? <Alert tone="danger" title="لم يُحفظ القرار" live>{fail.message}</Alert> : null}
      {open ? (
        // في الحجم الكبير القراران فوق المنتقي: خياراته تُفتح تحته، فما يقع عليه النظر بعد اختيار السبب هو
        // المنتقي نفسه لا «تابع رغم ذلك».
        <GazeHost className={gaze ? "flex-col-reverse" : undefined}>
          <Picker
            id={`flag-reason-${flag.id}`}
            label="سبب المتابعة"
            options={(Object.keys(DISMISS_REASON) as DismissReason[]).map((code) => ({ value: code, label: DISMISS_REASON[code] }))}
            value={reason}
            onValueChange={(value) => setReason(value as DismissReason)}
          />
          <div className={gaze ? "grid grid-cols-2 gap-tg" : "flex flex-wrap gap-tg"}>
            <Button id={`flag-edit-${flag.id}`} variant="secondary" icon={PencilLine} onClick={onEdit}>
              عدّل
            </Button>
            <Button id={`flag-dismiss-${flag.id}`} commit busy={busy} disabled={reason === null} onClick={() => void dismiss()} className="border-warning-line">
              تابع رغم ذلك
            </Button>
          </div>
        </GazeHost>
      ) : (
        <p role="status" className="text-small font-semibold">{flag.state === "DISMISSED" ? `تابعتَ رغم التنبيه: ${flag.dismiss_reason ? DISMISS_REASON[flag.dismiss_reason] : ""}.` : "أخذتَ بالتنبيه."}</p>
      )}
    </section>
  )
}

export function ReplyScreen(props: ReplyScreenProps) {
  const { ticket, reviewing, answer, late, onReviewAgain, onDecideAi, onAckRule, onHeedRule, onRelease, onConfirm, onEdit, onBack } = props
  const { size } = useSize()
  const gaze = size === "gaze"
  const reply = ticket.live_reply
  const [fail, setFail] = React.useState<Fail>(null)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [reading, setReading] = React.useState(false)
  // صفحات الحجم الكبير بمعرّفاتها لا بأرقامها: ملاحظاتٌ تصل متأخرةً (409 بعد «انسخ الردّ») تُدرج قبل صفحة النسخ
  // ولا تحلّ محلّها تحت النظر — تبقى الصفحة كما هي وأزرارها معطّلة حتى يُقرَّر فيها.
  const [pageId, setPageId] = React.useState("text")
  if (!reply) return null
  const released = reply.state === "RELEASED"
  const spoken = ticket.channel === "PHONE" || ticket.channel === "IN_PERSON"
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function"
  // جواب «لم تنتهِ المراجعة» بلا ملاحظات لا يخفي ملاحظاتٍ وصلت مع التذكرة.
  const aiFlags = late ?? (answer?.review.status === "DONE" ? answer.flags : reply.ai_flags)
  const openRules = reply.flags.filter((f) => f.state === "OPEN")
  const openAi = aiFlags.filter((f) => f.decision !== "PROCEED")
  const blocked = openRules.length > 0 || openAi.length > 0
  const line = reviewLine(reply, reviewing, answer, aiFlags)

  async function run(id: string, action: () => Promise<Fail>) {
    setBusy(id)
    setFail(null)
    const result = await action()
    setBusy(null)
    setFail(result)
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(reply!.body)
    } catch {
      setFail({ message: "تعذّر النسخ. اضغط «انسخ الردّ» مرةً أخرى.", field: null })
      return
    }
    await run("copy", () => onRelease("COPY"))
  }
  async function share() {
    try {
      await navigator.share({ text: reply!.body })
    } catch {
      return
    }
    await run("share", () => onRelease("SHARE"))
  }
  async function shareAgain() {
    try {
      await navigator.share({ text: reply!.body })
    } catch {
      // أُغلقت ورقة المشاركة: لا شيء يُسجَّل، فالردّ أُطلق من قبل.
    }
  }
  async function copyAgain() {
    try {
      await navigator.clipboard.writeText(reply!.body)
      setFail(null)
    } catch {
      setFail({ message: "تعذّر النسخ. حاول مرةً أخرى.", field: null })
    }
  }

  const failAlert = fail ? <Alert tone="danger" title="لم يتمّ" live>{fail.message}</Alert> : null
  const ruleCards = reply.flags.map((flag) => (
    <RuleFlagCard key={flag.id} flag={flag} gaze={gaze} onAck={(action, reason) => onAckRule(flag, action, reason)} onEdit={() => void run("edit", () => onHeedRule(flag))} />
  ))
  const aiCards = aiFlags.map((flag) => (
    <AIFlag
      key={flag.id}
      name={null}
      message={flag.headline}
      reason={flag.suggestion ?? "راجع الردّ قبل نسخه."}
      evidence={gaze ? undefined : flag.evidence}
      status={flag.decision === "PROCEED" ? "acknowledged" : "open"}
      onEdit={() => void onDecideAi(flag, "EDIT").then(() => run("edit", onEdit))}
      onProceed={() => void onDecideAi(flag, "PROCEED")}
      onUndo={() => void onDecideAi(flag, "UNDO")}
      actionsFirst={gaze}
    />
  ))
  const cards = [...ruleCards, ...aiCards]
  const statusLine = line ? <p id="reply-review" role="status" className="text-small font-semibold text-muted-foreground">{line}</p> : null
  const again = reply.needs_review && !reviewing && answer && answer.review.status !== "DONE" ? (
    <Button id="reply-review-again" icon={RefreshCw} onClick={onReviewAgain}>أعد المراجعة</Button>
  ) : null
  const body = gaze ? <PagedText text={reply.body} label="الردّ" perPage={{ gaze: 240, gazeShort: 120 }} /> : <p className="text-flow whitespace-pre-line rounded-card border border-border bg-card p-pad">{reply.body}</p>
  const sendButtons = (
    <div className="flex flex-col gap-tg tablet:flex-row tablet:flex-wrap">
      {spoken ? (
        <Button id="reply-script" variant="secondary" icon={Mic} disabled={blocked} onClick={() => setReading(true)}>
          اقرأه للعميل
        </Button>
      ) : null}
      <Button id="reply-copy" variant="primary" size="lg" commit icon={Copy} busy={busy === "copy"} disabled={blocked} onClick={() => void copy()}>
        انسخ الردّ
      </Button>
      {canShare ? (
        <Button id="reply-share" commit icon={Share2} busy={busy === "share"} disabled={blocked} onClick={() => void share()}>
          شارك الردّ
        </Button>
      ) : null}
    </div>
  )
  const confirm = (
    <>
      <Button id="reply-copy-again" icon={Copy} onClick={() => void copyAgain()} className="gaze:w-full">
        انسخه مرةً أخرى
      </Button>
      <p className="text-lead font-semibold">هل أرسلتَ الردّ إلى العميل؟</p>
      <div className="flex flex-col gap-tg tablet:flex-row">
        <Button id="reply-sent" variant="primary" size="lg" commit icon={CheckCircle2} busy={busy === "sent"} onClick={() => void run("sent", () => onConfirm(true))}>
          نعم، أرسلته
        </Button>
        <Button id="reply-not-sent" commit icon={X} busy={busy === "not-sent"} onClick={() => void run("not-sent", () => onConfirm(false))}>
          لا، لم أرسله
        </Button>
      </div>
    </>
  )
  // في الحجم الكبير: كل زرّ إرسالٍ يحلّ محلّه في التأكيد زرٌّ آمن بحجمه ومكانه («مرةً أخرى»)، فالضغطة التي
  // أطلقت الردّ — نسخاً أو مشاركةً أو قراءة، أو «أكّد الإرسال» من التذكرة — تقع على زرٍّ لا يعتمد شيئاً، و«نعم،
  // أرسلته» و«لا، لم أرسله» في أسفل المحتوى بعيداً عنها.
  const againButtons = (
    <div className="flex flex-col gap-tg">
      {spoken ? (
        <Button id="reply-script-again" variant="secondary" icon={Mic} onClick={() => setReading(true)}>
          اقرأه مرةً أخرى
        </Button>
      ) : null}
      <Button id="reply-copy-again" size="lg" icon={Copy} onClick={() => void copyAgain()}>
        انسخه مرةً أخرى
      </Button>
      {canShare ? (
        <Button id="reply-share-again" icon={Share2} onClick={() => void shareAgain()}>
          شاركه مرةً أخرى
        </Button>
      ) : null}
    </div>
  )
  const gazeConfirm = (
    <>
      {againButtons}
      <p className="text-lead font-semibold">هل أرسلتَ الردّ إلى العميل؟</p>
      {fail ? <Alert tone="danger" title="لم يتمّ" live>{fail.message}</Alert> : null}
      <div className="mt-auto grid grid-cols-2 gap-tg">
        <Button id="reply-sent" variant="primary" size="lg" commit icon={CheckCircle2} busy={busy === "sent"} onClick={() => void run("sent", () => onConfirm(true))}>
          نعم، أرسلته
        </Button>
        <Button id="reply-not-sent" size="lg" commit icon={X} busy={busy === "not-sent"} onClick={() => void run("not-sent", () => onConfirm(false))}>
          لا، لم أرسله
        </Button>
      </div>
    </>
  )
  const badges = (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="neutral">{REPLY_KIND[reply.kind]}</Badge>
      {released ? <Badge tone="warning">نُسخ ولم يُؤكَّد</Badge> : <Badge tone="info">جاهز</Badge>}
    </div>
  )

  /* ── القراءة للعميل ── */
  if (reading) {
    const scriptBack = <Button id="reply-script-back" icon={BackIcon} onClick={() => setReading(false)}>الردّ</Button>
    const scriptDone = released ? (
      <Button id="reply-script-done" icon={CheckCircle2} onClick={() => setReading(false)}>انتهيت</Button>
    ) : (
      <Button id="reply-script-done" variant="primary" commit icon={CheckCircle2} busy={busy === "script"} onClick={() => void run("script", async () => {
        const result = await onRelease("SCRIPT")
        if (!result) setReading(false)
        return result
      })}>
        انتهيت
      </Button>
    )
    // في الحجم الكبير: «الردّ» في أعلى المحتوى حيث كان «اقرأه للعميل»، و«انتهيت» في الخانة التي يقع فيها «التذكرة»
    // في التأكيد بعدها؛ فلا تقع ضغطةٌ على اعتماد، ولا يكون الاعتماد أقرب ما إليها.
    return (
      <Screen
        title="اقرأه للعميل"
        above={gaze ? badges : undefined}
        actions={gaze ? <>{scriptDone}<span aria-hidden="true" /></> : <>{scriptBack}{scriptDone}</>}
      >
        {gaze ? scriptBack : null}
        {failAlert}
        <PagedText text={reply.body} label="الردّ" className="text-lead" perPage={{ gaze: 200, gazeShort: 100 }} />
      </Screen>
    )
  }

  /* ── الحجم الكبير ── */
  if (gaze) {
    if (released) {
      return (
        <Screen title="تأكيد الإرسال" above={badges} actions={<><Button id="reply-back" icon={BackIcon} onClick={onBack}>التذكرة</Button><span aria-hidden="true" /></>}>
          {gazeConfirm}
        </Screen>
      )
    }
    // النصّ أوّلاً (فقرةٌ لا تُضغط تحت نظرٍ وصل من «أرسل كما هي»)، ثم تنبيهٌ في كل صفحة، ثم النسخ.
    const flagIds = [...reply.flags.map((f) => `rule-${f.id}`), ...aiFlags.map((f) => `ai-${f.id}`)]
    const pages = [{ id: "text", label: "الردّ", body: <>{statusLine}{body}</> }, ...cards.map((card, i) => ({ id: flagIds[i], label: "تنبيه", body: card })), { id: "send", label: "النسخ", body: null }]
    const index = Math.max(0, pages.findIndex((p) => p.id === pageId))
    const at = pages[index]
    const setPage = (next: number) => setPageId(pages[next].id)
    const flagIndex = index - 1
    const isFlag = flagIndex >= 0 && flagIndex < cards.length
    const decided = !isFlag || (flagIndex < ruleCards.length ? reply.flags[flagIndex].state !== "OPEN" : aiFlags[flagIndex - ruleCards.length].decision === "PROCEED")
    return (
      <Screen
        title={at.id === "send" ? "انسخ الردّ وأرسله" : isFlag ? `تنبيه ${flagIndex + 1} من ${cards.length}` : "الردّ كما سيصل"}
        above={badges}
        actions={
          <>
            <Button id="reply-prev" icon={BackIcon} onClick={index === 0 ? onBack : () => setPage(index - 1)}>
              {index === 0 ? "التذكرة" : "السابق"}
            </Button>
            {at.id === "send" ? <span aria-hidden="true" /> : (
              <Button id="reply-next" variant="secondary" iconEnd={NextIcon} disabled={!decided} onClick={() => setPage(index + 1)}>
                التالي
              </Button>
            )}
          </>
        }
      >
        {at.id === "send" ? (
          <>
            {sendButtons}
            {failAlert}
            {statusLine}
            {again}
            <Button id="reply-withdraw" icon={Undo2} busy={busy === "edit"} onClick={() => void run("edit", onEdit)}>
              عدّل الردّ
            </Button>
          </>
        ) : (
          at.body
        )}
      </Screen>
    )
  }

  /* ── الحجم العادي ── */
  return (
    <Screen
      title={released ? "تأكيد الإرسال" : "الردّ كما سيصل"}
      above={badges}
      back={{ id: "reply-back", label: "التذكرة", onClick: onBack }}
      end={released ? undefined : { id: "reply-withdraw", label: "عدّل الردّ", icon: Undo2, onClick: () => void run("edit", onEdit) }}
    >
      {failAlert}
      {released ? confirm : (
        <>
          {statusLine}
          {again}
          {cards.length ? <div className="flex flex-col gap-tg">{cards}</div> : null}
          {sendButtons}
          {blocked ? <p className="text-small font-semibold text-warning">قرّر في كل تنبيهٍ قبل النسخ.</p> : <p className="text-small text-muted-foreground">لا يُرسل التطبيق شيئاً؛ الصق الردّ في محادثة العميل وأرسله أنت.</p>}
          {body}
        </>
      )}
    </Screen>
  )
}
