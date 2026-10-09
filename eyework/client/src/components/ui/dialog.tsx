/*
 * Dialog وSheet — على <dialog> الأصلي
 * ==================================
 * الأصل: shadcn/ui dialog وsheet (MIT) — والمبدأ لا الشيفرة: Radix Dialog يضيف عنصر
 * <style> (ترفضه CSP: style-src 'self') ويُغلق بالضغط خارجه عند pointerdown. فيُبنى
 * على <dialog> وshowModal():
 *   • طبقةٌ عليا وما تحتها خاملٌ (inert) من المتصفّح نفسه: لا يُصاب ولا يُقرأ ولا يُركَّز.
 *   • Escape يطلب الإغلاق، والمضيف يقرّر (`onClose`)؛ والضغط خارج اللوحة لا يُغلق: نظرةٌ
 *     تستقرّ على الخلفية لا تُضيّع ما في اللوحة.
 *   • التركيز يُنقل إلى العنوان عند الفتح (يُعلَن ولا يقع على زرٍّ يعتمد)، ويعود عند
 *     الإغلاق إلى ما كان عليه.
 *   • «إغلاق» زرٌّ بنصّه في الطرف الأسفل البعيد — حيث كان زرّ الأدوات العائم — فنظرةٌ
 *     باقيةٌ على موضع الضغط تقع على ما يُغلق، لا على ما يعتمد.
 *   • الحركة: ظهورٌ قصير في الحجم العادي، ولا شيء في الكبير أو مع «تقليل الحركة».
 *     والإغلاق فوريّ.
 *   • في الحجم الكبير تملأ اللوحة الشاشة بلا تمرير؛ وفي العادي حوارٌ في الوسط، أو ورقةٌ
 *     من الأسفل في الهاتف ومن الطرف في الحاسوب.
 */

import * as React from "react"
import { motion } from "framer-motion"
import { X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { NONE, QUICK, useMotionAllowed } from "@/lib/motion"
import { cn } from "@/lib/utils"

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: React.ReactNode
  children: React.ReactNode
  /** أزرارٌ قبل «إغلاق» في الذيل. */
  footer?: React.ReactNode
  /** «إغلاق» بنصٍّ آخر («رجوع دون حذف»). */
  closeLabel?: string
  /** alertdialog: سؤالٌ يحتاج جواباً (حذف). */
  alert?: boolean
  className?: string
}

/** يفتح <dialog> ويغلقه بحسب `open`، ويعيد التركيز إلى ما كان عليه. */
function useNativeModal(open: boolean, onClose: () => void) {
  const ref = React.useRef<HTMLDialogElement>(null)
  const heading = React.useRef<HTMLHeadingElement>(null)
  const returnTo = React.useRef<Element | null>(null)

  React.useLayoutEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      returnTo.current = document.activeElement
      dialog.showModal()
      heading.current?.focus({ preventScroll: true })
    } else if (!open && dialog.open) {
      dialog.close()
      const target = returnTo.current
      if (target instanceof HTMLElement && target.isConnected) target.focus({ preventScroll: true })
    }
  }, [open])

  // Escape: المتصفّح يطلب الإغلاق، والحالة في React تقرّر.
  const onCancel = React.useCallback(
    (event: React.SyntheticEvent<HTMLDialogElement>) => {
      event.preventDefault()
      onClose()
    },
    [onClose],
  )
  return { ref, heading, onCancel }
}

function Panel({ children, className, from }: { children: React.ReactNode; className: string; from: "fade" | "bottom" | "end" }) {
  const animate = useMotionAllowed()
  const initial = !animate
    ? false
    : from === "bottom"
      ? { opacity: 0, y: 24 }
      : from === "end"
        ? { opacity: 0, x: -24 }
        : { opacity: 0, scale: 0.98 }
  return (
    <motion.div
      initial={initial}
      animate={{ opacity: 1, y: 0, x: 0, scale: 1 }}
      transition={animate ? QUICK : NONE}
      className={className}
    >
      {children}
    </motion.div>
  )
}

function Header({ title, description, heading, titleId, descriptionId }: {
  title: string
  description?: React.ReactNode
  heading: React.RefObject<HTMLHeadingElement>
  titleId: string
  descriptionId: string
}) {
  return (
    <header className="flex flex-col gap-1">
      <h2 ref={heading} id={titleId} tabIndex={-1} className="text-title font-bold leading-tight focus-visible:outline-none">
        {title}
      </h2>
      {description ? (
        <div id={descriptionId} className="text-small text-muted-foreground">
          {description}
        </div>
      ) : null}
    </header>
  )
}

