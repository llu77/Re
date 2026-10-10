/*
 * الحركة
 * ======
 * لا مكتبة حركة: ما يتحرّك يتحرّك بـ`tailwindcss-animate` (CSS وحده) في الحجم العادي، ويقصر
 * (150ms)، ولا يحرّك إلا الشفافية والانزلاق الأول للورقة. وفي الحجم الكبير أو مع «تقليل الحركة»
 * لا حركة إطلاقاً: ما يتحرّك تحت نظرٍ باقٍ قد يُضغط وهو يتحرّك. كل مكوّنٍ يسأل هنا ولا يقرّر
 * بنفسه.
 */

import { useMatch, useSize } from "@/lib/size"

export const REDUCED_QUERY = "(prefers-reduced-motion: reduce)"

export function useMotionAllowed(): boolean {
  const { size } = useSize()
  const reduce = useMatch(REDUCED_QUERY)
  return size === "compact" && !reduce
}
