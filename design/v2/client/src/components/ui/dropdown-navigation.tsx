/*
 * DropdownNavigation — أقسام البوابة
 * =================================
 * الأصل: dorpdown-navigation.tsx من 21st.dev كما لصقه المالك (القوائم بـframer-motion)،
 * بعد تكييف eyework/client له (الضغط لا التحويم، Escape، التركيز يعود إلى الزرّ، العربية).
 * وفي v2 صار له شكلان من البيانات نفسها:
 *
 *   • `bar` — الحاسوب في الحجم العادي: الأقسام صفٌّ في الرأس كما في الأصل، والقسم الحالي
 *     `aria-current="page"`، وما له قائمةٌ فرعية يفتحها بالضغط تحته (نمط الأصل).
 *   • `switcher` — الهاتف، والحجم الكبير في كل شاشة: زرٌّ واحد يقول المهنة والشاشة الحالية،
 *     يفتح لوحةً بالرئيسية وأعمال المهنة بعرض الرأس: قائمةٌ في العادي، وبلاطاتٌ في عمودين في
 *     الكبير (سبعة بنودٍ في أربعة صفوف: 360px، فتتّسع في أقصر شاشة بلا تمرير).
 *
 * ما بقي من تكييف v1 ولماذا:
 *   • يُفتح ويُغلق بالضغط وحده: لا onMouseEnter. قائمةٌ تُفتح حين يمرّ النظر عليها تفتح
 *     ما لم يطلبه أحد.
 *   • الحركة تلاشٍ قصير في الحجم العادي، ولا حركة في الكبير ولا مع «تقليل الحركة»؛ لا
 *     layoutId ولا انزلاق: ما يتحرّك تحت نظرٍ باقٍ قد يُضغط وهو يتحرّك.
 *   • الاختيار يغلق، وEscape يغلق، والضغط خارجها يغلق؛ والتركيز يعود إلى زرّها.
 *   • المضيف يجعل ما تحت اللوحة خاملاً وغير مرئي (`onOpenChange`): لا يُصاب من حوافّها.
 */

import * as React from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Check, ChevronDown, UserRound, type LucideIcon } from "lucide-react"

import { useOutsideClick } from "@/components/ui/popover"
import { NONE, QUICK, useMotionAllowed } from "@/lib/motion"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface NavLeaf {
  id: string
  label: string
  description?: string
  icon: LucideIcon
  href: string
  current?: boolean
}

export interface NavItem extends NavLeaf {
  /** قائمةٌ فرعية تُفتح بالضغط تحت البند (شكل `bar`). */
  subMenus?: { title: string; items: NavLeaf[] }[]
}

export interface DropdownNavigationProps {
  items: NavItem[]
  /** اسم التنقّل لقارئ الشاشة. */
  label: string
  variant: "bar" | "switcher"
  /** سطرٌ صغير فوق اسم القسم في زرّ `switcher`: اسم المهنة. */
  caption?: string
  /** اسم الشاشة الحالية في زرّ `switcher` حين لا بند لها في القائمة («حسابي»). */
  currentLabel?: string
  onNavigate?: (href: string) => void
  onOpenChange?: (open: boolean) => void
  /** مفتوحةٌ من أولها (صفحة العرض). */
  defaultOpen?: string | null
  className?: string
}

function Leaf({ leaf, tile, onDone }: { leaf: NavLeaf; tile: boolean; onDone: (href: string) => void }) {
  const Icon = leaf.icon
  return (
    <a
      href={leaf.href}
      data-safe=""
      aria-current={leaf.current ? "page" : undefined}
      onClick={(event) => {
        event.preventDefault()
        onDone(leaf.href)
      }}
      className={cn(
        "flex min-h-ctl w-full items-center gap-3 rounded-ctl border-2 px-3 py-1.5 text-start",
        leaf.current ? "border-primary bg-secondary" : "border-control bg-card hov:bg-muted",
        tile && "h-full flex-col justify-center gap-1.5 px-2 py-2 text-center",
      )}
    >
      <span
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-ctl",
          leaf.current ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground",
          tile && "size-9",
        )}
      >
        <Icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
      </span>
      <span className={cn("flex min-w-0 flex-1 flex-col", tile && "flex-none items-center")}>
        <span className="font-bold leading-snug text-foreground">{leaf.label}</span>
        {leaf.description && !tile ? <span className="text-small leading-snug text-muted-foreground">{leaf.description}</span> : null}
      </span>
      {leaf.current && !tile ? <Check aria-hidden="true" className="size-icon shrink-0 text-primary" strokeWidth={2.5} /> : null}
    </a>
  )
}

