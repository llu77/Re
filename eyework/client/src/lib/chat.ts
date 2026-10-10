/*
 * المحادثة مع سيمبول
 * ==================
 * الخادم لا يحفظ المحادثة: كل سؤالٍ طلبٌ مستقلّ (POST /api/ai/assistant) يحمل نوع الشاشة ومعرّفها لا
 * بياناتها، والسؤال (أو فهرس سؤالٍ جاهز)، وآخر ثلاثة أسئلةٍ بأجوبتها كما عُرضت (`history`). فالمحادثة
 * هنا، في مخزن الصفحة (lib/store.ts) لا في الجهاز: تبقى بين الشاشات وتُغلق الورقة وتُفتح عليها، وتذهب
 * بتحديث الصفحة أو الخروج أو «محادثة جديدة».
 *
 * سيمبول يقرأ بأدواته ولا يغيّر شيئاً: ما استعمله منها يعود في `tools` (الاسم الذي يراه الموظف
 * والمدخل)، والشاشة التي يقترح فتحها في `open` (معرّف بند الرئيسية في lib/workspace.ts)، فيظهر زرٌّ
 * يضغطه الموظف بنفسه.
 */

import { api, detail, errorField } from "./api"
import { getState, setState } from "./store"

/** الشاشة التي يُسأل منها، كما يعرفها سجلّ الشاشات في الخادم (assistant.SCREENS). */
export type ChatScreenKind = "HOME" | "CAMPAIGN" | "INVENTORY_ITEM" | "INVENTORY_PURCHASE" | "INVENTORY_COUNT" | "SUPPORT_TICKET"

export interface ChatScreen {
  kind: ChatScreenKind
  id: string | null
}

/** أداة قراءةٍ استعملها سيمبول للجواب: «بحث في المنتجات: «ماء»». */
export interface ChatTool {
  name: string
  label: string
  input: string
}

export interface ChatTurn {
  id: number
  /** السؤال كما أُرسل بعد الإخفاء («[رقم]» مكان الهاتف)، أو السؤال الجاهز بنصّه. */
  question: string
  status: "ANSWER" | "DONT_KNOW" | "OUT_OF_SCOPE"
  text: string
  tools: ChatTool[]
  /** شاشةٌ يقترح فتحها: معرّف بند الرئيسية واسمه. */
  open: { id: string; label: string } | null
}

/** ما يحتاجه زرّ المحادثة وورقتها من الشاشة التي يُفتح منها. */
export interface ChatApi {
  screen: ChatScreen
  /** الأسئلة الجاهزة لهذه الشاشة من الخادم (/api/choices). */
  ready: string[]
  questionMax: number
  /** ما بقي من أسئلة اليوم كما قاله الخادم عند الإقلاع. */
  remaining: number | null
}

/** أسئلةٌ سابقة تُرسل مع السؤال: ثلاثٌ على الأكثر (assistant_prompt.HISTORY_MAX). */
export const HISTORY_MAX = 3
/** ما يُعرض من المحادثة: الأحدث فقط، فلا تكبر الصفحة بلا حدّ. */
export const KEPT_TURNS = 20

interface AssistantAnswer {
  status: ChatTurn["status"]
  text: string
  question_sent: string
  usage: { per_day: number; used_today: number }
  tools: ChatTool[]
  open: { id: string; label: string } | null
}

export type AskInput = { question: string } | { ready: number }

export type AskResult = { ok: true; turn: ChatTurn } | { ok: false; message: string }

/** آخر ثلاثة أسئلةٍ بأجوبتها كما عُرضت: ما يُرسل مع السؤال. */
export function historyOf(turns: ChatTurn[]): { question: string; answer: string }[] {
  return turns.slice(-HISTORY_MAX).map((turn) => ({ question: turn.question, answer: turn.text }))
}

/** سطر الأداة كما يراه الموظف. */
export function toolLine(tool: ChatTool): string {
  return tool.input ? `${tool.label}: «${tool.input}»` : tool.label
}

/** ما بقي من أسئلة اليوم: من آخر جوابٍ إن وُجد، وإلا مما قاله الخادم عند الإقلاع. */
export function remainingOf(chat: ChatApi, usage: { per_day: number; used_today: number } | null): number | null {
  if (usage) return Math.max(0, usage.per_day - usage.used_today)
  return chat.remaining
}

let sequence = 0

/**
 * سؤالٌ واحد بسياق الشاشة والمحادثة السابقة. الجواب يُلحق بالمحادثة في المخزن؛ والخطأ يُعاد برسالة
 * الخادم كما هي. ومحادثةٌ سابقة يرفضها الخادم (`field = history`) تُنسى، فيصحّ السؤال التالي.
 */
export async function ask(screen: ChatScreen, input: AskInput): Promise<AskResult> {
  const before = getState().chat
  const body = {
    screen: screen.id ? { kind: screen.kind, id: screen.id } : { kind: screen.kind },
    ...("ready" in input ? { ready_question: input.ready } : { question: input.question }),
    history: historyOf(before),
  }
  const result = await api<AssistantAnswer>("POST", "/api/ai/assistant", { json: body })
  if (result.status !== 200 || !result.data) {
    if (errorField(result) === "history") setState({ chat: [] })
    return { ok: false, message: detail(result) }
  }
  const answer = result.data
  sequence += 1
  const turn: ChatTurn = {
    id: sequence,
    question: answer.question_sent,
    status: answer.status,
    text: answer.text,
    tools: answer.tools ?? [],
    open: answer.open ?? null,
  }
  setState((current) => ({ chat: [...current.chat, turn].slice(-KEPT_TURNS), chatUsage: answer.usage }))
  return { ok: true, turn }
}

/** «محادثة جديدة»: لا سؤال سابق يُرسل بعدها. */
export function resetChat() {
  setState({ chat: [] })
}
