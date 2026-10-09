/*
 * ملاحظةٌ ضمن المحتوى — من مكوّن Alert في shadcn/ui (new-york-v4/ui/alert، MIT)،
 * بلا role="alert": ما يُعلَن ويُقرّ هو `AlertOverlay` في الإطار وحده. هذا سطرٌ
 * يُقرأ قبل القرار (ما يُرسل وإلى من، مصدر المحتوى).
 */
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

const calloutVariants = cva("flex items-start gap-3 rounded-card border px-4 py-3 text-small", {
  variants: {
    variant: {
      info: "border-border bg-card text-muted-foreground",
      brand: "border-transparent bg-secondary text-secondary-foreground",
      plain: "border-transparent bg-transparent px-0 py-0 text-muted-foreground",
    },
  },
  defaultVariants: { variant: "info" },
})

export interface CalloutProps extends React.ComponentProps<"div">, VariantProps<typeof calloutVariants> {
  icon?: LucideIcon
}

export function Callout({ className, variant, icon: Icon, children, ...props }: CalloutProps) {
  return (
    <div data-slot="callout" className={cn(calloutVariants({ variant }), className)} {...props}>
      {Icon ? <Icon aria-hidden="true" strokeWidth={2.25} className="mt-[0.2em] size-[1.15em] shrink-0" /> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
