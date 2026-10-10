/*
 * قاعدة المعرفة: القائمة، والمقالة، والمحرّر، والاعتماد، و«تحسين المسودات»
 * =======================================================================
 * المقالات المنشورة وحدها يقرؤها سيمبول ويقتبس منها. المقالة بهيكل KCS: المشكلة كما يصفها العميل، والبيئة،
 * والحلّ خطوةً خطوة، والسبب. كل تعديلٍ نسخةٌ جديدة لا تُقرأ حتى تُعتمد؛ و«اعتمد» يراجعه سيمبول أولاً
 * (/api/ai/review بالأداة SUPPORT_ARTICLE_REVIEW) وملاحظاته تنتظر قرار الموظف قبل الاعتماد.
 * و«تحسين المسودات»: لماذا رُفضت المسودات، والتذاكر التي لم تجد القاعدة لها جواباً (منها تُكتب مقالة، أو
 * يقترحها سيمبول من التذكرة)، والمقالات التي تحتاج نظرة.
 */

import * as React from "react"
import { Archive, BookOpen, CheckCircle2, FilePlus2, Flag, FlagOff, Lightbulb, PencilLine, RefreshCw, Save, Search, Trash2 } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { AIFlag } from "@/components/ui/ai-flag"
import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { Field, Input, Textarea } from "@/components/ui/input"
import { PagedText } from "@/components/ui/paged-text"
import { Stepper } from "@/components/ui/stepper"
import { Tabs } from "@/components/ui/tabs"
import { formatDay } from "@/lib/format"
import {
  ARTICLE_STATE, REJECT_REASON, REVIEW_REASON, type AiFlag, type Article, type ArticleFields, type ArticleRow, type Improve, type KbView, type Paged, type ReviewAnswer,
} from "@/lib/support"
import { LONG_LIST_PAGE, useSize } from "@/lib/size"

import type { Fail } from "./common"

const STATE_TONE: Record<ArticleRow["state"], "success" | "info" | "neutral" | "warning"> = {
  PUBLISHED: "success", DRAFT: "neutral", ARCHIVED: "neutral", DISCARDED: "neutral",
}

function rowLine(row: ArticleRow): string {
  const parts = [ARTICLE_STATE[row.state]]
  if (row.state === "PUBLISHED" && row.published_version !== row.latest_version) parts.push("نسخةٌ جديدة لم تُعتمد")
  if (row.needs_review) parts.push("تحتاج مراجعة")
  if (row.reuse_count) parts.push(`استُعملت ${row.reuse_count} مرة`)
  return parts.join(" · ")
}

function ArticleTable({ caption, rows, total, page, onPage, onOpen, empty }: {
  caption: string
  rows: ArticleRow[]
  /** مجموع صفوف الخادم إن كانت صفحاتها منه؛ بلا قيمةٍ تُقسَّم الصفوف هنا. */
  total?: number
  page: number
  onPage: (page: number) => void
  onOpen: (row: ArticleRow) => void
  empty: React.ReactNode
}) {
  return (
    <DataTable<ArticleRow>
      caption={caption}
      rows={rows}
      rowKey={(row) => row.id}
      columns={[
        { id: "title", header: "المقالة", cell: (row) => `KB-${row.number} · ${row.title}` },
        { id: "state", header: "الحال", cell: (row) => rowLine(row) },
      ]}
      primary={(row) => `KB-${row.number} · ${row.title}`}
      secondary={rowLine}
      trailing={(row) => <Badge tone={row.needs_review ? "warning" : STATE_TONE[row.state]} className="gaze:hidden">{row.needs_review ? "تحتاج مراجعة" : ARTICLE_STATE[row.state]}</Badge>}
      onOpen={onOpen}
      openLabel={(row) => `افتح KB-${row.number}`}
      pageSize={LONG_LIST_PAGE}
      page={page}
      onPageChange={onPage}
      total={total}
      empty={empty}
    />
  )
}

/* ── القائمة ─────────────────────────────────────────────────────── */

