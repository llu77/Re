/*
 * مكوّنات صياغة فوق مكوّنات shadcn: البلاطة، ومجموعة الخيارات، وحقل القيمة، وسطر
 * المصدر، وتحيّة سيمبول. كلٌّ منها زرٌّ أصليّ بنقرٍ وحده، أو نصٌّ لا يُضغط.
 */
import * as React from "react"
import { BookOpen, Circle, CircleCheck, type LucideIcon } from "lucide-react"

import { SymbolMark } from "@/components/brand/symbol-mark"
import { Button, type ButtonProps } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/*
 * البلاطة: زرٌّ بأيقونةٍ في مربّع، وعنوانٍ، وسطرٍ ثانٍ (`row-status`). بنيتها من
 * Item في shadcn/ui (new-york-v4/ui/item، MIT): ItemMedia وItemTitle وItemDescription،
 * لكنها <button> كلّها: ما تحت المؤشر هو الزرّ نفسه لا أحد أجزائه.
 */
export function Tile({
  icon: Icon,
  title,
  description,
  layout = "row",
  className,
  variant = "quiet",
  ...props
}: Omit<ButtonProps, "icon" | "title"> & {
  icon: LucideIcon
  title: React.ReactNode
  description?: React.ReactNode
  layout?: "row" | "stack"
}) {
  return (
    <Button
      variant={variant}
      className={cn(
        "h-auto gap-3 px-4 py-3 text-start",
        layout === "row" ? "justify-start" : "flex-col items-start justify-between",
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "tile-icon flex size-11 shrink-0 items-center justify-center rounded-xl",
          variant === "secondary" ? "bg-card text-secondary-foreground" : "bg-secondary text-secondary-foreground",
        )}
      >
        <Icon aria-hidden="true" strokeWidth={2.25} className="size-6" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-bold leading-snug">{title}</span>
        {description ? (
          <span className="row-status text-[1rem] font-normal leading-snug text-muted-foreground">{description}</span>
        ) : null}
      </span>
    </Button>
  )
}

/*
 * مجموعة خياراتٍ بأزرارٍ مطلقة القيمة (UI.choiceGroup): الضغط على المختار نفسه لا
 * يفعل شيئاً. الاختيار ظاهرٌ بالإطار الأعرض وعلامة الدائرة الممتلئة، لا باللون وحده.
 */
export interface ChoiceOption<T> {
  value: T
  label: React.ReactNode
  disabled?: boolean
}

export function ChoiceGroup<T extends string | number>({
  options,
  selected,
  onPick,
  columns,
  label,
  id,
  className,
}: {
  options: ChoiceOption<T>[]
  selected: T | null
  onPick: (value: T) => void
  columns: 1 | 2 | 3
  label: string
  id?: string
  className?: string
}) {
  return (
    <div
      id={id}
      role="group"
      aria-label={label}
      className={cn(
        "grid flex-none gap-gap",
        columns === 3 && "grid-cols-3",
        columns === 2 && "grid-cols-2",
        className,
      )}
    >
      {options.map((option) => {
        const pressed = option.value === selected
        return (
          <Button
            key={String(option.value)}
            data-key={String(option.value)}
            aria-pressed={pressed}
            disabled={option.disabled}
            variant={pressed ? "secondary" : "quiet"}
            icon={columns === 1 ? (pressed ? CircleCheck : Circle) : undefined}
            className={cn(
              "chip min-w-0",
              columns === 1 ? "justify-start text-start" : "px-1",
              pressed && "chip--on",
            )}
            onClick={() => {
              if (!pressed) onPick(option.value)
            }}
          >
            {option.label}
          </Button>
        )
      })}
    </div>
  )
}

/* حقل القيمة (السنة، الميزانية، المدّة): الرقم كبيراً، وكلماته تحته. */
export function ValueDisplay({
  id,
  digits,
  words,
  empty,
}: {
  id: string
  digits: string | null
  words: string
  empty: string
}) {
  return (
    <div
      id={id}
      aria-live="polite"
      className="value flex min-h-[4.25rem] flex-col justify-center rounded-card border border-border bg-muted px-4 py-1"
    >
      {digits === null ? (
        <p className="text-muted-foreground">{empty}</p>
      ) : (
        <>
          <p className="font-display text-value font-bold tabular-nums text-heading">
            <bdi>{digits}</bdi>
          </p>
          <p className="text-small leading-snug text-foreground">{words}</p>
        </>
      )}
    </div>
  )
}

/* سطر المصدر تحت كل محتوى مترجم: المحتوى يُعرف من أين جاء. */
export function SourceLine({ children, id, className }: { children: React.ReactNode; id?: string; className?: string }) {
  return (
    <p id={id} className={cn("flex items-start gap-2 text-small text-muted-foreground", className)}>
      <BookOpen aria-hidden="true" strokeWidth={2.25} className="mt-[0.25em] size-[1.05em] shrink-0" />
      <span className="min-w-0">{children}</span>
    </p>
  )
}

/* صورة سيمبول: علامة Symbol في مربّعٍ مستدير. زخرفية؛ الاسم في النصّ بجانبها. */
export function PersonaMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex size-12 shrink-0 items-center justify-center rounded-2xl border border-border bg-card shadow-card",
        className,
      )}
    >
      <SymbolMark className="size-7" />
    </span>
  )
}
