/*
 * ما تشترك فيه شاشات مكتب الدعم
 * ==============================
 *   • شارات التذكرة: الحالة، والأولوية، وزمن الخدمة («متبقٍّ للردّ ٣٥ د»، «تأخّر الردّ ١ س»، «الوقت متوقّف»).
 *   • `TicketTable`: قوائم التذاكر بصفٍّ واحدٍ يُفتح (DataTable): «#12 · الموضوع» ثم الأولوية والزمن وما ينتظر.
 *   • `MaskedText`: نصّ العميل كما حُفظ، وما حُذف منه («[بريد محذوف]») شارةً لا نصّاً عادياً.
 *   • `Steps`: خطوات الحجم الكبير: الخطوة الحالية وحدها، و«السابق»/«التالي» في شريط الإجراءات.
 *   • `Fail`: رسالة الخادم كما هي، وحقلها إن سمّاه.
 */

import * as React from "react"
import { Inbox } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { BackIcon, Button, NextIcon } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { detail, errorField, type ApiResult } from "@/lib/api"
import { CATEGORY, PRIORITY, STATUS, slaText, ticketTitle, type Paged, type Priority, type TicketRow, type TicketStatus } from "@/lib/support"
import { usePageSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export type Fail = { message: string; field: string | null } | null

/** ردّ الخادم إلى رسالةٍ وحقل؛ وnull حين نجح. */
export function failOf(result: ApiResult): Fail {
  if (result.status >= 200 && result.status < 300) return null
  return { message: detail(result), field: errorField(result) }
}

const STATUS_TONE: Record<TicketStatus, "neutral" | "info" | "warning" | "success"> = {
  NEW: "info", OPEN: "info", PENDING: "neutral", ESCALATED: "warning", RESOLVED: "success", CLOSED: "neutral",
}
const PRIORITY_TONE: Record<Priority, "danger" | "warning" | "neutral"> = { URGENT: "danger", HIGH: "warning", NORMAL: "neutral", LOW: "neutral" }

export function StatusBadge({ status, className }: { status: TicketStatus; className?: string }) {
  return <Badge tone={STATUS_TONE[status]} className={className}>{STATUS[status]}</Badge>
}

export function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  return <Badge tone={PRIORITY_TONE[priority]} className={className}>{`أولوية ${PRIORITY[priority]}`}</Badge>
}

export function SlaBadge({ row, className }: { row: Pick<TicketRow, "sla">; className?: string }) {
  const sla = slaText(row.sla)
  if (!sla) return null
  return <Badge tone={sla.tone} className={className}>{sla.text}</Badge>
}

/** ما ينتظر في التذكرة، بكلمة: يُقرأ في الصفّ وفي «بانتظار قراري». */
export function waitingText(row: TicketRow): string | null {
  if (row.badges.awaiting_confirmation) return "نُسخ الردّ: أكّد إرساله"
  if (row.badges.reply_ready) return row.badges.open_flags ? "ردٌّ جاهز عليه تنبيه" : "ردٌّ جاهز لم يُنسخ"
  if (row.badges.draft_ready) return "مسودةٌ جاهزة"
  return null
}

export function TicketTable({ caption, data, page, onPage, onOpen, empty }: {
  caption: string
  data: Paged<TicketRow>
  page: number
  onPage: (page: number) => void
  onOpen: (row: TicketRow) => void
  empty: React.ReactNode
}) {
  return (
    <DataTable<TicketRow>
      caption={caption}
      rows={data.items}
      rowKey={(row) => row.id}
      columns={[
        { id: "title", header: "التذكرة", cell: (row) => ticketTitle(row) },
        { id: "priority", header: "الأولوية", cell: (row) => <PriorityBadge priority={row.priority} /> },
        { id: "sla", header: "الوقت", cell: (row) => <SlaBadge row={row} /> },
        { id: "waiting", header: "ينتظر", cell: (row) => waitingText(row) ?? STATUS[row.status] },
      ]}
      primary={(row) => ticketTitle(row)}
      secondary={(row) => [PRIORITY[row.priority], row.category ? CATEGORY[row.category] : null, slaText(row.sla)?.text, waitingText(row)].filter(Boolean).join(" · ")}
      trailing={(row) => <StatusBadge status={row.status} className="gaze:hidden" />}
      onOpen={onOpen}
      openLabel={(row) => `افتح التذكرة ${row.number}`}
      pageSize={{ compact: 20, gaze: 3, gazeShort: 2 }}
      page={page}
      onPageChange={onPage}
      total={data.total}
      empty={empty}
    />
  )
}