function Footer({ footer, closeLabel, onClose }: { footer?: React.ReactNode; closeLabel: string; onClose: () => void }) {
  return (
    <footer className="flex flex-wrap items-center gap-tg gaze:grid gaze:grid-cols-2">
      {footer}
      {/* «إغلاق» آخر الذيل: في الصفحة العربية هو الطرف الأيسر، تحت زرّ الأدوات العائم. */}
      <Button icon={X} onClick={onClose} className="ms-auto gaze:col-start-2 gaze:ms-0">
        {closeLabel}
      </Button>
    </footer>
  )
}

export function Dialog({ open, onClose, title, description, children, footer, closeLabel = "إغلاق", alert = false, className }: ModalProps) {
  const { ref, heading, onCancel } = useNativeModal(open, onClose)
  const id = React.useId()
  return (
    <dialog
      ref={ref}
      role={alert ? "alertdialog" : undefined}
      aria-labelledby={`${id}-title`}
      aria-describedby={description ? `${id}-desc` : undefined}
      onCancel={onCancel}
      className={cn(
        "m-auto w-[min(32rem,calc(100vw-2*var(--edge)))]",
        "gaze:fixed gaze:inset-0 gaze:m-0 gaze:h-dvh gaze:w-screen",
      )}
    >
      {open ? (
        <Panel
          from="fade"
          className={cn(
            "flex flex-col gap-sec rounded-card bg-card p-pad shadow-pop",
            "gaze:h-full gaze:justify-between gaze:rounded-none gaze:bg-background gaze:pt-safe gaze:pb-safe gaze:shadow-none",
            className,
          )}
        >
          <div className="flex min-h-0 flex-col gap-sec">
            <Header title={title} description={description} heading={heading} titleId={`${id}-title`} descriptionId={`${id}-desc`} />
            <div className="min-h-0 text-flow">{children}</div>
          </div>
          <Footer footer={footer} closeLabel={closeLabel} onClose={onClose} />
        </Panel>
      ) : null}
    </dialog>
  )
}

export interface SheetProps extends Omit<ModalProps, "alert"> {
  /** عنوانٌ صغير فوق العنوان: «الأدوات». */
  eyebrow?: string
}

export function Sheet({ open, onClose, title, eyebrow, description, children, footer, closeLabel = "إغلاق", className }: SheetProps) {
  const { ref, heading, onCancel } = useNativeModal(open, onClose)
  const id = React.useId()
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      aria-describedby={description ? `${id}-desc` : undefined}
      onCancel={onCancel}
      className={cn(
        // الهاتف: من الأسفل بعرض الشاشة.
        "fixed inset-x-0 bottom-0 top-auto m-0 max-h-[88dvh] w-full",
        // الحاسوب: من الطرف (يسار الصفحة العربية) بارتفاع الشاشة.
        "md:inset-y-0 md:end-0 md:start-auto md:max-h-none md:w-[26rem]",
        // الكبير: الشاشة كلّها، بلا تمرير.
        "gaze:inset-0 gaze:h-dvh gaze:max-h-none gaze:w-screen",
      )}
    >
      {open ? (
        <Panel
          from="bottom"
          className={cn(
            "flex max-h-[88dvh] flex-col gap-sec rounded-t-[calc(var(--radius-card)+0.25rem)] bg-card px-edge pb-safe pt-pad shadow-pop",
            "md:h-dvh md:max-h-none md:rounded-none md:pt-safe",
            "gaze:h-dvh gaze:max-h-none gaze:rounded-none gaze:bg-background gaze:pt-safe gaze:shadow-none",
            className,
          )}
        >
          <div className="flex flex-col gap-1">
            {eyebrow ? <p className="text-small font-semibold text-muted-foreground gaze:hidden">{eyebrow}</p> : null}
            <Header title={title} description={description} heading={heading} titleId={`${id}-title`} descriptionId={`${id}-desc`} />
          </div>
          {/* في الحجم العادي يمرّ محتوى الورقة داخلها؛ وفي الكبير يُبنى ليتّسع بلا تمرير. */}
          <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1 pb-1 gaze:overflow-hidden">{children}</div>
          <Footer footer={footer} closeLabel={closeLabel} onClose={onClose} />
        </Panel>
      ) : null}
    </dialog>
  )
}
