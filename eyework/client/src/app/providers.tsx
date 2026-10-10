/*
 * المزوّدات المشتركة بين التطبيق وصفحة العرض
 * ==========================================
 * الحجم (data-size على <html>) والرسائل. الحركة لا مزوّد لها: كل مكوّنٍ يسأل `useMotionAllowed`
 * (lib/motion.ts) فلا يتحرّك شيءٌ في الحجم الكبير ولا مع «تقليل الحركة».
 */

import * as React from "react"

import { ToastProvider, type ToastMessage } from "@/components/ui/toast"
import { SizeProvider, type SizeMode } from "@/lib/size"

export function AppProviders({ size, toast = null, children }: { size: SizeMode; toast?: ToastMessage | null; children: React.ReactNode }) {
  return (
    <SizeProvider initial={size}>
      <ToastProvider initial={toast}>{children}</ToastProvider>
    </SizeProvider>
  )
}
