/*
 * مكتب الدعم الفني: الطلبات والكلمات
 * ==================================
 * كل ما يقرؤه المكتب ويكتبه تحت /api/support (routes_support.py)، ومراجعة الردّ والمقالة عبر المسار
 * المشترك /api/ai/review. الكتابة على تذكرةٍ أو مقالةٍ قائمة تحمل رقم الصفّ الذي رآه الموظف؛ والإنشاء
 * والرسالة والردّ تحمل `client_token`: الضغطة المكرّرة تعيد ما سُجّل ولا تسجّل مرّتين.
 *
 * الكلمات هنا لكل رمزٍ يرسله الخادم (الحالة، والأولوية، والفئة، والقناة، والأسباب): الخادم يرسل
 * الرموز، والواجهة تقولها بالعربية. ورسائل الخطأ تبقى من الخادم كما هي.
 */

import { api, type ApiResult } from "./api"

export const BASE = "#/support"

export type TicketStatus = "NEW" | "OPEN" | "PENDING" | "ESCALATED" | "RESOLVED" | "CLOSED"
export type Priority = "URGENT" | "HIGH" | "NORMAL" | "LOW"
export type Category = "ACCOUNT" | "SOFTWARE" | "HARDWARE" | "PRINTING" | "NETWORK" | "EMAIL" | "INSTALL" | "HOW_TO" | "OTHER"
export type Channel = "MESSAGING" | "EMAIL" | "PHONE" | "IN_PERSON" | "WEB_FORM" | "OTHER"
export type ReplyKind = "ANSWER" | "ASK_INFO" | "UPDATE"
export type DraftResult = "DRAFT" | "CANNOT_ANSWER" | "NOT_SUPPORT"
export type Preset = "SHORTER" | "SIMPLER" | "MORE_FORMAL" | "WARMER" | "ASK_INFO"
export type RejectReason = "WRONG_INFO" | "NOT_IN_KB" | "MISUNDERSTOOD" | "TONE" | "TOO_LONG" | "INCOMPLETE" | "OUTDATED_ARTICLE" | "OTHER"
export type EscalationTarget = "TIER2" | "SUPERVISOR" | "VENDOR" | "FIELD_TECH" | "OTHER_TEAM"
export type Resolution = "BY_PHONE" | "IN_PERSON" | "DUPLICATE" | "NOT_SUPPORT" | "NO_RESPONSE"
export type DismissReason = "FALSE_ALARM" | "EMPLOYER_APPROVED" | "KB_OUTDATED" | "OTHER"
export type ReleaseVia = "COPY" | "SHARE" | "SCRIPT"
export type QuestionCode = "ERROR_TEXT" | "WHEN_STARTED" | "DEVICE" | "SCOPE" | "STEPS" | "TRIED" | "SCREENSHOT"
export type TicketView = "open" | "pending" | "escalated" | "resolved" | "closed"
export type KbView = "published" | "attention" | "drafts" | "proposals" | "archived"
export type ArticleState = "DRAFT" | "PROPOSED" | "PUBLISHED" | "ARCHIVED" | "DISCARDED"

export interface Paged<T> {
  items: T[]
  page: number
  pages: number
  total: number
}

export interface Sla {
  kind: "FIRST_REPLY" | "RESOLVE"
  state: "ON_TRACK" | "DUE_SOON" | "BREACHED" | "PAUSED" | "MET"
  minutes: number | null
}

export interface TicketRow {
  id: string
  number: number
  status: TicketStatus
  priority: Priority
  category: Category | null
  channel: Channel
  customer_label: string | null
  subject: string | null
  preview: string | null
  sla: Sla
  badges: {
    draft_ready: boolean
    awaiting_confirmation: boolean
    reply_ready: boolean
    open_flags: number
    suggested_priority: Priority | null
  }
  row_version: number
  updated_at: string | null
}

export interface Message {
  id: string
  author: "CUSTOMER" | "AGENT" | "NOTE"
  body: string
  masked_count: number
  at: string | null
}

export interface Citation {
  article_id: string
  number: number
  title: string
  version: number
  quote: string
}

export interface Draft {
  id: string
  seq: number
  result: DraftResult
  reply_kind: ReplyKind | null
  body: string | null
  subject: string | null
  note_to_employee: string | null
  suggestion: {
    category: Category | null
    priority: Priority | null
    impact: string | null
    urgency: string | null
    security_concern: boolean | null
    escalate: EscalationTarget | null
    because: string | null
  }
  citations: Citation[]
  rejected: { reason: RejectReason; note: string | null } | null
  current: boolean
  language: "AR" | "EN" | null
  at: string | null
}

