/*
 * التسمية — بنية Label في shadcn/ui (MIT) على <label> أصلي، بلا @radix-ui/react-label:
 * ذاك يضيف معالج onMouseDown، وعقد النظر لا يسمح إلا بالنقر.
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label data-slot="label" className={cn("text-small font-semibold text-foreground", className)} {...props} />
}
