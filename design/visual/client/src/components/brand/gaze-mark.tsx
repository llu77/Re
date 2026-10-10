/*
 * شعار الترحيب: علامة Symbol في مركز حلقة مكوثٍ ممتلئةٍ إلى ثلاثة أرباعها، وحولها
 * حلقةٌ رفيعة. صورةٌ واحدة تقول ما يفعله التطبيق: نظرةٌ تستقرّ فيُضغط الزرّ.
 * تتمدّد في المساحة المتاحة وتنكمش (لا تفيض): `preserveAspectRatio` والارتفاع 100%.
 */
import { cn } from "@/lib/utils"

export function GazeMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 240 240"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="xMidYMid meet"
      className={cn("h-full max-h-60 w-auto", className)}
    >
      <circle cx="120" cy="120" r="112" fill="none" strokeWidth="1.5" strokeDasharray="2 7" className="stroke-control" />
      <circle cx="120" cy="120" r="88" className="fill-card" />
      <circle cx="120" cy="120" r="88" fill="none" strokeWidth="14" className="stroke-secondary" />
      <g transform="rotate(90 120 120) scale(-1 1) translate(-240 0)">
        <circle
          cx="120"
          cy="120"
          r="88"
          fill="none"
          strokeWidth="14"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray="72 100"
          className="stroke-primary"
        />
      </g>
      {/* رأس القوس: حيث تستقرّ النظرة الآن. */}
      <circle cx="206.4" cy="136.5" r="7" className="fill-gaze" />
      <g transform="translate(84 84) scale(24)">
        <rect x="1" y="0" width="2" height="2" fill="#306BF5" />
        <rect x="0" y="1" width="2" height="1" fill="#63D7EE" />
        <rect x="1" y="2" width="1" height="1" fill="#63D7EE" />
        <rect x="1" y="1" width="1" height="1" fill="#061840" />
      </g>
    </svg>
  )
}
