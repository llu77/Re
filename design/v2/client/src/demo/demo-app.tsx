/*
 * صفحة العرض
 * ==========
 * المكوّنات الحقيقية بالبيانات الثابتة في fixtures.ts، لمراجعة التصميم وقياسه
 * (tools/shoot.py). `?screen=` يختار الشاشة وحالتها، و`?size=large` الحجم الكبير كما في
 * التطبيق. كل ما فيها يعمل: الضغط ينتقل ويفتح ويختار كما في التطبيق، والطلبات تُجاب من
 * البيانات الثابتة بدل الخادم. لا تُبنى مع الإنتاج (vite.config.ts، `--mode demo`).
 */

import * as React from "react"
import { ArrowUpFromLine, FilePlus2, ReceiptText, SquarePen, Undo2 } from "lucide-react"

import { AppProviders } from "@/app/providers"
import type { ToolEntry } from "@/components/shell/tools-fab"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import type { AssistantApi } from "@/components/tools/assistant-tool"
import type { NotesApi } from "@/components/tools/notes-tool"
import type { ComboboxOption } from "@/components/ui/combobox"
import { useToast } from "@/components/ui/toast"
import { sizeFromUrl, useSize } from "@/lib/size"
import { WORKSPACES, type ProfessionCode } from "@/lib/workspace"
import { AccountScreen } from "@/screens/account"
import { SignInScreen, SignupSizeStep, WelcomeScreen } from "@/screens/auth"
import { CampaignBoard } from "@/screens/marketing-board"
import { PurchaseInvoice, type DraftLine, type PurchaseApi, type PurchaseInitial } from "@/screens/purchase-invoice"
import { ReturnFlow, type ReturnApi } from "@/screens/return-flow"
import { ExpensesScreen, StoreTotalsScreen } from "@/screens/store-screens"
import { SupportQueue, SupportTicket } from "@/screens/support"
import { WorkHome } from "@/screens/work-home"
import * as F from "@/demo/fixtures"

const ok = <T,>(value: T) => Promise.resolve(value)

/** خطوات التسجيل بعد شاشتي الإشعار (registration_spec §8.5): «كيف تستخدم الجهاز؟» أولاها. */
const SIGNUP_STEPS = [
  { id: "use", label: "طريقة الاستخدام" },
  { id: "name", label: "الاسم" },
  { id: "year", label: "سنة الميلاد" },
  { id: "month", label: "الشهر" },
  { id: "day", label: "اليوم" },
  { id: "profession", label: "المهنة" },
  { id: "email", label: "البريد" },
  { id: "review", label: "المراجعة" },
  { id: "password", label: "كلمة المرور" },
]

/* ── الواجهات البرمجية من البيانات الثابتة ─────────────────────────── */

const notesApi: NotesApi = {
  max: 20,
  maxLength: 280,
  load: () => ok({ ok: true as const, notes: F.NOTES }),
  add: (text) => ok({ ok: true as const, note: { id: `n-${text.length}-${F.NOTES.length}`, text, created_at: F.NOW } }),
  remove: () => ok({ ok: true as const }),
}

function assistantApi(initial: boolean): AssistantApi {
  return {
    remaining: 28,
    ask: () => ok({ ok: true as const, reply: F.ASSISTANT_REPLY }),
    initial: initial ? { question: F.ASSISTANT_QUESTION, reply: F.ASSISTANT_REPLY } : undefined,
  }
}

const purchaseApi: PurchaseApi = {
  searchItems: (query) => ok(F.searchItems(query)),
  searchSuppliers: (query) => ok(F.SUPPLIERS.filter((s) => !query.trim() || s.label.includes(query.trim()))),
  createItem: (input) =>
    ok({ ok: true as const, option: { value: `new-${input.name}`, label: input.name, description: "صنفٌ جديد" } as ComboboxOption }),
  review: () => ok({ ok: true as const, flags: [F.FLAG] }),
  record: () => ok({ ok: true as const, number: "ش-0044" }),
}

