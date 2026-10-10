/*
 * Sidebar — الشريط الجانبي (الآيباد والحاسوب)
 * ==========================================
 * من 744px (iPad mini عمودياً) فأوسع: عمودٌ في بداية الصفحة (يمينها) بالعلامة واسم البوابة، ثم
 * الرئيسية وبنود البوابة، ثم «الأدوات» و«مساعدة»، ثم «حسابي» في أسفله؛ و«اسأل سيمبول» زرٌّ عائم في
 * الركن الآخر (chat-launcher.tsx). كل بندٍ صفٌّ بأيقونةٍ ونصّ، والحالي بتعبئةٍ مدرّجة وعلامة
 * `aria-current`. في الحجم الكبير سكّةٌ بأربعة بنود: الرئيسية والأقسام في أعلاها، و«سيمبول» بالتعبئة الملوّنة
 * و«حسابي» في أسفلها، و«الأدوات» من ورقة سيمبول؛ فتبقى الشاشة ضمن اثني عشر هدفاً. البنية مستوحاةٌ من «Sidebar» (wensity، 21st.dev:
 * https://21st.dev/wensity/components/sidebar، بشروط 21st.dev ورخصة صفحة المكوّن) بلا حركةٍ ولا طيّ:
 * لم تُنقل شيفرته، بل تخطيطه.
 */

import { BrandMark, SymbolMark } from "@/components/brand/marks"
import { SymbolBadge } from "@/components/chat/chat-launcher"
import type { NavEntry } from "@/components/shell/tab-bar"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface SidebarProps {
  workspaceName: string
  userName: string | null
  /** مجموعاتٌ تفصل بينها فاصلة: [الرئيسية والبنود] [الأدوات] [حسابي]. */
  groups: NavEntry[][]
  onNavigate: (href: string) => void
}

function Row({ entry, onNavigate }: { entry: NavEntry; onNavigate: (href: string) => void }) {
  // في الحجم الكبير بلا aria-haspopup: WebKit يجعله «زرّاً منبثقاً» بلا سمة الزرّ التي يقصدها «الانتقال إلى العنصر».
  const popup = useSize().size === "gaze" ? undefined : "dialog"
  const className = cn(
    "flex min-h-ctl w-full items-center gap-3 rounded-ctl px-3 text-start font-medium text-foreground",
    "hov:bg-muted",
    "[&[aria-current]]:bg-secondary [&[aria-current]]:text-secondary-foreground",
    entry.accent && "bg-primary text-primary-foreground hov:bg-primary/90",
  )
  const icon =
    entry.accent && entry.icon === "symbol" ? (
      <SymbolBadge className="-ms-1.5 size-7" />
    ) : entry.icon === "symbol" ? (
      <SymbolMark className="size-icon shrink-0" />
    ) : (
      <entry.icon aria-hidden="true" className="size-icon shrink-0 text-muted-foreground [[aria-current]_&]:text-secondary-foreground" strokeWidth={1.75} />
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
        {icon}
        <span className="truncate">{entry.label}</span>
      </a>
    )
  }
  return (
    <button id={entry.id} type="button" data-safe="" aria-haspopup={popup} onClick={entry.onClick} className={className}>
      {icon}
      <span className="truncate">{entry.label}</span>
    </button>
  )
}

export function Sidebar({ workspaceName, userName, groups, onNavigate }: SidebarProps) {
  const [main, ...rest] = groups
  return (
    <aside
      id="sidebar"
      className="sticky top-0 flex h-dvh w-side shrink-0 flex-col gap-sec border-e border-border bg-card px-edge pb-safe pt-safe"
    >
      <div className="flex items-center gap-2.5 px-1">
        <BrandMark />
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="font-semibold text-heading">صياغة</span>
          <span className="truncate text-small text-muted-foreground">{workspaceName}</span>
        </span>
      </div>
      <nav aria-label="أقسام البوابة" className="flex min-h-0 flex-1 flex-col gap-sec">
        {/* بين بنود السكّة في الحجم الكبير فجوة الهدفين لا فجوة النصّين: مراكزها على بعد 96 على الأقل. */}
        <ul className="flex flex-col gap-tg-min gaze:gap-tg">
          {main.map((entry) => (
            <li key={entry.id}>
              <Row entry={entry} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
        {rest.map((group, index) => (
          <ul key={index} className={cn("flex flex-col gap-tg-min gaze:gap-tg border-t border-border pt-sec", index === rest.length - 1 && "mt-auto")}>
            {group.map((entry) => (
              <li key={entry.id}>
                <Row entry={entry} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        ))}
      </nav>
      {userName ? (
        <p className="truncate px-3 text-small text-muted-foreground" aria-hidden="true">
          {userName}
        </p>
      ) : null}
    </aside>
  )
}