/** تنبيه قاعدةٍ من التطبيق على الردّ أو التذكرة، بنصّه من الخادم. */
export interface RuleFlag {
  id: string
  source: "RULE"
  code: string
  state: "OPEN" | "HEEDED" | "DISMISSED"
  message: string
  reason: string
  evidence: string | null
  dismiss_reason: DismissReason | null
}

/** ملاحظة سيمبول بشكل جواب /api/ai/review. */
export interface AiFlag {
  id: string
  check: string
  severity: string
  field: string | null
  line: number | null
  headline: string
  suggestion: string | null
  evidence: string[]
  decision: "EDIT" | "PROCEED" | "UNDO" | null
}

export interface Reply {
  id: string
  ticket_id: string
  kind: ReplyKind
  origin: "AS_IS" | "EDITED" | "MANUAL" | "TEMPLATE"
  core: string
  body: string
  body_sha256: string
  state: "READY" | "RELEASED" | "SENT" | "WITHDRAWN"
  release_via: ReleaseVia | null
  at: string | null
  needs_review: boolean
  /** مقالاتٌ أدرج الموظف خطواتها في الردّ؛ تعود إلى المحرّر بـ«عدّل الردّ». */
  kb_article_ids: string[]
  flags: RuleFlag[]
  ai_flags: AiFlag[]
}

export interface Allowed {
  draft: boolean
  send_as_is: boolean
  edit: boolean
  write: boolean
  ask_info: boolean
  reject: boolean
  escalate: boolean
  return_escalation: boolean
  resolve: boolean
  reopen: boolean
  follow_up: boolean
  note: boolean
}

export interface Ticket extends TicketRow {
  messages: Message[]
  language: "AR" | "EN"
  draft: Draft | null
  live_reply: Reply | null
  escalation: { target: EscalationTarget; note: string; at: string | null; returned_at: string | null; return_note: string | null } | null
  flags: RuleFlag[]
  follow_up_of: string | null
  resolution: string | null
  close_reason: string | null
  texts_purged: boolean
  allowed: Allowed
  ai: { draft_left_today: number | null }
}

export interface DeskNotice {
  current: string
  accepted: string | null
  title: string
  lines: string[]
}

export interface Home {
  counts: { decide: number; open: number; pending: number; escalated: number; kb_attention: number }
  notice: DeskNotice
}

export interface MaskPreview {
  text: string
  masked: { email: number; link: number; number: number }
  language: "AR" | "EN"
}

export interface ArticleRow {
  id: string
  number: number
  state: ArticleState
  title: string
  published_version: number | null
  latest_version: number
  needs_review: boolean
  needs_review_reason: string | null
  reuse_count: number
  row_version: number
  updated_at: string | null
}

export interface ArticleVersion {
  version: number
  title: string
  issue: string
  environment: string | null
  resolution: string
  cause: string | null
  origin: string
  at: string | null
}

export interface Article extends ArticleRow {
  versions: ArticleVersion[]
  source_ticket_id: string | null
  digest: string | null
  flags: AiFlag[]
}

export interface ArticleFields {
  title: string
  issue: string
  environment: string | null
  resolution: string
  cause: string | null
}

export interface Improve {
  rejections: { reason: RejectReason; count: number }[]
  gaps: { draft_id: string; ticket_id: string; ticket_number: number; reason: RejectReason; note: string | null; at: string | null }[]
  attention: ArticleRow[]
}

export interface Settings {
  signature: string | null
  sla: Record<Priority, { first_reply_minutes: number; resolve_minutes: number }>
  ai_usage: { kind: string; per_day: number | null; used_today: number | null }[]
  notice: DeskNotice
}

export interface Phrases {
  phrases: { id: string; ar: string; en: string }[]
  questions: { code: QuestionCode; ar: string; en: string }[]
  update_templates: { code: string; ar: string; en: string }[]
}

/** جواب /api/ai/review. */
export interface ReviewAnswer {
  subject: { kind: string; id: string; digest: string }
  review: { status: "DONE" | "PENDING" | "UNAVAILABLE"; reason: string | null; message: string | null }
  flags: AiFlag[]
}

/* ── الكلمات ─────────────────────────────────────────────────────── */

