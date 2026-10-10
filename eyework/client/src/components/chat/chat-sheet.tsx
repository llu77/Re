/*
 * ChatSheet — المحادثة مع سيمبول
 * =============================
 * تُفتح من زرّ «سيمبول» العائم في كل شاشةٍ من البوابة. المحادثة في الصفحة (lib/chat.ts): تبقى بين
 * الشاشات، وكل سؤالٍ يحمل الشاشة التي سُئل منها وآخر ثلاثة أسئلةٍ بأجوبتها. الجواب اقتراح: لا شيء فيه
 * يغيّر بياناتٍ؛ ما قرأه سيمبول بأدواته سطورٌ تحته («بحث في المنتجات: «ماء»»)، والشاشة التي يقترحها
 * زرٌّ يفتحها الموظف بنفسه («افتح «المخزون»»).
 *
 *   الحجم العادي: فقاعاتٌ بنمط «AI Message» (educalvolpz، 21st.dev: https://21st.dev/educalvolpz/components/ai-message،
 *                بشروط 21st.dev ورخصة صفحة المكوّن؛ التخطيط وحده: بلا أزرارٍ تظهر بالمرور ولا مؤقّتٍ ولا <style>
 *                محقون)، والأسئلة الجاهزة رقائق تحت التحية، وحقل السؤال في ذيل الورقة.
 *   الحجم الكبير: الورقة الشاشة كلّها بلا تمرير، وثلاث صفحات: البداية (الأسئلة الجاهزة، و«اكتب سؤالك» في
 *                الصفّ الأخير)، والكتابة (الحقل و«أرسل»)، والجواب (آخر جوابٍ بصفحاته، و«سؤالٌ جديد» في الصفّ
 *                الأخير نفسه، وبينه وبين الذيل فجوة هدفين: `mb-2` فوق فجوة الأقسام). وفي خانة الذيل الأولى ما
 *                يغادر: «الأدوات» أو «رجوع» أو «افتح …»، فما يقع تحت النظر بعد كل ضغطةٍ ليس سؤالاً يُرسل ولا «أرسل».
 */

import * as React from "react"
import { MessageSquarePlus, PenLine, Search, Send, Wrench } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { Alert } from "@/components/ui/alert"
import { BackArrow, Button, ForwardArrow } from "@/components/ui/button"
import { Sheet } from "@/components/ui/dialog"
import { Field, Textarea } from "@/components/ui/input"
import { PagedText } from "@/components/ui/paged-text"
import { ask, remainingOf, resetChat, toolLine, type AskInput, type ChatApi, type ChatTurn } from "@/lib/chat"
import { useSize } from "@/lib/size"
import { useStore } from "@/lib/store"
import { cn } from "@/lib/utils"
import type { Workspace } from "@/lib/workspace"

export interface ChatSheetProps {
  open: boolean
  onClose: () => void
  chat: ChatApi
  workspace: Workspace
  /** القسم الحالي (بند الرئيسية، أو "home"، أو null في «حسابي»): اسمه في التحية. */
  current: string | null
  userName: string | null
  onNavigate: (href: string) => void
  /** «الأدوات» من الورقة في الحجم الكبير: مكانها في شريط التبويب والسكّة لزرّ سيمبول. */
  onTools?: () => void
}

type GazeView = "start" | "write" | "answer"

function sectionName(workspace: Workspace, current: string | null): string {
  if (current === "home") return "الرئيسية"
  return workspace.home.find((entry) => entry.id === current)?.label ?? "حسابك"
}

/** علامة سيمبول في دائرة: بجانب كل جوابٍ منه. */
function Avatar() {
  return (
    <span aria-hidden="true" className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-card">
      <SymbolMark className="size-4" />
    </span>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] whitespace-pre-line rounded-[1.25rem] rounded-ee-md bg-primary px-3.5 py-2.5 leading-relaxed text-primary-foreground">
        <span className="sr-only">سؤالك: </span>
        {text}
      </p>
    </div>
  )
}

