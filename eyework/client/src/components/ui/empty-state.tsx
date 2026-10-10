/*
 * EmptyState — لا شيء هنا بعد
 * ==========================
 * الأصل: «Empty» (cnippet-dev، 21st.dev: https://21st.dev/@cnippet-dev/components/cnippet-empty، بشروط
 * 21st.dev ورخصة صفحة المكوّن) وshadcn empty: أيقونةٌ في مربّعٍ أبيض صغير، وعنوانٌ يقول ما الغائب،
 * وإجراءٌ واحد يبدأه إن وُجد. بلا إطارٍ متقطّع ولا رسمٍ يتحرّك ولا Radix.
 */

import * as React from "react"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center gap-3 px-pad py-sec text-center", className)}>
      <span className="flex size-10 items-center justify-center rounded-ctl bg-card text-muted-foreground shadow-card">
        <Icon aria-hidden="true" className="size-5" strokeWidth={1.75} />
      </span>
      <div className="flex max-w-sm flex-col gap-1">
        <p className="font-semibold text-heading">{title}</p>
        {description ? <p className="text-small text-muted-foreground">{description}</p> : null}
      </div>
      {action ? <div className="mt-1 flex flex-wrap justify-center gap-tg">{action}</div> : null}
    </div>
  )
}