export const STATUS: Record<TicketStatus, string> = {
  NEW: "جديدة", OPEN: "مفتوحة", PENDING: "بانتظار العميل", ESCALATED: "مُصعَّدة", RESOLVED: "محلولة", CLOSED: "مغلقة",
}
export const PRIORITY: Record<Priority, string> = { URGENT: "عاجلة", HIGH: "عالية", NORMAL: "عادية", LOW: "منخفضة" }
export const PRIORITIES: Priority[] = ["URGENT", "HIGH", "NORMAL", "LOW"]
export const CATEGORY: Record<Category, string> = {
  ACCOUNT: "الحساب والدخول", SOFTWARE: "البرامج", HARDWARE: "الأجهزة", PRINTING: "الطباعة", NETWORK: "الشبكة والإنترنت",
  EMAIL: "البريد", INSTALL: "التثبيت والإعداد", HOW_TO: "طريقة الاستخدام", OTHER: "أخرى",
}
export const CATEGORIES = Object.keys(CATEGORY) as Category[]
export const CHANNEL: Record<Channel, string> = {
  MESSAGING: "واتساب أو رسائل", EMAIL: "بريد", PHONE: "مكالمة", IN_PERSON: "حضوري", WEB_FORM: "نموذج جهة العمل", OTHER: "أخرى",
}
export const CHANNELS = Object.keys(CHANNEL) as Channel[]
export const REPLY_KIND: Record<ReplyKind, string> = { ANSWER: "جوابٌ يحلّ المشكلة", ASK_INFO: "طلب معلومات", UPDATE: "إفادةٌ بالمتابعة" }
export const PRESET: Record<Exclude<Preset, "ASK_INFO">, string> = { SHORTER: "أقصر", SIMPLER: "أبسط", MORE_FORMAL: "أكثر رسمية", WARMER: "أدفأ" }
export const REJECT_REASON: Record<RejectReason, string> = {
  WRONG_INFO: "معلومةٌ خاطئة", NOT_IN_KB: "القاعدة لا تغطّي المسألة", MISUNDERSTOOD: "لم يفهم المشكلة", TONE: "الأسلوب غير مناسب",
  TOO_LONG: "أطول من اللازم", INCOMPLETE: "ناقصة", OUTDATED_ARTICLE: "المقالة قديمة", OTHER: "سببٌ آخر",
}
export const ESCALATION_TARGET: Record<EscalationTarget, string> = {
  TIER2: "فريق الدعم المتقدّم", SUPERVISOR: "المشرف", VENDOR: "المورّد أو الشركة المصنّعة", FIELD_TECH: "فنيّ ميداني", OTHER_TEAM: "فريقٌ آخر في جهة العمل",
}
export const RESOLUTION: Record<Resolution, string> = {
  BY_PHONE: "حُلّت بالهاتف", IN_PERSON: "حُلّت حضورياً", DUPLICATE: "مكرّرة", NOT_SUPPORT: "ليست طلب دعم", NO_RESPONSE: "لم يردّ العميل",
}
export const DISMISS_REASON: Record<DismissReason, string> = {
  FALSE_ALARM: "تنبيهٌ في غير محلّه", EMPLOYER_APPROVED: "جهة العمل موافقة", KB_OUTDATED: "المقالة قديمة", OTHER: "سببٌ آخر",
}
export const ARTICLE_STATE: Record<ArticleState, string> = {
  DRAFT: "مسودة", PROPOSED: "مقترحة", PUBLISHED: "منشورة", ARCHIVED: "مؤرشفة", DISCARDED: "متروكة",
}
export const AUTHOR: Record<Message["author"], string> = { CUSTOMER: "العميل", AGENT: "ردّك", NOTE: "ملاحظة داخلية" }
export const SLA_FIRST: Record<number, string> = { 30: "نصف ساعة", 60: "ساعة", 120: "ساعتان", 240: "٤ ساعات", 480: "٨ ساعات", 1440: "يوم" }
export const SLA_RESOLVE: Record<number, string> = { 240: "٤ ساعات", 480: "٨ ساعات", 1440: "يوم", 2880: "يومان", 4320: "٣ أيام", 7200: "٥ أيام" }
export const USAGE_KIND: Record<string, string> = {
  SUPPORT_DRAFT: "المسودات", SUPPORT_REPLY_REVIEW: "مراجعة الردود", SUPPORT_ARTICLE_PROPOSAL: "اقتراح المقالات", SUPPORT_ARTICLE_REVIEW: "مراجعة المقالات",
}

