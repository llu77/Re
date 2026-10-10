/*
 * Button — الزرّ بحجمي الواجهة
 * ============================
 * الأصل: shadcn/ui button (MIT)، والمتغيّرات بأسلوب «Button — Variants» (micka_design، 21st.dev:
 * https://21st.dev/@micka_design/components/button، بشروط 21st.dev ورخصة صفحة المكوّن): تعبئةٌ
 * لا حدّ، والنصّ يعرّف الزرّ. التكييف:
 *   • الارتفاع `min-h-ctl` (40 أو 48) أو `min-h-ctl-lg` (44 أو 48): لا حجم أصغر من منطقة الإصابة.
 *   • `primary` بالتعبئة الملوّنة لما يعتمد أو يُرسل وحده، و`secondary` تعبئةٌ مدرّجة للخطوة التالية،
 *     و`outline` أبيضُ بحدٍّ خفيف لما يرجع أو يفتح، و`ghost` نصٌّ بلا تعبئة للصفّ العلوي.
 *   • `commit` يضع `data-commit` (ما لا يُعاد بضغطة: اعتماد، إرسال، حذف)؛ و`value`
 *     يضع `data-value` (يغيّر قيمةً ظاهرة: خيار، زيادة، نقصان)؛ وغيرهما `data-safe`.
 *     اختبارات الهبوط تقرأ هذه السمات (visual_spec §8).
 *   • لا `hover:` بل `hov:` (فأرةٌ في الحجم العادي وحده)، ولا انتقال، ولا Radix Slot ولا `<style>` محقون.
 *   • `busy` يُبقي الزرّ في مكانه بعرضه ويعطّله؛ وفي الحجم الكبير لا دوران.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Loader2, LogIn, LogOut, Send, Undo2, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export const buttonVariants = cva(
  [
    "inline-flex min-w-0 select-none items-center justify-center gap-1.5 rounded-ctl border border-transparent px-3.5 py-1 text-center",
    "min-h-ctl min-w-ctl text-body font-semibold leading-tight",
    "disabled:cursor-not-allowed disabled:border-transparent disabled:bg-border/60 disabled:text-muted-foreground disabled:shadow-none",
    "aria-disabled:cursor-not-allowed aria-disabled:border-transparent aria-disabled:bg-border/60 aria-disabled:text-muted-foreground",
    "[&_svg]:pointer-events-none [&_svg]:size-icon [&_svg]:shrink-0",
    "gaze:gap-2 gaze:px-4",
  ].join(" "),
  {
    variants: {
      variant: {
        /** يعتمد أو يُرسل: التعبئة الملوّنة لهذا وحده. */
        primary: "bg-primary text-primary-foreground hov:bg-primary/90",
        /** خطوةٌ إلى الأمام بلا إرسال، أو الإجراء الثاني: تعبئةٌ مدرّجة. */
        secondary: "bg-secondary text-secondary-foreground hov:bg-secondary/70",
        /** رجوعٌ أو فتحٌ أو تبديل: أبيضُ بحدٍّ خفيف. */
        outline: "border-border bg-card text-foreground hov:bg-muted",
        /** الصفّ العلوي: نصٌّ باللون الأساسي بلا تعبئة؛ وفي الحجم الكبير شكلٌ أبيض يُرى حدّه. */
        ghost: "bg-transparent px-2 text-primary hov:bg-primary/5 disabled:bg-transparent gaze:bg-card gaze:px-4 gaze:disabled:bg-border/60",
        /** يحذف أو يلغي، ولا يُستعاد. */
        danger: "bg-destructive text-destructive-foreground hov:bg-destructive/90",
        /** خطوةٌ آمنة نحو ما يحذف: تفتح التأكيد ولا تحذف. */
        "danger-outline": "bg-destructive-tint text-destructive hov:bg-destructive-tint/70",
        /** مثلها في الصفّ العلوي: نصٌّ أحمر بلا تعبئة. */
        "danger-ghost": "bg-transparent px-2 text-destructive hov:bg-destructive-tint disabled:bg-transparent gaze:bg-card gaze:px-4 gaze:disabled:bg-border/60",
      },
      size: {
        default: "",
        lg: "min-h-ctl-lg text-lead",
      },
      width: {
        auto: "",
        full: "w-full",
      },
    },
    defaultVariants: { variant: "outline", size: "default", width: "auto" },
  },
)

/* أيقوناتٌ لها اتجاه تُعكس في الصفحة العربية؛ والأسهم تُختار باتجاهها لا تُعكس. */
const DIRECTIONAL = new Set<LucideIcon>([LogIn, LogOut, Send, Undo2])
export const iconClass = (icon: LucideIcon) => (DIRECTIONAL.has(icon) ? "-scale-x-100" : undefined)
/** «التالي» في صفحةٍ من اليمين يشير يساراً، و«السابق» يميناً. */
export const NextIcon = ChevronLeft
export const BackIcon = ChevronRight
export const ForwardArrow = ArrowLeft
export const BackArrow = ArrowRight

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  icon?: LucideIcon
  iconEnd?: LucideIcon
  /** ما لا يُعاد بضغطة: اعتمادٌ أو إرسالٌ أو حذف. */
  commit?: boolean
  /** يغيّر قيمةً ظاهرة في مكانه (خيار، زيادة): أثره يُرى ويُعكس. */
  isValue?: boolean
  busy?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, size, width, icon: Icon, iconEnd: IconEnd, commit = false, isValue = false, busy = false,
      disabled, children, type = "button", ...props },
    ref,
  ) => {
    const marks = commit ? { "data-commit": "" } : isValue ? { "data-value": "" } : { "data-safe": "" }
    return (
      <button
        ref={ref}
        type={type}
        data-slot="button"
        {...marks}
        disabled={disabled || busy}
        aria-busy={busy || undefined}
        className={cn(buttonVariants({ variant, size, width }), className)}
        {...props}
      >
        {busy ? (
          <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none gaze:animate-none" />
        ) : Icon ? (
          <Icon aria-hidden="true" strokeWidth={2} className={iconClass(Icon)} />
        ) : null}
        {children}
        {IconEnd ? <IconEnd aria-hidden="true" strokeWidth={2} className={iconClass(IconEnd)} /> : null}
      </button>
    )
  },
)
Button.displayName = "Button"

export interface ButtonLinkProps
  extends React.AnchorHTMLAttributes<HTMLAnchorElement>,
    VariantProps<typeof buttonVariants> {
  icon?: LucideIcon
  iconEnd?: LucideIcon
}

/** رابطٌ بشكل الزرّ: تنقّلٌ لا فعل، فهو `data-safe` دائماً. */
export const ButtonLink = React.forwardRef<HTMLAnchorElement, ButtonLinkProps>(
  ({ className, variant, size, width, icon: Icon, iconEnd: IconEnd, children, ...props }, ref) => (
    <a ref={ref} data-safe="" className={cn(buttonVariants({ variant, size, width }), className)} {...props}>
      {Icon ? <Icon aria-hidden="true" strokeWidth={2} className={iconClass(Icon)} /> : null}
      {children}
      {IconEnd ? <IconEnd aria-hidden="true" strokeWidth={2} className={iconClass(IconEnd)} /> : null}
    </a>
  ),
)
ButtonLink.displayName = "ButtonLink"
