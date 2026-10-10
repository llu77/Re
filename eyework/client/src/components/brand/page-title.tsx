/*
 * PageTitle — عنوان الصفحة
 * ========================
 * العنوان الكبير. شعار «Symbol Work» في الحجم العادي صفٌّ في أعلى الصفحة فوقه (`PageBrand`، طلب المالك)؛ وفي الحجم
 * الكبير، ولا مكان فيه لصفٍّ آخر، في آخر سطر العنوان، زخرفياً. وفي شاشات البوابة على الآيباد والحاسوب الشعار في رأس
 * الشريط الجانبي، فلا يتكرّر (`mark="phone"`)؛ وما قبل الدخول لا شريط جانبياً له.
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
      <Logo className={cn("hidden gaze:block", mark === "phone" && "gaze:tablet:hidden")} />
    </h1>
  )
})
