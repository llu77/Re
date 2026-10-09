/*
 * Stepper — أين أنا من الخطوات
 * ============================
 * الأصل: نمط stepper في 21st.dev (originui stepper)، للقراءة لا للضغط: التنقّل بين
 * الخطوات بـ«التالي» و«رجوع» في الشاشة، فلا أهداف هنا تزيد عدد ما يُضغط.
 *   • قائمةٌ مرتّبة، والخطوة الحالية `aria-current="step"`، وما تمّ بعلامة صحٍّ ونصّ.
 *   • الهاتف والحجم الكبير: «الخطوة 2 من 4» واسمها وشريطٌ مقسّم؛ والحاسوب: الخطوات كلّها.
 */

import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

export interface StepperProps {
  steps: { id: string; label: string }[]
  /** الخطوة الحالية من 0. */
  current: number
  /** `brief`: «الخطوة 2 من 10» وحدها في كل عرض (خطواتٌ كثيرة لا تتّسع صفّاً). */
  variant?: "auto" | "brief"
  className?: string
}

export function Stepper({ steps, current, variant = "auto", className }: StepperProps) {
  const label = steps[current]?.label ?? ""
  return (
    // في الشاشة القصيرة بالحجم الكبير يكفي العنوان: لا يتّسع شريط الخطوات.
    <div className={cn("flex flex-col gap-2 gaze:short:hidden", className)}>
      {/* الهاتف والحجم الكبير */}
      <div className={cn("flex flex-col gap-2", variant === "auto" && "lg:hidden gaze:flex")}>
        <p className="text-small font-semibold text-muted-foreground">
          الخطوة <span className="num">{current + 1}</span> من <span className="num">{steps.length}</span>:{" "}
          <span className="text-foreground">{label}</span>
        </p>
        <div aria-hidden="true" className="flex gap-1.5">
          {steps.map((s, index) => (
            <span key={s.id} className={cn("h-1.5 flex-1 rounded-pill gaze:h-2", index <= current ? "bg-primary" : "bg-border")} />
          ))}
        </div>
      </div>
      {/* الحاسوب */}
      <ol aria-label="الخطوات" className={cn("hidden items-center gap-3", variant === "auto" && "lg:flex gaze:hidden")}>
        {steps.map((s, index) => {
          const done = index < current
          const now = index === current
          return (
            <li key={s.id} aria-current={now ? "step" : undefined} className="flex items-center gap-2">
              <span
                className={cn(
                  "num flex size-7 shrink-0 items-center justify-center rounded-pill border text-small font-bold",
                  done && "border-primary bg-primary text-primary-foreground",
                  now && "border-primary bg-secondary text-secondary-foreground",
                  !done && !now && "border-control bg-card text-muted-foreground",
                )}
              >
                {done ? <Check aria-hidden="true" className="size-4" strokeWidth={3} /> : index + 1}
              </span>
              <span className={cn("text-small", now ? "font-bold text-foreground" : "text-muted-foreground")}>
                {s.label}
                {done ? <span className="sr-only"> (تمّت)</span> : null}
              </span>
              {index < steps.length - 1 ? <span aria-hidden="true" className="h-0.5 w-8 rounded-pill bg-border" /> : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
