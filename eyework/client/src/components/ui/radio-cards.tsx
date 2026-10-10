/*
 * RadioCards — اختيارٌ واحدٌ من بطاقات
 * ====================================
 * لحجم الواجهة في التسجيل و«حسابي»، ولكل اختيارٍ له شرحٌ أو معاينة. بنمط ARIA APG
 * لمجموعة الأزرار الراديوية: role="radiogroup" وكل بطاقةٍ role="radio" وaria-checked،
 * وتركيزٌ متنقّل بالأسهم. والضغط يختار ولا يطبّق: التطبيق زرٌّ بعده، فنظرةٌ عابرة لا
 * تغيّر شيئاً لا يُرى أثره.
 *
 * وفي الحجم الكبير كل بطاقةٍ زرٌّ بـaria-pressed في مجموعة: «الانتقال إلى العنصر» في تتبّع العين
 * والرأس يقصد ما له سمة الزرّ، وWebKit لا يعطيها role="radio".
 */

import * as React from "react"
import { CircleCheck, Circle, type LucideIcon } from "lucide-react"

import { useSize } from "@/lib/size"
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
  /** الحجم الكبير: بطاقتان في الصفّ لخياراتٍ بعناوين قصيرة بلا أيقونةٍ ولا شرح (أربعة خياراتٍ في صفّين). */
  gazeColumns?: 1 | 2
  /** معرّفاتٌ ثابتة للخيارات حين تحتاجها الاختبارات («signup-use-GAZE»). */
  ids?: Partial<Record<V, string>>
  className?: string
}

export function RadioCards<V extends string>({ label, options, value, onValueChange, columns = 2, gazeColumns = 1, ids, className }: RadioCardsProps<V>) {
  const refs = React.useRef(new Map<V, HTMLButtonElement>())
  const focusable = value ?? options[0]?.value
  const gaze = useSize().size === "gaze"

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
    // في الحجم الكبير بطاقةٌ في كل صفّ: نصفُ عرض 320px لا يتّسع للأيقونة والعنوان والدائرة فيتراكبن — إلا عناوين
    // قصيرة وحدها (`gazeColumns`)، والعنوان يلتفّ سطرين في بطاقته ولا يخرج منها؛ وبين البطاقتين 24 بجانبهما.
    // `data-block`: بطاقاتٌ قد يليها حقلٌ بعنوانه (globals.css)؛ لا عنوان ظاهراً لها فلا تلي حقلاً بـ28px.
    <div data-block="" role={gaze ? "group" : "radiogroup"} aria-label={label}
      className={cn("grid gap-tg", columns === 2 ? "grid-cols-2" : "grid-cols-1", gazeColumns === 2 ? "gaze:grid-cols-2 gaze:gap-x-6" : "gaze:grid-cols-1", className)}>
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
            role={gaze ? undefined : "radio"}
            aria-checked={gaze ? undefined : checked}
            aria-pressed={gaze ? checked : undefined}
            tabIndex={gaze || option.value === focusable ? 0 : -1}
            data-value=""
            onClick={() => onValueChange(option.value)}
            onKeyDown={gaze ? undefined : (event) => onKeyDown(event, index)}
            className={cn(
              "flex min-h-ctl min-w-0 flex-col items-stretch gap-1.5 rounded-card border px-pad py-2.5 text-start",
              checked ? "border-primary bg-secondary" : "border-transparent bg-card shadow-card hov:bg-muted",
            )}
          >
            <span className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 font-medium text-foreground">
                {Icon ? <Icon aria-hidden="true" className="size-icon shrink-0 text-secondary-foreground" strokeWidth={1.75} /> : null}
                <span className="min-w-0">{option.title}</span>
              </span>
              {checked ? (
                <CircleCheck aria-hidden="true" className="size-icon shrink-0 text-primary" strokeWidth={2.25} />
              ) : (
                <Circle aria-hidden="true" className="size-icon shrink-0 text-control" strokeWidth={1.75} />
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
