/*
 * PageTitle — عنوان الصفحة بعلامة «صياغة»
 * =======================================
 * العلامة في كل صفحة (طلب المالك): صغيرةٌ في آخر سطر العنوان الكبير، كصورة الحساب في عناوين iOS، لا
 * قبل كل عنوان. زخرفيةٌ (`aria-hidden`) فاسم الصفحة هو العنوان وحده. في شاشات البوابة على الآيباد
 * والحاسوب العلامة في رأس الشريط الجانبي، فلا تتكرّر بجانب العنوان (`mark="phone"`)؛ وما قبل الدخول لا
 * شريط جانبياً له، فهي فيه دائماً.
 */

import * as React from "react"

import { BrandMark } from "@/components/brand/marks"
import { cn } from "@/lib/utils"

export const PageTitle = React.forwardRef<
  HTMLHeadingElement,
  { children: React.ReactNode; mark?: "always" | "phone"; className?: string } & React.HTMLAttributes<HTMLHeadingElement>
>(function PageTitle({ children, mark = "always", className, ...props }, ref) {
  return (
    <h1 ref={ref} className={cn("flex items-center justify-between gap-3 text-display font-bold leading-tight", className)} {...props}>
      <span className="min-w-0">{children}</span>
      <BrandMark className={cn("size-6 opacity-90 gaze:size-5", mark === "phone" && "tablet:hidden")} />
    </h1>
  )
})
