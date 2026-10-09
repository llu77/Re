/*
 * اسأل سيمبول
 * ===========
 * سؤالٌ واحد وجوابٌ واحد، بسياق القسم الحالي وحده: يصل النموذجَ السؤالُ واسمُ القسم، لا
 * اسم المستخدم ولا بياناته (prompt.py: «اسم المستخدم لا يصل النموذج أبداً»). والجواب
 * اقتراح: لا يغيّر شيئاً في البيانات، ولا زرّ فيه يفعل شيئاً غير «سؤالٌ آخر».
 *
 * الحدود من الخادم (ai_calls: لكل مستخدم ولليوم وللتطبيق كلّه)، والواجهة تعرض ما بقي
 * كما يقوله الخادم ولا تحسبه.
 */

import * as React from "react"
import { RotateCcw, Send } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, Textarea } from "@/components/ui/input"
import { addressed } from "@/components/ui/ai-flag"
import { PagedText } from "@/components/ui/paged-text"
import type { Workspace } from "@/lib/workspace"

/** الحدّ الافتراضي؛ الخادم يرسل حدّه في /api/choices (assistant.question_max) ويحلّ محلّه. */
export const QUESTION_MAX = 400

export interface AssistantReply {
  answer: string
  /** ما لم يتأكّد منه سيمبول، أو null. */
  note: string | null
  /** ما بقي من أسئلة اليوم كما يقوله الخادم. */
  remaining: number | null
}

export type AssistantResult = { ok: true; reply: AssistantReply } | { ok: false; message: string }

export interface AssistantApi {
  remaining: number | null
  /** أقصى طول السؤال كما يحدّه الخادم. */
  questionMax?: number
  ask: (question: string, screen: string | null) => Promise<AssistantResult>
  /** صفحة العرض: سؤالٌ وجوابٌ معروضان. */
  initial?: { question: string; reply: AssistantReply | null }
}

export function AssistantTool({ userName, screen, workspace, api }: {
  userName: string | null
  /** الشاشة الحالية: اسمها وحده سياق السؤال. */
  screen: string | null
  workspace: Workspace
  api: AssistantApi
}) {
  const [question, setQuestion] = React.useState(api.initial?.question ?? "")
  const [reply, setReply] = React.useState<AssistantReply | null>(api.initial?.reply ?? null)
  const [remaining, setRemaining] = React.useState<number | null>(api.initial?.reply?.remaining ?? api.remaining)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)
  const sectionName =
    screen === "home" ? "الرئيسية" : (workspace.home.find((entry) => entry.id === screen)?.label ?? "حسابك")
  const length = [...question].length
  const questionMax = api.questionMax ?? QUESTION_MAX
  const tooLong = length > questionMax

  async function send(event: React.FormEvent) {
    event.preventDefault()
    const text = question.trim()
    if (!text || tooLong || busy) return
    setBusy(true)
    setError(null)
    const result = await api.ask(text, screen)
    setBusy(false)
    if (result.ok) {
      setReply(result.reply)
      setRemaining(result.reply.remaining)
    } else {
      setError(result.message)
    }
  }

  if (reply) {
    return (
      <div className="flex flex-col gap-tg">
        <p className="rounded-card bg-muted p-3 text-small text-foreground gaze:short:hidden">
          <span className="font-semibold">سؤالك: </span>
          {question}
        </p>
        <section aria-label="جواب سيمبول" className="flex flex-col gap-2 rounded-card border border-primary-line/40 bg-secondary p-pad">
          <p className="flex items-center gap-2 text-small font-semibold text-secondary-foreground">
            <SymbolMark className="size-4" />
            جواب سيمبول · اقتراحٌ تتحقّق منه
          </p>
          <PagedText label="جواب سيمبول" text={addressed(userName, reply.answer)} className="text-foreground" perPage={{ gaze: 300, gazeShort: 110 }} />
          {reply.note ? <p className="text-small text-muted-foreground">{reply.note}</p> : null}
        </section>
        <div className="flex flex-wrap items-center justify-between gap-tg">
          <Button
            icon={RotateCcw}
            onClick={() => {
              setReply(null)
              setQuestion("")
            }}
          >
            سؤالٌ آخر
          </Button>
          {remaining !== null ? (
            <p className="text-small text-muted-foreground gaze:short:hidden">
              بقي لك اليوم <span className="num">{remaining}</span>
            </p>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <form noValidate onSubmit={send} className="flex flex-col gap-tg">
      <p className="text-small text-muted-foreground">
        يجيب سيمبول عن أسئلة عملك في «{sectionName}». يصله سؤالك وحده: لا اسمك ولا بياناتك.
      </p>
      <Field
        label="سؤالك"
        hint={
          <>
            <span className="num">{length}</span> من <span className="num">{questionMax}</span>
            {remaining !== null ? (
              <>
                {" · "}بقي لك اليوم <span className="num">{remaining}</span>
              </>
            ) : null}
          </>
        }
        error={tooLong ? `السؤال أطول من ${questionMax} حرف.` : null}
      >
        <Textarea rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} className="gaze:min-h-[6.5rem]" />
      </Field>
      {error ? (
        <Alert tone="danger" title="لم يصل الجواب" live>
          {error}
        </Alert>
      ) : null}
      <Button type="submit" variant="primary" commit icon={Send} busy={busy} disabled={!question.trim() || tooLong || remaining === 0}>
        {busy ? "سيمبول يكتب…" : "أرسل السؤال"}
      </Button>
    </form>
  )
}
