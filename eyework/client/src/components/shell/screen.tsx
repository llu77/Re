/*
 * Screen — إطار كل شاشة عمل
 * =========================
 * بنمط iOS: صفٌّ علويٌّ بخانتين ثابتتين («رجوع» في البداية، وفي النهاية ما يغادر أو يتقدّم) حين
 * تحتاجه الشاشة، ثم ما فوق العنوان (الخطوات)، ثم العنوان الكبير (h1، يُركَّز عند الوصول فيُعلَن ما
 * تغيّر)، ثم المحتوى، ثم شريط الإجراءات بخانتين ثابتتين.
 *
 *   • الحجم العادي: الصفحة تمرّ، والصفّ العلوي لاصقٌ بزجاجٍ خفيف، وشريط الإجراءات في آخر المحتوى.
 *   • الحجم الكبير: لا تمرير. الشاشة تملأ ما بين الرأس وشريط التبويب، والمحتوى يأخذ الباقي ويُقصّ
 *     لا يمرّ (والاختبار يرفض ما يُقصّ)، وشريط الإجراءات في الأسفل.
 */

import * as React from "react"

import { PageTitle } from "@/components/brand/page-title"

import { Slots, TopButton, type TopAction } from "@/components/shell/slots"
import { ToastLine, useToastMessage } from "@/components/ui/toast"
import { useSize } from "@/lib/size"
import { cn } from "@/lib/utils"

export interface ScreenProps {
  title: string
  description?: React.ReactNode
  /** «رجوع» في خانة البداية من الصفّ العلوي. */
  back?: TopAction
  /** خانة النهاية من الصفّ العلوي: «ألغِ الحملة»، «التالي»، «النسخة السابقة». */
  end?: TopAction
  /** فوق العنوان: الخطوات أو شارة الحالة. */
  above?: React.ReactNode
  /** بجانب العنوان في الآيباد والحاسوب: إجراءٌ ثانٍ. */
  aside?: React.ReactNode
  /** شريط الإجراءات. */
  actions?: React.ReactNode
  /** تملأ الشاشة في الحجم العادي أيضاً فيبقى شريط إجراءاتها في أسفلها («حسابي» وتأكيداه). */
  fill?: boolean
  children: React.ReactNode
  className?: string
}

export function Screen({ title, description, back, end, above, aside, actions, fill = false, children, className }: ScreenProps) {
  const { size } = useSize()
  const heading = React.useRef<HTMLHeadingElement>(null)
  React.useEffect(() => {
    heading.current?.focus({ preventScroll: true })
  }, [title])

  const gaze = size === "gaze"
  // الحجم الكبير: رسالة ما تمّ سطرٌ مكان الوصف، لا نافذةٌ تطفو فوق الأهداف.
  const toast = useToastMessage()
  const status = gaze && toast ? <ToastLine message={toast} /> : null
  return (
    <div data-screen-root="" className={cn("flex flex-col gap-sec", gaze && "min-h-0 flex-1 gap-tg", fill && "fill-screen", className)}>
      {/* الصفّ العلوي ابنٌ مباشر لجذر الشاشة: اللصق (sticky) يبقى ما بقيت الشاشة، لا مجموعة العنوان وحدها. */}
      {back || end ? (
        <div className={cn("-mx-edge px-edge py-1", !gaze && "bar-glass sticky top-0 z-10 -mb-sec -mt-sec pt-[calc(var(--tg)+env(safe-area-inset-top))]", gaze && "-mb-tg")}>
          <Slots start={back ? <TopButton action={back} back /> : undefined} end={end ? <TopButton action={end} back={false} /> : undefined} />
        </div>
      ) : null}
      <div className="flex flex-col gap-tg-min">
        {above}
        <div className="flex flex-wrap items-end justify-between gap-tg">
          <div className="flex min-w-0 flex-col gap-1">
            <PageTitle ref={heading} tabIndex={-1} mark="phone" className="focus-visible:outline-none">
              {title}
            </PageTitle>
            {status ?? (description ? <div className="text-flow text-muted-foreground gaze:text-small">{description}</div> : null)}
          </div>
          {aside ? <div className="hidden flex-wrap gap-tg tablet:flex">{aside}</div> : null}
        </div>
      </div>
      {/* في الحجم الكبير المحتوى يُقصّ ولا يمرّ؛ وحدّ القصّ أوسع منه بمساحة الإصابة الخفيّة (حشوٌ يقابله هامشٌ
          سالب): الصفّ الأول والأخير يُصابان كاملَين. */}
      <div
        className={cn(
          "flex flex-col gap-sec",
          gaze && "-my-[var(--hit-pad)] min-h-0 flex-1 gap-tg overflow-hidden py-[var(--hit-pad)]",
          fill && "flex-1",
        )}
      >
        {children}
      </div>
      {actions ? <ScreenActions>{actions}</ScreenActions> : null}
    </div>
  )
}

export function ScreenActions({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div data-screen-actions="" className={cn("flex flex-wrap items-center gap-tg", "gaze:shrink-0 gaze:flex-nowrap gaze:[&>*]:flex-1", className)}>
      {children}
    </div>
  )
}
