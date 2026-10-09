/*
 * TabBar — شريط التبويب السفلي (الهاتف)
 * ====================================
 * أربعة بنودٍ ثابتة في أسفل الشاشة في كل شاشةٍ من البوابة: الرئيسية، والأقسام، والأدوات، وحسابي.
 * أيقونةٌ ونصٌّ تحتها، والحالي باللون الأساسي وعلامة `aria-current`. كلّها آمنة (`data-safe`):
 * رابطٌ يفتح شاشةً أو زرٌّ يفتح ورقة، ولا شيء يعتمد. ارتفاعه `--tab` فوق الحافّة الآمنة،
 * وبين بنوده `--tg`؛ في 320px كل بندٍ 66px: فوق حدّ الهدف في الحجمين.
 *
 * ثابتٌ فوق الصفحة في الحجم العادي (المحتوى ينتهي قبله: `.pb-tab`)، ويختفي فيه ما دام حقلٌ
 * مركَّزاً (`kb:hidden`) فلا يركب لوحة المفاتيح. وفي الحجم الكبير في التدفّق أسفل الشاشة (لا
 * تمرير أصلاً) ولا يختفي: إخفاؤه يحرّك الأهداف تحت نظرٍ باقٍ. التخطيط مستوحىً من «Mobile
 * Navigation Tabs» (shadcnui-blocks، 21st.dev: https://21st.dev/shadcnui-blocks/components/tabs-08،
 * بشروط 21st.dev ورخصة صفحة المكوّن) بلا Radix: لم تُنقل شيفرته، بل تخطيطه.
 */

import type { LucideIcon } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { cn } from "@/lib/utils"

export interface NavEntry {
  id: string
  label: string
  icon: LucideIcon | "symbol"
  /** رابطٌ إلى شاشة… */
  href?: string
  /** …أو زرٌّ يفتح ورقة. */
  onClick?: () => void
  current?: boolean
}

function NavIcon({ icon, className }: { icon: LucideIcon | "symbol"; className?: string }) {
  if (icon === "symbol") return <SymbolMark className={className} />
  const Icon = icon
  return <Icon aria-hidden="true" className={className} strokeWidth={2.25} />
}

export function TabBar({ items, onNavigate }: { items: NavEntry[]; onNavigate: (href: string) => void }) {
  const item = (entry: NavEntry) => {
    const className = cn(
      "flex min-h-tab w-full flex-col items-center justify-center gap-0.5 rounded-ctl text-small font-semibold leading-none text-muted-foreground",
      "gaze:gap-1",
      "[&[aria-current]]:text-primary [&[aria-expanded=true]]:text-primary",
    )
    const content = (
      <>
        <NavIcon icon={entry.icon} className="size-icon shrink-0" />
        <span>{entry.label}</span>
      </>
    )
    if (entry.href) {
      return (
        <a
          id={entry.id}
          href={entry.href}
          data-safe=""
          aria-current={entry.current ? "page" : undefined}
          onClick={(event) => {
            event.preventDefault()
            onNavigate(entry.href!)
          }}
          className={className}
        >
          {content}
        </a>
      )
    }
    return (
      <button id={entry.id} type="button" data-safe="" aria-haspopup="dialog" onClick={entry.onClick} className={className}>
        {content}
      </button>
    )
  }
  return (
    <nav
      aria-label="أقسام البوابة"
      className={cn(
        "bar-glass z-20 border-t border-border kb:hidden",
        "compact:fixed compact:inset-x-0 compact:bottom-0",
        "gaze:shrink-0",
      )}
    >
      <ul className="mx-auto grid max-w-content grid-cols-4 gap-tg px-edge pb-[env(safe-area-inset-bottom)]">
        {items.map((entry) => (
          <li key={entry.id} className="min-w-0">
            {item(entry)}
          </li>
        ))}
      </ul>
    </nav>
  )
}
