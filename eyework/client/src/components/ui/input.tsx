/*
 * Field وInput وTextarea — الحقول
 * ===============================
 * الأصل: shadcn/ui input وfield وlabel (MIT). والتكييف:
 *   • التسمية ظاهرةٌ فوق الحقل دائماً، ولا `placeholder` بدلها: نصٌّ يختفي مع أول
 *     حرف لا يُعاد قراءته، ومن يكتب بالنظر يكتب ببطء.
 *   • الخطّ 16px على الأقل في الحجمين: iOS لا يكبّر الصفحة عند التركيز.
 *   • `Field` يربط التسمية والمساعدة والخطأ بالحقل (`aria-describedby` و`aria-invalid`)
 *     بالسياق، فلا يُنسى ربطٌ في شاشة.
 *   • الخطأ تحت الحقل نصٌّ وأيقونة، لا لونٌ وحده؛ ومكانه محجوزٌ إن طُلب (`reserve`)
 *     فلا يتحرّك ما تحته حين يظهر.
 *   • الوحدة (ر.س، حبة) نصٌّ داخل الحقل في طرفه، لا هدف.
 */

import * as React from "react"
import { AlertCircle } from "lucide-react"

import { cn } from "@/lib/utils"

interface FieldContextValue {
  id: string
  hintId?: string
  errorId?: string
  invalid: boolean
  required: boolean
}

const FieldContext = React.createContext<FieldContextValue | null>(null)

/** خصائص الحقل من `Field` المحيط به، أو لا شيء خارجه. */
export function useFieldControl() {
  const field = React.useContext(FieldContext)
  if (!field) return {}
  const describedBy = [field.hintId, field.errorId].filter(Boolean).join(" ") || undefined
  return {
    id: field.id,
    "aria-describedby": describedBy,
    "aria-invalid": field.invalid || undefined,
    "aria-required": field.required || undefined,
  }
}

export interface FieldProps {
  label: React.ReactNode
  hint?: React.ReactNode
  error?: string | null
  required?: boolean
  /** يحجز سطر الخطأ وإن لم يكن خطأ: لا يتحرّك ما تحت الحقل حين يظهر. */
  reserve?: boolean
  /** معرّفٌ ثابت للحقل حين يحتاجه غيره (تركيز «عدّل» في تنبيه سيمبول). */
  id?: string
  className?: string
  children: React.ReactNode
}

export function Field({ label, hint, error, required = false, reserve = false, id, className, children }: FieldProps) {
  const auto = React.useId()
  const controlId = id ?? `f${auto}`
  const value: FieldContextValue = {
    id: controlId,
    hintId: hint ? `${controlId}-hint` : undefined,
    errorId: error ? `${controlId}-error` : undefined,
    invalid: Boolean(error),
    required,
  }
  return (
    <FieldContext.Provider value={value}>
      <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
        <Label htmlFor={controlId}>
          {label}
          {required ? <span className="text-muted-foreground"> (مطلوب)</span> : null}
        </Label>
        {children}
        {hint ? (
          <p id={value.hintId} className="text-small text-muted-foreground">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={value.errorId} className="flex items-start gap-1.5 text-small font-medium text-destructive">
            <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        ) : reserve ? (
          <p aria-hidden="true" className="text-small">
            &nbsp;
          </p>
        ) : null}
      </div>
    </FieldContext.Provider>
  )
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-small font-semibold text-foreground", className)} {...props} />
}

export const fieldClass = [
  "w-full min-w-0 rounded-ctl border-2 border-control bg-card px-3 text-body text-foreground shadow-ctl",
  "min-h-ctl",
  "focus-visible:border-primary focus-visible:outline-offset-1",
  "aria-[invalid=true]:border-destructive",
  "disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground",
  "read-only:bg-muted",
].join(" ")

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** نصٌّ في طرف الحقل: «ر.س»، «حبة». */
  unit?: string
  /** أرقامٌ ومبالغ: لاتينيةٌ بعرضٍ ثابت ومن اليسار. */
  numeric?: boolean
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, unit, numeric, ...props }, ref) => {
  const control = useFieldControl()
  const input = (
    <input
      ref={ref}
      {...control}
      dir={numeric ? "ltr" : props.dir}
      className={cn(fieldClass, numeric && "num text-end", unit && (numeric ? "pe-3 ps-12" : "pe-12"), className)}
      {...props}
    />
  )
  if (!unit) return input
  return (
    <div className="relative">
      {input}
      {/* الوحدة في طرف الحقل البعيد عن بداية الكتابة: يسار الحقل العربي، ويساره أيضاً للأرقام. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-small font-medium text-muted-foreground"
      >
        {unit}
      </span>
    </div>
  )
})
Input.displayName = "Input"

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, rows = 3, ...props }, ref) => {
    const control = useFieldControl()
    return (
      <textarea
        ref={ref}
        rows={rows}
        {...control}
        className={cn(fieldClass, "resize-none py-2.5 leading-relaxed", className)}
        {...props}
      />
    )
  },
)
Textarea.displayName = "Textarea"
