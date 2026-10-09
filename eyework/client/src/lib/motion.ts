/*
 * الحركة
 * ======
 * framer-motion يحرّك على إطارات الشاشة (requestAnimationFrame) — وهذا مسموحٌ حين
 * يبدأ بضغطةٍ أو بردّ خادم، ويقصر (150ms)، ولا يحرّك إلا الشفافية والانزلاق الأول
 * للورقة. وفي الحجم الكبير أو مع «تقليل الحركة» لا حركة إطلاقاً: ما يتحرّك تحت نظرٍ
 * باقٍ قد يُضغط وهو يتحرّك. كل مكوّنٍ يسأل هنا ولا يقرّر بنفسه.
 */

import { useReducedMotion, type Transition } from "framer-motion"

import { useSize } from "@/lib/size"

export const QUICK: Transition = { duration: 0.15, ease: "easeOut" }
export const NONE: Transition = { duration: 0 }

export function useMotionAllowed(): boolean {
  const { size } = useSize()
  const reduce = useReducedMotion()
  return size === "compact" && !reduce
}
