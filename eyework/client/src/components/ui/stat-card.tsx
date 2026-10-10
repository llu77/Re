/*
 * StatCard — بطاقة مجموع
 * =====================
 * الأصل: «Statistics Card 2» (sean0205، 21st.dev: https://21st.dev/@sean0205/components/statistics-card-2، بشروط
 * 21st.dev ورخصة صفحة المكوّن) بلا أيقونةٍ في مربّع: التسمية صغيرةٌ فوق القيمة. القيمة رقمٌ لاتينيٌّ بعرضٍ ثابت ووحدتها نصّ،
 * والتغيّر نصٌّ بسهمٍ واتجاهه (لا لونٌ وحده)، والمصدر سطرٌ صغير («من 12 فاتورة»).
 * بطاقةٌ لها `onSelect` زرٌّ كلّها (تفتح قائمتها)، وإلا فهي تُقرأ فقط.
 */

import { ArrowDownRight, ArrowUpRight, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface StatCardProps {
  label: string
  value: string
  unit?: string
  icon?: LucideIcon
  /** «+12% عن الشهر الماضي». */
  delta?: { text: string; direction: "up" | "down"; good: boolean }
  hint?: string
  tone?: "default" | "warning"
  onSelect?: () => void
  className?: string
}

export function StatCard({ label, value, unit, icon: Icon, delta, hint, tone = "default", onSelect, className }: StatCardProps) {
  const body = (
    <>
      <span className={cn("flex items-center gap-1.5 text-small font-medium", tone === "warning" ? "text-warning" : "text-muted-foreground")}>
        {Icon ? <Icon aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={2} /> : null}
        {label}
      </span>
      <span className="flex items-baseline gap-1.5">
        <span className="num text-value font-bold text-heading" dir="ltr">
          {value}
        </span>
        {unit ? <span className="text-small font-semibold text-muted-foreground">{unit}</span> : null}
      </span>
      {delta ? (
        <span className={cn("flex items-center gap-1 text-small font-semibold", delta.good ? "text-success" : "text-destructive")}>
          {delta.direction === "up" ? (
            <ArrowUpRight aria-hidden="true" className="size-4" />
          ) : (
            <ArrowDownRight aria-hidden="true" className="size-4" />
          )}
          {delta.text}
        </span>
      ) : null}
      {hint ? <span className="text-small text-muted-foreground">{hint}</span> : null}
    </>
  )
  const box = cn(
    "flex min-w-0 flex-col items-start gap-1 rounded-card border bg-card p-pad text-start shadow-card gaze:short:gap-0.5 gaze:short:p-3",
    tone === "warning" ? "border-warning-line/40" : "border-transparent",
    className,
  )
  if (onSelect) {
    return (
      <button type="button" data-safe="" onClick={onSelect} className={cn(box, "min-h-ctl hov:bg-muted")}>
        {body}
      </button>
    )
  }
  return <div className={box}>{body}</div>
}
