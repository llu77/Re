/*
 * Screen — إطار كل شاشة عمل
 * =========================
 * العنوان (h1، يُركَّز عند الوصول فيُعلَن ما تغيّر)، و«رجوع» إن وُجد، ثم المحتوى، ثم شريط
 * الإجراءات.
 *
 *   • الحجم العادي: الصفحة تمرّ، وشريط الإجراءات في آخر المحتوى.
 *   • الحجم الكبير: لا تمرير. الشاشة تملأ ما تحت الرأس، والمحتوى يأخذ الباقي ويُقصّ لا
 *     يمرّ (والاختبار يرفض ما يُقصّ)، وشريط الإجراءات في الأسفل وخانته الأخيرة محجوزةٌ
 *     لزرّ الأدوات العائم: لا يقع زرٌّ تحته.
 *   • شريط الإجراءات: الأوّل في البداية (يمين الصفحة)، وما يعتمد آخر ما قبل خانة الأدوات،
 *     بعيداً عن «رجوع» أعلى الشاشة.
 */

import * as React from "react"

import { Button, BackIcon } from "@/components/ui/button"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface ScreenProps {
  title: string
  description?: React.ReactNode
  /** «رجوع إلى الفواتير». */
  back?: { label: string; onBack: () => void }
  /** فوق العنوان: الخطوات أو شارة الحالة. */
  above?: React.ReactNode
  /** بجانب العنوان في الحاسوب: إجراءٌ ثانٍ («مصروفٌ جديد»). */
  aside?: React.ReactNode
  /** شريط الإجراءات. */
  actions?: React.ReactNode
  /** العنوان اسم القسم نفسه الظاهر في زرّ الأقسام: في الحجم الكبير يُقرأ ولا يُرسم. */
  quietTitle?: boolean
  children: React.ReactNode
  className?: string
}

export function Screen({ title, description, back, above, aside, actions, quietTitle = false, children, className }: ScreenProps) {
  const { size } = useSize()
  const heading = React.useRef<HTMLHeadingElement>(null)
  React.useEffect(() => {
    heading.current?.focus({ preventScroll: true })
  }, [title])

  const gaze = size === "gaze"
  // عنوانٌ هادئ بلا ما يرافقه: يُقرأ ولا يأخذ مكاناً (ولا المسافة بعده).
  const silent = quietTitle && gaze && !back && !above && !aside && !description
  return (
    <div data-screen-root="" className={cn("flex flex-col gap-sec", gaze && "min-h-0 flex-1 gap-tg", className)}>
      <div className={cn("flex flex-col gap-tg-min", silent && "sr-only")}>
        {back ? (
          <div>
            <Button icon={BackIcon} onClick={back.onBack}>
              {back.label}
            </Button>
          </div>
        ) : null}
        {above}
        <div className="flex flex-wrap items-end justify-between gap-tg">
          <div className="flex min-w-0 flex-col gap-1">
            <h1
              ref={heading}
              tabIndex={-1}
              className={cn("text-display font-bold leading-tight focus-visible:outline-none", quietTitle && gaze && "sr-only")}
            >
              {title}
            </h1>
            {description ? <div className="text-flow text-muted-foreground gaze:text-small">{description}</div> : null}
          </div>
          {aside ? <div className="flex flex-wrap gap-tg">{aside}</div> : null}
        </div>
      </div>
      <div className={cn("flex flex-col gap-sec", gaze && "min-h-0 flex-1 gap-tg overflow-hidden")}>{children}</div>
      {actions ? <ScreenActions>{actions}</ScreenActions> : null}
    </div>
  )
}

export function ScreenActions({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-tg",
        // خانة زرّ الأدوات: عرضه وبعده مسافة، في طرف الشريط.
        "gaze:shrink-0 gaze:flex-nowrap gaze:pe-[calc(var(--fab)+var(--tg))] gaze:[&>*]:flex-1",
        className,
      )}
    >
      {children}
    </div>
  )
}
