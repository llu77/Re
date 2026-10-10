/*
 * EmptyState — لا شيء هنا بعد
 * ==========================
 * الأصل: نمط empty-state في 21st.dev وshadcn empty. أيقونةٌ في مربّعٍ هادئ، وعنوانٌ
 * يقول ما الغائب، وجملةٌ تقول ما يملؤه، وإجراءٌ واحد يبدأه. لا رسمٌ يتحرّك.
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
    <div className={cn("flex flex-col items-center gap-3 rounded-card border-2 border-dashed border-border px-pad py-sec text-center", className)}>
      <span className="flex size-12 items-center justify-center rounded-ctl bg-secondary text-secondary-foreground gaze:size-16">
        <Icon aria-hidden="true" className="size-6 gaze:size-8" strokeWidth={2} />
      </span>
      <div className="flex max-w-sm flex-col gap-1">
        <p className="text-lead font-bold text-heading">{title}</p>
        {description ? <p className="text-small text-muted-foreground">{description}</p> : null}
      </div>
      {action ? <div className="mt-1 flex flex-wrap justify-center gap-tg">{action}</div> : null}
    </div>
  )
}
