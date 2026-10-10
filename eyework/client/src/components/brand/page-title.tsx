/*
 * PageTitle — عنوان الصفحة بعلامة «صياغة»
 * =======================================
 * العلامة في كل صفحة (طلب المالك): قبل العنوان الكبير، زخرفيةٌ (`aria-hidden`) فاسم الصفحة هو العنوان
 * وحده. في شاشات البوابة على الآيباد والحاسوب العلامة في رأس الشريط الجانبي، فلا تتكرّر بجانب العنوان
 * (`mark="phone"`)؛ وما قبل الدخول لا شريط جانبياً له، فهي فيه دائماً.
 */

import * as React from "react"

import { BrandMark } from "@/components/brand/marks"
import { cn } from "@/lib/utils"

export const PageTitle = React.forwardRef<
  HTMLHeadingElement,
  { children: React.ReactNode; mark?: "always" | "phone"; className?: string } & React.HTMLAttributes<HTMLHeadingElement>
>(function PageTitle({ children, mark = "always", className, ...props }, ref) {
  return (
    <h1 ref={ref} className={cn("flex items-center gap-2 text-display font-semibold leading-tight tracking-tight", className)} {...props}>
      <BrandMark className={cn("size-7 gaze:size-6", mark === "phone" && "tablet:hidden")} />
      <span className="min-w-0">{children}</span>
    </h1>
  )
})
