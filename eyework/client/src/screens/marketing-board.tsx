/*
 * التسويق: لوحة الحملات
 * ====================
 * كل حملةٍ بحالتها من آلة حالات الحملة في الخادم (states.py): مسوّدة ← نصٌّ مقترح ← معتمد
 * ← جاهزة. الحاسوب: أعمدةٌ أربعة كلوحة كانبان، تُقرأ ولا تُسحب (لا سحب ولا إفلات: النظر
 * والإصبع يضغطان فقط)؛ والانتقال بين الحالات من داخل الحملة بأزرارها. الهاتف والحجم
 * الكبير: ألسنةٌ للحالات وقائمةٌ تصير صفحاتٍ في الكبير.
 * صورة كل حملةٍ من /api/campaigns/{id}/image (الأصل نفسه؛ CSP: img-src 'self').
 */

import * as React from "react"
import { CalendarDays, ImagePlus, Megaphone } from "lucide-react"

import { Screen } from "@/components/shell/screen"
import { Badge } from "@/components/ui/badge"
import { Button, NextIcon } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { EmptyState } from "@/components/ui/empty-state"
import { Tabs } from "@/components/ui/tabs"
import { formatAgo } from "@/lib/format"
import { formatWhole } from "@/lib/money"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"
import type { CampaignCard } from "@/lib/work-types"

const COLUMNS: { status: CampaignCard["status"]; label: string; hint: string }[] = [
  { status: "DRAFT", label: "مسوّدة", hint: "صورةٌ بلا نصٍّ بعد" },
  { status: "COPY_PROPOSED", label: "نصٌّ مقترح", hint: "كتبه سيمبول، ينتظر مراجعتك" },
  { status: "COPY_APPROVED", label: "معتمد", hint: "تبقى الميزانية والأيام" },
  { status: "READY", label: "جاهزة", hint: "تنتظر الإطلاق منك" },
]

export interface CampaignBoardProps {
  campaigns: CampaignCard[]
  now: string
  imageUrl: (campaign: CampaignCard) => string
  onNew: () => void
  onOpen: (campaign: CampaignCard) => void
}

function Thumb({ campaign, imageUrl, className }: { campaign: CampaignCard; imageUrl: CampaignBoardProps["imageUrl"]; className?: string }) {
  return (
    <img
      src={imageUrl(campaign)}
      alt={campaign.imageAlt}
      width={56}
      height={56}
      className={cn("size-12 shrink-0 rounded-ctl border border-border bg-muted object-cover gaze:size-14", className)}
    />
  )
}

function meta(campaign: CampaignCard) {
  const parts: string[] = []
  if (campaign.budget !== null) parts.push(`${formatWhole(campaign.budget)} ر.س`)
  if (campaign.days !== null) parts.push(`${campaign.days} يوماً`)
  return parts.join(" · ")
}

export function CampaignBoard({ campaigns, now, imageUrl, onNew, onOpen }: CampaignBoardProps) {
  const { size } = useSize()
  const gaze = size === "gaze"
  const [status, setStatus] = React.useState<CampaignCard["status"]>("COPY_PROPOSED")
  const counts = Object.fromEntries(COLUMNS.map((c) => [c.status, campaigns.filter((x) => x.status === c.status).length]))
  const inStatus = campaigns.filter((c) => c.status === status)
  const newButton = (
    <Button variant="primary" icon={ImagePlus} onClick={onNew}>
      حملة جديدة
    </Button>
  )

  const list = (
    <DataTable<CampaignCard>
      caption={`حملاتٌ في حالة ${COLUMNS.find((c) => c.status === status)?.label}`}
      rows={inStatus}
      rowKey={(c) => c.id}
      columns={[
        { id: "title", header: "الحملة", cell: (c) => c.title ?? "بلا عنوانٍ بعد" },
        { id: "meta", header: "الميزانية والأيام", cell: (c) => meta(c) || "—" },
        { id: "updated", header: "آخر تعديل", cell: (c) => formatAgo(c.updated, now) },
      ]}
      primary={(c) => (
        <span className="flex items-center gap-3">
          <Thumb campaign={c} imageUrl={imageUrl} />
          <span className="truncate">{c.title ?? "بلا عنوانٍ بعد"}</span>
        </span>
      )}
      secondary={(c) => [meta(c), formatAgo(c.updated, now)].filter(Boolean).join(" · ")}
      onOpen={onOpen}
      openLabel={(c) => `افتح الحملة ${c.title ?? ""}`}
      pageSize={{ compact: 8, gaze: 3 }}
      empty={<EmptyState icon={Megaphone} title="لا حملات في هذه الحالة" action={newButton} />}
    />
  )

  return (
    <Screen
      title="حملاتي"
      aside={gaze ? undefined : newButton}
      actions={gaze ? newButton : undefined}
    >
      {/* الحاسوب: أعمدةٌ تُقرأ، وكل بطاقةٍ زرٌّ يفتح الحملة. */}
      <div className={cn("hidden gap-tg lg:grid lg:grid-cols-4", gaze && "lg:hidden")}>
        {COLUMNS.map((column) => {
          const items = campaigns.filter((c) => c.status === column.status)
          return (
            <section key={column.status} aria-labelledby={`col-${column.status}`} className="flex flex-col gap-tg-min rounded-card bg-muted p-3">
              <header className="flex items-center justify-between gap-2">
                <h2 id={`col-${column.status}`} className="text-lead font-bold">
                  {column.label}
                </h2>
                <Badge tone={column.status === "READY" ? "success" : column.status === "COPY_PROPOSED" ? "ai" : "neutral"}>
                  <span className="num">{items.length}</span>
                </Badge>
              </header>
              <p className="text-small text-muted-foreground">{column.hint}</p>
              <ul className="flex flex-col gap-tg-min">
                {items.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      data-safe=""
                      onClick={() => onOpen(c)}
                      className="flex w-full min-h-ctl items-start gap-3 rounded-card border border-control bg-card p-2.5 text-start hov:bg-secondary/50"
                    >
                      <Thumb campaign={c} imageUrl={imageUrl} />
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="line-clamp-2 font-semibold leading-snug">{c.title ?? "بلا عنوانٍ بعد"}</span>
                        {meta(c) ? <span className="num text-small text-muted-foreground">{meta(c)}</span> : null}
                        <span className="flex items-center gap-1 text-small text-muted-foreground">
                          <CalendarDays aria-hidden="true" className="size-3.5" />
                          {formatAgo(c.updated, now)}
                        </span>
                      </span>
                      <NextIcon aria-hidden="true" className="mt-1 size-4 shrink-0 text-muted-foreground" />
                    </button>
                  </li>
                ))}
              </ul>
              {items.length === 0 ? <p className="py-2 text-center text-small text-muted-foreground">لا شيء هنا</p> : null}
            </section>
          )
        })}
      </div>

      {/* الهاتف والحجم الكبير */}
      <div className={cn("lg:hidden", gaze && "lg:block")}>
        <Tabs
          label="حالة الحملة"
          items={COLUMNS.map((c) => ({ id: c.status, label: c.label, count: counts[c.status] }))}
          value={status}
          onValueChange={(id) => setStatus(id as CampaignCard["status"])}
        >
          {list}
        </Tabs>
      </div>
    </Screen>
  )
}
