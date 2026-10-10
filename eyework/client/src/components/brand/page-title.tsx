/*
 * PageTitle — عنوان الصفحة بشعار «Symbol Work»
 * ============================================
 * الشعار في كل صفحة (طلب المالك): صغيرٌ في آخر سطر العنوان الكبير، كصورة الحساب في عناوين iOS. زخرفيٌّ
 * (`aria-hidden`) فاسم الصفحة هو العنوان وحده. في شاشات البوابة على الآيباد والحاسوب الشعار في رأس الشريط
 * الجانبي، فلا يتكرّر بجانب العنوان (`mark="phone"`)؛ وما قبل الدخول لا شريط جانبياً له، فهو فيه دائماً.
 */

import * as React from "react"

import { Logo } from "@/components/brand/marks"
import { cn } from "@/lib/utils"

export const PageTitle = React.forwardRef<
  HTMLHeadingElement,
  { children: React.ReactNode; mark?: "always" | "phone"; className?: string } & React.HTMLAttributes<HTMLHeadingElement>
>(function PageTitle({ children, mark = "always", className, ...props }, ref) {
  return (
    <h1 ref={ref} className={cn("flex items-center justify-between gap-3 text-display font-bold leading-tight", className)} {...props}>
      <span className="min-w-0">{children}</span>
      <Logo className={cn(mark === "phone" && "tablet:hidden")} />
    </h1>
  )
})
