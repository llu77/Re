/*
 * Slots — خانتان ثابتتان
 * ======================
 * الصفّ العلوي («رجوع» في البداية، وفي النهاية ما يغادر أو يتقدّم) وشريط الإجراءات كلاهما
 * خانتان بنصف العرض في مكانهما دائماً، والفارغة تبقى في مكانها. الخانات ثابتةٌ لأن قاعدة
 * الهبوط تقرأ المواضع: ما يقع تحت ضغطةٍ في الشاشة التالية لا يعتمد شيئاً ولا يغيّر قيمة،
 * وأقرب عنصرٍ مفعّلٍ إليها لا يعتمد.
 */

import * as React from "react"

import type { LucideIcon } from "lucide-react"

import { BackIcon, Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface TopAction {
  id: string
  label: string
  onClick: () => void
  /** يغادر أو يحذف: نصٌّ أحمر بلا تعبئة (الحذف نفسه في شاشة التأكيد). */
  danger?: boolean
  /** يعتمد (النسخة السابقة): `data-commit`. */
  commit?: boolean
  disabled?: boolean
  busy?: boolean
  /** أيقونةٌ في البداية («رجوع» بلا أيقونةٍ يأخذ سهم الرجوع). */
  icon?: LucideIcon
  /** أيقونةٌ في النهاية («التالي»). */
  iconEnd?: LucideIcon
}

export function Slots({ start, end, actions = false, top = false, className }: { start?: React.ReactNode; end?: React.ReactNode; actions?: boolean; top?: boolean; className?: string }) {
  return (
    // شريط الإجراءات: حشوٌ أقل في الخانتين (كلٌّ نصف العرض)، وفي الحجم الكبير نصٌّ بلا أيقونة. والصفّ العلوي (`top`)
    // بنمط iOS: «رجوع» في أوّل خانته، والفعل الآخر في آخر خانته، كلٌّ بعرض نصّه.
    <div
      className={cn(
        "grid min-h-ctl w-full grid-cols-2 gap-tg",
        actions && "[&>*]:px-2 gaze:[&_svg]:hidden",
        // في الحجم الكبير تملأ الخانة نصف العرض: الاسم الطويل يلتفّ في زرّه ولا يخرج منه في 320px.
        top && "items-center compact:[&>:first-child]:justify-self-start compact:[&>:last-child]:justify-self-end",
        className,
      )}
    >
      {start ?? <span aria-hidden="true" />}
      {end ?? <span aria-hidden="true" />}
    </div>
  )
}

export function TopButton({ action, back }: { action: TopAction; back: boolean }) {
  return (
    <Button
      id={action.id}
      icon={back ? (action.icon ?? BackIcon) : action.icon}
      iconEnd={action.iconEnd}
      variant={action.danger ? "danger-ghost" : action.commit ? "secondary" : "ghost"}
      commit={action.commit}
      disabled={action.disabled}
      busy={action.busy}
      onClick={action.onClick}
    >
      {action.label}
    </Button>
  )
}
