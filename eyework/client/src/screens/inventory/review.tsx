/*
 * المراجعة قبل التسجيل: فاتورةٌ أو مرتجع
 * ======================================
 * ضغطة «راجِع وسجّل» تفتح هذه الشاشة: تنبيهات التطبيق من الخادم (فرق الإجمالي، نقص التسليم،
 * فاتورة مكرّرة…) بنصّها الجاهز، يُقرّ بكلٍّ منها («تابع رغم ذلك») أو يُعاد إلى الحقل («عدّل»)؛
 * ومراجعة سيمبول عبر /api/ai/review: ملاحظاته باسم صاحب الحساب وسببها وشواهدها، وقراره يُسجَّل
 * في الخادم (عدّل / تابع / تراجع). «سجّل» معطّلٌ ما بقي تنبيهٌ بلا قرار؛ ولو وصلت ملاحظةٌ بعد
 * العرض ردّ الخادم 409 فتُعرض من جديد («قبل المتابعة»).
 *
 *   • الحجم العادي: الكلّ في صفحة، و«سجّل» في أعلاها بعيداً عن «راجِع» الذي فُتحت به.
 *   • الحجم الكبير: كل تنبيهٍ في شاشة (قراران فوق السبب)، ثم شاشة التسجيل.
 */

import * as React from "react"
import { CheckCircle2, RefreshCw, Save } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { AIFlag } from "@/components/ui/ai-flag"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Stepper } from "@/components/ui/stepper"
import type { AiFlag, Flags, ReviewAnswer, RuleFlag, Totals } from "@/lib/inventory"
import { useSize } from "@/lib/size"

import { Money, RuleFlagCard, lineSubject } from "./common"
import type { Fail } from "./setup"

export interface ReviewProps {
  kind: "PURCHASE" | "RETURN"
  title: string
  /** سطر الملخّص: المورّد ورقم الفاتورة. */
  subject: string
  lineNames: Record<number, string>
  totals: Totals
  linesCount: number
  flags: Flags | null
  answer: ReviewAnswer | null
  /** المراجعة جارية (ضغطةٌ واحدة؛ الخادم ينتظر حتى اثنتي عشرة ثانية). */
  reviewing: boolean
  onReviewAgain: () => void
  acknowledged: string[]
  onAcknowledge: (key: string, on: boolean) => void
  onDecide: (flag: AiFlag, choice: "EDIT" | "PROCEED" | "UNDO") => Promise<void>
  onEdit: (lineNo: number | null) => void
  onPost: () => Promise<Fail>
  posting: boolean
  onBack: () => void
  /** خطوات المستند لشريط الخطوات في الحجم الكبير. */
  steps: { id: string; label: string }[]
}

function reviewLine(answer: ReviewAnswer | null, reviewing: boolean, flags: AiFlag[]): { text: string; tone: "info" | "success" | "warning" } {
  if (reviewing) return { text: "سيمبول يراجع الآن…", tone: "info" }
  if (!answer) return { text: "لم تُطلب مراجعة سيمبول بعد.", tone: "info" }
  if (answer.review.status === "PENDING") return { text: answer.review.message ?? "المراجعة جارية؛ اضغط «تحقّق» بعد قليل.", tone: "info" }
  if (answer.review.status === "UNAVAILABLE") return { text: answer.review.message ?? "مراجعة سيمبول غير متاحة الآن؛ يمكنك التسجيل بتنبيهات التطبيق وحدها.", tone: "warning" }
  if (flags.length === 0) return { text: "راجع سيمبول ولم يجد ما يُستغرب.", tone: "success" }
  return { text: flags.length === 1 ? "ملاحظةٌ واحدة من سيمبول تنتظر قرارك." : `${flags.length} ملاحظات من سيمبول تنتظر قرارك.`, tone: "warning" }
}