/** المدّة بالدقائق بكلماتٍ قصيرة: «35 د»، «3 س»، «2 ي». */
export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} د`
  if (minutes < 60 * 48) return `${Math.floor(minutes / 60)} س`
  return `${Math.floor(minutes / 1440)} ي`
}

/** شارة زمن الخدمة: النصّ ونغمته. */
export function slaText(sla: Sla): { text: string; tone: "neutral" | "info" | "warning" | "danger" | "success" } | null {
  if (sla.state === "MET") return null
  if (sla.state === "PAUSED") return { text: "الوقت متوقّف", tone: "neutral" }
  const minutes = sla.minutes ?? 0
  if (sla.state === "BREACHED") return { text: sla.kind === "FIRST_REPLY" ? `تأخّر الردّ ${duration(minutes)}` : `تأخّر الحلّ ${duration(minutes)}`, tone: "danger" }
  const text = sla.kind === "FIRST_REPLY" ? `متبقٍّ للردّ ${duration(minutes)}` : `متبقٍّ للحلّ ${duration(minutes)}`
  return { text, tone: sla.state === "DUE_SOON" ? "warning" : "info" }
}

/** عنوان التذكرة: «#12 · الموضوع»، أو أوّل رسالة العميل إن لم يكن موضوع. */
export function ticketTitle(row: Pick<TicketRow, "number" | "subject" | "preview">): string {
  const text = row.subject ?? (row.preview ? [...row.preview].slice(0, 60).join("") : "")
  return text ? `#${row.number} · ${text}` : `#${row.number}`
}

/* ── المسارات ────────────────────────────────────────────────────── */

export const ticketRoute = (id: string, sub = "") => `${BASE}/t/${id}${sub}`
export const articleRoute = (id: string, sub = "") => `${BASE}/kb/a/${id}${sub}`

/* ── الطلبات ─────────────────────────────────────────────────────── */

const ROOT = "/api/support"

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ""
}

const get = <T,>(path: string, params: Record<string, string | number | boolean | null | undefined> = {}) =>
  api<T>("GET", `${ROOT}${path}${query(params)}`)
const post = <T,>(path: string, body: unknown) => api<T>("POST", `${ROOT}${path}`, { json: body })

/** معرّفٌ للضغطة: الضغطة المكرّرة بالمعرّف نفسه تعيد ما سُجّل. */
export function clientToken(): string {
  return crypto.randomUUID()
}

export const home = () => get<Home>("/home")
export const decideQueue = (page: number, size: number) => get<Paged<TicketRow>>("/decide", { page, size })
export const listTickets = (view: TicketView, page: number, size: number) => get<Paged<TicketRow>>("/tickets", { view, page, size })
export const maskPreview = (text: string) => post<MaskPreview>("/mask-preview", { text })
export const createTicket = (body: {
  client_token: string
  channel: Channel
  text: string
  customer_label?: string | null
  subject?: string | null
  priority?: Priority | null
}) => post<Ticket>("/tickets", body)
export const getTicket = (id: string) => get<Ticket>(`/tickets/${id}`)
export const addMessage = (id: string, rowVersion: number, author: "CUSTOMER" | "NOTE", text: string, token: string) =>
  post<Ticket>(`/tickets/${id}/messages`, { client_token: token, expected_row_version: rowVersion, author, text })
export const followUp = (id: string, text: string, token: string) => post<Ticket>(`/tickets/${id}/follow-up`, { client_token: token, text })
export const classify = (id: string, rowVersion: number, body: { category: Category | null; priority: Priority; subject?: string | null; accept_draft_id?: string | null }) =>
  post<Ticket>(`/tickets/${id}/classification`, { expected_row_version: rowVersion, ...body })
export const requestDraft = (id: string, rowVersion: number, body: { presets?: Preset[]; hint?: string | null; redraft_of?: string | null } = {}) =>
  post<Ticket>(`/tickets/${id}/drafts`, { expected_row_version: rowVersion, presets: [], ...body })
export const rejectDraft = (draftId: string, reason: RejectReason, note: string | null) => post<Ticket>(`/drafts/${draftId}/reject`, { reason, note })
export const prepareReply = (id: string, rowVersion: number, body: {
  client_token: string
  kind: ReplyKind
  draft_id?: string | null
  core?: string | null
  template_questions?: QuestionCode[]
  kb_article_ids?: string[]
}) => post<Reply>(`/tickets/${id}/replies`, { expected_row_version: rowVersion, ...body })
export const ackFlag = (flagId: string, action: "HEEDED" | "DISMISSED", reason: DismissReason | null) =>
  post<RuleFlag>(`/flags/${flagId}`, { action, reason })
