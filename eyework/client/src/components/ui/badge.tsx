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
  "inline-flex max-w-full items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-small font-medium leading-snug [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "bg-muted text-muted-foreground",
        info: "bg-secondary text-secondary-foreground",
        success: "bg-success-tint text-success",
        warning: "bg-warning-tint text-warning",
        danger: "bg-destructive-tint text-destructive",
        ai: "bg-ai-tint text-secondary-foreground",
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