const returnApi: ReturnApi = {
  searchInvoices: (query) =>
    ok(
      F.INVOICES.filter((v) => !query.trim() || `${v.number} ${v.supplier}`.includes(query.trim()))
        .map((v) => ({ value: v.id, label: `${v.number} — ${v.supplier}` })),
    ),
  loadInvoice: () => ok({ ok: true as const, invoice: F.RETURN_INVOICE }),
  review: () => ok({ ok: true as const }),
}

const line = (key: string, item: string | null, query: string, quantity: string, unitCost: string): DraftLine => {
  const found = item ? F.ITEMS.find((i) => i.id === item)! : null
  return { key, item: found ? F.itemOption(found) : null, query: found ? found.name : query, quantity, unitCost }
}

const NEW_CHAIR: ComboboxOption = { value: "new-chair", label: "كرسي دوّار بمسند رأس", description: "صنفٌ جديد · قطعة" }

const PURCHASE: Record<string, PurchaseInitial> = {
  "purchase-combobox": {
    supplier: F.SUPPLIERS[0],
    number: "INV-77812",
    lines: [line("a", "i1", "", "10", "285"), line("b", null, "كرسي دوّار", "6", "")],
    openLine: "b",
    gazeStep: 1,
    activeLine: "b",
  },
  "purchase-create": {
    supplier: F.SUPPLIERS[0],
    number: "INV-77812",
    lines: [line("a", "i1", "", "10", "285"), line("b", null, "كرسي دوّار بمسند رأس", "6", "")],
    creating: { lineKey: "b", name: "كرسي دوّار بمسند رأس" },
    gazeStep: 1,
    activeLine: "b",
  },
  "purchase-flag": {
    supplier: F.SUPPLIERS[0],
    number: "INV-77812",
    lines: [line("a", "i1", "", "10", "285"), { key: "b", item: NEW_CHAIR, query: NEW_CHAIR.label, quantity: "6", unitCost: "5200" }, line("c", "i5", "", "20", "92")],
    stage: "review",
    flags: [F.FLAG],
  },
  "purchase-ready": {
    supplier: F.SUPPLIERS[0],
    number: "INV-77812",
    lines: [line("a", "i1", "", "10", "285"), { key: "b", item: NEW_CHAIR, query: NEW_CHAIR.label, quantity: "6", unitCost: "5200" }, line("c", "i5", "", "20", "92")],
    gazeStep: 1,
    activeLine: "c",
  },
}

/* ── أدوات المهنة في الزرّ العائم (inventory_spec §8: الأرجح أوّلاً) ───────── */

const CONTEXT_TOOLS: Record<ProfessionCode, ToolEntry[]> = {
  STOREKEEPER: [
    { id: "purchase", label: "فاتورة شراء جديدة", icon: ReceiptText, route: "#/inventory/purchases/new" },
    { id: "return", label: "مرتجع من فاتورة", icon: Undo2, route: "#/inventory/returns/new" },
    { id: "issue", label: "صرف من المخزون", icon: ArrowUpFromLine, route: "#/inventory/vouchers/issue" },
  ],
  MARKETING: [{ id: "new", label: "حملة جديدة", icon: FilePlus2, route: "#/marketing/new" }],
  SUPPORT: [{ id: "new", label: "تذكرة جديدة", icon: SquarePen, route: "#/support/tickets/new" }],
}

/* ── الشاشات ──────────────────────────────────────────────────────── */

interface Where {
  profession: ProfessionCode
  /** بند الرئيسية، أو "home"، أو null في «حسابي». */
  current: string | null
}

