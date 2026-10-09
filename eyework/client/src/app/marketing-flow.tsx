/*
 * أداة الحملة: المسار
 * ==================
 * منطق static/app.js كما هو — الحملة الحالية في المخزن، وكل كتابةٍ تُعرض نتيجتها لمن بقي على
 * الشاشة التي أرسلت وحده، والانتظار بلا مؤقّت وبقفل الشاشة، و«تحقّق الآن» حين لا يُعرف مآل
 * الكتابة — على شاشات screens/campaign.tsx:
 *
 *   #/marketing/new            صورة حملةٍ جديدة
 *   #/marketing/campaigns      «حملاتي» بصفحاتها
 *   #/marketing/c/{id}         الحملة بحالتها: الصورة، أو الانتظار، أو النصّ المقترح، أو الجاهزة
 *   #/marketing/c/{id}/edit    طلب التعديل، و/note الملاحظة، و/budget و/days و/review
 *
 * التأكيد النهائي والإلغاء لا عنوان لهما: شاشتان فوق المسار الحالي تُغلقان بالرجوع، فإعادة
 * التحميل تعود إلى ما قبلهما.
 */

import * as React from "react"

import { assistantApi, navigate } from "@/app/workspace"
import { Redirect } from "@/components/redirect"
import { WorkspaceShell } from "@/components/shell/workspace-shell"
import { Notice } from "@/components/ui/notice"
import { detail, type ApiError, type ApiResult } from "@/lib/api"
import {
  BUSY_ELSEWHERE, PERSONA, approve, brief, campaignRoute, cancel, confirm, conflictOf, createCampaign, editCopy, fetchCampaign, fetchImage,
  generate, installedApp, listCampaigns, replaceImage, restore, setBudget, setDays, unapprove,
  type Campaign, type CampaignListItem, type CampaignPage, type GenerationResult,
} from "@/lib/campaigns"
import { currentHash, go, route } from "@/lib/router"
import { WIDE_QUERY, useMatch, useSize } from "@/lib/size"
import { EMPTY_EDIT, getState, setState, useStore, type Choices, type EditState, type Me } from "@/lib/store"
import { keepAwake, letSleep } from "@/lib/wake-lock"
import type { Workspace } from "@/lib/workspace"
import {
  CampaignsPane, CampaignsScreen, CancelScreen, ConfirmScreen, EditScreen, NoteScreen, PhotoScreen, ProposalScreen, ReadyScreen, ReviewScreen,
  ValueScreen, WaitingScreen,
} from "@/screens/campaign"

const NEW = "#/marketing/new"
const LIST = "#/marketing/campaigns"
const CAMPAIGN = /^#\/marketing\/c\/([0-9a-f-]{36})(?:\/(edit|note|budget|days|review))?$/

/** طلب التعديل للنسخة المعروضة: ما حُفظ إن كان لها، وإلا طلبٌ فارغ. */
function editFor(campaign: Campaign): EditState {
  const versionId = campaign.copy?.version_id ?? null
  const edit = getState().edit
  return edit.versionId === versionId ? edit : { ...EMPTY_EDIT, versionId }
}

const here = () => route(currentHash())

/* ── الملاحظة ────────────────────────────────────────────────────── */

function NoteContainer({ campaign, max, onSave, onBack }: {
  campaign: Campaign
  max: number
  onSave: (text: string) => void
  onBack: (text: string) => void
}) {
  const initial = editFor(campaign)
  const [text, setText] = React.useState(initial.draft || initial.note || "")
  return <NoteScreen text={text} max={max} onChange={setText} onSave={() => onSave(text)} onBack={() => onBack(text)} />
}

/* ── جاهزة للتسليم ───────────────────────────────────────────────── */

