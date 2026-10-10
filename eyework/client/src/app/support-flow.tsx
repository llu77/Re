/*
 * مكتب الدعم الفني: المسار
 * ========================
 * كل شاشةٍ حاويةٌ تقرأ ما تحتاجه من /api/support وتكتب إليه:
 *
 *   #/support                         الرئيسية: الأزرار الستة بأعدادها
 *   #/support/notice[?then=new]       إشعار المكتب، ثم ما طُلب قبله
 *   #/support/settings                التوقيع وأهداف زمن الخدمة والاستعمال
 *   #/support/decide                  بانتظار قراري
 *   #/support/open[?view=resolved|closed] · /pending · /escalated   قوائم التذاكر
 *   #/support/new                     تذكرة جديدة (بعد الإشعار)
 *   #/support/t/{id}[?draft=1]        التذكرة؛ و`draft=1` يطلب مسودة سيمبول حين تُفتح (بعد الحفظ أو ردّ العميل)
 *   #/support/t/{id}/compose?from=draft|blank · /ask · /escalate · /reject · /resolve · /classify · /redraft
 *   #/support/t/{id}/reply · /customer · /note · /follow-up
 *   #/support/kb[?view=…] · /kb/new[?ticket=…&n=…] · /kb/improve · /kb/a/{id}[/edit|/publish]
 *
 * ما يصل بعد انتقالٍ أحدث لطلبٍ أقدم لا يُرسم، ورسائل الخادم تُعرض كما هي.
 */

import * as React from "react"
import { MessageSquareQuote } from "lucide-react"

import { assistantApi, navigate } from "@/app/workspace"
import { Redirect } from "@/components/redirect"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import type { ToolEntry } from "@/components/shell/tools-sheet"
import { PhrasesTool } from "@/components/tools/phrases-tool"
import { Notice } from "@/components/ui/notice"
import { useToast } from "@/components/ui/toast"
import { detail, errorCode, type ApiResult } from "@/lib/api"
import { go } from "@/lib/router"
import { LONG_LIST_PAGE, useServerPage } from "@/lib/size"
import type { Choices, Me } from "@/lib/store"
import * as sup from "@/lib/support"
import { BASE, articleRoute, ticketRoute } from "@/lib/support"
import type { Workspace } from "@/lib/workspace"
import { AskInfoScreen, ClassifyScreen, EscalateScreen, RedraftScreen, RejectScreen, ResolveScreen } from "@/screens/support/actions"
import { failOf, type Fail } from "@/screens/support/common"
import { ComposeScreen } from "@/screens/support/compose"
import { DecideScreen, DeskNoticeScreen, SupportHome, TicketsScreen, noticeAccepted } from "@/screens/support/home"
import { ArticleEditor, ArticleScreen, ImproveScreen, KbListScreen, PublishScreen } from "@/screens/support/kb"
import { NewTicketScreen } from "@/screens/support/new-ticket"
import { ReplyScreen } from "@/screens/support/reply"
import { SettingsScreen } from "@/screens/support/settings"
import { TicketScreen, type TicketAction } from "@/screens/support/ticket"

type SetNotice = (message: string) => void

