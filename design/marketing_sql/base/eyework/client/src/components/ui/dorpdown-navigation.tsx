/*
 * DropdownNavigation — شريط التنقّل وقوائمه
 * ==========================================
 * الأصل: dorpdown-navigation.tsx من 21st.dev (القوائم بـframer-motion)، كما لصقه
 * المالك، واسم الملفّ كما ورد. مكيَّفٌ لـeyework، ولكل تكييفٍ سببه:
 *
 *  • القائمة تُفتح بالضغط وتُغلق بالضغط، لا بـonMouseEnter: النظر والإصبع لا يحومان،
 *    وقائمةٌ تُفتح حين يمرّ النظر عليها تفتح ما لم يطلبه أحد. ولا مستمع مرورٍ ولا
 *    مؤشّر في الملفّ كلّه.
 *  • البنود أزرارٌ وروابط بارتفاع 72px على الأقل، بأيقونةٍ ونصٍّ ووصف، وبين كل
 *    بندين 24px؛ والقائمة بعرض الشريط تحته، لا عمودٌ ضيّق بجانب الزرّ.
 *  • الحركة تلاشٍ قصير بـframer-motion، ومع «تقليل الحركة» لا حركة أصلاً. لا layoutId
 *    ولا انزلاق: ما يتحرّك تحت نظرٍ باقٍ قد يُضغط وهو يتحرّك.
 *  • اختيار بندٍ يغلق القائمة؛ وEscape يغلقها؛ وفي الحالين يعود التركيز إلى زرّها.
 *    والقائمة تلي زرّها في ترتيب التركيز، لا بعد الأزرار كلّها.
 *  • العربية من اليمين: `start` و`gap` بدل `left` و`space-x`.
 *  • شريطٌ يوضع في رأس الصفحة، لا <main> بارتفاع الشاشة كما في العرض؛ والنوع
 *    `Props` في الأصل كان نوع البند لا نوع الخصائص، فصُحّح.
 */

import * as React from "react"
import { useEffect, useId, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { ChevronDown } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface NavLeaf {
  label: string
  description: string
  icon: React.ElementType
  /** وجهة البند. بندٌ بلا `href` يحمل `onSelect`. */
  href?: string
  onSelect?: () => void
  /** أيقونةٌ لها اتجاه (دخول، خروج): تُعكس في الصفحة العربية. */
  directional?: boolean
}

export interface NavSubMenu {
  title: string
  items: NavLeaf[]
}

export interface NavItem {
  id: number
  label: string
  subMenus?: NavSubMenu[]
  link?: string
}

export interface DropdownNavigationProps {
  navItems: NavItem[]
  /** اسم الشريط لقارئ الشاشة. */
  label?: string
  /** يُبلَّغ المضيف حين تُفتح قائمةٌ أو تُغلق، ليجعل ما تحتها خاملاً (`inert`). */
  onOpenChange?: (open: boolean) => void
  className?: string
}

const leafClass =
  "flex min-h-target w-full items-center gap-4 rounded-xl border border-border bg-card px-4 py-3 text-start shadow-sm transition-colors hover:bg-accent motion-reduce:transition-none"

function Leaf({ leaf, onDone }: { leaf: NavLeaf; onDone: () => void }) {
  const Icon = leaf.icon
  const body = (
    <>
      <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
        <Icon className={cn("size-6", leaf.directional && "rtl:-scale-x-100")} aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="block text-lg font-medium leading-snug text-foreground">{leaf.label}</span>
        <span className="block text-base leading-snug text-muted-foreground">{leaf.description}</span>
      </span>
    </>
  )
  if (leaf.href) {
    return (
      <a href={leaf.href} className={leafClass} onClick={onDone}>
        {body}
      </a>
    )
  }
  return (
    <button
      type="button"
      className={leafClass}
      onClick={() => {
        onDone()
        leaf.onSelect?.()
      }}
    >
      {body}
    </button>
  )
}

export function DropdownNavigation({ navItems, label = "التنقّل", onOpenChange, className }: DropdownNavigationProps) {
  const [openId, setOpenId] = useState<number | null>(null)
  const reduceMotion = useReducedMotion()
  const panelId = useId()
  const triggers = useRef(new Map<number, HTMLButtonElement>())

  function setOpen(next: number | null) {
    setOpenId(next)
    onOpenChange?.(next !== null)
  }

  // الإغلاق بعد اختيارٍ أو بـEscape يعيد التركيز إلى زرّ القائمة، فلا يسقط إلى <body>.
  function close(id: number) {
    setOpen(null)
    triggers.current.get(id)?.focus()
  }

  useEffect(() => {
    if (openId === null) return
    const current = openId
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenId(null)
        onOpenChange?.(false)
        triggers.current.get(current)?.focus()
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [openId, onOpenChange])

  return (
    <nav dir="rtl" aria-label={label} className={cn("relative", className)}>
      <ul className="grid auto-cols-fr grid-flow-col gap-target-gap">
        {navItems.map((item) => (
          <li key={item.id}>
            {item.subMenus ? (
              <button
                ref={(node) => {
                  if (node) triggers.current.set(item.id, node)
                  else triggers.current.delete(item.id)
                }}
                type="button"
                aria-expanded={openId === item.id}
                aria-controls={openId === item.id ? panelId : undefined}
                onClick={() => setOpen(openId === item.id ? null : item.id)}
                className={cn(
                  buttonVariants({ variant: openId === item.id ? "default" : "secondary", width: "full" }),
                  // في أضيق الشاشات: التسمية فوق السهم، فلا يفيض شيءٌ من الزرّ.
                  "min-w-0 px-3 max-[359px]:flex-col max-[359px]:gap-0 max-[359px]:px-2",
                )}
              >
                <span>{item.label}</span>
                <ChevronDown
                  className={cn(
                    "transition-transform motion-reduce:transition-none max-[359px]:!size-4",
                    openId === item.id && "rotate-180",
                  )}
                  aria-hidden="true"
                />
              </button>
            ) : (
              <a href={item.link} className={cn(buttonVariants({ variant: "secondary", width: "full" }), "min-w-0 px-3")}>
                {item.label}
              </a>
            )}

            {/* القائمة في <li> زرّها، مباشرةً بعده في ترتيب التركيز؛ وموضعها نسبةً إلى <nav>. */}
            <AnimatePresence initial={false}>
              {openId === item.id && item.subMenus && (
                <motion.div
                  key={item.id}
                  id={panelId}
                  role="region"
                  aria-label={item.label}
                  initial={reduceMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={reduceMotion ? undefined : { opacity: 0 }}
                  transition={{ duration: 0.15, ease: "easeOut" }}
                  className="absolute inset-x-0 top-full z-20 mt-target-gap rounded-2xl border border-border bg-popover p-5 text-popover-foreground shadow-xl"
                >
                  <div className="flex flex-col gap-target-gap">
                    {item.subMenus.map((sub) => (
                      <section key={sub.title} aria-label={sub.title}>
                        <h3 className="mb-3 text-base font-medium text-muted-foreground">{sub.title}</h3>
                        <ul className="flex flex-col gap-target-gap">
                          {sub.items.map((leaf) => (
                            <li key={leaf.label}>
                              <Leaf leaf={leaf} onDone={() => close(item.id)} />
                            </li>
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </li>
        ))}
      </ul>
    </nav>
  )
}
