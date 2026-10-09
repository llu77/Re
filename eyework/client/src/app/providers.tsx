/*
 * المزوّدات المشتركة بين التطبيق وصفحة العرض
 * ==========================================
 * الحجم (data-size على <html>)، والحركة (لا حركة في الكبير)، والرسائل.
 */

import * as React from "react"
import { MotionConfig } from "framer-motion"

import { ToastProvider, type ToastMessage } from "@/components/ui/toast"
import { SizeProvider, useSize, type SizeMode } from "@/lib/size"

function Motion({ children }: { children: React.ReactNode }) {
  const { size } = useSize()
  // حارسٌ ثانٍ: كل مكوّنٍ يسأل useMotionAllowed، وهذا يُسكت framer-motion كلّه في الكبير.
  return <MotionConfig reducedMotion={size === "gaze" ? "always" : "user"}>{children}</MotionConfig>
}

export function AppProviders({ size, toast = null, children }: { size: SizeMode; toast?: ToastMessage | null; children: React.ReactNode }) {
  return (
    <SizeProvider initial={size}>
      <Motion>
        <ToastProvider initial={toast}>{children}</ToastProvider>
      </Motion>
    </SizeProvider>
  )
}
