/*
 * SectionsSheet — ورقة الأقسام
 * ===========================
 * من «الأقسام» في شريط التبويب (أو سكّة الحجم الكبير): بنود البوابة كلّها بلاطاتٍ في عمودين،
 * كل بلاطةٍ رابطٌ آمن يفتح شاشة العمل ويغلق الورقة. في الحجم الكبير: البندان أو الستّة وإغلاق،
 * وبنود الشريط الأربعة خلفها خاملة (<dialog>): لا يزيد ما يُضغط على اثني عشر.
 */

import { Sheet } from "@/components/ui/dialog"
import type { Workspace } from "@/lib/workspace"

export function SectionsSheet({ open, workspace, current, onClose, onNavigate }: {
  open: boolean
  workspace: Workspace
  current: string | null
  onClose: () => void
  onNavigate: (href: string) => void
}) {
  return (
    <Sheet open={open} onClose={onClose} eyebrow={workspace.name} title="الأقسام" description="كل زرٍّ يفتح عملاً.">
      <ul className="grid grid-cols-2 gap-tg">
        {workspace.home.map((entry) => {
          const Icon = entry.icon
          const active = entry.id === current
          return (
            <li key={entry.id}>
              <a
                id={`section-${entry.id}`}
                href={entry.route}
                data-safe=""
                aria-current={active ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault()
                  onClose()
                  onNavigate(entry.route)
                }}
                className={
                  active
                    ? "flex min-h-ctl-lg w-full items-center gap-3 rounded-card border border-primary-line bg-secondary px-3 font-semibold text-secondary-foreground"
                    : "flex min-h-ctl-lg w-full items-center gap-3 rounded-card border border-control bg-card px-3 font-semibold text-foreground hov:bg-muted"
                }
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-ctl bg-secondary text-secondary-foreground gaze:size-9">
                  <Icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
                </span>
                <span className="leading-snug">{entry.label}</span>
              </a>
            </li>
          )
        })}
      </ul>
    </Sheet>
  )
}
