/*
 * Notice — تنبيه الخطأ بزرّ «حسناً»
 * =================================
 * رسالةٌ من الخادم أو من المتصفّح تبقى حتى يقرّها صاحبها: `role=alert` في خانةٍ ثابتة أعلى
 * المحتوى، وزرّها «حسناً» آمن (`data-ack data-safe`) فوق وسط الشاشة حيث لا زرّ في أيّ
 * شاشة؛ وما حولها خاملٌ (`inert`) ما دامت ظاهرة، فنظرةٌ باقيةٌ على الزرّ الذي فشل لا تعيد
 * طلباً. بعد الإقرار تُرسم الشاشة كما كانت.
 */

import * as React from "react"

import { Button } from "@/components/ui/button"

export function Notice({ message, onAck, children }: { message: string | null; onAck: () => void; children: React.ReactNode }) {
  const content = React.useRef<HTMLDivElement>(null)
  // React 18 لا يعرف الخاصيّة `inert`، فتُكتب على العنصر نفسه.
  React.useEffect(() => {
    if (content.current) content.current.inert = message !== null
  }, [message])
  return (
    <>
      {message !== null ? (
        <div
          role="alert"
          className="fixed inset-x-edge top-[max(var(--edge),env(safe-area-inset-top))] z-40 flex flex-col items-center gap-tg rounded-card border-2 border-destructive bg-card p-edge shadow-pop"
        >
          <Button id="notice-ack" data-ack="" variant="primary" size="lg" onClick={onAck} className="w-ctl-lg min-w-[6rem]">
            حسناً
          </Button>
          <p className="text-flow text-center font-bold text-destructive">{message}</p>
        </div>
      ) : null}
      <div ref={content} data-content="" className={message !== null ? "invisible" : undefined}>
        {children}
      </div>
    </>
  )
}