export const releaseReply = (replyId: string, via: ReleaseVia, bodySha256: string) => post<Ticket>(`/replies/${replyId}/release`, { via, body_sha256: bodySha256 })
export const confirmReply = (replyId: string, sent: boolean) => post<Ticket>(`/replies/${replyId}/confirm`, { sent })
export const escalate = (id: string, rowVersion: number, target: EscalationTarget, note: string, notifyCustomer: boolean) =>
  post<Ticket>(`/tickets/${id}/escalate`, { expected_row_version: rowVersion, target, note, notify_customer: notifyCustomer })
export const returnEscalation = (id: string, rowVersion: number, note: string | null) =>
  post<Ticket>(`/tickets/${id}/escalation-return`, { expected_row_version: rowVersion, note })
export const resolve = (id: string, rowVersion: number, resolution: Resolution, confirmed: boolean) =>
  post<Ticket>(`/tickets/${id}/resolve`, { expected_row_version: rowVersion, resolution, confirmed })
export const reopen = (id: string, rowVersion: number) => post<Ticket>(`/tickets/${id}/reopen`, { expected_row_version: rowVersion })

export const listArticles = (view: KbView, q: string, page: number, size = 20) => get<Paged<ArticleRow>>("/kb", { view, q: q.trim() || null, page, size })
export const getArticle = (id: string) => get<Article>(`/kb/${id}`)
export const createArticle = (fields: ArticleFields, token: string, sourceTicketId: string | null) =>
  post<Article>("/kb", { client_token: token, source_ticket_id: sourceTicketId, ...fields })
export const proposeArticle = (ticketId: string) => post<Article>("/kb/proposals", { ticket_id: ticketId })
export const addVersion = (id: string, rowVersion: number, fields: ArticleFields) => post<Article>(`/kb/${id}/versions`, { expected_row_version: rowVersion, ...fields })
export const publishArticle = (id: string, rowVersion: number, version: number) => post<Article>(`/kb/${id}/publish`, { expected_row_version: rowVersion, version })
export const setArticleState = (id: string, rowVersion: number, state: "ARCHIVED" | "DISCARDED") => post<Article>(`/kb/${id}/state`, { expected_row_version: rowVersion, state })
export const markReview = (id: string, rowVersion: number, needs: boolean) => post<Article>(`/kb/${id}/needs-review`, { expected_row_version: rowVersion, needs_review: needs })
export const improve = () => get<Improve>("/improve")

export const getSettings = () => get<Settings>("/settings")
export const saveSettings = (body: { signature?: string | null; sla?: Partial<Settings["sla"]> | null }) => api<Settings>("PUT", `${ROOT}/settings`, { json: body })
export const acceptNotice = (version: string) => post<null>("/notice", { version })
export const phrases = () => get<Phrases>("/phrases")

/** ضغطة «راجِع» على ردٍّ عدّله الموظف أو كتبه، أو على مقالةٍ قبل اعتمادها. */
export const review = (feature: "SUPPORT_REPLY_REVIEW" | "SUPPORT_ARTICLE_REVIEW", kind: "SUPPORT_REPLY" | "KB_ARTICLE", id: string) =>
  api<ReviewAnswer>("POST", "/api/ai/review", { json: { feature, subject_kind: kind, subject_id: id } })
/** قرار الموظف في ملاحظة سيمبول؛ الجواب القرار وحده (بلا الملاحظة)، فيُدمج فيها بمعرّفها. */
export interface FlagDecision {
  flag_id: string
  decision: AiFlag["decision"]
  decided_at: string
}

export const decideFlag = (flagId: string, choice: "EDIT" | "PROCEED" | "UNDO", digest: string) =>
  api<FlagDecision>("POST", `/api/ai/flags/${flagId}/decision`, { json: { choice, digest } })

/** يضع القرار في ملاحظته من القائمة. */
export function withDecision(flags: AiFlag[] | null, decided: FlagDecision): AiFlag[] | null {
  return flags?.map((flag) => (flag.id === decided.flag_id ? { ...flag, decision: decided.decision } : flag)) ?? null
}

export type Result<T> = ApiResult<T>
