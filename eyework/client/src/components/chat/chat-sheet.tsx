/*
 * ChatSheet — المحادثة مع سيمبول
 * =============================
 * تُفتح من زرّ «سيمبول» العائم في كل شاشةٍ من البوابة. المحادثة في الصفحة (lib/chat.ts): تبقى بين
 * الشاشات، وكل سؤالٍ يحمل الشاشة التي سُئل منها وآخر ثلاثة أسئلةٍ بأجوبتها. الجواب اقتراح: لا شيء فيه
 * يغيّر بياناتٍ؛ ما قرأه سيمبول بأدواته سطورٌ تحته («بحث في المنتجات: «ماء»»)، والشاشة التي يقترحها
 * زرٌّ يفتحها الموظف بنفسه («افتح «المخزون»»). لا شرح في الورقة ولا سطر مصدر.
 *
 *   الحجم العادي: بنمط «Agent Chat» (serafimcloud، 21st.dev: https://21st.dev/@serafimcloud/components/agent-chat،
 *                بشروط 21st.dev ورخصة صفحة المكوّن): سؤال الموظف فقاعةٌ هادئة في جهته، وجواب سيمبول نصٌّ بلا فقاعة
 *                بجانب صورته، وما قرأه رقائق صغيرة تحته. وقبل أول سؤال: صورة سيمبول والتحية في الوسط والأسئلة الجاهزة
 *                صفوفٌ تحتها. وحقل السؤال صندوقٌ مدوّر يكبر مع النصّ وزرّ الإرسال دائرةٌ في طرفه (Enter يرسل، وShift+Enter
 *                سطرٌ جديد). التخطيط وحده: بلا حركة ظهورٍ ولا مؤقّتٍ ولا <style> محقون.
 *   الحجم الكبير: الورقة الشاشة كلّها بلا تمرير، وثلاث صفحات: البداية (الأسئلة الجاهزة، و«اكتب سؤالك» في
 *                الصفّ الأخير)، والكتابة (الحقل و«أرسل»)، والجواب (آخر جوابٍ بصفحاته، و«سؤالٌ جديد» في الصفّ
 *                الأخير نفسه، وبينه وبين الذيل فجوة هدفين: `mb-2` فوق فجوة الأقسام). وفي خانة الذيل الأولى ما
 *                يغادر: «الأدوات» أو «رجوع» أو «افتح …»، فما يقع تحت النظر بعد كل ضغطةٍ ليس سؤالاً يُرسل ولا «أرسل».
 */

import * as React from "react"
import { ArrowUp, MessageSquarePlus, PenLine, Search, Send, Wrench } from "lucide-react"

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

/** صورة سيمبول: علامته في دائرةٍ بيضاء بحدٍّ هادئ؛ كبيرةٌ في التحية وصغيرةٌ بجانب كل جواب. */
function Avatar({ large = false }: { large?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-card shadow-sm shadow-black/5 ring-1 ring-border",
        large ? "size-12" : "mt-0.5 size-7",
      )}
    >
      <SymbolMark className={large ? "size-6" : "size-3.5"} />
    </span>
  )
}

/** سؤال الموظف: فقاعةٌ هادئة في جهته. */
function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] whitespace-pre-line break-words rounded-2xl rounded-ee-md bg-muted px-3.5 py-2 leading-relaxed text-foreground">
        <span className="sr-only">سؤالك: </span>
        {text}
      </p>
    </div>
  )
}

/** ما قرأه سيمبول بأدواته: رقائق صغيرة تحت الجواب، لا أهداف. */
function AnswerNotes({ turn }: { turn: ChatTurn }) {
  if (!turn.tools.length) return null
  return (
    <ul aria-label="ما قرأه سيمبول" className="flex flex-wrap gap-1.5">
      {turn.tools.map((tool) => (
        <li key={`${tool.name}:${tool.input}`}
          className="inline-flex min-w-0 max-w-full items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-small leading-snug text-muted-foreground">
          <Search aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={2} />
          <span className="min-w-0">{toolLine(tool)}</span>
        </li>
      ))}
    </ul>
  )
}

