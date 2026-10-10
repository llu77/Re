/*
 * المساعد سيمبول. شاشتان على مسارٍ واحد:
 *   • السؤال: سؤالان جاهزان (خياراتٌ تُختار ولا ترسل)، و«اكتب سؤالك» أسفل النهاية،
 *     و«اسأل سيمبول» أسفل البداية هو الاعتماد الوحيد — وتحته في شاشة الجواب «السابق»
 *     محجوزاً.
 *   • الجواب: اقتراحٌ بشارته ومصادره، مقسومٌ أجزاءً تُقلّب ولا تُمرَّر.
 * ما يُرسل إلى مزوّد النموذج يُقال قبل الإرسال، فوق الأسئلة.
 */
import * as React from "react"
import { ChevronLeft, ChevronRight, Globe, MessageSquareText, PenLine, RotateCcw, Send } from "lucide-react"

import { DwellArc } from "@/components/brand/dwell-arc"
import { ChoiceGroup, PersonaMark, SourceLine } from "@/components/eyework/parts"
import { BottomBar, Content, Screen, Step, TopBar } from "@/components/frame/screen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Callout } from "@/components/ui/callout"
import { Card } from "@/components/ui/card"
import { api, detail } from "@/lib/api"
import { PERSONA } from "@/lib/labels"
import { go } from "@/lib/router"
import { getState, setState, showAlert, useStore, type AssistantAnswer } from "@/lib/store"

interface Starters {
  suggestions: string[]
  left_today: number
}

function patchAssistant(next: Partial<ReturnType<typeof getState>["assistant"]>) {
  setState((s) => ({ assistant: { ...s.assistant, ...next } }))
}

export function Assistant({ context }: { context?: { kind: "tasks" | "skills"; n: number } }) {
  const answer = useStore((s) => s.assistant.answer)
  React.useEffect(() => {
    if (!context) return
    const portal = getState().portal
    const item = portal?.[context.kind][context.n - 1]
    if (item) patchAssistant({ picked: `كيف أؤدّي هذه المهمة: «${item.text}»؟`, answer: null, part: 0 })
    go("#/assistant", { replace: true })
  }, [context])
  return answer ? <AnswerView answer={answer} /> : <AskView />
}

function AskView() {
  const picked = useStore((s) => s.assistant.picked)
  const [starters, setStarters] = React.useState<Starters | null>(null)

  React.useEffect(() => {
    let current = true
    void api<Starters>("GET", "/api/assistant").then((result) => {
      if (current && result.status === 200) setStarters(result.data)
    })
    return () => {
      current = false
    }
  }, [])

  async function ask() {
    const question = getState().assistant.picked
    if (!question || getState().busy || getState().alert) return
    setState({ busy: true })
    const result = await api<AssistantAnswer>("POST", "/api/assistant/ask", { json: { question } })
    setState({ busy: false })
    if (result.status === 200 && result.data) patchAssistant({ answer: result.data, part: 0 })
    else if (result.status !== 401) showAlert("assistant", detail(result))
  }

  // سؤالان على الأكثر: ما كُتب أو جاء من بندٍ في البوابة أولاً، ثم الجاهز.
  const suggestions = starters?.suggestions ?? []
  const custom = picked !== null && !suggestions.includes(picked)
  const options = (custom ? [picked, ...suggestions] : suggestions)
    .slice(0, 2)
    .map((text) => ({ value: text, label: text }))

  return (
    <Screen name="assistant">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/")}>
            رجوع
          </Button>
        }
        step="المساعد"
      />
      <Content>
        <div className="flex flex-none items-center gap-3">
          <PersonaMark />
          <h2 tabIndex={-1} className="text-title">
            بماذا أساعدك اليوم؟
          </h2>
        </div>
        <p className="flex-none text-muted-foreground">جوابه اقتراحٌ بمصادره، تراجعه قبل العمل به.</p>
        <Callout id="assistant-privacy" icon={Globe} variant="plain" className="flex-none">
          يُرسَل السؤال وحده إلى Anthropic، بلا اسمك ولا بيانات حسابك.
        </Callout>
        {/*
          الأسئلة في أسفل المحتوى: أعلاه — حيث كانت بلاطة «اسأل سيمبول» في الرئيسية —
          نصٌّ لا يُضغط، فلا يقع خيارٌ تحت نظرٍ باقٍ عليها.
        */}
        <ChoiceGroup
          id="assistant-suggestions"
          label="أسئلةٌ جاهزة"
          columns={1}
          className="mt-auto pt-4"
          options={options}
          selected={picked}
          onPick={(value) => patchAssistant({ picked: value })}
        />
      </Content>
      <BottomBar
        start={
          <Button id="assistant-ask" commit variant="primary" icon={Send} disabled={!picked} onClick={ask}>
            اسأل {PERSONA}
          </Button>
        }
        end={
          <Button id="assistant-write" icon={PenLine} onClick={() => go("#/assistant/write")}>
            اكتب سؤالك
          </Button>
        }
      />
    </Screen>
  )
}