function ReadyContainer({ campaign, setNotice, onHome, onWithdraw }: {
  campaign: Campaign
  setNotice: (message: string) => void
  onHome: () => void
  onWithdraw: () => void
}) {
  const [blob, setBlob] = React.useState<Blob | null>(null)
  const [fetched, setFetched] = React.useState(false)
  const [status, setStatus] = React.useState("")
  const installed = installedApp()

  // الصورة تُجلب الآن لا عند الضغط: المشاركة يجب أن تبدأ داخل الضغطة نفسها. وحتى تصل لا
  // مشاركة، وإلا أُرسل النصّ وحده دون أن يُقال.
  React.useEffect(() => {
    let current = true
    void fetchImage(campaign).then((result) => {
      if (!current || result.status === 401) return
      if (result.status === 200 && result.data) setBlob(result.data)
      else setStatus("تعذّر تحميل الصورة: «شارك الحملة» ترسل النصّ وحده.")
      setFetched(true)
    })
    return () => {
      current = false
    }
  }, [campaign.id, campaign.image?.tag])

  async function copyText(text: string, done: string) {
    try {
      await navigator.clipboard.writeText(text)
      setStatus(done)
    } catch {
      setNotice("تعذّر النسخ. استخدم «شارك الحملة».")
    }
  }

  async function share() {
    const copy = campaign.copy
    if (!copy) return
    const data: ShareData = { title: copy.title, text: brief(campaign) }
    if (blob) {
      const file = new File([blob], "campaign.jpg", { type: "image/jpeg" })
      if (navigator.canShare && navigator.canShare({ files: [file] })) data.files = [file]
    }
    if (!navigator.share) {
      await copyText(data.text ?? "", "نُسخ ملخّص الحملة.")
      return
    }
    try {
      await navigator.share(data)
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setNotice(installed ? "تعذّرت المشاركة. استخدم «انسخ العنوان» و«انسخ الوصف»." : "تعذّرت المشاركة. استخدم «نزّل الصورة» و«انسخ الوصف».")
      }
    }
  }

  return (
    <ReadyScreen
      campaign={campaign}
      shareEnabled={fetched}
      status={status}
      downloadOffered={!installed}
      onCopyTitle={() => void copyText(campaign.copy?.title ?? "", "نُسخ العنوان.")}
      onCopyDescription={() => void copyText(campaign.copy?.description ?? "", "نُسخ الوصف.")}
      onShare={() => void share()}
      onHome={onHome}
      onWithdraw={onWithdraw}
    />
  )
}

/* ── حملاتي ──────────────────────────────────────────────────────── */

function ListContainer({ pageSize, setNotice, onOpen, onNew }: {
  pageSize: number
  setNotice: (message: string) => void
  onOpen: (item: CampaignListItem) => void
  onNew: () => void
}) {
  const page = useStore((s) => s.page)
  const [data, setData] = React.useState<CampaignPage | null>(null)
  React.useEffect(() => {
    let current = true
    setState({ campaign: null })
    void listCampaigns(page).then((result) => {
      if (!current) return
      if (result.status === 200 && result.data) setData(result.data)
      else if (result.status !== 401) setNotice(detail(result))
    })
    return () => {
      current = false
    }
  }, [page, setNotice])
  return (
    <CampaignsScreen
      items={data ? data.items : null}
      page={page}
      pageSize={pageSize}
      hasMore={Boolean(data?.has_more)}
      installHint={data !== null && data.items.length <= 1 && !installedApp()}
      onOpen={onOpen}
      onOlder={() => setState((s) => ({ page: s.page + 1 }))}
      onNewer={() => setState((s) => ({ page: Math.max(1, s.page - 1) }))}
      onNew={onNew}
    />
  )
}


/* ── «حملاتي» بجانب الحملة (العريض بحجم اللمس) ──────────────────── */

function PaneContainer({ campaignId, status, setNotice }: { campaignId: string; status: string | null; setNotice: (message: string) => void }) {
  const [data, setData] = React.useState<CampaignPage | null>(null)
  // الصفحة الأولى، وتُقرأ من جديد حين تتغيّر الحملة المفتوحة (من المسار، فلا تختفي القائمة وهي تُقرأ)
  // أو حالتها (الشارة في صفّها).
  React.useEffect(() => {
    let current = true
    void listCampaigns(1).then((result) => {
      if (!current) return
      if (result.status === 200 && result.data) setData(result.data)
      else if (result.status !== 401) setNotice(detail(result))
    })
    return () => {
      current = false
    }
  }, [campaignId, status, setNotice])
  if (!data) return null
  return <CampaignsPane items={data.items} currentId={campaignId} onOpen={(item) => go(campaignRoute(item.id))} />
}