export function DropdownNavigation({
  items, label, variant, caption, currentLabel, onNavigate, onOpenChange, defaultOpen = null, className,
}: DropdownNavigationProps) {
  const { size } = useSize()
  const animate = useMotionAllowed()
  const [openId, setOpenId] = React.useState<string | null>(defaultOpen)
  const root = React.useRef<HTMLElement>(null)
  const triggers = React.useRef(new Map<string, HTMLButtonElement>())
  const panelId = React.useId()

  const report = React.useRef(onOpenChange)
  report.current = onOpenChange
  React.useEffect(() => {
    report.current?.(openId !== null)
  }, [openId])

  const opened = React.useRef(openId)
  opened.current = openId
  const close = React.useCallback((returnFocus: boolean) => {
    const id = opened.current
    setOpenId(null)
    if (returnFocus && id) triggers.current.get(id)?.focus()
  }, [])

  useOutsideClick(openId !== null, root, () => close(false))

  React.useEffect(() => {
    if (openId === null) return
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close(true)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [openId, close])

  function navigate(href: string) {
    close(true)
    onNavigate?.(href)
  }

  const register = (id: string) => (node: HTMLButtonElement | null) => {
    if (node) triggers.current.set(id, node)
    else triggers.current.delete(id)
  }

  const fade = {
    initial: animate ? { opacity: 0 } : false,
    animate: { opacity: 1 },
    exit: animate ? { opacity: 0 } : undefined,
    transition: animate ? QUICK : NONE,
  } as const

  if (variant === "switcher") {
    const current = items.find((item) => item.current) ?? null
    const open = openId === "switcher"
    const CurrentIcon = current?.icon ?? UserRound
    return (
      <nav ref={root} aria-label={label} className={cn("min-w-0", className)}>
        <button
          ref={register("switcher")}
          type="button"
          data-safe=""
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={() => setOpenId(open ? null : "switcher")}
          className={cn(
            "flex min-h-ctl w-full min-w-0 items-center gap-2.5 rounded-ctl border-2 px-2.5 text-start",
            open ? "border-primary bg-secondary" : "border-control bg-card hov:bg-muted",
          )}
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-ctl bg-primary text-primary-foreground gaze:size-10">
            <CurrentIcon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
          </span>
          <span className="flex min-w-0 flex-1 flex-col leading-tight">
            {caption ? <span className="truncate text-small text-muted-foreground">{caption}</span> : null}
            <span className="truncate font-bold text-foreground">{currentLabel ?? current?.label}</span>
          </span>
          <ChevronDown aria-hidden="true" className={cn("size-icon shrink-0 text-muted-foreground", open && "rotate-180")} />
        </button>
        <AnimatePresence initial={false}>
          {open ? (
            <motion.div
              key="panel"
              id={panelId}
              role="region"
              aria-label="الأقسام"
              {...fade}
              className="absolute inset-x-0 top-full z-30 mt-tg-min rounded-card border border-border bg-card p-pad shadow-pop"
            >
              <ul className={cn("grid gap-tg-min", size === "gaze" ? "grid-cols-2 gap-tg" : "grid-cols-1")}>
                {items.map((item) => (
                  <li key={item.id}>
                    <Leaf leaf={item} tile={size === "gaze"} onDone={navigate} />
                  </li>
                ))}
              </ul>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </nav>
    )
  }

  return (
    <nav ref={root} aria-label={label} className={cn("min-w-0", className)}>
      <ul className="flex items-center gap-tg-min">
        {items.map((item) => {
          const Icon = item.icon
          const open = openId === item.id
          const look = cn(
            "inline-flex min-h-ctl items-center gap-2 whitespace-nowrap rounded-ctl border-2 px-3 font-semibold",
            item.current ? "border-primary bg-secondary text-secondary-foreground" : "border-transparent text-foreground hov:bg-muted",
            open && "border-primary",
          )
          return (
            <li key={item.id} className="relative">
              {item.subMenus ? (
                <button
                  ref={register(item.id)}
                  type="button"
                  data-safe=""
                  aria-expanded={open}
                  aria-controls={open ? panelId : undefined}
                  onClick={() => setOpenId(open ? null : item.id)}
                  className={look}
                >
                  <Icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
                  {item.label}
                  <ChevronDown aria-hidden="true" className={cn("size-4", open && "rotate-180")} />
                </button>
              ) : (
                <a
                  href={item.href}
                  data-safe=""
                  aria-current={item.current ? "page" : undefined}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(item.href)
                  }}
                  className={look}
                >
                  <Icon aria-hidden="true" className="size-icon" strokeWidth={2.25} />
                  {item.label}
                </a>
              )}
              <AnimatePresence initial={false}>
                {open && item.subMenus ? (
                  <motion.div
                    key={item.id}
                    id={panelId}
                    role="region"
                    aria-label={item.label}
                    {...fade}
                    className="absolute start-0 top-full z-30 mt-tg-min w-max min-w-[18rem] rounded-card border border-border bg-card p-pad shadow-pop"
                  >
                    <div className="flex gap-sec">
                      {item.subMenus.map((sub) => (
                        <section key={sub.title} aria-label={sub.title} className="flex flex-col gap-2">
                          <h3 className="text-small font-semibold text-muted-foreground">{sub.title}</h3>
                          <ul className="flex flex-col gap-tg-min">
                            {sub.items.map((leaf) => (
                              <li key={leaf.id}>
                                <Leaf leaf={leaf} tile={false} onDone={navigate} />
                              </li>
                            ))}
                          </ul>
                        </section>
                      ))}
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