export function NoTickets({ title, action }: { title: string; action?: React.ReactNode }) {
  return <EmptyState icon={Inbox} title={title} action={action} />
}

const MASK = /(\[بريد محذوف\]|\[رقم محذوف\]|\[رابط محذوف[^\]]*\])/
const IS_MASK = /^\[(?:بريد محذوف|رقم محذوف|رابط محذوف[^\]]*)\]$/

/** النصّ كما حُفظ، وما حذفه التطبيق شاراتٌ ظاهرة. */
export function MaskedText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(MASK)
  return (
    <p className={cn("text-flow whitespace-pre-line", className)}>
      {parts.map((part, index) =>
        IS_MASK.test(part) ? (
          <Badge key={index} tone="neutral" className="mx-0.5 align-baseline">{part.slice(1, -1)}</Badge>
        ) : (
          <React.Fragment key={index}>{part}</React.Fragment>
        ),
      )}
    </p>
  )
}

/** «حُذف: بريدٌ واحد، ورقمان، ورابطٌ واحد.» أو null حين لم يُحذف شيء. */
export function maskedSummary(masked: { email: number; link: number; number: number }): string | null {
  const parts: string[] = []
  const say = (n: number, one: string, two: string, many: string) => (n === 1 ? one : n === 2 ? two : `${n} ${many}`)
  if (masked.email) parts.push(say(masked.email, "بريدٌ واحد", "بريدان", "عناوين بريد"))
  if (masked.number) parts.push(say(masked.number, "رقمٌ واحد", "رقمان", "أرقام"))
  if (masked.link) parts.push(say(masked.link, "رابطٌ واحد", "رابطان", "روابط"))
  if (!parts.length) return null
  return `حُذف: ${parts.join("، و")}.`
}

/** خطوات الحجم الكبير: اسم كل خطوة لشريط الخطوات. */
export interface Step {
  id: string
  label: string
}

/** يقرأ الملصق من الحافظة داخل الضغطة؛ وnull حين رُفض أو لم يكن نصّاً. */
export async function readClipboard(): Promise<string | null> {
  try {
    if (!navigator.clipboard?.readText) return null
    const text = await navigator.clipboard.readText()
    return text || null
  } catch {
    return null
  }
}

/** قائمةٌ قصيرة بصفحاتٍ في الحجم الكبير (ثلاثةٌ في الصفحة، واثنان في الشاشة القصيرة) وكلّها في العادي. */
export function usePages<T>(items: T[], per: { compact: number; gaze: number; gazeShort?: number } = { compact: 50, gaze: 3, gazeShort: 2 }, label = "الصفحات") {
  const size = usePageSize(per)
  const [page, setPage] = React.useState(0)
  const pages = Math.max(1, Math.ceil(items.length / size))
  const current = Math.min(page, pages - 1)
  const slice = items.slice(current * size, current * size + size)
  const pager = pages > 1 ? (
    <nav aria-label={label} className="flex items-center justify-between gap-tg">
      <Button icon={BackIcon} disabled={current === 0} onClick={() => setPage(current - 1)}>
        السابق
      </Button>
      <span className="num whitespace-nowrap text-small text-muted-foreground">
        {current + 1} من {pages}
      </span>
      <Button iconEnd={NextIcon} disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
        التالي
      </Button>
    </nav>
  ) : null
  return { slice, pager, reset: () => setPage(0) }
}
