/*
 * «عدّل ثم أرسل» و«اكتب الردّ بنفسك»
 * ==================================
 * الردّ يُحرَّر بلا كتابةٍ تقريباً: «احذف جملاً» (كل جملةٍ زرٌّ يشطبها)، و«أضف عبارةً جاهزة» (من
 * /api/support/phrases بلغة العميل)، و«أضف من قاعدة المعرفة» (خطوات الحلّ من مقالةٍ منشورة، وتُحفظ المقالة
 * سنداً للردّ)، و«اكتب بنفسك»، و«اطلب من سيمبول تعديلها» (مسودةٌ جديدة). ثم نوع الردّ، ثم «جهّز الردّ»:
 * الخادم يضع التحية والتوقيع ويحسب تنبيهات القواعد، وتفتح شاشة الردّ.
 *
 *   • الحجم العادي: صفحةٌ واحدة: النوع، والنصّ، وأدوات التعديل تحته.
 *   • الحجم الكبير: النوع، ثم «ما الذي تغيّره؟»، ثم الأداة، ثم الردّ كما سيُجهَّز و«جهّز الردّ» في أعلاه.
 */

import * as React from "react"
import { BookOpen, Check, Eraser, MessageSquareQuote, NotebookPen, Search, Sparkles, X } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { Field, Input, Textarea } from "@/components/ui/input"
import { PagedText, sentences } from "@/components/ui/paged-text"
import { RadioCards } from "@/components/ui/radio-cards"
import { Stepper } from "@/components/ui/stepper"
import { REPLY_KIND, type ArticleRow, type Phrases, type ReplyKind, type Ticket } from "@/lib/support"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import { GazeHost, Picker } from "@/screens/inventory/common"

import { usePages, type Fail } from "./common"

type Tool = "sentences" | "phrases" | "kb" | "write" | "symbol"

const CORE_MIN = 20
const CORE_MAX = 1200
const KB_MAX = 3

export interface ComposeProps {
  ticket: Ticket
  /** من مسودة سيمبول («عدّل ثم أرسل») أو من صفحةٍ فارغة («اكتب الردّ بنفسك»). */
  fromDraft: boolean
  phrases: Phrases | null
  /** المقالات المنشورة المطابقة، أو رسالة الخادم إن تعذّر البحث. */
  onSearch: (query: string) => Promise<ArticleRow[] | string>
  /** خطوات الحلّ من النسخة المنشورة للمقالة، أو رسالة الخادم. */
  onResolution: (articleId: string) => Promise<{ text: string } | { fail: string }>
  onPrepare: (body: { kind: ReplyKind; core: string; kb_article_ids: string[]; draft_id: string | null }) => Promise<Fail>
  onRedraft: () => void
  onBack: () => void
  /** ردٌّ سُحب ليُعدَّل: نصّه ونوعه بدل المسودة. */
  initial?: { text: string; kind: ReplyKind; kbIds?: string[] } | null
}

/** يشطب الجمل المختارة، ويضمّ الباقي كما كان. */
function withoutSentences(text: string, removed: Set<number>): string {
  return sentences(text).filter((_, i) => !removed.has(i)).join("").replace(/\n{3,}/g, "\n\n").trim()
}

function append(text: string, addition: string): string {
  const base = text.trimEnd()
  return base ? `${base}\n${addition}` : addition
}