function AnswerView({ answer }: { answer: AssistantAnswer }) {
  const part = useStore((s) => s.assistant.part)
  const total = answer.parts.length
  return (
    <Screen name="assistant-answer">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/")}>
            رجوع
          </Button>
        }
        stepId="assistant-position"
        step={
          <Step arc={<DwellArc value={part + 1} total={total} />} noun="الجزء" n={part + 1} total={total} />
        }
        end={
          <Button id="assistant-again" icon={RotateCcw} onClick={() => patchAssistant({ answer: null, part: 0 })}>
            سؤالٌ آخر
          </Button>
        }
      />
      <Content>
        <p className="flex flex-none items-start gap-2 text-small text-muted-foreground">
          <MessageSquareText aria-hidden="true" strokeWidth={2.25} className="mt-[0.25em] size-[1.05em] shrink-0" />
          <span className="min-w-0">سؤالك: {answer.question}</span>
        </p>
        <Card className="min-h-0 gap-3">
          <div className="flex items-center gap-3">
            <PersonaMark className="size-10 rounded-xl shadow-none" />
            <h2 tabIndex={-1} className="font-display text-body font-bold">
              {PERSONA}
            </h2>
            <Badge variant="brand" className="ms-auto">
              اقتراح
            </Badge>
          </div>
          <p id="assistant-answer-text" className="whitespace-pre-line">
            {answer.parts[part]}
          </p>
        </Card>
        <SourceLine id="assistant-sources">{answer.sources.join(" · ")}</SourceLine>
        <p className="text-small text-muted-foreground">اقتراحٌ آليّ: راجِعه قبل العمل به، والقرار لك.</p>
      </Content>
      <BottomBar
        start={
          <Button
            id="assistant-previous"
            icon={ChevronRight}
            reserved={part <= 0}
            onClick={() => patchAssistant({ part: part - 1 })}
          >
            السابق
          </Button>
        }
        end={
          <Button
            id="assistant-next"
            variant="secondary"
            iconEnd={ChevronLeft}
            reserved={part >= total - 1}
            onClick={() => patchAssistant({ part: part + 1 })}
          >
            التالي
          </Button>
        }
      />
    </Screen>
  )
}

/* السؤال مكتوباً: نصٌّ حتى 300 حرف، يُحفظ في الذاكرة ويعود إلى شاشة السؤال ولا يُرسل. */
export function AssistantWrite() {
  const area = React.useRef<HTMLTextAreaElement>(null)
  const picked = useStore((s) => s.assistant.picked)
  const [left, setLeft] = React.useState(300 - (picked?.length ?? 0))
  return (
    <Screen name="assistant-write">
      <TopBar
        start={
          <Button icon={ChevronRight} data-back="" onClick={() => go("#/assistant")}>
            رجوع
          </Button>
        }
        end={
          <Button
            id="assistant-save"
            variant="secondary"
            onClick={() => {
              const text = (area.current?.value ?? "").replace(/\s+/g, " ").trim()
              patchAssistant({ picked: text || null })
              go("#/assistant")
            }}
          >
            احفظ السؤال
          </Button>
        }
      />
      <Content>
        <h2 tabIndex={-1} className="text-title">
          سؤالك لسيمبول
        </h2>
        <label htmlFor="assistant-text" className="text-small text-muted-foreground">
          عن عملك فقط، بلا بياناتٍ شخصية أو صحية. حتى 300 حرف.
        </label>
        <textarea
          ref={area}
          id="assistant-text"
          rows={4}
          maxLength={300}
          defaultValue={picked ?? ""}
          onInput={(event) => setLeft(300 - event.currentTarget.value.length)}
          className="field min-h-[9rem] resize-none rounded-control border-input bg-card px-4 py-3 text-control text-foreground outline-none focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-ring"
        />
        <p className="text-small text-muted-foreground">الأحرف المتبقية: {left}</p>
      </Content>
      <BottomBar />
    </Screen>
  )
}
