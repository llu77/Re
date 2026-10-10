/*
 * Badge — الشارة
 * ==============
 * الأصل: shadcn/ui badge (MIT). نصٌّ دائماً، وأيقونةٌ اختيارية؛ اللون يقوّي المعنى
 * ولا يحمله وحده. ليست هدفاً: لا تُضغط ولا تُركَّز.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-pill border px-2.5 py-0.5 text-small font-semibold leading-snug [&_svg]:size-3.5 [&_svg]:shrink-0 gaze:[&_svg]:size-4",
  {
    variants: {
      tone: {
        neutral: "border-border bg-muted text-foreground",
        info: "border-transparent bg-secondary text-secondary-foreground",
        success: "border-transparent bg-success-tint text-success",
        warning: "border-warning-line/40 bg-warning-tint text-warning",
        danger: "border-transparent bg-destructive-tint text-destructive",
        ai: "border-ai/30 bg-ai-tint text-secondary-foreground",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
)

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  icon?: LucideIcon
}

export function Badge({ className, tone, icon: Icon, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {Icon ? <Icon aria-hidden="true" strokeWidth={2.5} /> : null}
      <span className="truncate">{children}</span>
    </span>
  )
}
