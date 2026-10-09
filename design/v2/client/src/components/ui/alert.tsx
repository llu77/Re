/*
 * Alert — التنبيه في الصفحة
 * =========================
 * الأصل: shadcn/ui alert (MIT). أربع نبرات بأيقونةٍ ونصّ، لا بلونٍ وحده. `live`
 * يعلنه قارئ الشاشة حين يظهر بعد فعل (role="alert" للخطأ، و"status" لغيره)؛ وما كان
 * في الصفحة من أولها لا يُعلن.
 */

import * as React from "react"
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export type AlertTone = "info" | "success" | "warning" | "danger"

const TONES: Record<AlertTone, { box: string; icon: LucideIcon; iconColor: string }> = {
  info: { box: "border-primary/30 bg-secondary", icon: Info, iconColor: "text-primary" },
  success: { box: "border-success/30 bg-success-tint", icon: CheckCircle2, iconColor: "text-success" },
  warning: { box: "border-warning-line bg-warning-tint", icon: AlertTriangle, iconColor: "text-warning" },
  danger: { box: "border-destructive/40 bg-destructive-tint", icon: OctagonAlert, iconColor: "text-destructive" },
}

export interface AlertProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  tone?: AlertTone
  title: React.ReactNode
  /** يُعلن حين يظهر بعد فعل. */
  live?: boolean
  icon?: LucideIcon
  actions?: React.ReactNode
}

export function Alert({ tone = "info", title, live = false, icon, actions, className, children, ...props }: AlertProps) {
  const t = TONES[tone]
  const Icon = icon ?? t.icon
  const role = live ? (tone === "danger" ? "alert" : "status") : undefined
  return (
    <div role={role} className={cn("flex gap-3 rounded-card border-2 p-pad", t.box, className)} {...props}>
      <Icon aria-hidden="true" className={cn("mt-0.5 size-icon shrink-0", t.iconColor)} strokeWidth={2.25} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="font-bold leading-snug text-foreground">{title}</p>
        {children ? <div className="text-small text-foreground">{children}</div> : null}
        {actions ? <div className="mt-2 flex flex-wrap gap-tg">{actions}</div> : null}
      </div>
    </div>
  )
}
