/*
 * الزرّ — من shadcn/ui (new-york-v4/ui/button، MIT)، مكيَّفاً لعقد النظر:
 *   • لا `hover:` ولا `transition`: ما يتغيّر تحت النظر ضجيج.
 *   • 72×72 على الأقل، والحدّ (2px، و3px مع «زيادة التباين») في `.btn` لا هنا:
 *     الأداة `border-2` كانت ستغلب قاعدة التباين.
 *   • `commit` يضع data-commit (اختبار الهبوط يرفض أن يقع تحت ضغطةٍ سابقة)،
 *     وإلا data-safe. والتعبئة الملوّنة للاعتماد وحده.
 *   • `reserved` يُخفي الزرّ ويُبقي مكانه: لا يتحرّك ما حوله.
 *   • أيقونة lucide مع النصّ دائماً، لا بدلاً منه.
 */
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { LogIn, LogOut, Send, type LucideIcon } from "lucide-react"

import { BarLock } from "@/components/frame/bar-lock"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  [
    "btn inline-flex shrink-0 items-center justify-center gap-2.5 rounded-control px-4",
    "min-h-target min-w-target text-control font-semibold text-center [text-wrap:balance]",
    "outline-none focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-ring",
    "disabled:border-border disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none",
    "aria-disabled:border-border aria-disabled:bg-muted aria-disabled:text-muted-foreground aria-disabled:shadow-none",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-6",
  ].join(" "),
  {
    variants: {
      variant: {
        // يعتمد أو يُرسل: التعبئة الملوّنة لهذا وحده.
        primary: "border-primary bg-primary text-primary-foreground shadow-control",
        // يتقدّم خطوةً بلا إرسال.
        secondary: "border-primary bg-secondary text-secondary-foreground",
        // رجوعٌ أو فتحٌ أو تبديلٌ يُعكس.
        quiet: "border-control bg-card text-foreground",
        // يحذف أو يلغي، ولا يُستعاد.
        danger: "border-destructive bg-destructive text-destructive-foreground shadow-control",
        // خطوةٌ آمنة نحو ما يحذف: تفتح شاشة التأكيد ولا تحذف.
        "danger-quiet": "border-destructive bg-card text-destructive",
      },
    },
    defaultVariants: { variant: "quiet" },
  },
)

/* أيقوناتٌ لها اتجاه (دخول، خروج، إرسال) تُعكس في الواجهة العربية؛ والأسهم تُختار باتجاهها. */
const DIRECTIONAL = new Set<LucideIcon>([LogIn, LogOut, Send])
const iconClass = (icon: LucideIcon) => (DIRECTIONAL.has(icon) ? "-scale-x-100" : undefined)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  commit?: boolean
  reserved?: boolean
  icon?: LucideIcon
  iconEnd?: LucideIcon
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { className, variant, asChild = false, commit = false, reserved = false, icon: Icon, iconEnd: IconEnd,
      disabled, children, type = "button", ...props },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button"
    // تنبيهٌ ظاهر يقفل أزرار الشريطين؛ والرابط لا يعرف disabled فيُقفل بـaria-disabled.
    const locked = React.useContext(BarLock)
    const marks = commit ? { "data-commit": "" } : { "data-safe": "" }
    const lock = locked ? { "data-locked-by-alert": "", ...(asChild ? { "aria-disabled": true, tabIndex: -1 } : {}) } : {}
    const content = asChild ? children : (
      <>
        {Icon ? <Icon aria-hidden="true" strokeWidth={2.25} className={iconClass(Icon)} /> : null}
        {children}
        {IconEnd ? <IconEnd aria-hidden="true" strokeWidth={2.25} className={iconClass(IconEnd)} /> : null}
      </>
    )
    return (
      <Comp
        ref={ref}
        data-slot="button"
        data-variant={variant ?? "quiet"}
        {...marks}
        {...lock}
        {...(asChild ? {} : { type, disabled: disabled || reserved || locked })}
        className={cn(buttonVariants({ variant }), reserved && "is-reserved", className)}
        {...props}
      >
        {content}
      </Comp>
    )
  },
)
Button.displayName = "Button"

export { buttonVariants }
