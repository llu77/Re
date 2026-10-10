/*
 * المحادثة مع سيمبول بلا متصفّح: ما يُرسل مع كل سؤال (الشاشة، والسؤال أو فهرس الجاهز، وآخر ثلاثة أسئلةٍ
 * بأجوبتها)، وما يُعرض من الجواب (الفقاعة، وما قرأه بأدواته، وزرّ الشاشة المقترحة)، وصفحات الحجم الكبير.
 * القياس والهبوط في Chromium (test_chat.py).
 */

import { act, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AppProviders } from "@/app/providers"
import { ChatSheet } from "@/components/chat/chat-sheet"
import { ask, historyOf, remainingOf, toolLine, type ChatApi, type ChatTurn } from "@/lib/chat"
import { getState, resetState, setState } from "@/lib/store"
import { WORKSPACES } from "@/lib/workspace"

const CHAT: ChatApi = {
  screen: { kind: "HOME", id: null },
  ready: ["ماذا أتحقّق منه اليوم؟", "متى أطلب بضاعة؟"],
  questionMax: 300,
  remaining: 60,
}

function turn(id: number, extra: Partial<ChatTurn> = {}): ChatTurn {
  return { id, question: `سؤال ${id}`, status: "ANSWER", text: `جواب ${id}`, tools: [], open: null, ...extra }
}

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

const ANSWER = {
  status: "ANSWER", text: "رصيد الماء 2 كرتون، تحت حدّ الطلب.", question_sent: "هل أطلب ماءً؟",
  usage: { per_day: 60, used_today: 4 }, tools: [{ name: "ITEMS", label: "بحث في المنتجات", input: "ماء" }],
  open: { id: "stock", label: "المخزون" },
}

beforeEach(() => {
  resetState()
  // هاتفٌ بعرض 390 في الطول: لا استعلام وسائط يصدق (لا آيباد، ولا شاشةٌ قصيرة، ولا تقليل حركة).
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false, media: query, onchange: null,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
  })
})
afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ""
})

describe("what goes with a question", () => {
  it("sends the screen, the question and the last three turns as shown, and keeps the answer", async () => {
    setState({ chat: [turn(1), turn(2), turn(3), turn(4)] })
    const fetched = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, ANSWER))
    const result = await ask({ kind: "INVENTORY_ITEM", id: "abc" }, { question: "هل أطلب ماءً؟" })
    const body = JSON.parse((fetched.mock.calls[0][1] as RequestInit).body as string)
    expect(body).toEqual({
      screen: { kind: "INVENTORY_ITEM", id: "abc" },
      question: "هل أطلب ماءً؟",
      history: [2, 3, 4].map((n) => ({ question: `سؤال ${n}`, answer: `جواب ${n}` })),
    })
    expect(result.ok).toBe(true)
    const kept = getState().chat
    expect(kept).toHaveLength(5)
    expect(kept[4]).toMatchObject({ question: "هل أطلب ماءً؟", tools: ANSWER.tools, open: ANSWER.open })
    expect(remainingOf(CHAT, getState().chatUsage)).toBe(56)
  })

  it("sends a ready question by its index, without an id on a screen that has none", async () => {
    const fetched = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, ANSWER))
    await ask({ kind: "HOME", id: null }, { ready: 1 })
    expect(JSON.parse((fetched.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      screen: { kind: "HOME" }, ready_question: 1, history: [],
    })
  })

  it("forgets a conversation the server refuses, and says why", async () => {
    setState({ chat: [turn(1)] })
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      reply(422, { code: "INVALID", detail: "في المحادثة السابقة ما لا يُرسل؛ ابدأ محادثةً جديدة.", field: "history" }))
    const result = await ask({ kind: "HOME", id: null }, { question: "وبعدها؟" })
    expect(result).toEqual({ ok: false, message: "في المحادثة السابقة ما لا يُرسل؛ ابدأ محادثةً جديدة." })
    expect(getState().chat).toEqual([])
  })

  it("keeps the conversation on any other failure", async () => {
    setState({ chat: [turn(1)] })
    vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(503, { code: "AI_BUSY", detail: "سيمبول مشغول." }))
    expect(await ask({ kind: "HOME", id: null }, { question: "وبعدها؟" })).toEqual({ ok: false, message: "سيمبول مشغول." })
    expect(getState().chat).toHaveLength(1)
  })

  it("names each tool as the employee reads it", () => {
    expect(toolLine({ name: "ITEMS", label: "بحث في المنتجات", input: "ماء" })).toBe("بحث في المنتجات: «ماء»")
    expect(toolLine({ name: "LOW_STOCK", label: "المنتجات تحت حدّ الطلب", input: "" })).toBe("المنتجات تحت حدّ الطلب")
    expect(historyOf([turn(1)])).toEqual([{ question: "سؤال 1", answer: "جواب 1" }])
  })
})

