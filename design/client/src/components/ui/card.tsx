/*
 * البطاقة — من shadcn/ui (new-york-v4/ui/card، MIT). للقراءة لا للضغط: حدٌّ خفيف
 * وظلّ، وحشوٌ أضيق (16) من الأصل (24) ليتّسع المحتوى في 320×635 بلا تمرير.
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "card-surface flex flex-col gap-2 rounded-card border border-border bg-card p-4 text-card-foreground shadow-card",
        className,
      )}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: React.ComponentProps<"p">) {
  return <p data-slot="card-title" className={cn("font-bold text-heading", className)} {...props} />
}

export function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p data-slot="card-description" className={cn("text-small text-muted-foreground", className)} {...props} />
}