export function DocumentReview(props: ReviewProps) {
  const { kind, title, subject, lineNames, totals, linesCount, flags, answer, reviewing, onReviewAgain, acknowledged, onAcknowledge, onDecide, onEdit,
          onPost, posting, onBack, steps } = props
  const { size } = useSize()
  const gaze = size === "gaze"
  const [index, setIndex] = React.useState(0)
  const [fail, setFail] = React.useState<Fail>(null)
  const rules: RuleFlag[] = flags?.flags ?? []
  const ai: AiFlag[] = flags?.ai ?? []
  const openRules = rules.filter((flag) => !acknowledged.includes(flag.key))
  const openAi = ai.filter((flag) => flag.decision !== "PROCEED")
  const line = reviewLine(answer, reviewing, ai)
  const ready = flags !== null && !reviewing && openRules.length === 0 && openAi.length === 0 && answer?.review.status !== "PENDING"
  const noun = kind === "PURCHASE" ? "الفاتورة" : "المرتجع"

  async function post() {
    setFail(null)
    const result = await onPost()
    if (result) setFail(result)
  }

  const ruleCards = rules.map((flag) => (
    <RuleFlagCard
      key={flag.key}
      flag={flag}
      acknowledged={acknowledged.includes(flag.key)}
      subject={lineSubject(flag.line_no, flag.line_no === null ? undefined : lineNames[flag.line_no])}
      onAcknowledge={() => onAcknowledge(flag.key, true)}
      onUndo={() => onAcknowledge(flag.key, false)}
      onEdit={() => onEdit(flag.line_no)}
      actionsFirst={gaze}
    />
  ))
  const aiCards = ai.map((flag) => (
    <AIFlag
      key={flag.id}
      name={null}
      subject={lineSubject(flag.line, flag.line === null ? undefined : lineNames[flag.line])}
      message={flag.headline}
      reason={flag.suggestion ?? "راجع السطر قبل التسجيل."}
      evidence={gaze ? undefined : flag.evidence}
      status={flag.decision === "PROCEED" ? "acknowledged" : "open"}
      onEdit={() => void onDecide(flag, "EDIT").then(() => onEdit(flag.line))}
      onProceed={() => void onDecide(flag, "PROCEED")}
      onUndo={() => void onDecide(flag, "UNDO")}
      actionsFirst={gaze}
    />
  ))
  const cards = [...ruleCards, ...aiCards]
  const statusLine = (
    <p id="review-status" role="status" className={line.tone === "warning" ? "text-small font-semibold text-warning" : line.tone === "success" ? "text-small font-semibold text-success" : "text-small font-semibold text-muted-foreground"}>
      {line.text}
    </p>
  )
  const again = answer?.review.status === "PENDING" || answer?.review.status === "UNAVAILABLE" || (answer && answer.review.status === "DONE" && false) ? (
    <Button id="review-again" icon={RefreshCw} busy={reviewing} onClick={onReviewAgain}>
      {answer?.review.status === "PENDING" ? "تحقّق" : "أعد المحاولة"}
    </Button>
  ) : null
  const postButton = (
    <Button id="review-post" variant="primary" size="lg" commit icon={Save} disabled={!ready} busy={posting} onClick={() => void post()} className="gaze:w-full">
      {kind === "PURCHASE" ? "سجّل الفاتورة" : "سجّل المرتجع"}
    </Button>
  )
  const failAlert = fail ? (
    <Alert tone="danger" title="لم يُسجَّل" live>
      {fail.message}
    </Alert>
  ) : null
  const summary = (
    <dl className="flex flex-col gap-1 rounded-card border border-border bg-card p-pad text-flow">
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">{kind === "PURCHASE" ? "المورّد" : "من الفاتورة"}</dt>
        <dd className="truncate font-semibold">{subject}</dd>
      </div>
      <div className="flex justify-between gap-tg">
        <dt className="text-muted-foreground">الأسطر</dt>
        <dd className="num font-semibold">{linesCount}</dd>
      </div>
      <div className="flex justify-between gap-tg text-lead font-bold text-heading">
        <dt>الإجمالي</dt>
        <dd><Money halalas={totals.gross} /></dd>
      </div>
    </dl>
  )

  /* ── الحجم الكبير: تنبيهٌ في كل شاشة، ثم التسجيل ── */
  if (gaze) {
    const current = Math.min(index, cards.length)
    if (current < cards.length) {
      const isRule = current < rules.length
      const decided = isRule ? acknowledged.includes(rules[current].key) : ai[current - rules.length].decision === "PROCEED"
      return (
        <Screen
          title={cards.length > 1 ? `تنبيه ${current + 1} من ${cards.length}` : "قبل التسجيل"}
          above={<Stepper steps={steps} current={steps.length - 1} />}
          actions={
            <>
              <Button id="review-prev" icon={BackIcon} onClick={current === 0 ? onBack : () => setIndex(current - 1)}>
                {current === 0 ? `عدّل ${noun}` : "السابق"}
              </Button>
              <Button id="review-next" variant="secondary" iconEnd={NextIcon} disabled={!decided} onClick={() => setIndex(current + 1)}>
                التالي
              </Button>
            </>
          }
        >
          {cards[current]}
        </Screen>
      )
    }
    return (
      <Screen
        title={kind === "PURCHASE" ? "سجّل الفاتورة" : "سجّل المرتجع"}
        above={<Stepper steps={steps} current={steps.length - 1} />}
        actions={
          <>
            <Button id="review-prev" icon={BackIcon} onClick={cards.length ? () => setIndex(cards.length - 1) : onBack}>
              {cards.length ? "التنبيه" : `عدّل ${noun}`}
            </Button>
            {again ?? <span aria-hidden="true" />}
          </>
        }
      >
        {postButton}
        {failAlert}
        {statusLine}
        {summary}
      </Screen>
    )
  }

  /* ── الحجم العادي: الكلّ في صفحة ── */
  return (
    <Screen
      title={title}
      above={<Badge tone="info" className="self-start">لم يُسجَّل بعد</Badge>}
      description={kind === "PURCHASE" ? "تزيد المخزون وتدخل المصاريف حين تسجّلها." : "ينقص المخزون ويُخصم من المصاريف حين تسجّله."}
      back={{ id: "review-back", label: `عدّل ${noun}`, onClick: onBack }}
      actions={
        <>
          {again}
          <div className="ms-auto">{postButton}</div>
        </>
      }
    >
      {failAlert}
      <div className="flex flex-wrap items-center gap-tg">
        {ready ? <CheckCircle2 aria-hidden="true" className="size-icon text-success" /> : null}
        {statusLine}
        {openRules.length ? (
          <p role="status" className="text-small font-semibold text-warning">
            {openRules.length === 1 ? "تنبيهٌ واحد من التطبيق ينتظر إقرارك." : `${openRules.length} تنبيهات من التطبيق تنتظر إقرارك.`}
          </p>
        ) : null}
      </div>
      {cards.length ? <div className="flex flex-col gap-tg">{cards}</div> : null}
      {summary}
    </Screen>
  )
}