export function ComposeScreen({ ticket, fromDraft, phrases, onSearch, onResolution, onPrepare, onRedraft, onBack, initial = null }: ComposeProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const draft = fromDraft && ticket.draft?.current ? ticket.draft : null
  const english = ticket.language === "EN"
  const [kind, setKind] = React.useState<ReplyKind>(initial?.kind ?? draft?.reply_kind ?? "ANSWER")
  const [text, setText] = React.useState(initial?.text ?? draft?.body ?? "")
  const [tool, setTool] = React.useState<Tool | null>(null)
  const [removed, setRemoved] = React.useState<Set<number>>(new Set())
  const [kbIds, setKbIds] = React.useState<string[]>(initial?.kbIds ?? [])
  const [query, setQuery] = React.useState("")
  const [found, setFound] = React.useState<ArticleRow[] | string | null>(null)
  const [note, setNote] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)
  const [busy, setBusy] = React.useState(false)
  const [step, setStep] = React.useState(0)

  const parts = sentences(text)
  const sentenceItems = parts.map((sentence, index) => ({ sentence, index })).filter((item) => item.sentence.trim())
  const sentencePages = usePages(sentenceItems, { compact: 60, gaze: 3, gazeShort: 2 }, "صفحات الجمل")
  const phraseList = phrases?.phrases ?? []
  const phrasePages = usePages(phraseList, { compact: 20, gaze: 3, gazeShort: 2 }, "صفحات العبارات")
  const length = [...text.trim()].length
  const ready = length >= CORE_MIN && length <= CORE_MAX

  function applySentences() {
    setText(withoutSentences(text, removed))
    setRemoved(new Set())
    sentencePages.reset()
  }

  async function search() {
    if (query.trim().length < 2) return
    setBusy(true)
    setFound(await onSearch(query))
    setBusy(false)
  }

  async function insert(article: ArticleRow) {
    setBusy(true)
    setNote(null)
    const result = await onResolution(article.id)
    setBusy(false)
    if ("fail" in result) {
      setNote(result.fail)
      return
    }
    setText(append(text, result.text))
    setKbIds(kbIds.includes(article.id) ? kbIds : [...kbIds, article.id].slice(0, KB_MAX))
    setNote(`أُدرج حلّ KB-${article.number}.`)
  }

  async function prepare() {
    setBusy(true)
    setFail(null)
    const result = await onPrepare({ kind, core: text.trim(), kb_article_ids: kbIds, draft_id: draft?.id ?? null })
    setBusy(false)
    if (result) setFail(result)
  }

  const kindField = (
    <RadioCards<ReplyKind>
      label="نوع الردّ"
      options={(["ANSWER", "ASK_INFO", "UPDATE"] as ReplyKind[]).map((value) => ({ value, title: REPLY_KIND[value] }))}
      value={kind}
      onValueChange={setKind}
      columns={gaze ? 1 : 2}
      ids={{ ANSWER: "compose-kind-ANSWER", ASK_INFO: "compose-kind-ASK_INFO", UPDATE: "compose-kind-UPDATE" }}
    />
  )
  const textField = (
    <Field
      label="الردّ"
      hint={`${length} من ${CORE_MAX}. التحية باسم العميل والتوقيع يضيفهما التطبيق.`}
      error={fail?.field === "core" ? fail.message : null}
    >
      <Textarea id="compose-text" rows={gaze ? 4 : 8} maxLength={1500} value={text} onChange={(event) => setText(event.target.value)} />
    </Field>
  )

  const sentencesPanel = (
    <div className="flex flex-col gap-tg">
      <p className="text-small text-muted-foreground">اضغط جملةً لحذفها، ثم «احذف المختار».</p>
      <ul aria-label="جمل الردّ" className="flex flex-col gap-tg">
        {sentencePages.slice.map(({ sentence, index }) => {
          const off = removed.has(index)
          return (
            <li key={index}>
              <Button
                isValue
                aria-pressed={off}
                width="full"
                className={cn("justify-start text-start font-normal", off && "line-through text-muted-foreground")}
                onClick={() => {
                  const next = new Set(removed)
                  if (off) next.delete(index)
                  else next.add(index)
                  setRemoved(next)
                }}
              >
                <span className="line-clamp-2">{sentence.trim()}</span>
              </Button>
            </li>
          )
        })}
      </ul>
      {sentencePages.pager}
      <Button id="compose-apply-sentences" variant="secondary" icon={Eraser} disabled={removed.size === 0} onClick={applySentences} className="self-start gaze:w-full">
        احذف المختار ({removed.size})
      </Button>
    </div>
  )

  const phrasesPanel = (
    <div className="flex flex-col gap-tg">
      <ul aria-label="عبارات جاهزة" className="flex flex-col gap-tg">
        {phrasePages.slice.map((phrase) => (
          <li key={phrase.id}>
            <Button
              id={`compose-phrase-${phrase.id}`}
              isValue
              width="full"
              className="justify-start text-start font-normal"
              onClick={() => {
                setText(append(text, english ? phrase.en : phrase.ar))
                setNote("أُضيفت العبارة في آخر الردّ.")
              }}
            >
              <span className="line-clamp-2">{english ? phrase.en : phrase.ar}</span>
            </Button>
          </li>
        ))}
      </ul>
      {phrasePages.pager}
    </div>
  )

  const kbPanel = (
    <div className="flex flex-col gap-tg">
      <div className="flex items-end gap-tg">
        <Field label="ابحث في قاعدة المعرفة" className="flex-1">
          <Input id="compose-kb-search" type="search" autoComplete="off" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void search() }} />
        </Field>
        <Button id="compose-kb-go" icon={Search} busy={busy} disabled={query.trim().length < 2} onClick={() => void search()}>
          ابحث
        </Button>
      </div>
      {found === null ? null : typeof found === "string" ? <p role="alert" className="text-small font-semibold text-destructive">{found}</p> : found.length === 0 ? <p className="text-small text-muted-foreground">لا مقالة منشورة تطابق.</p> : (
        <ul aria-label="المقالات" className="flex flex-col gap-tg">
          {found.slice(0, gaze ? 2 : 5).map((article) => (
            <li key={article.id}>
              <Button id={`compose-insert-${article.number}`} width="full" icon={BookOpen} disabled={kbIds.length >= KB_MAX && !kbIds.includes(article.id)} onClick={() => void insert(article)} className="justify-start text-start">
                <span className="line-clamp-2">أدرج حلّ KB-{article.number} · {article.title}</span>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )

  const noteLine = note ? <p role="status" className="text-small font-semibold text-success">{note}</p> : null
  const failAlert = fail && fail.field !== "core" ? <Alert tone="danger" title="لم يُجهَّز الردّ" live>{fail.message}</Alert> : null
  const prepareButton = (
    <Button id="compose-prepare" variant="primary" size="lg" icon={Check} busy={busy} disabled={!ready} onClick={() => void prepare()} className="gaze:w-full">
      جهّز الردّ
    </Button>
  )

  /* ── الحجم الكبير ── */
  if (gaze) {
    // النصّ أوّلاً: فقرةٌ لا تُضغط تحت نظرٍ وصل من «عدّل ثم أرسل»؛ ثم الأداة بـ«التالي»، ثم «جهّز الردّ» في أعلى
    // آخر خطوة ونوع الردّ منتقٍ تحته.
    const steps = [
      { id: "text", label: "الردّ" },
      { id: "how", label: "التعديل" },
      { id: "tool", label: "الأداة" },
      { id: "done", label: "التجهيز" },
    ]
    // الحجم الكبير: بطاقتان في الصفّ، فالعنوان الطويل أقصر.
    const toolLabels: Record<Tool, string> = {
      sentences: "احذف جملاً", phrases: "أضف عبارةً جاهزة", kb: gaze ? "من قاعدة المعرفة" : "أضف من قاعدة المعرفة", write: "اكتب بنفسك",
      symbol: gaze ? "اطلب من سيمبول" : "اطلب من سيمبول تعديلها",
    }
    const toolOptions: Tool[] = draft ? ["sentences", "phrases", "kb", "write", "symbol"] : ["write", "phrases", "kb", "sentences"]
    const next = () => {
      if (step === 1 && tool === "symbol") {
        onRedraft()
        return
      }
      if (step === 1 && tool === "sentences") {
        setRemoved(new Set())
        sentencePages.reset()
      }
      setNote(null)
      setStep(step + 1)
    }
    const prev = () => {
      setFail(null)
      if (step === 0) onBack()
      else if (step === 3) setStep(1)
      else setStep(step - 1)
    }
    const kindPicker = (
      <GazeHost>
        <Picker id="compose-kind" label="نوع الردّ" options={(["ANSWER", "ASK_INFO", "UPDATE"] as ReplyKind[]).map((value) => ({ value, label: REPLY_KIND[value] }))} value={kind} onValueChange={(value) => setKind(value as ReplyKind)} />
      </GazeHost>
    )
    return (
      <Screen
        title={draft ? "عدّل ثم أرسل" : "اكتب الردّ"}
        above={<Stepper steps={steps} current={step} />}
        actions={
          <>
            <Button id="compose-prev" icon={BackIcon} onClick={prev}>
              {step === 0 ? "التذكرة" : step === 3 ? "عدّل" : "السابق"}
            </Button>
            {step === 3 ? <span aria-hidden="true" /> : (
              <Button id="compose-next" variant="secondary" iconEnd={NextIcon} disabled={(step === 1 && tool === null) || (step === 2 && tool === "sentences" && removed.size > 0)} onClick={next}>
                {step === 1 && tool === "symbol" ? "اطلب" : step === 2 ? "جهّز" : "التالي"}
              </Button>
            )}
          </>
        }
      >
        {step === 0 ? <PagedText text={text.trim() || "لا نصّ بعد. اختر في الخطوة التالية «اكتب بنفسك» أو عبارةً جاهزة."} label="الردّ" perPage={{ gaze: 240, gazeShort: 120 }} /> : null}
        {step === 1 ? (
          <RadioCards<Tool>
            label="ما الذي تغيّره؟"
            options={toolOptions.map((value) => ({ value, title: toolLabels[value] }))}
            value={tool}
            onValueChange={setTool}
            columns={1}
            gazeColumns={2}
            ids={Object.fromEntries(toolOptions.map((value) => [value, `compose-tool-${value}`]))}
          />
        ) : null}
        {step === 2 && tool === "sentences" ? sentencesPanel : null}
        {step === 2 && tool === "phrases" ? <>{phrasesPanel}{noteLine}</> : null}
        {step === 2 && tool === "kb" ? <>{kbPanel}{noteLine}</> : null}
        {step === 2 && tool === "write" ? textField : null}
        {step === 3 ? (
          <>
            {prepareButton}
            {failAlert}
            {fail?.field === "core" ? <Alert tone="danger" title="لم يُجهَّز الردّ" live>{fail.message}</Alert> : null}
            {ready ? null : <p className="text-small font-semibold text-warning">الردّ بين {CORE_MIN} و{CORE_MAX} حرفاً.</p>}
            {kindPicker}
          </>
        ) : null}
      </Screen>
    )
  }

  /* ── الحجم العادي ── */
  const tools: { id: Tool; label: string; icon: typeof Eraser }[] = [
    { id: "sentences", label: "احذف جملاً", icon: Eraser },
    { id: "phrases", label: "أضف عبارةً جاهزة", icon: MessageSquareQuote },
    { id: "kb", label: "أضف من قاعدة المعرفة", icon: BookOpen },
  ]
  return (
    <Screen
      title={draft ? "عدّل ثم أرسل" : "اكتب الردّ"}
      back={{ id: "compose-back", label: "التذكرة", onClick: onBack }}
      actions={<div className="ms-auto">{prepareButton}</div>}
    >
      {failAlert}
      {kindField}
      {textField}
      <div role="group" aria-label="أدوات التعديل" className="flex flex-wrap gap-tg">
        {tools.map((entry) => (
          <Button key={entry.id} id={`compose-tool-${entry.id}`} icon={tool === entry.id ? X : entry.icon} aria-expanded={tool === entry.id} onClick={() => {
            setNote(null)
            setRemoved(new Set())
            setTool(tool === entry.id ? null : entry.id)
          }}>
            {tool === entry.id ? "أغلق" : entry.label}
          </Button>
        ))}
        {draft ? (
          <Button id="compose-tool-symbol" icon={Sparkles} onClick={onRedraft}>
            اطلب من سيمبول تعديلها
          </Button>
        ) : null}
      </div>
      {noteLine}
      {tool === "sentences" ? sentencesPanel : null}
      {tool === "phrases" ? phrasesPanel : null}
      {tool === "kb" ? kbPanel : null}
      {kbIds.length ? <p className="text-small text-muted-foreground"><NotebookPen aria-hidden="true" className="me-1 inline size-4" />سند الردّ: {kbIds.length} من قاعدة المعرفة.</p> : null}
    </Screen>
  )
}
