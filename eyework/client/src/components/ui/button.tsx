/*
 * Button — الزرّ بحجمي الواجهة
 * ============================
 * الأصل: «Button» من originui (21st.dev: https://21st.dev/@originui/components/button، تحسينٌ لزرّ shadcn/ui،
 * بشروط 21st.dev ورخصة صفحة المكوّن): النصّ في سطرٍ واحد لا يلتفّ (`whitespace-nowrap`)، ووزنٌ متوسّط،
 * وظلٌّ خفيف على المملوء، وحدٌّ هادئ على المحدَّد، والمعطَّل بنصف الشفافية بشكله نفسه. والتكييف:
 *   • الارتفاع `min-h-ctl` (40 أو 48) أو `min-h-ctl-lg` (44 أو 48): لا حجم أصغر من منطقة الإصابة.
 *   • `primary` لما يعتمد أو يُرسل وحده، و`secondary` مدرّجٌ للخطوة التالية، و`outline` أبيضُ بحدٍّ لما يرجع أو
 *     يفتح، و`ghost` نصٌّ بلا تعبئة للصفّ العلوي في الحجم العادي.
 *   • `commit` يضع `data-commit` (ما لا يُعاد بضغطة: اعتماد، إرسال، حذف)؛ و`value`
 *     يضع `data-value` (يغيّر قيمةً ظاهرة: خيار، زيادة، نقصان)؛ وغيرهما `data-safe`.
 *     اختبارات الهبوط تقرأ هذه السمات (visual_spec §8).
 *   • لا `hover:` بل `hov:` (فأرةٌ في الحجم العادي وحده)، ولا Radix Slot ولا `<style>` محقون، ولا انتقال في الحجم الكبير.
 *   • `busy` يُبقي الزرّ في مكانه بعرضه ويعطّله؛ وفي الحجم الكبير لا دوران.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight, Loader2, LogIn, LogOut, Send, Undo2, type LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export const buttonVariants = cva(
  [
    "inline-flex min-w-0 select-none items-center justify-center gap-2 whitespace-nowrap rounded-ctl border border-transparent px-4 text-center",
    "min-h-ctl min-w-ctl text-body font-medium leading-none",
    "transition-colors gaze:transition-none outline-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none",
    "aria-disabled:cursor-not-allowed aria-disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:size-icon [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        /** يعتمد أو يُرسل: التعبئة الملوّنة لهذا وحده. */
        primary: "bg-primary text-primary-foreground shadow-sm shadow-black/5 hov:bg-primary/90",
        /** خطوةٌ إلى الأمام بلا إرسال، أو الإجراء الثاني: تعبئةٌ مدرّجة. */
        secondary: "bg-secondary text-secondary-foreground shadow-sm shadow-black/5 hov:bg-secondary/80",
        /** رجوعٌ أو فتحٌ أو تبديل: أبيضُ بحدٍّ هادئ. */
        outline: "border-border bg-card text-foreground shadow-sm shadow-black/5 hov:bg-muted",
        /** الصفّ العلوي في الحجم العادي: نصٌّ باللون الأساسي بلا تعبئة؛ وفي الحجم الكبير حبّةٌ بيضاء بحدّها. */
        ghost: "px-2 text-primary hov:bg-primary/5 gaze:border-border gaze:bg-card gaze:px-4 gaze:shadow-sm gaze:shadow-black/5",
        /** يحذف أو يلغي، ولا يُستعاد. */
        danger: "bg-destructive text-destructive-foreground shadow-sm shadow-black/5 hov:bg-destructive/90",
        /** خطوةٌ آمنة نحو ما يحذف: تفتح التأكيد ولا تحذف. */
        "danger-outline": "border-border bg-card text-destructive shadow-sm shadow-black/5 hov:bg-destructive-tint",
        /** مثلها في الصفّ العلوي: نصٌّ أحمر بلا تعبئة؛ وفي الحجم الكبير حبّةٌ بيضاء بحدّها. */
        "danger-ghost": "px-2 text-destructive hov:bg-destructive-tint gaze:border-border gaze:bg-card gaze:px-4 gaze:shadow-sm gaze:shadow-black/5",
      },
      size: {
        default: "",
        lg: "min-h-ctl-lg",
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