/* ── المسار ──────────────────────────────────────────────────────── */

export function MarketingFlow({ path, choices, me, workspace }: { path: string; choices: Choices; me: Me; workspace: Workspace }) {
  const [notice, setNoticeState] = React.useState<string | null>(null)
  const setNotice = React.useCallback((message: string) => setNoticeState(message), [])
  const [overlay, setOverlay] = React.useState<{ path: string; kind: "confirm" | "cancel" } | null>(null)
  const [uploading, setUploading] = React.useState(false)
  const campaign = useStore((s) => s.campaign)
  const busy = useStore((s) => s.busy)
  const waitingFor = useStore((s) => s.waitingFor)
  const waitUnknown = useStore((s) => s.waitUnknown)
  const mayLock = useStore((s) => s.wakeLock === null)
  const edit = useStore((s) => s.edit)
  const base = workspace.base
  const { size } = useSize()
  const wide = useMatch(WIDE_QUERY)

  const match = path.match(CAMPAIGN)
  const id = match?.[1] ?? null
  const sub = match?.[2] ?? null
  const loaded = id && campaign && campaign.id === id ? campaign : null

  // #/marketing/new: لا حملة في الذاكرة — الصورة لحملةٍ جديدة، لا لما بقي من قبل.
  React.useEffect(() => {
    if (path === NEW) setState({ campaign: null, edit: EMPTY_EDIT })
  }, [path])

  // الحملة من الخادم إن لم تكن المحفوظة؛ وما يصل بعد انتقالٍ أحدث لا يصير الحالية — وإلا ذهبت
  // صورةٌ جديدة إلى مسودةٍ أخرى.
  React.useEffect(() => {
    if (!id || loaded) return undefined
    let current = true
    void fetchCampaign(id).then((result) => {
      if (!current) return
      if (result.status === 200 && result.data) setState({ campaign: result.data, waitUnknown: null })
      else if (result.status !== 401) go(base, { replace: true })
    })
    return () => {
      current = false
    }
  }, [id, loaded, base])

  // صفحةٌ تعود من ذاكرة الرجوع في Safari قد تعرض تأكيداً قديماً: تُقرأ الحملة من جديد.
  React.useEffect(() => {
    const onShow = (event: PageTransitionEvent) => {
      if (event.persisted) setState({ campaign: null })
    }
    window.addEventListener("pageshow", onShow)
    return () => window.removeEventListener("pageshow", onShow)
  }, [])

  // عادت الصفحة والكتابة جارية: يُطلب القفل من جديد، فقد أسقطه النظام حين أُخفيت.
  React.useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible") return
      const state = getState()
      if (state.waitingFor && !state.wakeLock) void keepAwake()
    }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [])

  /*
   * كتابةٌ على الحملة الحالية. تعيد الحملة الجديدة إن بقي المستخدم على الشاشة التي أرسلت؛ فإن
   * غادرها لا تُرسم شاشته من تحته — ولا يقع زرٌّ يعتمد تحت نظرٍ استقرّ على شاشةٍ أخرى — وتُحدَّث
   * الحملة المحفوظة إن كانت هي نفسها فقط.
   */
  async function mutate(c: Campaign, request: () => Promise<ApiResult<Campaign>>): Promise<Campaign | null> {
    if (getState().busy) return null
    const screen = here()
    setState({ busy: true })
    const result = await request()
    setState({ busy: false })
    if (here() !== screen) {
      if (result.status === 200 && result.data && getState().campaign?.id === c.id) setState({ campaign: result.data })
      return null
    }
    if (result.status === 200 && result.data) {
      setState({ campaign: result.data })
      return result.data
    }
    if (result.status !== 401) {
      if (result.status === 409) {
        // تغيّرت الحملة: تُقرأ من جديد قبل أيّ قرارٍ آخر.
        const fresh = await fetchCampaign(c.id)
        if (fresh.status === 200 && fresh.data) setState({ campaign: fresh.data })
      }
      setNotice(detail(result))
    }
    return null
  }

  async function runGeneration(c: Campaign, request: () => Promise<ApiResult<GenerationResult>>) {
    setState({ waitingFor: c.id, waitUnknown: null })
    await keepAwake()
    const result = await request()
    letSleep()
    setState({ waitingFor: null })
    if (result.status === 401) return
    // شاشة الانتظار تُعرض على كل مسارات الحملة (الطلب من /edit أيضاً): من بقي عليها هو من يرى النتيجة.
    const stillHere = here().startsWith(campaignRoute(c.id)) && getState().campaign?.id === c.id
    if (result.status !== 200 && !(result.data && (result.data as ApiError).code)) {
      // انقطع الطلب في الطريق (شبكة أو وكيل) لا عند الخادم: قد يكون النصّ كُتب. تُقرأ الحملة كما
      // هي، ولا يُفترض شيء — ويُقال ما حدث.
      if (!stillHere) return
      const fresh = await fetchCampaign(c.id)
      if (fresh.status === 401) return
      if (fresh.status === 200 && fresh.data) {
        setState({ campaign: fresh.data })
        setNotice("انقطع الاتصال قبل أن يصل الردّ. هذا ما حُفظ في الحملة الآن.")
      } else {
        // الحملة لم تُقرأ أيضاً: تبقى شاشة الانتظار و«تحقّق الآن» فيها.
        setState({ campaign: c, waitUnknown: c.id })
        setNotice("تعذّر الاتصال، ولم يُعرف إن كُتب النص. تحقّق من الاتصال ثم اضغط «تحقّق الآن».")
      }
      return
    }
    if (result.status === 200 && result.data) {
      const next = result.data.campaign
      // من غادر الشاشة لا تُغيَّر شاشته ولا تعديله من تحته؛ تُحدَّث الحملة المحفوظة فقط إن كانت هي نفسها.
      if (!stillHere) {
        if (getState().campaign?.id === c.id) setState({ campaign: next })
        return
      }
      setState({ campaign: next, edit: EMPTY_EDIT })
      // العنوان يتبع الحالة: إعادة التحميل بعدها تعرض ما يُعرض الآن.
      go(campaignRoute(next.id), { replace: true })
      if (result.data.result === "UNUSABLE_PHOTO") {
        const advice = result.data.assistant_note ? ` ${PERSONA}: ${result.data.assistant_note}` : ""
        setNotice(`${result.data.message ?? ""}${advice}`)
      }
      return
    }
    if (stillHere) {
      // الفشل يُقرّ قبل أيّ شيء: «حسناً» تعيد الشاشة التي بدأ منها، بالحملة كما هي الآن.
      const fresh = await fetchCampaign(c.id)
      if (fresh.status === 200 && fresh.data) setState({ campaign: fresh.data })
      setNotice(detail(result))
    }
  }

  /* «تحقّق الآن» بعد ردٍّ لم يصل: تُقرأ الحملة، ويبقى الانتظار ما دام الاتصال مقطوعاً. */
  async function check(c: Campaign) {
    if (getState().busy) return
    const screen = here()
    setState({ busy: true })
    const result = await fetchCampaign(c.id)
    setState({ busy: false })
    if (here() !== screen || result.status === 401) return
    if (result.status === 404) {
      go(base, { replace: true })
      return
    }
    if (result.status !== 200 || !result.data) {
      setNotice(`${detail(result)} «تحقّق الآن» تعيد المحاولة.`)
      return
    }
    setState({ campaign: result.data, waitUnknown: null })
  }

  async function onFile(c: Campaign | null, file: File) {
    if (getState().busy) return
    const screen = here()
    setUploading(true)
    setState({ busy: true })
    const result = c ? await replaceImage(c, file) : await createCampaign(file)
    setState({ busy: false })
    setUploading(false)
    if (here() !== screen) return
    if ((result.status === 200 || result.status === 201) && result.data) {
      setState({ campaign: result.data })
      go(campaignRoute(result.data.id), { replace: true })
    } else if (result.status !== 401) {
      setNotice(detail(result))
    }
  }

  function onGenerate(c: Campaign) {
    if (getState().busy) return
    if (getState().waitingFor) {
      setNotice(BUSY_ELSEWHERE)
      return
    }
    void runGeneration(c, () => generate(c))
  }

  function onProposalStart(c: Campaign) {
    if (c.status === "COPY_APPROVED") {
      void mutate(c, () => unapprove(c))
      return
    }
    // الوصول إلى شاشة التعديل لا يُرسل شيئاً: «اطلب نسخة جديدة» تبقى معطّلةً حتى يختار المستخدم
    // فيها، فلا يرسل الطلبَ نظرٌ مرّ بها في الطريق.
    setState({ edit: { ...editFor(c), armed: false } })
    go(campaignRoute(c.id, "/edit"))
  }

  function onProposalEnd(c: Campaign) {
    if (c.status === "COPY_APPROVED") {
      go(campaignRoute(c.id, "/budget"))
      return
    }
    void mutate(c, () => approve(c))
  }

  function onToggle(c: Campaign, preset: string) {
    const current = editFor(c)
    const presets = current.presets.includes(preset) ? current.presets.filter((p) => p !== preset) : [...current.presets, preset]
    setState({ edit: { ...current, presets, armed: true } })
  }

  function onEditSubmit(c: Campaign) {
    if (c.versions_left <= 0) {
      go(campaignRoute(c.id))
      return
    }
    const current = editFor(c)
    if (getState().busy || !current.armed || (!current.presets.length && !current.note)) return
    if (getState().waitingFor) {
      setNotice(BUSY_ELSEWHERE)
      return
    }
    void runGeneration(c, () => editCopy(c, current.presets, current.note))
  }

  async function onRestore(c: Campaign, target: "previous" | "newest") {
    const view = await mutate(c, () => restore(c, target))
    if (view) go(campaignRoute(view.id))
  }

  function onNoteSave(c: Campaign, text: string) {
    // ما يُرسل هو ما يُحسب: المسافات المتكرّرة وفواصل الأسطر مسافةٌ واحدة.
    const note = text.replace(/\s+/g, " ").trim()
    setState({ edit: { ...editFor(c), note: note || null, draft: "", armed: true } })
    go(campaignRoute(c.id, "/edit"))
  }

  // «رجوع» من الملاحظة لا يمحو ما كُتب بالنظر حرفاً حرفاً: يبقى مسودةً تعود إليها، ولا يُرسل حتى تُحفظ.
  function onNoteBack(c: Campaign, text: string) {
    setState({ edit: { ...editFor(c), draft: text } })
    go(campaignRoute(c.id, "/edit"))
  }

  async function onConfirm(c: Campaign) {
    const view = await mutate(c, () => confirm(c))
    if (view) {
      setOverlay(null)
      go(campaignRoute(view.id))
    }
  }

  async function onCancelYes(c: Campaign) {
    const view = await mutate(c, () => cancel(c))
    if (view) {
      setOverlay(null)
      setState({ campaign: null })
      go(base)
    }
  }

  let current = "campaigns"
  let content: React.ReactNode = null
  if (path === NEW) {
    current = "new"
    content = (
      <PhotoScreen campaign={null} uploading={uploading} onFile={(file) => void onFile(null, file)} onGenerate={() => {}} onBack={() => go(base)} onCancel={null} />
    )
  } else if (path === LIST) {
    content = <ListContainer pageSize={choices.limits.page_size} setNotice={setNotice} onOpen={(item) => go(campaignRoute(item.id))} onNew={() => go(NEW)} />
  } else if (!id) {
    content = <Redirect to={base} />
  } else if (loaded) {
    const c = loaded
    const over = overlay && overlay.path === path ? overlay.kind : null
    const openCancel = () => setOverlay({ path, kind: "cancel" })
    const toHome = () => go(base)
    if (c.status === "CANCELLED") {
      content = <Redirect to={base} />
    } else if (over === "cancel") {
      content = <CancelScreen withdraw={c.status === "READY"} busy={busy} onYes={() => void onCancelYes(c)} onBack={() => setOverlay(null)} />
    } else if (c.status === "READY") {
      content = <ReadyContainer campaign={c} setNotice={setNotice} onHome={toHome} onWithdraw={openCancel} />
    } else if ((c.generating && waitingFor !== c.id) || waitUnknown === c.id) {
      // انتظارٌ لم تبدأه هذه الصفحة لا قفل له، و«تحقّق الآن» فيه.
      content = <WaitingScreen reloaded mayLock={mayLock} busy={busy} onCheck={() => void check(c)} onBack={toHome} />
    } else if (waitingFor === c.id) {
      content = <WaitingScreen reloaded={false} mayLock={mayLock} busy={busy} onCheck={() => {}} onBack={toHome} />
    } else if (c.status === "DRAFT") {
      content = (
        <PhotoScreen campaign={c} uploading={uploading} onFile={(file) => void onFile(c, file)} onGenerate={() => onGenerate(c)} onBack={toHome} onCancel={openCancel} />
      )
    } else if (sub === "edit" && c.status === "COPY_PROPOSED") {
      content = (
        <EditScreen
          campaign={c}
          edit={edit.versionId === c.copy?.version_id ? edit : { ...EMPTY_EDIT, versionId: c.copy?.version_id ?? null }}
          presets={choices.edit_presets}
          presetsMax={choices.limits.presets_max}
          conflictOf={(preset) => conflictOf(choices.preset_conflicts, preset)}
          busy={busy}
          onToggle={(preset) => onToggle(c, preset)}
          onNote={() => go(campaignRoute(c.id, "/note"))}
          onRestore={(target) => void onRestore(c, target)}
          onSubmit={() => onEditSubmit(c)}
          onBack={() => go(campaignRoute(c.id))}
        />
      )
    } else if (sub === "note" && c.status === "COPY_PROPOSED") {
      content = (
        <NoteContainer key={c.copy?.version_id} campaign={c} max={choices.limits.note_max} onSave={(text) => onNoteSave(c, text)} onBack={(text) => onNoteBack(c, text)} />
      )
    } else if (sub === "budget" && c.status === "COPY_APPROVED") {
      content = (
        <ValueScreen
          key="budget"
          kind="budget"
          campaign={c}
          table={choices.budget}
          busy={busy}
          onPick={(sar) => void mutate(c, () => setBudget(c, sar))}
          onNext={() => go(campaignRoute(c.id, "/days"))}
          onBack={() => go(campaignRoute(c.id))}
        />
      )
    } else if (sub === "days" && c.status === "COPY_APPROVED" && c.budget) {
      content = (
        <ValueScreen
          key="days"
          kind="days"
          campaign={c}
          table={choices.days}
          busy={busy}
          onPick={(days) => void mutate(c, () => setDays(c, days))}
          onNext={() => go(campaignRoute(c.id, "/review"))}
          onBack={() => go(campaignRoute(c.id, "/budget"))}
        />
      )
    } else if (sub === "review" && c.status === "COPY_APPROVED" && c.budget && c.days) {
      content =
        over === "confirm" ? (
          <ConfirmScreen campaign={c} busy={busy} onYes={() => void onConfirm(c)} onBack={() => setOverlay(null)} />
        ) : (
          <ReviewScreen campaign={c} onContinue={() => setOverlay({ path, kind: "confirm" })} onBack={() => go(campaignRoute(c.id, "/days"))} onCancel={openCancel} />
        )
    } else if (sub) {
      content = <Redirect to={campaignRoute(c.id)} />
    } else {
      content = (
        <ProposalScreen
          campaign={c}
          versionsMax={choices.limits.versions_max}
          busy={busy}
          onStart={() => onProposalStart(c)}
          onEnd={() => onProposalEnd(c)}
          onBack={toHome}
          onCancel={openCancel}
        />
      )
    }
  }

  // «حملاتي» بجانب الحملة المفتوحة في العريض بحجم اللمس وحده؛ ولا تُقرأ القائمة في غيره.
  const pane = wide && size === "compact" && id ? <PaneContainer campaignId={id} status={loaded?.status ?? null} setNotice={setNotice} /> : undefined
  return (
    <Notice message={notice} onAck={() => setNoticeState(null)}>
      <WorkspaceShell
        workspace={workspace}
        current={current}
        userName={me.display_name}
        onNavigate={navigate}
        tools={{
          userName: me.display_name,
          assistant: assistantApi(me, choices, id ? "CAMPAIGN" : "HOME", id),
          supportContact: choices.support_contact,
        }}
        pane={pane}
      >
        {content}
      </WorkspaceShell>
    </Notice>
  )
}
