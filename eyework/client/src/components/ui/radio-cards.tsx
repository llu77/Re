/*
 * RadioCards — اختيارٌ واحدٌ من بطاقات
 * ====================================
 * لحجم الواجهة في التسجيل و«حسابي»، ولكل اختيارٍ له شرحٌ أو معاينة. بنمط ARIA APG
 * لمجموعة الأزرار الراديوية: role="radiogroup" وكل بطاقةٍ role="radio" وaria-checked،
 * وتركيزٌ متنقّل بالأسهم. والضغط يختار ولا يطبّق: التطبيق زرٌّ بعده، فنظرةٌ عابرة لا
 * تغيّر شيئاً لا يُرى أثره.
 */

import * as React from "react"
import { CircleCheck, Circle, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface RadioCardOption<V extends string> {
  value: V
  title: string
  description?: string
  icon?: LucideIcon
  /** رسمٌ صغير يُري الاختيار (معاينة الحجم). */
  preview?: React.ReactNode
}

export interface RadioCardsProps<V extends string> {
  label: string
  options: RadioCardOption<V>[]
  value: V | null
  onValueChange: (value: V) => void
  columns?: 1 | 2
  /** معرّفاتٌ ثابتة للخيارات حين تحتاجها الاختبارات («signup-use-GAZE»). */
  ids?: Partial<Record<V, string>>
  className?: string
}

export function RadioCards<V extends string>({ label, options, value, onValueChange, columns = 2, ids, className }: RadioCardsProps<V>) {
  const refs = React.useRef(new Map<V, HTMLButtonElement>())
  const focusable = value ?? options[0]?.value

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    const rtl = getComputedStyle(event.currentTarget).direction === "rtl"
    const delta: Record<string, number> = {
      ArrowDown: 1, ArrowUp: -1, ArrowLeft: rtl ? 1 : -1, ArrowRight: rtl ? -1 : 1,
    }
    if (delta[event.key] === undefined) return
    event.preventDefault()
    const next = options[(index + delta[event.key] + options.length) % options.length]
    onValueChange(next.value)
    refs.current.get(next.value)?.focus()
  }

  return (
    <div role="radiogroup" aria-label={label} className={cn("grid gap-tg", columns === 2 ? "grid-cols-2" : "grid-cols-1", className)}>
      {options.map((option, index) => {
        const checked = option.value === value
        const Icon = option.icon
        return (
          <button
            key={option.value}
            ref={(node) => {
              if (node) refs.current.set(option.value, node)
              else refs.current.delete(option.value)
            }}
            type="button"
            id={ids?.[option.value]}
            role="radio"
            aria-checked={checked}
            tabIndex={option.value === focusable ? 0 : -1}
            data-value=""
            onClick={() => onValueChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "flex min-h-ctl min-w-0 flex-col items-stretch gap-1.5 rounded-card border px-pad py-2.5 text-start",
              checked ? "border-primary-line bg-secondary" : "border-control bg-card hov:bg-muted",
            )}
          >
            <span className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 font-semibold text-foreground">
                {Icon ? <Icon aria-hidden="true" className="size-icon shrink-0 text-secondary-foreground" /> : null}
                {option.title}
              </span>
              {checked ? (
                <CircleCheck aria-hidden="true" className="size-icon shrink-0 text-primary" strokeWidth={2.5} />
              ) : (
                <Circle aria-hidden="true" className="size-icon shrink-0 text-control" />
              )}
            </span>
            {option.preview}
            {option.description ? <span className="text-small text-muted-foreground">{option.description}</span> : null}
          </button>
        )
      })}
    </div>
  )
}
