/*
 * TabBar — شريط التبويب السفلي وزرّ سيمبول (الهاتف)
 * =================================================
 * الأصل: «Bottom Nav Bar» (arunachalam، 21st.dev: https://21st.dev/@arunachalam/components/bottom-nav-bar، بشروط
 * 21st.dev ورخصة صفحة المكوّن): حبّةٌ بيضاء عائمة فوق أسفل الشاشة بحدٍّ هادئ وظلٍّ واسع، وبنودها حبّاتٌ مدوّرة،
 * والحالي بتعبئةٍ خفيفة من اللون الأساسي. وبجانبها في طرف النهاية زرّ سيمبول العائم: دائرةٌ بالتعبئة الملوّنة
 * وفقاعة محادثةٍ بيضاء، كزرّ البحث بجانب شريط التبويب في iOS. أُخذ التخطيط والمظهر بلا framer-motion ولا حركةٍ عند
 * الضغط: لا مستمعات لمسٍ ولا حركة في الحجم الكبير.
 *
 *   الحجم العادي:  أربعة بنود [الرئيسية · الأقسام · الأدوات · حسابي] أيقونةٌ فوق اسمٍ صغير، وزرّ سيمبول بجانبها.
 *                  ثابتٌ فوق الصفحة (المحتوى ينتهي قبله: `.pb-tab`)، ويختفي ما دام حقلٌ مركَّزاً (`kb:hidden`).
 *   الحجم الكبير:  بندان [الرئيسية · حسابي] وزرّ سيمبول، في التدفّق أسفل الشاشة (لا تمرير)؛ البند 48 ومساحة
 *                  إصابته الخفيّة تملأ الشريط (72)، ومراكز الأهداف الثلاثة على بعد 96 على الأقل.
 *
 * كلّها آمنة (`data-safe`): رابطٌ يفتح شاشةً أو زرٌّ يفتح ورقة، ولا شيء يعتمد. والحالي بعلامة `aria-current`.
 */

import { MessageCircle, type LucideIcon } from "lucide-react"

import { SymbolMark } from "@/components/brand/marks"
import { useSize } from "@/lib/size"
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
  /** بالتعبئة الملوّنة: سيمبول. */
  accent?: boolean
}

function NavIcon({ icon, className }: { icon: LucideIcon | "symbol"; className?: string }) {
  if (icon === "symbol") return <SymbolMark className={className} />
  const Icon = icon
  return <Icon aria-hidden="true" className={className} strokeWidth={1.75} />
}

/** زرّ سيمبول العائم: دائرةٌ بالتعبئة الملوّنة وفقاعة محادثةٍ بيضاء، واسمه «اسأل سيمبول» لقارئ الشاشة. */
export function SymbolButton({ id, onClick, className }: { id: string; onClick?: () => void; className?: string }) {
  // في الحجم الكبير بلا aria-haspopup: WebKit يجعله «زرّاً منبثقاً» بلا سمة الزرّ التي يقصدها «الانتقال إلى العنصر».
  const popup = useSize().size === "gaze" ? undefined : "dialog"
  return (
    <button
      id={id}
      type="button"
      data-safe=""
      aria-haspopup={popup}
      aria-label="اسأل سيمبول"
      onClick={onClick}
      className={cn(
        "inline-flex size-14 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground",
        "shadow-lg shadow-primary/30 hov:bg-primary/90",
        className,
      )}
    >
      <MessageCircle aria-hidden="true" className="size-6 -scale-x-100" strokeWidth={2} />
    </button>
  )
}

export function TabBar({ items, symbol, onNavigate }: { items: NavEntry[]; symbol?: NavEntry; onNavigate: (href: string) => void }) {
  // في الحجم الكبير بلا aria-haspopup: WebKit يجعله «زرّاً منبثقاً» بلا سمة الزرّ التي يقصدها «الانتقال إلى العنصر».
  const popup = useSize().size === "gaze" ? undefined : "dialog"
  const item = (entry: NavEntry) => {
    const className = cn(
      "flex h-11 w-full min-w-0 flex-col items-center justify-center gap-0.5 rounded-full text-[0.6875rem] font-medium leading-normal text-muted-foreground",
      "gaze:h-ctl gaze:gap-1 gaze:text-small",
      "hov:text-foreground [&[aria-current]]:bg-primary/10 [&[aria-current]]:text-primary",
    )
    const content = (
      <>
        <NavIcon icon={entry.icon} className="size-5 shrink-0 gaze:size-icon" />
        {/* حشوٌ سفليٌّ داخل القصّ: نقطتا الياء الأخيرة («حسابي») تنزلان تحت السطر. */}
        <span className="max-w-full truncate px-0.5 pb-0.5">{entry.label}</span>
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
      <button id={entry.id} type="button" data-safe="" aria-haspopup={popup} onClick={entry.onClick} className={className}>
        {content}
      </button>
    )
  }
  return (
    <div data-tab-bar="" className={cn("z-20 kb:hidden", "compact:fixed compact:inset-x-0 compact:bottom-0", "gaze:shrink-0")}>
      <div className="mx-auto flex max-w-content items-center gap-2 px-edge pb-[max(0.5rem,env(safe-area-inset-bottom))] gaze:gap-6 gaze:pt-2">
        <nav
          aria-label="أقسام البوابة"
          className="flex h-14 min-w-0 flex-1 items-center rounded-full border border-border/70 bg-card/95 p-[5px] shadow-xl shadow-black/10 backdrop-blur gaze:bg-card gaze:p-[3px] gaze:backdrop-blur-none"
        >
          <ul className={cn("grid min-w-0 flex-1 gap-2 gaze:gap-6", items.length === 2 ? "grid-cols-2" : "grid-cols-4")}>
            {items.map((entry) => (
              <li key={entry.id} className="min-w-0">
                {item(entry)}
              </li>
            ))}
          </ul>
        </nav>
        {symbol ? <SymbolButton id={symbol.id} onClick={symbol.onClick} /> : null}
      </div>
    </div>
  )
}
