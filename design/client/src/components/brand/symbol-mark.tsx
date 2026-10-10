/*
 * علامة Symbol AI كما في لوحة الممارس (console/src/components/console/symbol-mark.tsx)
 * والبوابة: أربعة مستطيلات على شبكة 3×3. زخرفيةٌ (`aria-hidden`)؛ الاسم بجانبها نصّ.
 */
import { cn } from "@/lib/utils"

export function SymbolMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 3 3" aria-hidden="true" focusable="false" className={cn("size-8 shrink-0", className)}>
      <rect x="1" y="0" width="2" height="2" fill="#306BF5" />
      <rect x="0" y="1" width="2" height="1" fill="#63D7EE" />
      <rect x="1" y="2" width="1" height="1" fill="#63D7EE" />
      <rect x="1" y="1" width="1" height="1" fill="#061840" />
    </svg>
  )
}
