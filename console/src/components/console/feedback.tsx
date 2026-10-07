import * as React from "react"
import { CircleAlert, CircleCheck } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/** خطأٌ يُعلَن فور ظهوره. النصّ من الخادم أو من `api.ts`، لا تفاصيل تقنية. */
export function ErrorNotice({ message, className }: { message: string; className?: string }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-destructive",
        className,
      )}
    >
      <CircleAlert className="mt-1 size-5 shrink-0" aria-hidden="true" />
      <p>{message}</p>
    </div>
  )
}

/** نتيجة إجراءٍ نجح. منطقةٌ حيّة مهذّبة: تُقرأ دون أن تقاطع. */
export function SuccessNotice({ message }: { message: string | null }) {
  return (
    <div role="status" aria-live="polite" className="empty:hidden">
      {message ? (
        <p className="flex items-center gap-2 rounded-md border border-primary/30 bg-accent p-3 text-foreground">
          <CircleCheck className="size-5 shrink-0 text-primary" aria-hidden="true" />
          {message}
        </p>
      ) : null}
    </div>
  )
}

/** هيكل تحميلٍ بارتفاع البطاقات نفسه، فلا تقفز الصفحة حين تصل البيانات. */
export function LoadingList({ rows = 3, label }: { rows?: number; label: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="flex flex-col gap-3">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-24 w-full" />
      ))}
    </div>
  )
}

/** عنوان الصفحة يأخذ التركيز عند فتحها، فيعلنها قارئ الشاشة ويبدأ منها السهم. */
export function PageHeading({ children, id }: { children: React.ReactNode; id?: string }) {
  const ref = React.useRef<HTMLHeadingElement>(null)
  React.useEffect(() => {
    ref.current?.focus({ preventScroll: true })
  }, [])
  return (
    <h1 ref={ref} id={id} tabIndex={-1} className="text-xl font-bold outline-none">
      {children}
    </h1>
  )
}
