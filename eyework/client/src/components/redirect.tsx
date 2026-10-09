/*
 * Redirect — انتقالٌ من داخل الرسم
 * ===============================
 * لا يُغيَّر الوسم أثناء الرسم (يعيد الرسم بلا نهاية)، بل بعده في تأثير، وبلا أثرٍ في التاريخ.
 */

import * as React from "react"

import { go } from "@/lib/router"

export function Redirect({ to }: { to: string }) {
  React.useEffect(() => go(to, { replace: true }), [to])
  return null
}
