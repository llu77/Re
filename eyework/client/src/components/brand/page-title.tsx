/*
 * PageTitle — عنوان الصفحة
 * ========================
 * العنوان الكبير وحده: شعار «Symbol Work» في رأس الصفحة (`AppHeader`) فوقه، لا في سطره.
 */

import * as React from "react"

import { cn } from "@/lib/utils"

export const PageTitle = React.forwardRef<
  HTMLHeadingElement,
  { children: React.ReactNode; className?: string } & React.HTMLAttributes<HTMLHeadingElement>
>(function PageTitle({ children, className, ...props }, ref) {
  return (
    <h1 ref={ref} className={cn("text-display font-bold leading-tight", className)} {...props}>
      {children}
    </h1>
  )
})
