import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/*
 * زرّ shadcn/ui بأحجام عقد النظر: لا حجم أصغر من 72px، فلا يُختار خطأً هدفٌ
 * أصغر مما يُصاب بالنظر. والنصّ ظاهرٌ دائماً بجانب الأيقونة: لا زرّ بأيقونةٍ وحدها.
 */
const buttonVariants = cva(
  "inline-flex min-h-target min-w-target items-center justify-center gap-3 rounded-xl px-6 text-lg font-medium leading-snug transition-colors motion-reduce:transition-none disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:size-6 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        secondary: "border border-input bg-card text-foreground shadow-sm hover:bg-accent",
        quiet: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
      },
      width: {
        auto: "",
        full: "w-full",
      },
    },
    defaultVariants: {
      variant: "default",
      width: "auto",
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, width, type = "button", ...props }, ref) => (
    <button ref={ref} type={type} className={cn(buttonVariants({ variant, width, className }))} {...props} />
  ),
)
Button.displayName = "Button"

export { Button, buttonVariants }
