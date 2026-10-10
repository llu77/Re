/*
 * رئيسية مكتب الدعم، وإشعاره، وقوائم التذاكر
 * ==========================================
 *   • الرئيسية: الأزرار الستة بأعدادها من /api/support/home (والصفر لا يُكتب). قبل الموافقة على إشعار المكتب
 *     سطرٌ فوق الأزرار وزرّ «اقرأ الإشعار»؛ و«تذكرة جديدة» يفتح الإشعار أولاً. «قاعدة المعرفة» تعمل بلا إشعار.
 *   • الإشعار: نصّ الخادم كما هو (support_notice.py)، ثم «قرأتُه»، ثم «أوافق وأتابع» في أعلى الخطوة الثانية
 *     بعيداً عن موضع «قرأتُه»: نظرةٌ باقية على الزرّ الأوّل لا تعتمد الثاني.
 *   • القوائم: «بانتظار قراري»، والمفتوحة (ومعها المحلولة والمغلقة)، وبانتظار العميل، والمُصعَّدة. صفٌّ واحدٌ يُفتح.
 */

import { ArrowLeftRight, Check, FilePlus2, Settings2, ShieldCheck } from "lucide-react"
import * as React from "react"

import { Screen } from "@/components/shell/screen"
import { Alert } from "@/components/ui/alert"
import { BackIcon, Button, ButtonLink } from "@/components/ui/button"
import { PagedText } from "@/components/ui/paged-text"
import { Tabs } from "@/components/ui/tabs"
import { BASE, type DeskNotice, type Home, type Paged, type TicketRow, type TicketView } from "@/lib/support"
import { useSize } from "@/lib/size"
import type { Workspace } from "@/lib/workspace"
import { HomeGrid, homeTitle } from "@/screens/work-home"

import { NoTickets, TicketTable, type Fail } from "./common"

export function noticeAccepted(notice: DeskNotice | null | undefined): boolean {
  return Boolean(notice?.accepted && notice.accepted >= notice.current)
}

export function SupportHome({ workspace, userName, home, onNavigate }: {
  workspace: Workspace
  userName: string | null
  home: Home | null
  onNavigate: (href: string) => void
}) {
  const c = home?.counts
  const counts = c ? { decide: c.decide, open: c.open, pending: c.pending, escalated: c.escalated, knowledge: c.kb_attention } : undefined
  const needsNotice = home !== null && !noticeAccepted(home.notice)
  const settings = `${BASE}/settings`
  return (
    <Screen
      title={homeTitle(userName)}
      aside={
        <ButtonLink id="home-settings" href={settings} icon={Settings2} onClick={(event) => { event.preventDefault(); onNavigate(settings) }}>
          إعدادات الدعم
        </ButtonLink>
      }
    >
      {needsNotice ? (
        // في الحجم الكبير الزرّ وحده: الأزرار الستة وزرّ الإشعار ورابط الإعدادات تملأ الهاتف الأضيق.
        <Alert tone="warning" title="قبل أن تلصق أول رسالة" className="gaze:hidden">
          اقرأ إشعار المكتب ووافق عليه: لا تُحفظ رسائل العملاء ولا يكتب سيمبول قبله.
        </Alert>
      ) : null}
      {needsNotice ? (
        <Button id="home-notice" variant="secondary" icon={ShieldCheck} onClick={() => onNavigate(`${BASE}/notice`)} className="self-start gaze:w-full">
          اقرأ الإشعار
        </Button>
      ) : null}
      <HomeGrid workspace={workspace} onNavigate={onNavigate} counts={counts} />
      <div className={needsNotice ? "tablet:hidden gaze:hidden" : "tablet:hidden"}>
        <ButtonLink id="home-settings-phone" href={settings} icon={Settings2} onClick={(event) => { event.preventDefault(); onNavigate(settings) }} className="gaze:w-full">
          إعدادات الدعم
        </ButtonLink>
      </div>
    </Screen>
  )
}

/* ── إشعار المكتب ────────────────────────────────────────────────── */