/** جواب سيمبول (الحجم العادي): نصٌّ بلا فقاعة بجانب صورته، ثم ما قرأه، ثم زرّ الشاشة المقترحة. */
function SymbolMessage({ turn, onOpen }: { turn: ChatTurn; onOpen: (turn: ChatTurn) => void }) {
  return (
    <div className="flex items-start gap-2.5">
      <Avatar />
      <div className="flex min-w-0 flex-1 flex-col items-start gap-2">
        <p className={cn("whitespace-pre-line break-words leading-relaxed", turn.status === "ANSWER" ? "text-foreground" : "text-muted-foreground")}>
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

/** قبل أول سؤال: صورة سيمبول والتحية في الوسط. */
function Greeting({ userName, section }: { userName: string | null; section: string }) {
  return (
    <div className="flex flex-col items-center gap-3 pt-2 text-center">
      <Avatar large />
      <p className="text-lead font-semibold text-foreground">
        {userName ? `أهلاً ${userName}، ` : "أهلاً، "}كيف أساعدك في «{section}»؟
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
  const input = React.useRef<HTMLTextAreaElement>(null)
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

  // الحجم العادي: الحقل يكبر مع النصّ، ارتفاعه من محتواه حتى خمسة أسطر (`max-h-32`) ثم يمرّ داخله.
  React.useLayoutEffect(() => {
    const field = input.current
    if (!open || gaze || !field) return
    field.style.height = "auto"
    field.style.height = `${field.scrollHeight}px`
  }, [open, gaze, draft])

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
        // «افتح» وحده في نصف الشريط، واسم الشاشة في سطرٍ فوقه: «افتح «حملة جديدة»» لا يتّسع لنصفه في 320.
        <Button id="chat-answer-open" variant="secondary" iconEnd={ForwardArrow} aria-label={`افتح «${place.open!.label}»`} onClick={() => openPlace(place)}>
          افتح
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
              <p className="flex items-center gap-2.5 text-lead font-semibold text-foreground">
                <Avatar />
                <span className="min-w-0">{userName ? `أهلاً ${userName}، ` : "أهلاً، "}كيف أساعدك؟</span>
              </p>
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
                {/* سؤال الموظف فقاعةٌ هادئة في جهته بسطرٍ واحد، ثم صورة سيمبول واسمه، ثم جوابه نصّاً بعرض الورقة:
                    «السابق» و«التالي» تحته بعرضها. */}
                <div className="flex justify-end">
                  <p className="max-w-[85%] truncate rounded-2xl rounded-ee-md bg-card px-3 py-1.5 text-small text-foreground shadow-sm shadow-black/5 ring-1 ring-border">
                    <span className="sr-only">سؤالك: </span>
                    {latest.question}
                  </p>
                </div>
                <p className="flex items-center gap-2 text-small font-semibold text-foreground">
                  <Avatar />
                  سيمبول
                </p>
                <PagedText
                  key={latest.id}
                  label="جواب سيمبول"
                  text={latest.text}
                  perPage={{ gaze: 150, gazeShort: 80 }}
                  className={cn("leading-relaxed", latest.status === "ANSWER" ? "text-foreground" : "text-muted-foreground")}
                />
                <AnswerNotes turn={latest} />
                {place ? (
                  <p className="truncate text-small text-muted-foreground">
                    الشاشة المقترحة: <span className="text-foreground">{place.open!.label}</span>
                  </p>
                ) : null}
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

  // Enter يرسل وShift+Enter سطرٌ جديد؛ وأثناء تركيب الحروف (لوحة اليابانية والصينية) لا يرسل.
  function onComposerKey(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  const composer = (
    <form noValidate onSubmit={submit} className="flex w-full basis-full flex-col gap-2">
      {failure}
      <Field label={<span className="sr-only">سؤالك</span>} hint={hint} error={tooLong ? `السؤال أطول من ${chat.questionMax} حرف.` : null}>
        {/* صندوقٌ مدوّر: الحقل يكبر مع النصّ إلى خمسة أسطر، وزرّ الإرسال دائرةٌ في طرفه. */}
        <div className="flex items-end gap-2 rounded-[1.25rem] border border-control bg-card py-1.5 pe-1.5 ps-3.5 shadow-sm shadow-black/5 focus-within:border-primary">
          <Textarea
            ref={input}
            rows={1}
            value={draft}
            placeholder={`اسأل عن عملك في «${section}»`}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onComposerKey}
            className="max-h-32 min-h-0 flex-1 rounded-none border-0 bg-transparent px-0 py-1.5 shadow-none outline-none focus-visible:outline-none"
          />
          <Button
            type="submit"
            variant="primary"
            commit
            aria-label="أرسل"
            icon={ArrowUp}
            busy={pending !== null}
            disabled={!draft.trim() || tooLong || exhausted}
            className="size-ctl shrink-0 rounded-full p-0"
          />
        </div>
      </Field>
    </form>
  )

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="سيمبول"
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
      <div role="log" aria-label="المحادثة مع سيمبول" aria-live="polite" className="flex flex-col gap-5">
        {turns.length === 0 ? <Greeting userName={userName} section={section} /> : null}
        {turns.map((turn) => (
          <React.Fragment key={turn.id}>
            <UserBubble text={turn.question} />
            <SymbolMessage turn={turn} onOpen={openPlace} />
          </React.Fragment>
        ))}
        {pending !== null ? (
          <>
            <UserBubble text={pending} />
            <div className="flex items-start gap-2.5">
              <Avatar />
              <p className="leading-relaxed text-muted-foreground">سيمبول يكتب…</p>
            </div>
          </>
        ) : null}
        {turns.length === 0 && pending === null && chat.ready.length ? (
          <ul aria-label="أسئلةٌ جاهزة" className="flex flex-col gap-2">
            {chat.ready.map((question, index) => (
              <li key={question}>
                <Button commit width="full" iconEnd={ForwardArrow} disabled={exhausted} onClick={() => void send({ ready: index }, question)}
                  className="justify-between text-start font-normal">
                  {question}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        <div ref={end} />
      </div>
    </Sheet>
  )
}
