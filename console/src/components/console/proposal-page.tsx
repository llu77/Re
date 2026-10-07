import * as React from "react"
import { ArrowRight, ExternalLink, Flag } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { ApiError, type PractitionerApi } from "@/lib/api"
import { formatDateTime, kindLabel, sideLabel, statusLabel } from "@/lib/labels"
import type { Citation, Proposal } from "@/lib/types"

import { ErrorNotice, LoadingList } from "./feedback"
import { href } from "./route"
import { PayloadView } from "./payload-view"

const REASON_MAX = 2000

type Step = "idle" | "approving" | "rejecting"

/**
 * صفحة المقترح: المحتوى كاملاً، وأدلّته بجانبه لا في شاشةٍ أخرى، والقرار.
 *
 * القرار خطوتان. «اعتماد» لا يعتمد؛ يعرض ما سيحدث ويطلب تأكيداً. و«رفض»
 * يفتح حقل السبب، والتأكيد معطّلٌ حتى يُكتب سبب — كما يفرضه العقد وقيد القاعدة.
 * لا تعديل هنا: «تعديل واعتماد» يحتاج محرّراً لكل نوع، ولم يُبنَ بعد.
 */
export function ProposalPage({
  api,
  id,
  onDecided,
}: {
  api: PractitionerApi
  id: string
  onDecided: (message: string) => void
}) {
  const [proposal, setProposal] = React.useState<Proposal | null>(null)
  const [citations, setCitations] = React.useState<Citation[] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [step, setStep] = React.useState<Step>("idle")
  const [reason, setReason] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [actionError, setActionError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let current = true
    setProposal(null)
    setCitations(null)
    setLoadError(null)
    Promise.all([api.proposal(id), api.citations(id)])
      .then(([loaded, sources]) => {
        if (!current) return
        setProposal(loaded)
        setCitations(sources)
      })
      .catch((error: unknown) => {
        if (current) setLoadError(error instanceof ApiError ? error.message : "تعذّر تحميل المقترح.")
      })
    return () => {
      current = false
    }
  }, [api, id])

  async function decide(action: () => Promise<Proposal>, message: string) {
    if (busy) return
    setBusy(true)
    setActionError(null)
    try {
      await action()
      onDecided(message)
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "تعذّر تنفيذ القرار.")
      setBusy(false)
    }
  }

  const back = (
    <a
      href={href({ name: "queue" })}
      className="inline-flex min-h-12 items-center gap-2 rounded-md px-1 text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <ArrowRight className="size-5" aria-hidden="true" />
      العودة إلى الطابور
    </a>
  )

  if (loadError) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <ErrorNotice message={loadError} />
      </div>
    )
  }
  if (!proposal || !citations) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <LoadingList rows={2} label="جارٍ تحميل المقترح" />
      </div>
    )
  }

  const pending = proposal.status === "PENDING"
  const reasonText = reason.trim()

  return (
    <div className="flex flex-col gap-6">
      {back}

      <section aria-labelledby="proposal-title" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="proposal-title" className="text-2xl font-bold">
            {kindLabel(proposal.kind)}
          </h2>
          <span className="rounded-full bg-secondary px-2.5 py-0.5 text-sm">
            {statusLabel(proposal.status)}
          </span>
          {proposal.is_red_flag ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-destructive px-2.5 py-0.5 text-sm text-destructive-foreground">
              <Flag className="size-4" aria-hidden="true" />
              علامة حمراء
            </span>
          ) : null}
        </div>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Fact term="المريض">
            <bdi dir="ltr" className="font-mono break-all">
              {proposal.patient_id}
            </bdi>
          </Fact>
          <Fact term="الجانب المصاب">
            {proposal.affected_side ? sideLabel(proposal.affected_side) : "غير محدّد"}
          </Fact>
          <Fact term="الأولوية">{proposal.priority}</Fact>
          <Fact term="النسخة">{proposal.version}</Fact>
          <Fact term="دخل الطابور">{formatDateTime(proposal.queued_at)}</Fact>
          <Fact term="تنتهي مهلته">{formatDateTime(proposal.expires_at)}</Fact>
        </dl>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section aria-labelledby="payload-title" className="flex min-w-0 flex-col gap-3 rounded-lg border bg-card p-4">
          <h3 id="payload-title" className="text-lg font-bold">
            المحتوى المقترح كما سيصل المريض
          </h3>
          <PayloadView value={proposal.payload} label="المحتوى المقترح" />
          <details className="mt-2 rounded-md bg-secondary p-3">
            <summary className="min-h-12 cursor-pointer py-3 font-bold">مصدر المقترح</summary>
            <PayloadView value={proposal.provenance} label="مصدر المقترح" />
          </details>
        </section>

        <aside aria-labelledby="citations-title" className="flex min-w-0 flex-col gap-3 rounded-lg border bg-card p-4">
          <h3 id="citations-title" className="text-lg font-bold">
            الأدلّة ({citations.length})
          </h3>
          {citations.length === 0 ? (
            <p className="text-muted-foreground">لا أدلّة مرفقة بهذا المقترح.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {citations.map((citation) => (
                <li key={citation.source_id} className="flex flex-col gap-1 border-b pb-3 last:border-b-0">
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-12 items-center gap-1 rounded-md text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    dir="auto"
                  >
                    <span className="break-words">{citation.title}</span>
                    <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
                    <span className="sr-only">(يفتح في نافذة جديدة)</span>
                  </a>
                  <p className="text-sm text-muted-foreground">
                    <bdi dir="ltr">{citation.external_id}</bdi>
                    {citation.published_year ? ` · ${citation.published_year}` : ""}
                    {citation.locator ? ` · ${citation.locator}` : ""}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>

      <section aria-labelledby="decision-title" className="flex flex-col gap-4 rounded-lg border-2 border-primary/30 bg-card p-4">
        <h3 id="decision-title" className="text-lg font-bold">
          القرار
        </h3>

        {!pending ? (
          <div className="flex flex-col gap-1">
            <p>قُرِّر هذا المقترح: {statusLabel(proposal.status)}.</p>
            {proposal.rejection_reason ? (
              <p className="whitespace-pre-wrap text-muted-foreground" dir="auto">
                السبب: {proposal.rejection_reason}
              </p>
            ) : null}
          </div>
        ) : step === "idle" ? (
          <div className="flex flex-wrap gap-3">
            <Button className="h-12 min-w-36 text-base" onClick={() => setStep("approving")}>
              اعتماد
            </Button>
            <Button
              variant="outline"
              className="h-12 min-w-36 border-destructive text-base text-destructive hover:bg-destructive/5 hover:text-destructive"
              onClick={() => setStep("rejecting")}
            >
              رفض
            </Button>
          </div>
        ) : step === "approving" ? (
          <div className="flex flex-col gap-3">
            <p>بعد الاعتماد يصل هذا المحتوى إلى المريض كما هو معروضٌ أعلاه.</p>
            <div className="flex flex-wrap gap-3">
              <Button
                className="h-12 min-w-36 text-base"
                disabled={busy}
                onClick={() => decide(() => api.approve(proposal.id), "اعتُمد المقترح.")}
              >
                {busy ? "جارٍ الاعتماد…" : "تأكيد الاعتماد"}
              </Button>
              <Button
                variant="outline"
                className="h-12 min-w-36 text-base"
                disabled={busy}
                onClick={() => setStep("idle")}
              >
                تراجع
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Label htmlFor="reject-reason" className="text-base">
              سبب الرفض (إلزامي)
            </Label>
            <textarea
              id="reject-reason"
              value={reason}
              maxLength={REASON_MAX}
              rows={4}
              dir="auto"
              aria-describedby="reject-reason-hint"
              onChange={(event) => setReason(event.target.value)}
              className="w-full rounded-md border border-input bg-background p-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <p id="reject-reason-hint" className="text-sm text-muted-foreground">
              يُحفظ السبب مع القرار ويراه من يراجع المقترح بعدك. {reason.length} من {REASON_MAX}.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="destructive"
                className="h-12 min-w-36 text-base"
                disabled={busy || !reasonText}
                onClick={() => decide(() => api.reject(proposal.id, reasonText), "رُفض المقترح وحُفظ السبب.")}
              >
                {busy ? "جارٍ الرفض…" : "تأكيد الرفض"}
              </Button>
              <Button
                variant="outline"
                className="h-12 min-w-36 text-base"
                disabled={busy}
                onClick={() => {
                  setStep("idle")
                  setReason("")
                }}
              >
                تراجع
              </Button>
            </div>
          </div>
        )}

        {actionError ? <ErrorNotice message={actionError} /> : null}
      </section>
    </div>
  )
}

function Fact({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 text-muted-foreground">{term}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  )
}