/** يقرأ من الخادم ويعيد القراءة حين تتغيّر المفاتيح؛ وما يصل بعد تغييرٍ أحدث يُهمل. */
function useLoad<T>(load: () => Promise<ApiResult<T>>, deps: React.DependencyList, setNotice: SetNotice, onMissing?: () => void) {
  const key = JSON.stringify(deps)
  const [state, setState] = React.useState<{ key: string; data: T | null }>({ key, data: null })
  const [tick, setTick] = React.useState(0)
  const reload = React.useCallback(() => setTick((t) => t + 1), [])
  const setData = React.useCallback((data: T | null) => setState({ key, data }), [key])
  React.useEffect(() => {
    let current = true
    void load().then((result) => {
      if (!current) return
      if (result.status === 200) setState({ key, data: result.data })
      else if (result.status === 404 && onMissing) onMissing()
      else if (result.status !== 401) setNotice(detail(result))
    })
    return () => {
      current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick])
  return { data: state.key === key ? state.data : null, setData, reload }
}

/** معرّف ضغطةٍ ثابتٌ حتى تنجح، ثم جديد: الضغطة المكرّرة تعيد ما سُجّل. */
function useToken(): [string, () => void] {
  const [token, setToken] = React.useState(sup.clientToken)
  return [token, React.useCallback(() => setToken(sup.clientToken()), [])]
}

const UUID = "[0-9a-f-]{36}"
const TICKET = new RegExp(`^/t/(${UUID})(?:/([a-z-]+))?$`)
const ARTICLE = new RegExp(`^/kb/a/(${UUID})(?:/([a-z-]+))?$`)

/** بند الرئيسية الذي تنتمي إليه الشاشة (للشريط والمساعدة). */
export function sectionOf(clean: string): string {
  const head = clean.replace(/^\//, "").split("/")[0]
  if (head === "decide" || head === "open" || head === "pending" || head === "escalated" || head === "new") return head
  if (head === "kb") return "knowledge"
  if (head === "t") return "open"
  return "home"
}

/* ── الرئيسية والإشعار والإعدادات ────────────────────────────────── */

function NoticeContainer({ home, then, onAccepted }: { home: sup.Home | null; then: string | null; onAccepted: () => void }) {
  if (!home) return null
  return (
    <DeskNoticeScreen
      notice={home.notice}
      onBack={() => go(BASE)}
      onAgree={async () => {
        const result = await sup.acceptNotice(home.notice.current)
        const fail = failOf(result)
        if (!fail) {
          onAccepted()
          go(then === "new" ? `${BASE}/new` : BASE, { replace: true })
        }
        return fail
      }}
    />
  )
}

function SettingsContainer({ setNotice }: { setNotice: SetNotice }) {
  const { data, setData } = useLoad(() => sup.getSettings(), [], setNotice)
  if (!data) return null
  return (
    <SettingsScreen
      settings={data}
      onBack={() => go(BASE)}
      onNotice={() => go(`${BASE}/notice`)}
      onSave={async (body) => {
        const result = await sup.saveSettings(body)
        if (result.status === 200 && result.data) setData(result.data)
        return failOf(result)
      }}
    />
  )
}

/* ── القوائم ─────────────────────────────────────────────────────── */

function DecideContainer({ setNotice }: { setNotice: SetNotice }) {
  const [page, setPage] = React.useState(0)
  const size = useServerPage(LONG_LIST_PAGE, setPage)
  const { data } = useLoad(() => sup.decideQueue(page + 1, size), [page, size], setNotice)
  return <DecideScreen data={data} page={page} onPage={setPage} onOpen={(row) => go(ticketRoute(row.id))} onOpenList={() => go(`${BASE}/open`)} onBack={() => go(BASE)} />
}

function TicketsContainer({ view, setNotice }: { view: sup.TicketView; setNotice: SetNotice }) {
  const [page, setPage] = React.useState(0)
  const size = useServerPage(LONG_LIST_PAGE, setPage)
  const { data } = useLoad(() => sup.listTickets(view, page + 1, size), [view, page, size], setNotice)
  const opening = view === "open" || view === "resolved" || view === "closed"
  return (
    <TicketsScreen
      view={view}
      data={data}
      page={page}
      onPage={setPage}
      onView={opening ? (next) => { setPage(0); go(next === "open" ? `${BASE}/open` : `${BASE}/open?view=${next}`, { replace: true }) } : null}
      onOpen={(row) => go(ticketRoute(row.id))}
      onNew={() => go(`${BASE}/new`)}
      onBack={() => go(BASE)}
    />
  )
}

/* ── تذكرة جديدة ─────────────────────────────────────────────────── */

async function previewOf(text: string): Promise<{ preview: sup.MaskPreview | null; fail: Fail }> {
  const result = await sup.maskPreview(text)
  if (result.status === 200 && result.data) return { preview: result.data, fail: null }
  if (result.status === 409 && errorCode(result) === "NOTICE") go(`${BASE}/notice`)
  return { preview: null, fail: failOf(result) }
}

function NewTicketContainer({ onCreated }: { onCreated: () => void }) {
  const [token] = useToken()
  return (
    <NewTicketScreen
      onBack={() => go(BASE)}
      onPreview={previewOf}
      onSave={async (body) => {
        const result = await sup.createTicket({ client_token: token, ...body })
        if ((result.status === 201 || result.status === 200) && result.data) {
          onCreated()
          go(`${ticketRoute(result.data.id)}?draft=1`, { replace: true })
          return null
        }
        if (result.status === 409 && errorCode(result) === "NOTICE") go(`${BASE}/notice?then=new`)
        return failOf(result)
      }}
    />
  )
}

/* ── التذكرة ─────────────────────────────────────────────────────── */

function TicketContainer({ id, sub, params, phrases, onChanged, setNotice }: {
  id: string
  sub: string | null
  params: URLSearchParams
  phrases: sup.Phrases | null
  onChanged: () => void
  setNotice: SetNotice
}) {
  const toast = useToast()
  const { data: ticket, setData } = useLoad(() => sup.getTicket(id), [id], setNotice, () => go(`${BASE}/open`, { replace: true }))
  const [drafting, setDrafting] = React.useState(false)
  const [draftFail, setDraftFail] = React.useState<string | null>(null)
  const [seed, setSeed] = React.useState<{ text: string; kind: sup.ReplyKind; kbIds?: string[] } | null>(null)
  const [replyToken, renewReplyToken] = useToken()
  const [messageToken, renewMessageToken] = useToken()
  const [review, setReview] = React.useState<{ replyId: string; reviewing: boolean; answer: sup.ReviewAnswer | null; late: sup.AiFlag[] | null } | null>(null)
  const autoDraft = params.get("draft") === "1"

  /** يقرأ التذكرة من جديد ويعرضها؛ وnull حين لم تُقرأ. */
  const refresh = React.useCallback(async (): Promise<sup.Ticket | null> => {
    const result = await sup.getTicket(id)
    if (result.status === 200 && result.data) {
      setData(result.data)
      return result.data
    }
    return null
  }, [id, setData])

  /** رسالة الخادم؛ والتذكرة تُقرأ من جديد حين تغيّرت منذ عرضها. */
  const failed = React.useCallback((result: ApiResult): Fail => {
    if (result.status === 409 && errorCode(result) === "STALE") void refresh()
    if (result.status === 409 && errorCode(result) === "NOTICE") go(`${BASE}/notice`)
    return failOf(result)
  }, [refresh])

  const requestDraft = React.useCallback(async (current: sup.Ticket, body: { presets?: sup.Preset[]; hint?: string | null; redraft_of?: string | null } = {}) => {
    setDrafting(true)
    setDraftFail(null)
    const result = await sup.requestDraft(id, current.row_version, body)
    setDrafting(false)
    if (result.status === 201 && result.data) {
      setData(result.data)
      onChanged()
      return
    }
    if (result.status === 409 && errorCode(result) === "NOTICE") {
      go(`${BASE}/notice`)
      return
    }
    setDraftFail(detail(result))
    void refresh()
  }, [id, onChanged, refresh, setData])

  // رسالة القرار السابق («رُفضت المسودة»، «صُعّدت») تبقى على التذكرة، وتُغلق حين تُفتح خطوةٌ منها: لا تغطّي
  // في الحجم الكبير ما في أعلى الخطوة («صعّد التذكرة»، «انسخ الردّ»).
  React.useEffect(() => {
    if (sub !== null) toast.dismiss()
  }, [sub, toast])

  // بعد الحفظ أو ردّ العميل: المسودة تُطلب حين تُفتح التذكرة، مرّةً واحدة (`draft=1` يُمحى من العنوان).
  React.useEffect(() => {
    if (!autoDraft || !ticket || ticket.id !== id) return
    go(ticketRoute(id), { replace: true })
    if (ticket.allowed.draft && !ticket.draft?.current) void requestDraft(ticket)
  }, [autoDraft, ticket, id, requestDraft])

  // مراجعة سيمبول لردٍّ عدّله الموظف أو كتبه: تبدأ وحدها حين تُفتح شاشة الردّ، مرّةً لكل ردّ.
  const live = ticket?.live_reply ?? null
  const runReview = React.useCallback(async (replyId: string) => {
    setReview({ replyId, reviewing: true, answer: null, late: null })
    const result = await sup.review("SUPPORT_REPLY_REVIEW", "SUPPORT_REPLY", replyId)
    const answer: sup.ReviewAnswer = result.status === 200 && result.data ? result.data
      : { subject: { kind: "SUPPORT_REPLY", id: replyId, digest: "" }, review: { status: "UNAVAILABLE", reason: null, message: detail(result) }, flags: [] }
    setReview({ replyId, reviewing: false, answer, late: null })
  }, [])
  React.useEffect(() => {
    if (sub !== "reply" || !live || live.state !== "READY" || !live.needs_review) return
    if (review?.replyId === live.id) return
    void runReview(live.id)
  }, [sub, live, review, runReview])

  if (!ticket || ticket.id !== id) return null
  const back = () => go(ticketRoute(id))
  const listOf = ticket.status === "PENDING" ? "pending" : ticket.status === "ESCALATED" ? "escalated" : "open"
  const backLabel = ticket.status === "PENDING" ? "بانتظار العميل" : ticket.status === "ESCALATED" ? "المُصعَّدة" : "التذاكر"

  async function prepare(body: { kind: sup.ReplyKind; draft_id?: string | null; core?: string | null; template_questions?: sup.QuestionCode[]; kb_article_ids?: string[] }): Promise<Fail> {
    const result = await sup.prepareReply(id, ticket!.row_version, { client_token: replyToken, ...body })
    if (result.status !== 201) return failed(result)
    renewReplyToken()
    setSeed(null)
    await refresh()
    go(ticketRoute(id, "/reply"))
    return null
  }

  async function addMessage(author: "CUSTOMER" | "NOTE", text: string): Promise<Fail> {
    const result = await sup.addMessage(id, ticket!.row_version, author, text, messageToken)
    if (result.status !== 201 || !result.data) return failed(result)
    renewMessageToken()
    setData(result.data)
    onChanged()
    go(author === "CUSTOMER" ? `${ticketRoute(id)}?draft=1` : ticketRoute(id))
    return null
  }

  const onAction = (action: TicketAction) => {
    const route: Record<TicketAction, string> = {
      "compose-draft": "/compose?from=draft", "compose-blank": "/compose?from=blank", ask: "/ask", escalate: "/escalate", reject: "/reject",
      resolve: "/resolve", customer: "/customer", note: "/note", classify: "/classify", redraft: "/redraft", reply: "/reply", "follow-up": "/follow-up",
    }
    if (action === "compose-draft" || action === "compose-blank") setSeed(null)
    go(ticketRoute(id, route[action]))
  }

  const draft = ticket.draft?.current ? ticket.draft : null

  switch (sub) {
    case null:
      return (
        <TicketScreen
          ticket={ticket}
          drafting={drafting}
          draftFail={draftFail}
          backLabel={backLabel}
          onBack={() => go(`${BASE}/${listOf}`)}
          onAction={onAction}
          onAckRule={async (flag, action, reason) => {
            const result = await sup.ackFlag(flag.id, action, reason)
            if (result.status !== 200) return failed(result)
            const fresh = await sup.getTicket(id)
            if (fresh.status === 200 && fresh.data) setData(fresh.data)
            return null
          }}
          onRequestDraft={() => void requestDraft(ticket, ticket.draft ? { redraft_of: ticket.draft.id } : {})}
          onSendAsIs={() => prepare({ kind: draft?.reply_kind ?? "ANSWER", draft_id: draft?.id ?? null, core: draft?.body ?? "" })}
          onAcceptSuggestion={async () => {
            if (!draft) return null
            const result = await sup.classify(id, ticket.row_version, {
              // الموضوع يبقى كما هو: الدالة تكتب ما يُرسل، فلو لم يُرسل لمُسح.
              category: draft.suggestion.category, priority: draft.suggestion.priority ?? ticket.priority, subject: ticket.subject, accept_draft_id: draft.id,
            })
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            return null
          }}
          onReopen={async () => {
            const result = await sup.reopen(id, ticket.row_version)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            onChanged()
            return null
          }}
          onReturnEscalation={async () => {
            const result = await sup.returnEscalation(id, ticket.row_version, null)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            onChanged()
            return null
          }}
        />
      )
    case "compose":
      return (
        <ComposeScreen
          key={`${params.get("from")}-${seed ? "seed" : "draft"}`}
          ticket={ticket}
          fromDraft={params.get("from") === "draft"}
          initial={seed}
          phrases={phrases}
          onBack={back}
          onRedraft={() => go(ticketRoute(id, "/redraft"))}
          onSearch={async (query) => {
            const result = await sup.listArticles("published", query, 1)
            return result.status === 200 && result.data ? result.data.items : []
          }}
          onResolution={async (articleId) => {
            const result = await sup.getArticle(articleId)
            if (result.status !== 200 || !result.data) return { fail: detail(result) }
            const published = result.data.versions.find((v) => v.version === result.data!.published_version)
            return published ? { text: published.resolution } : { fail: "لا نسخة منشورة من هذه المقالة." }
          }}
          onPrepare={(body) => prepare({ kind: body.kind, core: body.core, kb_article_ids: body.kb_article_ids, draft_id: params.get("from") === "draft" ? body.draft_id : null })}
        />
      )
    case "ask":
      return (
        <AskInfoScreen
          ticket={ticket}
          phrases={phrases}
          onBack={back}
          onQuestions={(codes) => prepare({ kind: "ASK_INFO", template_questions: codes })}
          onRedraft={ticket.allowed.draft ? () => {
            back()
            void requestDraft(ticket, { presets: ["ASK_INFO"], redraft_of: ticket.draft?.id ?? null })
          } : null}
        />
      )
    case "escalate":
      return (
        <EscalateScreen
          ticket={ticket}
          onBack={back}
          onEscalate={async (target, note, notify) => {
            const result = await sup.escalate(id, ticket.row_version, target, note, notify)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            onChanged()
            toast.show({ title: `صُعّدت التذكرة #${ticket.number}`, tone: "success" })
            go(notify ? ticketRoute(id, "/reply") : ticketRoute(id))
            return null
          }}
        />
      )
    case "reject":
      if (!draft) return <Redirect to={ticketRoute(id)} />
      return (
        <RejectScreen
          onBack={back}
          onReject={async (reason, note) => {
            const result = await sup.rejectDraft(draft.id, reason, note)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            const marked = (reason === "WRONG_INFO" || reason === "OUTDATED_ARTICLE") && draft.citations.length
            toast.show({ title: "رُفضت المسودة", description: marked ? `عُلّمت ${draft.citations.map((c) => `KB-${c.number}`).filter((v, i, a) => a.indexOf(v) === i).join(" و")} «تحتاج مراجعة».` : undefined, tone: "info" })
            back()
            return null
          }}
        />
      )
    case "resolve":
      return (
        <ResolveScreen
          ticket={ticket}
          onBack={back}
          onResolve={async (resolution, confirmed) => {
            const result = await sup.resolve(id, ticket.row_version, resolution, confirmed)
            if (result.status === 200 && result.data) {
              setData(result.data)
              onChanged()
              toast.show({ title: `حُلّت التذكرة #${ticket.number}`, tone: "success" })
              back()
              return { fail: null, unanswered: null }
            }
            const data = result.data as { code?: string; flag?: { message: string; reason: string }; confirmable?: boolean } | null
            if (result.status === 409 && data?.code === "UNANSWERED" && data.flag) {
              return { fail: null, unanswered: { message: data.flag.message, reason: data.flag.reason, confirmable: Boolean(data.confirmable) } }
            }
            return { fail: failed(result), unanswered: null }
          }}
        />
      )
    case "classify":
      return (
        <ClassifyScreen
          ticket={ticket}
          onBack={back}
          onSave={async (body) => {
            const result = await sup.classify(id, ticket.row_version, body)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            back()
            return null
          }}
        />
      )
    case "redraft":
      return (
        <RedraftScreen
          left={ticket.ai.draft_left_today}
          onBack={back}
          onRedraft={(presets, hint) => {
            back()
            void requestDraft(ticket, { presets, hint, redraft_of: ticket.draft?.id ?? null })
          }}
        />
      )
    case "reply": {
      if (!live) return <Redirect to={ticketRoute(id)} />
      const state = review?.replyId === live.id ? review : null
      return (
        <ReplyScreen
          ticket={ticket}
          reviewing={state?.reviewing ?? false}
          answer={state?.answer ?? null}
          late={state?.late ?? null}
          onBack={back}
          onReviewAgain={() => void runReview(live.id)}
          onDecideAi={async (flag, choice) => {
            const digest = state?.answer?.subject.digest || live.body_sha256
            const result = await sup.decideFlag(flag.id, choice, digest)
            if (result.status === 200 && result.data) {
              const decided = result.data
              setReview({ replyId: live.id, reviewing: false, answer: state?.answer ? { ...state.answer, flags: sup.withDecision(state.answer.flags, decided) ?? [] } : null, late: sup.withDecision(state?.late ?? null, decided) })
              if (!state?.answer) void refresh()
            } else {
              setNotice(detail(result))
            }
          }}
          onAckRule={async (flag, action, reason) => {
            const result = await sup.ackFlag(flag.id, action, reason)
            if (result.status !== 200) return failed(result)
            await refresh()
            return null
          }}
          onRelease={async (via) => {
            const result = await sup.releaseReply(live.id, via, live.body_sha256)
            if (result.status === 200 && result.data) {
              setData(result.data)
              return null
            }
            const data = result.data as { code?: string; flags?: sup.AiFlag[] } | null
            if (result.status === 409 && data?.code === "FLAGS_UNDECIDED" && data.flags) {
              setReview({ replyId: live.id, reviewing: false, answer: state?.answer ?? null, late: data.flags })
            }
            return failed(result)
          }}
          onConfirm={async (sent) => {
            const result = await sup.confirmReply(live.id, sent)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            onChanged()
            toast.show({ title: sent ? "سُجّل أنك أرسلت الردّ" : "سُحب الردّ", tone: sent ? "success" : "info" })
            back()
            return null
          }}
          onEdit={async () => {
            const result = await sup.confirmReply(live.id, false)
            if (result.status !== 200 || !result.data) return failed(result)
            setData(result.data)
            setSeed({ text: live.core, kind: live.kind, kbIds: live.kb_article_ids })
            go(ticketRoute(id, `/compose?from=${result.data.draft?.current ? "draft" : "blank"}`))
            return null
          }}
          onHeedRule={async (flag) => {
            const result = await sup.ackFlag(flag.id, "HEEDED", null)
            if (result.status !== 200) return failed(result)
            const fresh = await sup.getTicket(id)
            if (fresh.status === 200 && fresh.data) setData(fresh.data)
            setSeed({ text: live.core, kind: live.kind, kbIds: live.kb_article_ids })
            go(ticketRoute(id, `/compose?from=${fresh.data?.draft?.current ? "draft" : "blank"}`))
            return null
          }}
        />
      )
    }
    case "customer":
    case "note":
      return (
        <NewTicketScreen
          key={sub}
          title={sub === "customer" ? "ردّ العميل" : "ملاحظة داخلية"}
          channelFixed={ticket.channel}
          saveLabel={sub === "customer" ? "أضف ردّ العميل" : "احفظ الملاحظة"}
          onBack={back}
          onPreview={previewOf}
          onSave={(body) => addMessage(sub === "customer" ? "CUSTOMER" : "NOTE", body.text)}
        />
      )
    case "follow-up":
      return (
        <NewTicketScreen
          title={`متابعة للتذكرة #${ticket.number}`}
          channelFixed={ticket.channel}
          saveLabel="افتح تذكرة متابعة"
          onBack={back}
          onPreview={previewOf}
          onSave={async (body) => {
            const result = await sup.followUp(id, body.text, messageToken)
            if ((result.status !== 201 && result.status !== 200) || !result.data) return failed(result)
            renewMessageToken()
            onChanged()
            go(`${ticketRoute(result.data.id)}?draft=1`, { replace: true })
            return null
          }}
        />
      )
    default:
      return <Redirect to={ticketRoute(id)} />
  }
}

/* ── قاعدة المعرفة ───────────────────────────────────────────────── */

function KbListContainer({ params, setNotice }: { params: URLSearchParams; setNotice: SetNotice }) {
  const view = (params.get("view") as sup.KbView | null) ?? "published"
  const [query, setQuery] = React.useState("")
  const [page, setPage] = React.useState(0)
  const size = useServerPage(LONG_LIST_PAGE, setPage)
  const { data } = useLoad(() => sup.listArticles(view, query, page + 1, size), [view, query, page, size], setNotice)
  return (
    <KbListScreen
      view={view}
      query={query}
      data={data}
      page={page}
      onPage={setPage}
      onView={(next) => { setPage(0); go(next === "published" ? `${BASE}/kb` : `${BASE}/kb?view=${next}`, { replace: true }) }}
      onSearch={(q) => { setPage(0); setQuery(q.trim()) }}
      onOpen={(row) => go(articleRoute(row.id))}
      onNew={() => go(`${BASE}/kb/new`)}
      onImprove={() => go(`${BASE}/kb/improve`)}
      onBack={() => go(BASE)}
    />
  )
}

function NewArticleContainer({ params, onChanged }: { params: URLSearchParams; onChanged: () => void }) {
  const [token] = useToken()
  const ticketId = params.get("ticket")
  const number = Number(params.get("n")) || null
  return (
    <ArticleEditor
      article={null}
      sourceTicket={ticketId ? { id: ticketId, number } : null}
      onBack={() => go(ticketId ? `${BASE}/kb/improve` : `${BASE}/kb`)}
      onSave={async (fields) => {
        const result = await sup.createArticle(fields, token, ticketId)
        if (result.status !== 201 || !result.data) return failOf(result)
        onChanged()
        go(articleRoute(result.data.id), { replace: true })
        return null
      }}
      onPropose={ticketId ? async () => {
        const result = await sup.proposeArticle(ticketId)
        if (result.status !== 201 || !result.data) return failOf(result)
        onChanged()
        go(articleRoute(result.data.id), { replace: true })
        return null
      } : null}
    />
  )
}

function ArticleContainer({ id, sub, onChanged, setNotice }: { id: string; sub: string | null; onChanged: () => void; setNotice: SetNotice }) {
  const toast = useToast()
  const { data: article, setData } = useLoad(() => sup.getArticle(id), [id], setNotice, () => go(`${BASE}/kb`, { replace: true }))
  const [review, setReview] = React.useState<{ reviewing: boolean; answer: sup.ReviewAnswer | null; late: sup.AiFlag[] | null; digest: string | null } | null>(null)
  // مرّةً لكل نسخة (بصمتها): ما لم يُراجَع (سيمبول غير متاح، أو قبل إشعار المكتب) يُعاد بالزرّ لا وحده.
  const runReview = React.useCallback(async (digest: string | null) => {
    setReview({ reviewing: true, answer: null, late: null, digest })
    const result = await sup.review("SUPPORT_ARTICLE_REVIEW", "KB_ARTICLE", id)
    const answer: sup.ReviewAnswer = result.status === 200 && result.data ? result.data
      : { subject: { kind: "KB_ARTICLE", id, digest: "" }, review: { status: "UNAVAILABLE", reason: null, message: detail(result) }, flags: [] }
    setReview({ reviewing: false, answer, late: null, digest })
  }, [id])
  React.useEffect(() => {
    if (sub !== null) toast.dismiss()
  }, [sub, toast])
  const unpublished = article ? article.state !== "PUBLISHED" || article.published_version !== article.latest_version : false
  React.useEffect(() => {
    if (sub !== "publish" || !article || article.id !== id || !unpublished) return
    if (review && review.digest === article.digest) return
    void runReview(article.digest)
  }, [sub, article, id, unpublished, review, runReview])

  if (!article || article.id !== id) return null
  const back = () => go(articleRoute(id))
  const write = async (result: ApiResult<sup.Article>): Promise<Fail> => {
    if (result.status !== 200 || !result.data) return failOf(result)
    setData(result.data)
    onChanged()
    return null
  }
  if (sub === "edit") {
    return (
      <ArticleEditor
        article={article}
        sourceTicket={null}
        onPropose={null}
        onBack={back}
        onSave={async (fields) => {
          const fail = await write(await sup.addVersion(id, article.row_version, fields))
          if (!fail) {
            setReview(null)
            back()
          }
          return fail
        }}
      />
    )
  }
  if (sub === "publish") {
    if (!unpublished) return <Redirect to={articleRoute(id)} />
    return (
      <PublishScreen
        article={article}
        reviewing={review?.reviewing ?? false}
        answer={review?.answer ?? null}
        late={review?.late ?? null}
        onReviewAgain={() => void runReview(article.digest)}
        onBack={(edit) => go(articleRoute(id, edit ? "/edit" : ""))}
        onDecide={async (flag, choice) => {
          const digest = review?.answer?.subject.digest || article.digest || ""
          const result = await sup.decideFlag(flag.id, choice, digest)
          if (result.status === 200 && result.data) {
            const decided = result.data
            setReview(review ? { ...review, answer: review.answer ? { ...review.answer, flags: sup.withDecision(review.answer.flags, decided) ?? [] } : null, late: sup.withDecision(review.late, decided) } : null)
            if (!review?.answer) setData({ ...article, flags: sup.withDecision(article.flags, decided) ?? [] })
          } else {
            setNotice(detail(result))
          }
        }}
        onPublish={async () => {
          const result = await sup.publishArticle(id, article.row_version, article.latest_version)
          if (result.status === 200 && result.data) {
            setData(result.data)
            onChanged()
            toast.show({ title: `اعتُمدت KB-${article.number}`, description: "يقرؤها سيمبول الآن ويقتبس منها.", tone: "success" })
            back()
            return null
          }
          const data = result.data as { code?: string; flags?: sup.AiFlag[] } | null
          if (result.status === 409 && data?.code === "FLAGS_UNDECIDED" && data.flags) {
            setReview({ reviewing: false, answer: review?.answer ?? null, late: data.flags, digest: review?.digest ?? null })
          }
          return failOf(result)
        }}
      />
    )
  }
  if (sub !== null) return <Redirect to={articleRoute(id)} />
  return (
    <ArticleScreen
      article={article}
      onBack={() => go(`${BASE}/kb`)}
      onEdit={() => go(articleRoute(id, "/edit"))}
      onPublish={() => go(articleRoute(id, "/publish"))}
      onMarkReview={async (needs) => write(await sup.markReview(id, article.row_version, needs))}
      onState={async (state) => write(await sup.setArticleState(id, article.row_version, state))}
    />
  )
}

function ImproveContainer({ setNotice }: { setNotice: SetNotice }) {
  const { data } = useLoad(() => sup.improve(), [], setNotice)
  return (
    <ImproveScreen
      data={data}
      onBack={() => go(`${BASE}/kb`)}
      onWrite={(gap) => go(`${BASE}/kb/new?ticket=${gap.ticket_id}&n=${gap.ticket_number}`)}
      onOpenArticle={(row) => go(articleRoute(row.id))}
    />
  )
}

/* ── المسار ──────────────────────────────────────────────────────── */

export function SupportFlow({ path, choices, me, workspace }: { path: string; choices: Choices; me: Me; workspace: Workspace }) {
  const toast = useToast()
  const [notice, setNoticeState] = React.useState<string | null>(null)
  const setNotice = React.useCallback((message: string) => setNoticeState(message), [])
  const rel = path.slice(BASE.length)
  const [clean, search = ""] = rel.split("?")
  const params = React.useMemo(() => new URLSearchParams(search), [search])
  const home = useLoad(() => sup.home(), [], setNotice)
  const phrases = useLoad(() => sup.phrases(), [], setNotice)
  const section = sectionOf(clean)

  // الأعداد تُقرأ من جديد عند العودة إلى الرئيسية وإلى القوائم: ما تغيّر في الطريق يظهر.
  const homeKey = clean === "" || clean === "/" || ["/decide", "/open", "/pending", "/escalated", "/kb"].includes(clean) ? clean || "/" : ""
  const reloadHome = home.reload
  const lastHomeKey = React.useRef(homeKey)
  React.useEffect(() => {
    if (homeKey && homeKey !== lastHomeKey.current) reloadHome()
    lastHomeKey.current = homeKey
  }, [homeKey, reloadHome])

  const loadPhrases = React.useCallback(async () => {
    const result = await sup.phrases()
    if (result.status !== 200 || !result.data) return null
    return {
      phrases: result.data.phrases,
      questions: result.data.questions.map((q) => ({ id: q.code, ar: q.ar, en: q.en })),
    }
  }, [])
  const tools: ToolEntry[] = [
    { id: "phrases", label: "عبارات وأسئلة جاهزة", description: "تُنسخ وتُلصق في الردّ", icon: MessageSquareQuote, panel: () => <PhrasesTool load={loadPhrases} /> },
  ]

  const ticket = clean.match(TICKET)
  const article = clean.match(ARTICLE)
  const accepted = noticeAccepted(home.data?.notice)
  let content: React.ReactNode = null
  if (clean === "" || clean === "/") {
    content = <SupportHome workspace={workspace} userName={me.display_name} home={home.data} onNavigate={navigate} />
  } else if (clean === "/notice") {
    // الموافقة تُرى في الرئيسية فور عودتها: لا يبقى «اقرأ الإشعار» حتى تصل القراءة الجديدة.
    content = <NoticeContainer home={home.data} then={params.get("then")} onAccepted={() => {
      if (home.data) home.setData({ ...home.data, notice: { ...home.data.notice, accepted: home.data.notice.current } })
      home.reload()
    }} />
  } else if (clean === "/settings") {
    content = <SettingsContainer setNotice={setNotice} />
  } else if (clean === "/decide") {
    content = <DecideContainer setNotice={setNotice} />
  } else if (clean === "/open") {
    const view = params.get("view")
    content = <TicketsContainer view={view === "resolved" || view === "closed" ? view : "open"} setNotice={setNotice} />
  } else if (clean === "/pending" || clean === "/escalated") {
    content = <TicketsContainer view={clean.slice(1) as sup.TicketView} setNotice={setNotice} />
  } else if (clean === "/new") {
    content = !home.data ? null : accepted ? <NewTicketContainer onCreated={home.reload} /> : <Redirect to={`${BASE}/notice?then=new`} />
  } else if (ticket) {
    content = <TicketContainer key={ticket[1]} id={ticket[1]} sub={ticket[2] ?? null} params={params} phrases={phrases.data} onChanged={home.reload} setNotice={setNotice} />
  } else if (clean === "/kb") {
    content = <KbListContainer params={params} setNotice={setNotice} />
  } else if (clean === "/kb/new") {
    content = <NewArticleContainer params={params} onChanged={home.reload} />
  } else if (clean === "/kb/improve") {
    content = <ImproveContainer setNotice={setNotice} />
  } else if (article) {
    content = <ArticleContainer key={article[1]} id={article[1]} sub={article[2] ?? null} onChanged={home.reload} setNotice={setNotice} />
  } else {
    content = <Redirect to={BASE} />
  }

  return (
    <Notice message={notice} onAck={() => setNoticeState(null)}>
      <WorkspaceShell
        workspace={workspace}
        current={section}
        userName={me.display_name}
        onNavigate={(href) => {
          toast.dismiss()
          navigate(href)
        }}
        tools={{
          userName: me.display_name,
          assistant: assistantApi(me, choices, ticket ? "SUPPORT_TICKET" : "HOME", ticket ? ticket[1] : null),
          supportContact: choices.support_contact,
          context: tools,
        }}
      >
        {content}
      </WorkspaceShell>
    </Notice>
  )
}