/** ما قرأه سيمبول بأدواته وما استند إليه: سطورٌ تحت الجواب، لا أهداف. */
function AnswerNotes({ turn }: { turn: ChatTurn }) {
  if (!turn.tools.length && !turn.sources.length) return null
  return (
    <div className="flex flex-col gap-0.5 text-small leading-snug text-muted-foreground">
      {turn.tools.length ? (
        <ul aria-label="ما قرأه سيمبول" className="flex flex-col gap-0.5">
          {turn.tools.map((tool) => (
            <li key={`${tool.name}:${tool.input}`} className="flex items-start gap-1.5">
              <Search aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" strokeWidth={2.25} />
              <span className="min-w-0">{toolLine(tool)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {turn.sources.map((source) => (
        <p key={source.line}>{source.line}</p>
      ))}
    </div>
  )
}

function bubbleTone(turn: ChatTurn | null): string {
  return turn && turn.status !== "ANSWER" ? "bg-muted text-foreground" : "bg-secondary text-foreground"
}

/** جوابٌ في المحادثة (الحجم العادي): الفقاعة، ثم ما قرأه، ثم زرّ الشاشة المقترحة. */
function SymbolBubble({ turn, onOpen }: { turn: ChatTurn; onOpen: (turn: ChatTurn) => void }) {
  return (
    <div className="flex items-start gap-2.5">
      <Avatar />
      <div className="flex min-w-0 max-w-[90%] flex-col items-start gap-2">
        <p className={cn("whitespace-pre-line rounded-[1.25rem] rounded-ss-md px-3.5 py-2.5 leading-relaxed", bubbleTone(turn))}>
          <span className="sr-only">سيمبول: </span>
          {turn.text}
        </p>
        <AnswerNotes turn={turn} />
        {turn.open ? (
          <Button variant="secondary" iconEnd={ForwardArrow} onClick={() => onOpen(turn)}>
            افتح «{turn.open.label}»
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function Greeting({ userName, section }: { userName: string | null; section: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <Avatar />
      <p className="min-w-0 max-w-[90%] rounded-[1.25rem] rounded-ss-md bg-secondary px-3.5 py-2.5 leading-relaxed text-foreground">
        {userName ? `أهلاً ${userName}، ` : "أهلاً، "}أنا سيمبول. اسألني عن عملك في «{section}»: أجيب من مهامّ مهنتك وشاشتك،
        وأقرأ بأدواتي ما يلزم من بوابتك، ولا أغيّر شيئاً.
      </p>
    </div>
  )
}

export function ChatSheet({ open, onClose, chat, workspace, current, userName, onNavigate, onTools }: ChatSheetProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const turns = useStore((state) => state.chat)
  const usage = useStore((state) => state.chatUsage)
  const [draft, setDraft] = React.useState("")
  // ما يُنتظر جوابه: نصّ السؤال كما سيظهر، أو null.
  const [pending, setPending] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [view, setView] = React.useState<GazeView>("start")
  const [back, setBack] = React.useState<GazeView>("start")
  const end = React.useRef<HTMLDivElement>(null)
  const latest = turns.length ? turns[turns.length - 1] : null
  const remaining = remainingOf(chat, usage)
  const section = sectionName(workspace, current)
  const length = [...draft].length
  const tooLong = length > chat.questionMax
  const exhausted = remaining === 0

  // كل فتحٍ في الحجم الكبير يبدأ من آخر جوابٍ إن وُجد، وإلا من البداية — قبل أن تُرسم الورقة. الفتح وحده:
  // ما يصل من جوابٍ وهي مفتوحة يغيّر الصفحة بنفسه.
  const opened = React.useRef(false)
  React.useLayoutEffect(() => {
    if (open && !opened.current) {
      setView(turns.length ? "answer" : "start")
      setError(null)
    }
    opened.current = open
  }, [open, turns.length])

  // الحجم العادي: آخر ما في المحادثة ظاهرٌ بعد كل سؤالٍ وجواب.
  React.useLayoutEffect(() => {
    if (open && !gaze) end.current?.scrollIntoView?.({ block: "end" })
  }, [open, gaze, turns.length, pending, error])

  async function send(input: AskInput, shown: string) {
    if (pending !== null || exhausted) return
    setPending(shown)
    setError(null)
    const result = await ask(chat.screen, input)
    setPending(null)
    if (result.ok) {
      if ("question" in input) setDraft("")
      setView("answer")
    } else {
      setError(result.message)
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || tooLong) return
    void send({ question: text }, text)
  }

  function openPlace(turn: ChatTurn) {
    const entry = turn.open ? workspace.home.find((item) => item.id === turn.open!.id) : undefined
    if (!entry) return
    onClose()
    onNavigate(entry.route)
  }

  const hint = (
    <>
      <span className="num">{length}</span> من <span className="num">{chat.questionMax}</span>
      {remaining !== null ? (
        <>
          {" · "}بقي لك اليوم <span className="num">{remaining}</span>
        </>
      ) : null}
    </>
  )
  const failure = error ? (
    <Alert tone="danger" title="لم يصل الجواب" live>
      {error}
    </Alert>
  ) : null

  if (gaze) {
    const place = view === "answer" && latest?.open ? latest : null
    const footer =
      view === "write" ? (
        <Button icon={BackArrow} onClick={() => setView(back)}>
          رجوع
        </Button>
      ) : place ? (
        <Button variant="secondary" iconEnd={ForwardArrow} onClick={() => openPlace(place)}>
          افتح «{place.open!.label}»
        </Button>
      ) : onTools ? (
        <Button icon={Wrench} onClick={onTools}>
          الأدوات
        </Button>
      ) : null
    return (
      <Sheet open={open} onClose={onClose} title="سيمبول" footer={footer}>
        <div className="flex h-full flex-col gap-tg">
          {view === "start" ? (
            <>
              {chat.ready.length ? (
                <ul aria-label="أسئلةٌ جاهزة" className="flex flex-col gap-tg">
                  {chat.ready.map((question, index) => (
                    <li key={question}>
                      <Button
                        commit
                        width="full"
                        busy={pending === question}
                        disabled={pending !== null || exhausted}
                        onClick={() => void send({ ready: index }, question)}
                        className="justify-start text-start"
                      >
                        {question}
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : null}
              {failure}
              <Button
                icon={PenLine}
                width="full"
                className="mb-2 mt-auto"
                disabled={pending !== null}
                onClick={() => {
                  setBack("start")
                  setError(null)
                  setView("write")
                }}
              >
                اكتب سؤالك
              </Button>
            </>
          ) : view === "write" ? (
            <form noValidate onSubmit={submit} className="flex flex-col gap-tg">
              <Field label="سؤالك" hint={hint} error={tooLong ? `السؤال أطول من ${chat.questionMax} حرف.` : null}>
                <Textarea rows={3} value={draft} onChange={(event) => setDraft(event.target.value)} className="min-h-[6.5rem]" />
              </Field>
              <Button
                type="submit"
                variant="primary"
                commit
                icon={Send}
                width="full"
                busy={pending !== null}
                disabled={!draft.trim() || tooLong || exhausted}
              >
                {pending !== null ? "سيمبول يكتب…" : "أرسل"}
              </Button>
              {failure}
            </form>
          ) : latest ? (
            <>
              <section aria-label="جواب سيمبول" className="flex min-h-0 flex-col gap-tg-min">
                <p className="truncate text-small text-muted-foreground">
                  سؤالك: <span className="text-foreground">{latest.question}</span>
                </p>
                {/* الفقاعة على النصّ وحده: «السابق» و«التالي» تحتها بعرض الورقة. */}
                <PagedText
                  key={latest.id}
                  label="جواب سيمبول"
                  text={latest.text}
                  perPage={{ gaze: 150, gazeShort: 80 }}
                  className={cn("rounded-card px-pad py-3", bubbleTone(latest))}
                />
                <AnswerNotes turn={latest} />
              </section>
              <Button
                icon={MessageSquarePlus}
                width="full"
                className="mb-2 mt-auto"
                onClick={() => {
                  setBack("answer")
                  setError(null)
                  setView("start")
                }}
              >
                سؤالٌ جديد
              </Button>
            </>
          ) : null}
        </div>
      </Sheet>
    )
  }

  const composer = (
    <form noValidate onSubmit={submit} className="flex w-full basis-full flex-col gap-2">
      {failure}
      <Field label={<span className="sr-only">سؤالك</span>} hint={hint} error={tooLong ? `السؤال أطول من ${chat.questionMax} حرف.` : null}>
        <div className="flex items-end gap-tg">
          <Textarea
            rows={2}
            value={draft}
            placeholder={`اسأل عن عملك في «${section}»`}
            onChange={(event) => setDraft(event.target.value)}
            className="min-w-0 flex-1"
          />
          <Button type="submit" variant="primary" commit icon={Send} busy={pending !== null} disabled={!draft.trim() || tooLong || exhausted}>
            أرسل
          </Button>
        </div>
      </Field>
    </form>
  )

  return (
    <Sheet
      open={open}
      onClose={onClose}
      eyebrow="المساعد"
      title="سيمبول"
      description="يجيب عن عملك من مهامّ مهنتك وشاشتك، ويقرأ بأدواته ولا يغيّر شيئاً."
      footer={
        <>
          {composer}
          {turns.length ? (
            <Button icon={MessageSquarePlus} disabled={pending !== null} onClick={resetChat}>
              محادثة جديدة
            </Button>
          ) : null}
        </>
      }
    >
      <div role="log" aria-label="المحادثة مع سيمبول" aria-live="polite" className="flex flex-col gap-4">
        {turns.length === 0 ? <Greeting userName={userName} section={section} /> : null}
        {turns.map((turn) => (
          <React.Fragment key={turn.id}>
            <UserBubble text={turn.question} />
            <SymbolBubble turn={turn} onOpen={openPlace} />
          </React.Fragment>
        ))}
        {pending !== null ? (
          <>
            <UserBubble text={pending} />
            <div className="flex items-start gap-2.5">
              <Avatar />
              <p className="rounded-[1.25rem] rounded-ss-md bg-muted px-3.5 py-2.5 text-muted-foreground">سيمبول يقرأ ويكتب…</p>
            </div>
          </>
        ) : null}
        {turns.length === 0 && pending === null && chat.ready.length ? (
          <div className="flex flex-col gap-2 ps-[2.625rem]">
            <p className="text-small font-semibold text-muted-foreground">أسئلةٌ جاهزة</p>
            <ul aria-label="أسئلةٌ جاهزة" className="flex flex-wrap gap-tg">
              {chat.ready.map((question, index) => (
                <li key={question} className="min-w-0">
                  <Button commit disabled={exhausted} onClick={() => void send({ ready: index }, question)} className="rounded-full text-start text-small">
                    {question}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div ref={end} />
      </div>
    </Sheet>
  )
}