export function DeskNoticeScreen({ notice, onAgree, onBack }: { notice: DeskNotice; onAgree: () => Promise<Fail>; onBack: () => void }) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [read, setRead] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [fail, setFail] = React.useState<Fail>(null)
  const agreed = noticeAccepted(notice)

  async function agree() {
    setBusy(true)
    setFail(null)
    const result = await onAgree()
    setBusy(false)
    if (result) setFail(result)
  }

  const lines = gaze ? (
    <PagedText text={notice.lines.join(" ")} label="الإشعار" perPage={{ gaze: 300, gazeShort: 150 }} className="min-h-0" />
  ) : (
    <ul aria-label="الإشعار" className="flex list-disc flex-col gap-2 ps-5 text-flow">
      {notice.lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  )

  if (!read || agreed) {
    return (
      <Screen
        title={notice.title}
        above={<p className="text-small font-semibold text-muted-foreground">{agreed ? `وافقتَ على هذه النسخة (${notice.accepted}).` : "إشعار مكتب الدعم · 1 من 2"}</p>}
        actions={
          <>
            <Button id="notice-back" icon={BackIcon} onClick={onBack}>
              رجوع
            </Button>
            {agreed ? <span aria-hidden="true" /> : (
              <Button id="notice-read" variant="secondary" icon={Check} onClick={() => setRead(true)} className="ms-auto">
                قرأتُه
              </Button>
            )}
          </>
        }
      >
        {lines}
      </Screen>
    )
  }
  return (
    <Screen
      title="الموافقة"
      above={<p className="text-small font-semibold text-muted-foreground">إشعار مكتب الدعم · 2 من 2</p>}
      actions={
        <>
          <Button id="notice-back" icon={BackIcon} onClick={() => setRead(false)}>
            الإشعار
          </Button>
          <span aria-hidden="true" />
        </>
      }
    >
      {/* في أعلى الخطوة: لا يقع حيث كان «قرأتُه» في شريط الإجراءات. */}
      <Button id="notice-agree" variant="primary" size="lg" commit icon={ShieldCheck} busy={busy} onClick={() => void agree()} className="self-start gaze:w-full">
        أوافق وأتابع
      </Button>
      {fail ? <Alert tone="danger" title="لم تُحفظ الموافقة" live>{fail.message}</Alert> : null}
      <p className="text-flow">{notice.lines[notice.lines.length - 1]}</p>
    </Screen>
  )
}

/* ── القوائم ─────────────────────────────────────────────────────── */

export function DecideScreen({ data, page, onPage, onOpen, onOpenList, onBack }: {
  data: Paged<TicketRow> | null
  page: number
  onPage: (page: number) => void
  onOpen: (row: TicketRow) => void
  onOpenList: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  return (
    <Screen title="بانتظار قراري" description={size === "gaze" ? undefined : "ما نسختَه ولم تؤكّد إرساله أولاً، ثم الردود الجاهزة، ثم المسودات بالأقرب موعداً."} back={size === "gaze" ? undefined : { id: "decide-back", label: "الرئيسية", onClick: onBack }}>
      {data === null ? null : (
        <TicketTable
          caption="بانتظار قراري"
          data={data}
          page={page}
          onPage={onPage}
          onOpen={onOpen}
          empty={<NoTickets title="لا شيء ينتظر قرارك الآن." action={<Button icon={ArrowLeftRight} onClick={onOpenList}>التذاكر المفتوحة</Button>} />}
        />
      )}
    </Screen>
  )
}

const LIST_TITLE: Record<TicketView, string> = {
  open: "التذاكر المفتوحة", pending: "بانتظار العميل", escalated: "المُصعَّدة", resolved: "المحلولة", closed: "المغلقة",
}
const LIST_EMPTY: Record<TicketView, string> = {
  open: "لا تذاكر مفتوحة. الصق رسالة عميلٍ لتبدأ.", pending: "لا أحد بانتظار ردّه.", escalated: "لا تذاكر عند جهةٍ أخرى.",
  resolved: "لا تذاكر محلولة.", closed: "لا تذاكر مغلقة.",
}

export function TicketsScreen({ view, data, page, onPage, onView, onOpen, onNew, onBack }: {
  view: TicketView
  data: Paged<TicketRow> | null
  page: number
  onPage: (page: number) => void
  /** بين المفتوحة والمحلولة والمغلقة؛ وnull في القائمتين الأخريين. */
  onView: ((view: TicketView) => void) | null
  onOpen: (row: TicketRow) => void
  onNew: () => void
  onBack: () => void
}) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const table = data === null ? null : (
    <TicketTable
      caption={LIST_TITLE[view]}
      data={data}
      page={page}
      onPage={onPage}
      onOpen={onOpen}
      empty={<NoTickets title={LIST_EMPTY[view]} action={view === "open" ? <Button variant="primary" icon={FilePlus2} onClick={onNew}>تذكرة جديدة</Button> : undefined} />}
    />
  )
  const opening = view === "open" || view === "resolved" || view === "closed"
  return (
    <Screen
      title={opening ? "التذاكر" : LIST_TITLE[view]}
      back={gaze ? undefined : { id: "tickets-back", label: "الرئيسية", onClick: onBack }}
      end={opening ? { id: "tickets-new", label: "تذكرة جديدة", icon: FilePlus2, onClick: onNew } : undefined}
    >
      {opening && onView ? (
        <Tabs
          items={[{ id: "open", label: "المفتوحة" }, { id: "resolved", label: "المحلولة" }, { id: "closed", label: "المغلقة" }]}
          value={view}
          onValueChange={(id) => onView(id as TicketView)}
          label="التذاكر"
        >
          {table}
        </Tabs>
      ) : (
        table
      )}
    </Screen>
  )
}
