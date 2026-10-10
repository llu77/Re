/*
 * RadioCards — اختيارٌ واحدٌ من بطاقات
 * ====================================
 * الأصل: «Styled Radio Group» (ai2، 21st.dev: https://21st.dev/@ai2/components/radio-group-styled) و«Icon Card Radio
 * Group» (sean0205، 21st.dev: https://21st.dev/@sean0205/components/c-radio-group-11)، بشروط 21st.dev ورخصة صفحة كلٍّ
 * منهما. ثلاثة أشكالٍ بحسب الخيارات، وعناوينها في سطرٍ واحد لا يلتفّ:
 *   • صفٌّ (Card): العنوان ثم دائرة الاختيار في آخره، والشرح تحته. لعمودٍ واحد، أو لخياراتٍ لها شرح.
 *   • زرّا اختيارٍ متساويان في الصفّ (Pill): عنوانٌ قصير في الوسط بلا دائرة، والمختار بحدٍّ ملوّن وتعبئةٍ خفيفة.
 *     لعمودين بعناوين قصيرة وحدها؛ ما لا يتّسع عنوانه لنصف الصفّ في 320 يُعطى عموداً واحداً.
 *   • بطاقةٌ بأيقونة (Icon Card): مربّعُ أيقونةٍ أبيض فوق العنوان، والدائرة في زاوية النهاية العليا. لعمودين بأيقونات.
 * والدائرة كما في «Styled Radio Group»: حلقةٌ هادئة، والمختارة مملوءةٌ بنقطةٍ بيضاء. أُخذ المظهر بلا Radix ولا
 * framer-motion: البطاقة زرٌّ واحد، ولا حركة.
 *
 * لحجم الواجهة في التسجيل و«حسابي»، ولكل اختيارٍ له شرحٌ أو معاينة. بنمط ARIA APG
 * لمجموعة الأزرار الراديوية: role="radiogroup" وكل بطاقةٍ role="radio" وaria-checked،
 * وتركيزٌ متنقّل بالأسهم. والضغط يختار ولا يطبّق: التطبيق زرٌّ بعده، فنظرةٌ عابرة لا
 * تغيّر شيئاً لا يُرى أثره.
 *
 * وفي الحجم الكبير كل بطاقةٍ زرٌّ بـaria-pressed في مجموعة: «الانتقال إلى العنصر» في تتبّع العين
 * والرأس يقصد ما له سمة الزرّ، وWebKit لا يعطيها role="radio".
 */

import * as React from "react"
import type { LucideIcon } from "lucide-react"

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

/** دائرة الاختيار: حلقةٌ هادئة، والمختارة مملوءةٌ بنقطةٍ بيضاء. */
function Dot({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-4 shrink-0 items-center justify-center rounded-full border gaze:size-5",
        checked ? "border-primary bg-primary" : "border-control bg-card",
      )}
    >
      {checked ? <span className="size-1.5 rounded-full bg-primary-foreground gaze:size-2" /> : null}
    </span>
  )
}

export function RadioCards<V extends string>({ label, options, value, onValueChange, columns = 2, gazeColumns = 1, ids, className }: RadioCardsProps<V>) {
  const refs = React.useRef(new Map<V, HTMLButtonElement>())
  const focusable = value ?? options[0]?.value
  const gaze = useSize().size === "gaze"
  const two = gaze ? gazeColumns === 2 : columns === 2
  const plain = options.every((option) => !option.icon && !option.description && !option.preview)
  const shape: "row" | "pill" | "icon" = two && plain ? "pill" : two && !gaze && options.every((option) => option.icon) ? "icon" : "row"

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
    // في الحجم الكبير بطاقةٌ في كل صفّ: نصفُ عرض 320px لا يتّسع للأيقونة والعنوان والدائرة — إلا زرّا اختيارٍ
    // بعناوين قصيرة وحدها (`gazeColumns`)، وبينهما 24 بجانبهما.
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
              "relative flex min-h-ctl min-w-0 rounded-card border transition-colors gaze:transition-none",
              shape === "pill" && "items-center justify-center whitespace-nowrap px-2 text-center font-medium",
              shape === "icon" && "flex-col items-stretch gap-2 p-3 text-start",
              shape === "row" && "flex-col items-stretch justify-center gap-1 px-pad py-2.5 text-start",
              checked
                ? cn("border-primary bg-secondary shadow-sm shadow-black/5", shape === "pill" ? "text-secondary-foreground" : "text-foreground")
                : "border-border bg-card text-foreground shadow-sm shadow-black/5 hov:bg-muted",
            )}
          >
            {shape === "pill" ? (
              option.title
            ) : shape === "icon" && Icon ? (
              <>
                <span className="absolute end-3 top-3">
                  <Dot checked={checked} />
                </span>
                <span className="flex size-8 items-center justify-center self-start rounded-ctl border border-border bg-background shadow-sm shadow-black/5">
                  <Icon aria-hidden="true" className="size-4" strokeWidth={1.75} />
                </span>
                <span className="whitespace-nowrap font-medium">{option.title}</span>
              </>
            ) : (
              <span className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2 whitespace-nowrap font-medium">
                  {Icon ? <Icon aria-hidden="true" className="size-icon shrink-0 text-secondary-foreground" strokeWidth={1.75} /> : null}
                  {option.title}
                </span>
                <Dot checked={checked} />
              </span>
            )}
            {shape === "pill" ? null : option.preview}
            {shape !== "pill" && option.description ? (
              // الشرح نصٌّ جارٍ يلتفّ في بطاقته (`data-wrap`)؛ العنوان وحده سطرٌ واحد.
              <span data-wrap="" className="text-small text-muted-foreground">
                {option.description}
              </span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