const PLACE: Record<string, Where> = {
  home: { profession: "STOREKEEPER", current: "home" },
  "marketing-home": { profession: "MARKETING", current: "home" },
  "support-home": { profession: "SUPPORT", current: "home" },
  totals: { profession: "STOREKEEPER", current: "totals" },
  "nav-open": { profession: "STOREKEEPER", current: "purchase" },
  "fab-sheet": { profession: "STOREKEEPER", current: "home" },
  "fab-vat": { profession: "STOREKEEPER", current: "purchase" },
  "fab-assistant": { profession: "STOREKEEPER", current: "return" },
  "fab-notes": { profession: "STOREKEEPER", current: "home" },
  "purchase-combobox": { profession: "STOREKEEPER", current: "purchase" },
  "purchase-create": { profession: "STOREKEEPER", current: "purchase" },
  "purchase-flag": { profession: "STOREKEEPER", current: "purchase" },
  "purchase-ready": { profession: "STOREKEEPER", current: "purchase" },
  return: { profession: "STOREKEEPER", current: "return" },
  expenses: { profession: "STOREKEEPER", current: "expenses" },
  account: { profession: "STOREKEEPER", current: null },
  "marketing-board": { profession: "MARKETING", current: "campaigns" },
  "support-queue": { profession: "SUPPORT", current: "open" },
  "support-ticket": { profession: "SUPPORT", current: "open" },
  "support-ticket-open": { profession: "SUPPORT", current: "open" },
}

const ROUTES: Record<string, string> = {
  "#/inventory": "home",
  "#/inventory/purchases/new": "purchase-ready",
  "#/inventory/returns/new": "return",
  "#/inventory/expenses": "expenses",
  "#/inventory/totals": "totals",
  "#/account": "account",
  "#/marketing": "marketing-home",
  "#/marketing/campaigns": "marketing-board",
  "#/support": "support-home",
  "#/support/tickets": "support-queue",
}