function sheet(size: "compact" | "gaze", props: Partial<React.ComponentProps<typeof ChatSheet>> = {}) {
  const onNavigate = vi.fn()
  const onClose = vi.fn()
  const view = render(
    <AppProviders size={size}>
      <ChatSheet open onClose={onClose} chat={CHAT} workspace={WORKSPACES.STOREKEEPER} current="home" userName="سارة"
        onNavigate={onNavigate} {...props} />
    </AppProviders>,
  )
  return { ...view, onNavigate, onClose }
}

describe("the conversation sheet", () => {
  it("greets by name and offers the ready questions as presses that send", () => {
    sheet("compact")
    const log = screen.getByRole("log")
    expect(log.textContent).toContain("أهلاً سارة، كيف أساعدك")
    const ready = within(screen.getByRole("list", { name: "أسئلةٌ جاهزة" })).getAllByRole("button")
    expect(ready.map((b) => b.textContent)).toEqual(CHAT.ready)
    expect(ready.every((b) => b.hasAttribute("data-commit"))).toBe(true)
  })

  it("shows each turn with what Symbol read and the screen it suggests, which the employee opens", () => {
    setState({ chat: [turn(1, { tools: ANSWER.tools, open: ANSWER.open })] })
    const { onNavigate, onClose } = sheet("compact")
    const log = screen.getByRole("log")
    expect(within(log).getByText("بحث في المنتجات: «ماء»")).toBeTruthy()
    expect(within(log).queryByText("أسئلةٌ جاهزة")).toBeNull()
    const open = within(log).getByRole("button", { name: "افتح «المخزون»" })
    expect(open.hasAttribute("data-safe")).toBe(true)
    fireEvent.click(open)
    expect(onClose).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith("#/inventory/stock")
    // «محادثة جديدة» تنسى المحادثة.
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "محادثة جديدة" }))
    })
    expect(getState().chat).toEqual([])
  })

  it("opens on the gaze size at the start page: the ready questions on top and «اكتب سؤالك» last", () => {
    sheet("gaze", { onTools: () => {} })
    const dialog = screen.getByRole("dialog")
    const names = [...dialog.querySelectorAll("button")].map((b) => b.textContent?.trim())
    expect(names).toEqual([...CHAT.ready, "اكتب سؤالك", "الأدوات", "إغلاق"])
    fireEvent.click(screen.getByRole("button", { name: "اكتب سؤالك" }))
    expect(screen.getByRole("textbox")).toBeTruthy()
    const send = screen.getByRole("button", { name: "أرسل" })
    expect((send as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole("button", { name: "رجوع" })).toBeTruthy()
  })

  it("opens on the gaze size at the last answer, with the suggested screen in the footer's first place", () => {
    setState({ chat: [turn(1), turn(2, { open: ANSWER.open, tools: ANSWER.tools })] })
    const { onNavigate } = sheet("gaze", { onTools: () => {} })
    const dialog = screen.getByRole("dialog")
    expect(dialog.textContent).toContain("جواب 2")
    expect(dialog.textContent).not.toContain("جواب 1")
    const names = [...dialog.querySelectorAll("button")].map((b) => b.textContent?.trim())
    // «افتح» وحده في نصف الشريط، واسم الشاشة في سطرٍ فوقه وفي اسم الزرّ.
    expect(names).toEqual(["سؤالٌ جديد", "افتح", "إغلاق"])
    expect(dialog.textContent).toContain("الشاشة المقترحة: المخزون")
    fireEvent.click(screen.getByRole("button", { name: "افتح «المخزون»" }))
    expect(onNavigate).toHaveBeenCalledWith("#/inventory/stock")
  })
})
