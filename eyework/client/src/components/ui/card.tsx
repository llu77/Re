/*
 * Card — البطاقة
 * ==============
 * الأصل: shadcn/ui card (MIT). بطاقةٌ تُقرأ لا تُضغط: حدٌّ زخرفيٌّ خفيف وظلٌّ قليل؛
 * وما يُضغط فيها أزرارٌ بحدودها. بطاقةٌ كلّها هدفٌ تُبنى زرّاً (`CardButton`) لا
 * <div> بمستمع: لوحة المفاتيح وقارئ الشاشة يعرفانه.
 */

import * as React from "react"

import { cn } from "@/lib/utils"

export interface CardProps extends React.HTMLAttributes<HTMLElement> {
  as?: "section" | "article" | "div" | "li"
}

export function Card({ as: Tag = "section", className, ...props }: CardProps) {
  return <Tag className={cn("min-w-0 rounded-card border border-border bg-card text-foreground shadow-card", className)} {...props} />
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-pad pb-0", className)} {...props} />
}

export function CardTitle({ className, as: Tag = "h2", ...props }: React.HTMLAttributes<HTMLHeadingElement> & { as?: "h2" | "h3" }) {
  return <Tag className={cn("text-title font-bold leading-tight", className)} {...props} />
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-small text-muted-foreground", className)} {...props} />
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-pad", className)} {...props} />
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-wrap items-center gap-tg p-pad pt-0", className)} {...props} />
}
