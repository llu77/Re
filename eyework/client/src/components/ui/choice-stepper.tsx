/*
 * ChoiceStepper — اختيارٌ بخطوتين بدل قائمةٍ تنفتح
 * ==============================================
 * في الحجم الكبير لا تتّسع قائمة خياراتٍ تنفتح تحت حقلٍ في أسفل الشاشة (خيارٌ واحد وأزرار صفحاته 240px على
 * الأقل). فالقيم القليلة المرتّبة (مدّة الخدمة، سبب المتابعة) تُقلَّب في مكانها: «السابق» و«التالي» حول القيمة،
 * كعدّاد الكمية، بعنوانٍ فوقها؛ صفٌّ واحد لا يتحرّك ولا يُخفي شيئاً. الزرّان قيمٌ (`data-value`): ما تحت الضغطة
 * بعدها الزرّ نفسه.
 */

import { ChevronLeft, ChevronRight } from "lucide-react"

const STEP =
  "inline-flex size-ctl shrink-0 items-center justify-center rounded-ctl bg-secondary text-secondary-foreground shadow-sm shadow-black/5 disabled:opacity-50 hov:bg-secondary/80 [&_svg]:size-icon"

export interface ChoiceStepperProps<V extends string | number> {
  /** معرّف القيمة الظاهرة (`output`)، والزرّان `${id}-prev` و`${id}-next`. */
  id: string
  label: string
  options: { value: V; label: string }[]
  value: V | null
  onChange: (value: V) => void
  /** ما يُقرأ قبل الاختيار: «اختر السبب». */
  emptyLabel?: string
  /** اسما الزرّين لقارئ الشاشة: «أقصر» و«أطول» للمدّة. */
  prevLabel?: string
  nextLabel?: string
  error?: string | null
}

export function ChoiceStepper<V extends string | number>({
  id, label, options, value, onChange, emptyLabel = "اختر", prevLabel = "السابق", nextLabel = "التالي", error,
}: ChoiceStepperProps<V>) {
  const index = options.findIndex((option) => option.value === value)
  const labelId = `label-${id}`
  return (
    <div data-field="" className="flex min-w-0 flex-col gap-1">
      <span id={labelId} className="text-small font-medium text-muted-foreground">{label}</span>
      <div role="group" aria-labelledby={labelId} className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-6">
        {/* في الصفحة العربية «السابق» في البداية (يمين) وسهمه إليه، و«التالي» في النهاية. */}
        <button type="button" id={`${id}-prev`} data-value="" aria-label={`${prevLabel}: ${label}`} disabled={index <= 0} onClick={() => onChange(options[index - 1].value)} className={STEP}>
          <ChevronRight aria-hidden="true" strokeWidth={2.5} />
        </button>
        <output id={id} aria-live="polite" className={index < 0 ? "truncate text-center text-muted-foreground" : "truncate text-center text-lead font-bold"}>
          {index < 0 ? emptyLabel : options[index].label}
        </output>
        <button type="button" id={`${id}-next`} data-value="" aria-label={`${nextLabel}: ${label}`} disabled={index >= options.length - 1} onClick={() => onChange(options[index + 1].value)} className={STEP}>
          <ChevronLeft aria-hidden="true" strokeWidth={2.5} />
        </button>
      </div>
      {error ? <p className="text-small font-medium text-destructive">{error}</p> : null}
    </div>
  )
}
