/*
 * QuantityStepper — كميةٌ بزرّين
 * ===============================
 * − والقيمة و+، بحدٍّ أدنى وأعلى ظاهرين («من 10»). الزرّان قيمٌ (`data-value`):
 * أثرهما في مكانهما ويُعكس بالآخر. والقيمة تُعلَن مهذّبةً بعد كل ضغطة. لا ضغطٌ مطوّل
 * يكرّر: الضغطة الواحدة خطوةٌ واحدة، والمدى الكبير يُكتب في حقل.
 */

import { Minus, Plus } from "lucide-react"

import { cn } from "@/lib/utils"

export interface QuantityStepperProps {
  /** ما تُعدّ: «الكمية المرتجعة من كرسي مكتب». */
  label: string
  value: number
  min?: number
  max: number
  onChange: (value: number) => void
  unit?: string
  className?: string
}

export function QuantityStepper({ label, value, min = 0, max, onChange, unit, className }: QuantityStepperProps) {
  const button =
    "inline-flex size-ctl shrink-0 items-center justify-center rounded-ctl border-2 border-control bg-card text-foreground disabled:border-border disabled:bg-muted disabled:text-muted-foreground hov:bg-muted [&_svg]:size-icon"
  return (
    <div role="group" aria-label={label} className={cn("flex items-center gap-tg-min", className)}>
      <button type="button" data-value="" aria-label={`أنقص ${label}`} disabled={value <= min} onClick={() => onChange(Math.max(min, value - 1))} className={button}>
        <Minus aria-hidden="true" strokeWidth={2.5} />
      </button>
      <output aria-live="polite" className="flex min-w-ctl flex-col items-center leading-tight gaze:flex-1">
        <span className="num text-lead font-bold">{value}</span>
        <span className="text-small text-muted-foreground">
          من <span className="num">{max}</span>
          {unit ? ` ${unit}` : ""}
        </span>
      </output>
      <button type="button" data-value="" aria-label={`زِد ${label}`} disabled={value >= max} onClick={() => onChange(Math.min(max, value + 1))} className={button}>
        <Plus aria-hidden="true" strokeWidth={2.5} />
      </button>
    </div>
  )
}