function Workspace({ screen, go }: { screen: string; go: (screen: string) => void }) {
  const toast = useToast()
  const { size } = useSize()
  const where = PLACE[screen]
  const workspace = WORKSPACES[where.profession]
  const tool = screen === "fab-vat" ? "vat" : screen === "fab-assistant" ? "assistant" : screen === "fab-notes" ? "notes" : null

  const navigate = (href: string) => {
    toast.dismiss()
    const next = ROUTES[href.split("?")[0]]
    if (next) go(next)
  }

  let body: React.ReactNode
  if (screen === "home" || screen === "marketing-home" || screen === "support-home" || screen === "fab-sheet" || screen === "fab-notes") {
    body = <WorkHome workspace={workspace} userName={F.USER} onNavigate={navigate} />
  } else if (screen === "totals" || screen === "nav-open") {
    body = (
      <StoreTotalsScreen
        totals={F.TOTALS}
        attention={F.ATTENTION}
        recent={F.INVOICES}
        onAttention={() => undefined}
        onOpenInvoice={() => go("purchase-flag")}
      />
    )
  } else if (screen.startsWith("purchase-") || screen === "fab-vat") {
    const key = screen === "fab-vat" ? "purchase-ready" : screen
    body = (
      <PurchaseInvoice
        key={`${key}-${size}`}
        userName={F.USER}
        vatRateBp={F.VAT_BP}
        units={F.UNITS}
        today={F.TODAY}
        api={purchaseApi}
        onDone={(number) => {
          toast.show({ title: `سُجّلت فاتورة الشراء ${number}.`, description: "زاد المخزون، وأُضيفت إلى المصاريف." })
          go("home")
        }}
        onCancel={() => go("home")}
        initial={PURCHASE[key]}
      />
    )
  } else if (screen === "return" || screen === "fab-assistant") {
    body = (
      <ReturnFlow
        vatRateBp={F.VAT_BP}
        api={returnApi}
        onCancel={() => go("home")}
        initial={{ step: 1, invoice: F.RETURN_INVOICE, quantities: { r1: 2, r2: 1 } }}
      />
    )
  } else if (screen === "expenses") {
    body = (
      <ExpensesScreen
        month="أكتوبر 2026"
        onPrevious={() => undefined}
        onNext={null}
        rows={F.EXPENSES}
        totals={F.EXPENSE_TOTALS}
        onOpen={() => undefined}
      />
    )
  } else if (screen === "account") {
    body = (
      <AccountScreen
        name={F.USER}
        profession={workspace.name}
        sizeNames={F.SIZE_NAMES}
        saveSize={() => ok(null)}
        onSources={() => undefined}
        onLogout={() => undefined}
        onDelete={() => undefined}
        initialChoice={size === "gaze" ? "compact" : "gaze"}
        initialView="size"
      />
    )
  } else if (screen === "marketing-board") {
    body = (
      <CampaignBoard
        campaigns={F.CAMPAIGNS}
        now={F.NOW}
        imageUrl={(c) => `/demo/campaign-${c.tone}.png`}
        onNew={() => undefined}
        onOpen={() => undefined}
      />
    )
  } else if (screen === "support-queue") {
    body = (
      <SupportQueue
        tab="new"
        tabs={F.TICKET_TABS}
        onTabChange={() => undefined}
        tickets={F.TICKETS}
        now={F.NOW}
        onNext={() => go("support-ticket-open")}
        onOpen={() => go("support-ticket-open")}
      />
    )
  } else {
    body = (
      <SupportTicket
        ticket={F.TICKETS[1]}
        messages={F.TICKET_MESSAGES}
        draft={F.TICKET_DRAFT}
        now={F.NOW}
        initialStep={screen === "support-ticket-open" ? 0 : 1}
        onBack={() => go("support-queue")}
        onDecide={(decision) => {
          toast.show({ title: decision.kind === "send" ? "أُرسل الردّ إلى فهد." : "حُفظ قرارك." })
          go("support-queue")
        }}
      />
    )
  }

  return (
    <WorkspaceShell
      key={screen}
      workspace={workspace}
      current={where.current}
      userName={F.USER}
      onNavigate={navigate}
      navOpen={screen === "nav-open"}
      tools={{
        userName: F.USER,
        context: CONTEXT_TOOLS[where.profession],
        vatRateBp: F.VAT_BP,
        assistant: assistantApi(screen === "fab-assistant"),
        notes: notesApi,
        supportContact: F.CONTACT,
        initialOpen: screen.startsWith("fab-"),
        initialTool: tool,
      }}
    >
      {body}
    </WorkspaceShell>
  )
}

function Screens({ initial }: { initial: string }) {
  const [screen, setScreen] = React.useState(initial)
  const { size, setSize } = useSize()
  const go = React.useCallback((next: string) => setScreen(next), [])
  React.useLayoutEffect(() => {
    document.body.dataset.screen = screen
  }, [screen])

  if (screen === "welcome") return <WelcomeScreen mode="open" onSignup={() => go("signup-size")} onLogin={() => go("signin")} />
  if (screen === "signin")
    return (
      <SignInScreen
        onSubmit={() => ok({ ok: false as const, message: "البريد أو كلمة المرور غير صحيحة.", refused: true })}
        onPasskey={() => undefined}
        onSignup={() => go("signup-size")}
        contact={F.CONTACT}
        initial={{ username: "sara@example.sa" }}
      />
    )
  if (screen === "signup-size")
    return (
      <SignupSizeStep
        step={0}
        steps={SIGNUP_STEPS}
        value={size}
        choices={F.UI_SIZES}
        onBack={() => go("welcome")}
        onNext={(mode) => {
          setSize(mode)
          go("home")
        }}
      />
    )
  if (!PLACE[screen]) return <p className="p-edge">لا شاشة باسم «{screen}».</p>
  return <Workspace screen={screen} go={go} />
}

export function DemoApp() {
  const params = new URLSearchParams(window.location.search)
  const screen = params.get("screen") ?? "welcome"
  return (
    <AppProviders size={sizeFromUrl() ?? "compact"}>
      <Screens initial={screen} />
    </AppProviders>
  )
}
