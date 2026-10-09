/*
 * Tabs — الألسنة
 * ==============
 * الأصل: نمط tabs في 21st.dev وshadcn tabs (MIT)، بنمط ARIA APG للألسنة:
 *   • role="tablist" و"tab" و"tabpanel"، وaria-selected وaria-controls.
 *   • تركيزٌ متنقّل: لسانٌ واحد في ترتيب Tab، والأسهم بين الألسنة. في الصفحة العربية
 *     السهم الأيسر إلى التالي والأيمن إلى السابق؛ وHome وEnd إلى الطرفين. الاختيار
 *     يتبع التركيز: اللوحة جاهزةٌ بلا انتظار.
 *   • كل لسانٍ هدفٌ بحدّه وبين كل لسانين `gap-tg-min` (8 أو 24): لا شريطٌ ملتصق.
 *   • المختار يُرى بالإطار والخطّ والعلامة تحته، لا باللون وحده.
 *   • في الحجم الكبير: لسانان يبقيان لسانين؛ وثلاثةٌ أو أكثر تصير زرّاً واحداً «الحالة: جديدة ▾»
 *     يفتح الخيارات مكان المحتوى، ثم يعود المحتوى بعد الاختيار. أربعة ألسنةٍ أربعة أهداف من
 *     عشرة، وزرٌّ واحدٌ هدفٌ واحد؛ ولا يُقصّ شيءٌ ولا تمرّ الشاشة.
 *   • الألسنة قيم (`data-value`): أثرها ظاهرٌ في مكانها ويُعكس بضغطة.
 */

import * as React from "react"
import { Check, ChevronDown, type LucideIcon } from "lucide-react"

import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface TabItem {
  id: string
  label: string
  /** عددٌ بجانب التسمية: «بانتظار ردّي 4». */
  count?: number
  icon?: LucideIcon
}

export interface TabsProps {
  items: TabItem[]
  value: string
  onValueChange: (id: string) => void
  /** اسم المجموعة لقارئ الشاشة. */
  label: string
  /** محتوى اللسان المختار. */
  children: React.ReactNode
  className?: string
  /** يملأ الألسنة عرض الصفّ بالتساوي. */
  stretch?: boolean
}

export function Tabs(props: TabsProps) {
  const { size } = useSize()
  if (size === "gaze" && props.items.length > 2) return <GazeFilter {...props} />
  return <TabList {...props} />
}

/** الحجم الكبير بثلاثة خياراتٍ أو أكثر: زرٌّ يفتح الخيارات مكان المحتوى. */
function GazeFilter({ items, value, onValueChange, label, children, className }: TabsProps) {
  const [open, setOpen] = React.useState(false)
  const toggle = React.useRef<HTMLButtonElement>(null)
  const current = items.find((item) => item.id === value) ?? items[0]
  const regionId = React.useId()
  return (
    <div className={cn("flex min-h-0 flex-col gap-tg", className)}>
      <button
        ref={toggle}
        type="button"
        data-safe=""
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((shown) => !shown)}
        className={cn(
          "flex min-h-ctl w-full items-center justify-between gap-3 rounded-ctl border px-4 text-start",
          open ? "border-primary bg-secondary" : "border-control bg-card",
        )}
      >
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="text-small text-muted-foreground">{label}</span>
          <span className="truncate font-bold">
            {current.label}
            {current.count !== undefined ? <span className="num font-semibold text-muted-foreground"> · {current.count}</span> : null}
          </span>
        </span>
        <ChevronDown aria-hidden="true" className={cn("size-icon shrink-0", open && "rotate-180")} />
      </button>
      <div id={regionId} className="min-h-0">
        {open ? (
          <div role="radiogroup" aria-label={label} className="grid grid-cols-2 gap-tg">
            {items.map((item) => {
              const checked = item.id === value
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={checked}
                  data-value=""
                  onClick={() => {
                    onValueChange(item.id)
                    setOpen(false)
                    toggle.current?.focus()
                  }}
                  className={cn(
                    "flex min-h-ctl items-center justify-between gap-2 rounded-ctl border px-3 text-start",
                    checked ? "border-primary bg-secondary font-bold" : "border-control bg-card",
                  )}
                >
                  <span>
                    {item.label}
                    {item.count !== undefined ? <span className="num text-muted-foreground"> {item.count}</span> : null}
                  </span>
                  {checked ? <Check aria-hidden="true" className="size-icon shrink-0 text-primary" /> : null}
                </button>
              )
            })}
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  )
}

function TabList({ items, value, onValueChange, label, children, className, stretch = false }: TabsProps) {
  const base = React.useId()
  const refs = React.useRef(new Map<string, HTMLButtonElement>())
  const tabId = (id: string) => `${base}-tab-${id}`
  const panelId = (id: string) => `${base}-panel-${id}`

  function move(from: string, step: number | "first" | "last") {
    const index = items.findIndex((item) => item.id === from)
    let next: number
    if (step === "first") next = 0
    else if (step === "last") next = items.length - 1
    else next = (index + step + items.length) % items.length
    const target = items[next]
    onValueChange(target.id)
    refs.current.get(target.id)?.focus()
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, id: string) {
    const rtl = getComputedStyle(event.currentTarget).direction === "rtl"
    const keys: Record<string, number | "first" | "last"> = {
      ArrowLeft: rtl ? 1 : -1,
      ArrowRight: rtl ? -1 : 1,
      Home: "first",
      End: "last",
    }
    const step = keys[event.key]
    if (step === undefined) return
    event.preventDefault()
    move(id, step)
  }

  const many = items.length > 3
  return (
    <div className={cn("flex flex-col gap-tg", className)}>
      <div
        role="tablist"
        aria-label={label}
        className={cn(
          "flex flex-wrap gap-tg-min",
          stretch && "[&>*]:flex-1",
          "gaze:grid gaze:grid-cols-3",
          many && "gaze:grid-cols-2",
        )}
      >
        {items.map((item) => {
          const selected = item.id === value
          const Icon = item.icon
          return (
            <button
              key={item.id}
              ref={(node) => {
                if (node) refs.current.set(item.id, node)
                else refs.current.delete(item.id)
              }}
              type="button"
              role="tab"
              id={tabId(item.id)}
              aria-selected={selected}
              aria-controls={selected ? panelId(item.id) : undefined}
              tabIndex={selected ? 0 : -1}
              data-value=""
              onClick={() => onValueChange(item.id)}
              onKeyDown={(event) => onKeyDown(event, item.id)}
              className={cn(
                "relative inline-flex min-h-ctl min-w-ctl items-center justify-center gap-2 rounded-ctl border px-3.5 text-body",
                "[&_svg]:size-icon [&_svg]:shrink-0",
                selected
                  ? "border-primary bg-secondary font-bold text-secondary-foreground shadow-[inset_0_-3px_0_hsl(var(--primary))]"
                  : "border-control bg-card font-medium text-foreground hov:bg-muted",
              )}
            >
              {Icon ? <Icon aria-hidden="true" strokeWidth={2.25} /> : null}
              <span>{item.label}</span>
              {item.count !== undefined ? (
                <span
                  className={cn(
                    "num min-w-6 rounded-pill px-1.5 text-small font-bold",
                    selected ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
                  )}
                >
                  {item.count}
                </span>
              ) : null}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={panelId(value)} aria-labelledby={tabId(value)} tabIndex={0} className="min-w-0 focus-visible:outline-offset-4">
        {children}
      </div>
    </div>
  )
}
