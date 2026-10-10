/*
 * الحقل — من shadcn/ui (new-york-v4/ui/input، MIT) مع أيقونة البداية من «Input with
 * start icon» في Origin UI (originui/input على 21st.dev، MIT) — مرجعاً للشكل.
 * 72px ارتفاعاً، وخطّ 18 (≥ 16 فلا يكبّر iOS الصفحة عند التركيز)، والحدّ 3:1.
 */
import * as React from "react"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface InputProps extends React.ComponentProps<"input"> {
  icon?: LucideIcon
}

// الغلاف باتجاه الحقل: حقلٌ لاتيني (البريد) أيقونته وحشوه في بدايته هو، فلا يركب النصّ الأيقونة.
export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, icon: Icon, dir, ...props }, ref) => (
  <div className="relative" dir={dir}>
    {Icon ? (
      <Icon
        aria-hidden="true"
        strokeWidth={2}
        className="pointer-events-none absolute inset-y-0 start-4 my-auto size-6 text-muted-foreground"
      />
    ) : null}
    <input
      ref={ref}
      dir={dir}
      data-slot="input"
      className={cn(
        "field block h-target w-full rounded-control border-input bg-card px-4 text-control text-foreground",
        "placeholder:text-muted-foreground read-only:bg-muted",
        "outline-none focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-ring",
        Icon && "ps-14",
        className,
      )}
      {...props}
    />
  </div>
))
Input.displayName = "Input"
