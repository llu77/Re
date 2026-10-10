/*
 * قوس المكوث — العلامة المميِّزة. حلقةٌ تمتلئ كما تمتلئ حلقة المكوث في تتبّع العين،
 * لكنها هنا ثابتة (لا حركة) وتقول شيئاً صحيحاً: كم مضى من سلسلةٍ مرتّبة — خطوات
 * التسجيل، وبنود البوابة، وأجزاء جواب المساعد. تمتلئ عكس عقارب الساعة: اتجاه القراءة.
 * زخرفيةٌ لقارئ الشاشة: النصّ بجانبها يقول الموضع نفسه.
 */
import { cn } from "@/lib/utils"

export function DwellArc({
  value,
  total,
  className,
}: {
  value: number
  total: number
  className?: string
}) {
  const share = total > 0 ? Math.min(100, Math.max(0, (value / total) * 100)) : 0
  return (
    <svg
      viewBox="0 0 40 40"
      aria-hidden="true"
      focusable="false"
      className={cn("size-7 shrink-0 -scale-x-100 rotate-90", className)}
    >
      <circle cx="20" cy="20" r="16" fill="none" strokeWidth="5" className="stroke-secondary" />
      <circle
        cx="20"
        cy="20"
        r="16"
        fill="none"
        strokeWidth="5"
        strokeLinecap="round"
        pathLength={100}
        strokeDasharray={`${share} 100`}
        className="stroke-primary"
      />
    </svg>
  )
}