export function KbListScreen({ view, query, data, page, onPage, onView, onSearch, onOpen, onNew, onImprove, onBack }: {
  view: KbView
  query: string
  data: Paged<ArticleRow> | null
  page: number
  onPage: (page: number) => void
  onView: (view: KbView) => void
  onSearch: (query: string) => void
  onOpen: (row: ArticleRow) => void
  onNew: () => void
  onImprove: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [text, setText] = React.useState(query)
  const table = data === null ? null : (
    <ArticleTable
      caption="المقالات"
      rows={data.items}
      total={data.total}
      page={page}
      onPage={onPage}
      onOpen={onOpen}
      empty={
        <EmptyState
          icon={BookOpen}
          title={query ? "لا مقالة تطابق" : view === "published" ? "لا مقالات منشورة بعد" : "لا شيء هنا"}
          // في الحجم الكبير «مقالة جديدة» في الصفّ العلوي وحده: زرٌّ ثانٍ بالاسم نفسه هدفٌ زائد في شاشةٍ لا تتّسع.
          action={query || gaze ? undefined : <Button variant="primary" icon={FilePlus2} onClick={onNew}>مقالة جديدة</Button>}
        />
      }
    />
  )
  return (
    <Screen
      title="قاعدة المعرفة"
      back={gaze ? undefined : { id: "kb-back", label: "الرئيسية", onClick: onBack }}
      end={{ id: "kb-new", label: "مقالة جديدة", icon: FilePlus2, onClick: onNew }}
    >
      {gaze ? null : (
        <form className="flex items-end gap-tg" onSubmit={(event) => { event.preventDefault(); onSearch(text) }}>
          <Field label="ابحث" className="flex-1">
            <Input id="kb-search" type="search" autoComplete="off" maxLength={200} value={text} onChange={(event) => { setText(event.target.value); if (!event.target.value) onSearch("") }} />
          </Field>
          <Button id="kb-search-go" type="submit" icon={Search} disabled={text.trim().length < 2}>ابحث</Button>
        </form>
      )}
      {query ? table : (
        <Tabs
          items={[{ id: "published", label: "المنشورة" }, { id: "attention", label: "تحتاج نظرة" }, { id: "drafts", label: "المسودات" }, { id: "archived", label: "المؤرشفة" }]}
          value={view}
          onValueChange={(id) => onView(id as KbView)}
          label="المقالات"
        >
          {table}
        </Tabs>
      )}
      <Button id="kb-improve" icon={Lightbulb} onClick={onImprove} className="self-start gaze:w-full">
        تحسين المسودات
      </Button>
    </Screen>
  )
}

/* ── المقالة ─────────────────────────────────────────────────────── */

export function articleText(v: Article["versions"][number]): string {
  return [
    `المشكلة: ${v.issue}`,
    v.environment ? `البيئة: ${v.environment}` : null,
    `الحلّ:\n${v.resolution}`,
    v.cause ? `السبب: ${v.cause}` : null,
  ].filter(Boolean).join("\n\n")
}

export function ArticleScreen({ article, onEdit, onPublish, onMarkReview, onState, onBack }: {
  article: Article
  onEdit: () => void
  onPublish: () => void
  onMarkReview: (needs: boolean) => Promise<Fail>
  onState: (state: "ARCHIVED" | "DISCARDED") => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)
  // الحجم الكبير: المقالة صفحةٌ تُقرأ، وإجراءاتها صفحةٌ ثانية («الإجراءات» في خانة النهاية السفلية، وخانتها في
  // صفحة الإجراءات فارغة فلا يقع تحت النظر ما لم يُقصد).
  const [actionsPage, setActionsPage] = React.useState(false)
  const latest = article.versions[0]
  const unpublished = article.state !== "PUBLISHED" || article.published_version !== article.latest_version
  async function run(id: string, action: () => Promise<Fail>) {
    setBusy(id)
    setFail(null)
    setFail(await action())
    setBusy(null)
  }
  const actions: React.ReactNode[] = []
  if (article.state !== "DISCARDED") actions.push(<Button key="edit" id="article-edit" icon={PencilLine} onClick={onEdit}>عدّل</Button>)
  if (article.state !== "DISCARDED" && unpublished) actions.push(<Button key="publish" id="article-publish" variant="secondary" icon={CheckCircle2} onClick={onPublish}>اعتمد</Button>)
  if (article.state === "PUBLISHED") {
    actions.push(article.needs_review
      ? <Button key="fixed" id="article-fixed" icon={FlagOff} busy={busy === "review"} onClick={() => void run("review", () => onMarkReview(false))}>أُصلحت</Button>
      : <Button key="review" id="article-needs-review" icon={Flag} busy={busy === "review"} onClick={() => void run("review", () => onMarkReview(true))}>علّمها تحتاج مراجعة</Button>)
    actions.push(<Button key="archive" id="article-archive" icon={Archive} busy={busy === "archive"} onClick={() => void run("archive", () => onState("ARCHIVED"))}>أرشف</Button>)
  }
  if (article.state === "DRAFT") {
    actions.push(<Button key="discard" id="article-discard" variant="danger-outline" icon={Trash2} busy={busy === "discard"} onClick={() => void run("discard", () => onState("DISCARDED"))}>تجاهل المسودة</Button>)
  }
  const facts = (
    <p className="text-small text-muted-foreground">
      النسخة {latest.version}
      {article.published_version ? ` · المنشورة ${article.published_version}` : " · لم تُنشر بعد"}
      {latest.at ? ` · ${formatDay(latest.at)}` : ""}
      {article.needs_review ? ` · تحتاج مراجعة${article.needs_review_reason ? `: ${REVIEW_REASON[article.needs_review_reason] ?? ""}` : ""}` : ""}
    </p>
  )
  return (
    <Screen
      title={`KB-${article.number} · ${latest.title}`}
      above={<Badge tone={article.needs_review ? "warning" : STATE_TONE[article.state]} className="self-start">{article.needs_review ? "تحتاج مراجعة" : ARTICLE_STATE[article.state]}</Badge>}
      back={gaze ? undefined : { id: "article-back", label: "قاعدة المعرفة", onClick: onBack }}
      actions={
        gaze ? (
          actionsPage ? (
            <>
              <Button id="article-text" icon={BackIcon} onClick={() => setActionsPage(false)}>المقالة</Button>
              <span aria-hidden="true" />
            </>
          ) : (
            <>
              <Button id="article-prev" icon={BackIcon} onClick={onBack}>القائمة</Button>
              {actions.length ? <Button id="article-actions" iconEnd={NextIcon} onClick={() => setActionsPage(true)}>الإجراءات</Button> : <span aria-hidden="true" />}
            </>
          )
        ) : undefined
      }
    >
      {fail ? <Alert tone="danger" title="لم يتمّ" live>{fail.message}</Alert> : null}
      {gaze ? (
        // صفحة الإجراءات بأزرارها وحدها: الحال في الشارة فوق العنوان، وسطر النسخ والتاريخ في الحجم العادي.
        actionsPage ? null : (
          <PagedText text={articleText(latest)} label="المقالة" perPage={{ gaze: 170, gazeShort: 90 }} />
        )
      ) : (
        <>
          {facts}
          <dl className="flex flex-col gap-tg rounded-card bg-card shadow-card p-pad text-flow">
            <div><dt className="text-small font-semibold text-muted-foreground">المشكلة كما يصفها العميل</dt><dd>{latest.issue}</dd></div>
            {latest.environment ? <div><dt className="text-small font-semibold text-muted-foreground">البيئة</dt><dd>{latest.environment}</dd></div> : null}
            <div><dt className="text-small font-semibold text-muted-foreground">الحلّ</dt><dd className="whitespace-pre-line">{latest.resolution}</dd></div>
            {latest.cause ? <div><dt className="text-small font-semibold text-muted-foreground">السبب</dt><dd>{latest.cause}</dd></div> : null}
          </dl>
        </>
      )}
      {actions.length && (!gaze || actionsPage) ? <div className="flex flex-wrap gap-tg gaze:grid gaze:grid-cols-2">{actions}</div> : null}
    </Screen>
  )
}

/* ── المحرّر ─────────────────────────────────────────────────────── */

const EMPTY: ArticleFields = { title: "", issue: "", environment: null, resolution: "", cause: null }

export function ArticleEditor({ article, sourceTicket, onSave, onBack }: {
  /** المقالة التي تُضاف إليها نسخة، أو null لمقالةٍ جديدة. */
  article: Article | null
  /** التذكرة التي تُكتب منها المقالة («ثغرات القاعدة»)، أو null. */
  sourceTicket: { id: string; number: number | null } | null
  onSave: (fields: ArticleFields) => Promise<Fail>
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const latest = article?.versions[0]
  const [fields, setFields] = React.useState<ArticleFields>(latest ? { title: latest.title, issue: latest.issue, environment: latest.environment, resolution: latest.resolution, cause: latest.cause } : EMPTY)
  const [step, setStep] = React.useState(0)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [fail, setFail] = React.useState<Fail>(null)
  const set = (key: keyof ArticleFields) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setFields({ ...fields, [key]: event.target.value })
  const error = (key: string) => (fail?.field === key ? fail.message : null)
  async function run(id: string, action: () => Promise<Fail>) {
    setBusy(id)
    setFail(null)
    setFail(await action())
    setBusy(null)
  }
  const clean = (): ArticleFields => ({
    title: fields.title.trim(), issue: fields.issue.trim(), resolution: fields.resolution.trim(),
    environment: fields.environment?.trim() || null, cause: fields.cause?.trim() || null,
  })
  const title = (
    <Field label="العنوان" error={error("title")} required>
      <Input id="article-title" autoComplete="off" maxLength={80} value={fields.title} onChange={set("title")} />
    </Field>
  )
  const issue = (
    <Field label="المشكلة كما يصفها العميل" error={error("issue")} required>
      <Textarea id="article-issue" rows={gaze ? 2 : 3} maxLength={400} value={fields.issue} onChange={set("issue")} />
    </Field>
  )
  const resolution = (
    <Field label="الحلّ خطوةً خطوة" error={error("resolution")} required>
      <Textarea id="article-resolution" rows={gaze ? 5 : 6} maxLength={4000} value={fields.resolution} onChange={set("resolution")} />
    </Field>
  )
  const environment = (
    <Field label="البيئة: الجهاز والنظام والبرنامج" error={error("environment")}>
      <Input id="article-environment" autoComplete="off" maxLength={300} value={fields.environment ?? ""} onChange={set("environment")} />
    </Field>
  )
  const cause = (
    <Field label="السبب" error={error("cause")}>
      <Input id="article-cause" autoComplete="off" maxLength={400} value={fields.cause ?? ""} onChange={set("cause")} />
    </Field>
  )
  const save = (
    <Button id="article-save" variant="primary" size="lg" icon={Save} busy={busy === "save"} disabled={!fields.title.trim() || !fields.issue.trim() || !fields.resolution.trim()} onClick={() => void run("save", () => onSave(clean()))} className="gaze:w-full">
      {article ? "احفظ نسخةً جديدة" : "احفظ المقالة"}
    </Button>
  )
  const failAlert = fail && !["title", "issue", "resolution", "environment", "cause"].includes(fail.field ?? "") ? <Alert tone="danger" title="لم تُحفظ" live>{fail.message}</Alert> : null
  const heading = article ? `تعديل KB-${article.number}` : sourceTicket?.number ? `مقالة من التذكرة #${sourceTicket.number}` : "مقالة جديدة"
  if (gaze) {
    const steps = [{ id: "issue", label: "المشكلة" }, { id: "resolution", label: "الحلّ" }, { id: "more", label: "البيئة والسبب" }, { id: "save", label: "الحفظ" }]
    const canNext = step === 0 ? Boolean(fields.title.trim() && fields.issue.trim()) : step === 1 ? Boolean(fields.resolution.trim()) : true
    return (
      <Screen title={heading} above={<Stepper steps={steps} current={step} />}
        actions={
          <>
            <Button id="article-prev" icon={BackIcon} onClick={step === 0 ? onBack : () => setStep(step - 1)}>{step === 0 ? "رجوع" : "السابق"}</Button>
            {step < 3 ? <Button id="article-next" variant="secondary" iconEnd={NextIcon} disabled={!canNext} onClick={() => setStep(step + 1)}>التالي</Button> : <span aria-hidden="true" />}
          </>
        }>
        {step === 0 ? <>{title}{issue}</> : null}
        {step === 1 ? resolution : null}
        {step === 2 ? <>{environment}{cause}</> : null}
        {step === 3 ? <>{save}{failAlert}{fail && !failAlert ? <Alert tone="danger" title="لم تُحفظ" live>{fail.message}</Alert> : null}</> : null}
      </Screen>
    )
  }
  return (
    <Screen title={heading} back={{ id: "article-back", label: "رجوع", onClick: onBack }} actions={<div className="ms-auto">{save}</div>}>
      {failAlert}
      {title}
      {issue}
      {environment}
      {resolution}
      {cause}
    </Screen>
  )
}

/* ── الاعتماد ────────────────────────────────────────────────────── */

export function PublishScreen({ article, reviewing, answer, late, onReviewAgain, onDecide, onPublish, onBack }: {
  article: Article
  reviewing: boolean
  answer: ReviewAnswer | null
  late: AiFlag[] | null
  onReviewAgain: () => void
  onDecide: (flag: AiFlag, choice: "EDIT" | "PROCEED" | "UNDO") => Promise<void>
  onPublish: () => Promise<Fail>
  onBack: (edit: boolean) => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  // بمعرّف الصفحة لا رقمها: ملاحظاتٌ متأخرة (409 بعد «اعتمد المقالة») تُدرج قبل صفحة الاعتماد ولا تحلّ محلّها.
  const [pageId, setPageId] = React.useState("summary")
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const flags = late ?? answer?.flags ?? article.flags
  const open = flags.filter((f) => f.decision !== "PROCEED")
  const latest = article.versions[0]
  const line = reviewing ? "سيمبول يراجع المقالة…"
    : !answer ? null
    : answer.review.status !== "DONE" ? answer.review.message ?? "مراجعة سيمبول غير متاحة الآن. يمكنك الاعتماد."
    : flags.length === 0 ? "راجع سيمبول المقالة ولم يجد ما يُستغرب."
    : open.length ? `${open.length} من ملاحظات سيمبول تنتظر قرارك.` : "قرّرتَ في ملاحظات سيمبول."
  const statusLine = line ? <p id="publish-review" role="status" className="text-small font-semibold text-muted-foreground">{line}</p> : null
  async function publish() {
    setBusy(true)
    setFail(null)
    setFail(await onPublish())
    setBusy(false)
  }
  const cards = flags.map((flag) => (
    <AIFlag key={flag.id} name={null} message={flag.headline} reason={flag.suggestion ?? "راجع المقالة قبل اعتمادها."} evidence={gaze ? undefined : flag.evidence}
      status={flag.decision === "PROCEED" ? "acknowledged" : "open"} onEdit={() => void onDecide(flag, "EDIT").then(() => onBack(true))}
      onProceed={() => void onDecide(flag, "PROCEED")} onUndo={() => void onDecide(flag, "UNDO")} actionsFirst={gaze} />
  ))
  const publishButton = (
    <Button id="publish-submit" variant="primary" size="lg" commit icon={CheckCircle2} busy={busy} disabled={reviewing || open.length > 0} onClick={() => void publish()} className="gaze:w-full">
      اعتمد المقالة
    </Button>
  )
  const again = !reviewing && answer && answer.review.status !== "DONE" ? <Button id="publish-review-again" icon={RefreshCw} onClick={onReviewAgain}>أعد المراجعة</Button> : null
  const failAlert = fail ? <Alert tone="danger" title="لم تُعتمد" live>{fail.message}</Alert> : null
  if (gaze) {
    // الملخّص أوّلاً (لا شيء يُضغط تحت نظرٍ وصل من «اعتمد»)، ثم ملاحظةٌ في كل صفحة، ثم «اعتمد المقالة» في أعلى آخرها.
    const pages = [{ id: "summary" }, ...flags.map((f) => ({ id: `flag-${f.id}` })), { id: "publish" }]
    const index = Math.max(0, pages.findIndex((p) => p.id === pageId))
    const at = pages[index]
    const setPage = (next: number) => setPageId(pages[next].id)
    const flagIndex = index - 1
    const decided = at.id.startsWith("flag-") ? flags[flagIndex].decision === "PROCEED" : !(at.id === "summary" && reviewing)
    return (
      <Screen title={at.id.startsWith("flag-") ? `ملاحظة ${flagIndex + 1} من ${cards.length}` : "اعتمد المقالة"}
        actions={
          <>
            <Button id="publish-prev" icon={BackIcon} onClick={index === 0 ? () => onBack(false) : () => setPage(index - 1)}>{index === 0 ? "المقالة" : "السابق"}</Button>
            {at.id === "publish" ? <span aria-hidden="true" /> : <Button id="publish-next" variant="secondary" iconEnd={NextIcon} disabled={!decided} onClick={() => setPage(index + 1)}>التالي</Button>}
          </>
        }>
        {at.id === "summary" ? <><p className="text-lead font-semibold">KB-{article.number} · {latest.title}</p><p className="text-small text-muted-foreground">النسخة {latest.version}</p>{statusLine}{again}</> : null}
        {at.id.startsWith("flag-") ? cards[flagIndex] : null}
        {at.id === "publish" ? <>{publishButton}{failAlert}{statusLine}</> : null}
      </Screen>
    )
  }
  return (
    <Screen title="اعتمد المقالة" description={`KB-${article.number} · ${latest.title} · النسخة ${latest.version}`} back={{ id: "publish-back", label: "المقالة", onClick: () => onBack(false) }}
      actions={<><div>{again}</div><div className="ms-auto">{publishButton}</div></>}>
      {failAlert}
      {statusLine}
      {cards.length ? <div className="flex flex-col gap-tg">{cards}</div> : null}
    </Screen>
  )
}

/* ── تحسين المسودات ──────────────────────────────────────────────── */

type ImproveTab = "gaps" | "reasons" | "attention"

export function ImproveScreen({ data, onWrite, onOpenArticle, onBack }: {
  data: Improve | null
  onWrite: (gap: Improve["gaps"][number]) => void
  onOpenArticle: (row: ArticleRow) => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [tab, setTab] = React.useState<ImproveTab>("gaps")
  const [page, setPage] = React.useState(0)
  let body: React.ReactNode = null
  if (data && tab === "reasons") {
    body = data.rejections.length ? (
      <ul aria-label="أسباب الرفض" className="flex flex-col gap-1 text-flow">
        {data.rejections.map((r) => <li key={r.reason}>{REJECT_REASON[r.reason]} · <span className="num">{r.count}</span></li>)}
      </ul>
    ) : <p className="text-flow text-muted-foreground">لم تُرفض مسودةٌ في آخر ثلاثين يوماً.</p>
  } else if (data && tab === "gaps") {
    body = (
      <DataTable<Improve["gaps"][number]>
        caption="ثغرات القاعدة"
        rows={data.gaps}
        rowKey={(g) => g.draft_id}
        columns={[
          { id: "ticket", header: "التذكرة", cell: (g) => `#${g.ticket_number}` },
          { id: "reason", header: "السبب", cell: (g) => `${REJECT_REASON[g.reason]}${g.note ? `: ${g.note}` : ""}` },
        ]}
        primary={(g) => `#${g.ticket_number} · ${REJECT_REASON[g.reason]}`}
        secondary={(g) => g.note ?? "اكتب مقالةً تجيب عنها"}
        onOpen={onWrite}
        openLabel={(g) => `اكتب مقالة من التذكرة ${g.ticket_number}`}
        pageSize={{ compact: 20, gaze: 2, gazeShort: 1 }}
        page={page}
        onPageChange={setPage}
        empty={<EmptyState icon={Lightbulb} title="لا ثغرات في آخر ثلاثين يوماً" />}
      />
    )
  } else if (data && tab === "attention") {
    body = <ArticleTable caption="تحتاج نظرة" rows={data.attention} page={page} onPage={setPage} onOpen={onOpenArticle} empty={<EmptyState icon={BookOpen} title="لا مقالة تحتاج نظرة" />} />
  }
  return (
    <Screen
      title="تحسين المسودات"
      back={gaze ? undefined : { id: "improve-back", label: "قاعدة المعرفة", onClick: onBack }}
      actions={gaze ? <><Button id="improve-prev" icon={BackIcon} onClick={onBack}>القاعدة</Button><span aria-hidden="true" /></> : undefined}
    >
      <Tabs
        items={[{ id: "gaps", label: "ثغرات القاعدة", count: data?.gaps.length }, { id: "reasons", label: "أسباب الرفض" }, { id: "attention", label: "تحتاج نظرة", count: data?.attention.length }]}
        value={tab}
        onValueChange={(id) => { setTab(id as ImproveTab); setPage(0) }}
        label="تحسين المسودات"
      >
        {body}
      </Tabs>
    </Screen>
  )
}
