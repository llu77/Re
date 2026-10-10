/*
 * الشارة — من shadcn/ui (new-york-v4/ui/badge، MIT). نصٌّ لا هدف: لا asChild ولا
 * رابط. 16px على الأقل (الأصل 12): الشارة تُقرأ لا تُلمح.
 */
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border px-3 py-0.5 text-small font-semibold [&>svg]:size-[1.1em] [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        brand: "border-transparent bg-secondary text-secondary-foreground",
        neutral: "border-border bg-muted text-foreground",
        success: "border-transparent bg-success-tint text-success",
        outline: "border-control bg-card text-foreground",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
)

export interface BadgeProps extends React.ComponentProps<"span">, VariantProps<typeof badgeVariants> {
  icon?: LucideIcon
}

export function Badge({ className, variant, icon: Icon, children, ...props }: BadgeProps) {
  return (
    <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props}>
      {Icon ? <Icon aria-hidden="true" strokeWidth={2.25} /> : null}
      {children}
    </span>
  )
}
